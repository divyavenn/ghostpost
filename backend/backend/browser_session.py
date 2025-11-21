"""
Browser session management for frontend-controlled OAuth login.
Allows users to login via browser on backend while viewing/controlling from frontend.
"""
import secrets
import time

from playwright.async_api import BrowserContext, Page, async_playwright

from backend.config import SESSION_TIMEOUT

# Store active browser sessions
# Key: session_id, Value: {browser, context, page, username, created_at}
active_sessions: dict[str, dict] = {}


async def is_session_active(session: dict) -> bool:
    """
    Check if a browser session is actively being used.
    Returns True if the page is still navigating or loading.
    """
    try:
        page: Page = session["page"]
        # Check if page is closed or browser is disconnected
        if page.is_closed():
            return False

        # Try to get current URL - if this fails, browser is disconnected
        try:
            _ = page.url
            return True
        except Exception:
            return False
    except Exception:
        return False


async def cleanup_expired_sessions():
    """
    Remove sessions older than SESSION_TIMEOUT that are not actively being used.
    This prevents interrupting users who are actively completing OAuth login.
    """
    from backend.utils import notify

    current_time = time.time()
    expired_sids = []

    for sid, session in active_sessions.items():
        session_age = current_time - session["created_at"]

        # Only consider sessions that have exceeded timeout
        if session_age > SESSION_TIMEOUT:
            # Check if session is still active
            is_active = await is_session_active(session)

            if is_active:
                # Session is active despite being old - user is still logging in
                notify(f"⏱️ OAuth session {sid[:8]}... is {int(session_age)}s old but still active - keeping alive")
            else:
                # Session is inactive and expired - safe to clean up
                expired_sids.append(sid)

    # Clean up inactive expired sessions
    for sid in expired_sids:
        notify(f"🧹 Cleaning up expired inactive OAuth session {sid[:8]}...")
        await close_session(sid)


async def create_browser_session(username: str) -> dict:
    """
    Create a new browser session for OAuth login.
    Returns session info including how to connect to it.
    """
    from backend.backend.browser_management.twitter.oauth import get_authorization_url

    # Generate session ID
    session_id = secrets.token_urlsafe(32)

    # Start Playwright
    playwright = await async_playwright().start()

    # OAuth/login sessions MUST be visible so user can interact
    # Launch browser with remote debugging enabled
    # Browser will appear on virtual display (DISPLAY=:99) accessible via noVNC
    browser = await playwright.chromium.launch(
        headless=False,  # User needs to see browser via noVNC
        args=[
            '--remote-debugging-port=9222',  # Enable CDP
            '--disable-blink-features=AutomationControlled',  # Hide automation
            '--no-sandbox',  # Required for Docker
            '--disable-dev-shm-usage',  # Overcome limited resource problems
        ])

    context = await browser.new_context(viewport={'width': 1280, 'height': 720}, user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36')

    page = await context.new_page()

    # Navigate to Twitter OAuth
    state = secrets.token_urlsafe(32)
    auth_url, code_verifier = get_authorization_url(state)
    await page.goto(auth_url)

    # Store session
    active_sessions[session_id] = {
        "browser": browser,
        "context": context,
        "page": page,
        "username": username,
        "playwright": playwright,
        "code_verifier": code_verifier,
        "state": state,
        "created_at": time.time()
    }

    # Get CDP endpoint
    cdp_endpoint = browser._impl_obj._connection.url if hasattr(browser, '_impl_obj') else None

    return {"session_id": session_id, "cdp_endpoint": cdp_endpoint, "message": "Browser session created. User should login via the opened browser window."}


async def get_session_status(session_id: str) -> dict:
    """
    Check if user has completed login by checking current URL.
    Returns status and whether login is complete.
    """
    session = active_sessions.get(session_id)
    if not session:
        return {"status": "not_found", "complete": False}

    page: Page = session["page"]
    current_url = page.url

    # Check if we're on a callback URL or Twitter home (login complete)
    if "callback" in current_url or "home" in current_url or current_url.startswith("https://twitter.com/home"):
        return {"status": "complete", "complete": True, "url": current_url}

    return {"status": "waiting", "complete": False, "url": current_url}


async def save_and_close_session(session_id: str) -> dict:
    """
    Save browser state and close the session after successful login.
    """
    from backend.backend.browser_management.twitter.oauth import exchange_code_for_token
    from backend.utils import error, store_browser_state
    session = active_sessions.get(session_id)
    if not session:
        error("Session not found", status_code=404, function_name="save_and_close_session")
        raise ValueError("Session not found")

    username = session["username"]
    context: BrowserContext = session["context"]
    page: Page = session["page"]

    # Save browser state (cookies, localStorage, etc.)
    await store_browser_state(username, context)

    # Try to extract authorization code from URL if present
    current_url = page.url
    token_data = None

    if "code=" in current_url:
        # Extract code from callback URL
        from urllib.parse import parse_qs, urlparse
        parsed = urlparse(current_url)
        params = parse_qs(parsed.query)
        code = params.get("code", [""])[0]

        if code:
            # Exchange code for tokens
            code_verifier = session["code_verifier"]
            token_response = exchange_code_for_token(code, code_verifier)

            # Store tokens
            from backend.utils import store_token
            access_token = token_response.get("access_token")
            refresh_token = token_response.get("refresh_token")
            expires_in = token_response.get("expires_in", 7200)

            if access_token and refresh_token:
                store_token(username, refresh_token, access_token, expires_in)
                token_data = {"access_token": access_token, "expires_in": expires_in}

    # Close session
    await close_session(session_id)

    return {"status": "saved", "username": username, "tokens": token_data}


async def close_session(session_id: str):
    """Close and cleanup a browser session"""
    session = active_sessions.get(session_id)
    if not session:
        return

    try:
        await session["context"].close()
        await session["browser"].close()
        await session["playwright"].stop()
    except Exception as e:
        from backend.utils import error
        error("Error closing session", exception_text=str(e), function_name="close_session")
    finally:
        del active_sessions[session_id]


async def get_session_screenshot(session_id: str) -> bytes | None:
    """Get a screenshot of the current browser state"""
    session = active_sessions.get(session_id)
    if not session:
        return None

    page: Page = session["page"]
    return await page.screenshot()
