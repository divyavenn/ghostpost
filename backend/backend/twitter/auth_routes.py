"""Authentication routes for Twitter OAuth without requiring pre-authentication."""

import datetime
import json
import secrets

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse
from playwright.async_api import async_playwright
from pydantic import BaseModel

from backend.browser_management.context import cleanup_browser_session
from backend.config import (
    BROWSER_STATE_FILE,
    BROWSERBASE_API_KEY,
    BROWSERBASE_PROJECT_ID,
    SHOW_BROWSER,
)
from backend.twitter.authentication import exchange_code_for_token, get_authorization_url
from backend.user.user import get_user_info
from backend.utlils.utils import atomic_file_update, error, notify, read_user_info, store_browser_state, store_token

router = APIRouter(prefix="/auth", tags=["auth"])

# Store state temporarily (in production, use Redis or database)
_oauth_states = {}
_browser_sessions = {}


class StartOAuthRequest(BaseModel):
    redirect_to: str | None = None


class LoginStatus(BaseModel):
    status: str  # "pending", "complete", "error"
    username: str | None = None
    error: str | None = None


# Store login completion status
_login_status = {}

# Store cookie import sessions (session_id -> {username, timestamp, verified})
_cookie_sessions = {}


@router.post("/twitter/start")
async def start_oauth(payload: StartOAuthRequest | None = None) -> dict[str, str]:
    """
    Start Twitter OAuth flow with browser session.
    Opens a browser on backend, saves both OAuth tokens AND browser state.
    """
    from playwright.async_api import async_playwright

    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)

    # Generate OAuth URL with state
    auth_url, code_verifier = get_authorization_url(state)

    # Launch browser session - MUST be visible for user to log in
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(
        headless=False,  # User needs to see browser to complete OAuth
        args=['--disable-blink-features=AutomationControlled'])
    context = await browser.new_context(viewport={'width': 1280, 'height': 720}, user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36')
    page = await context.new_page()

    # Navigate to OAuth URL in browser
    await page.goto(auth_url)

    # Store browser session and OAuth data
    _oauth_states[state] = {"code_verifier": code_verifier, "redirect_to": payload.redirect_to if payload else None}

    _browser_sessions[state] = {"playwright": playwright, "browser": browser, "context": context, "page": page}

    # Initialize login status as pending
    _login_status[state] = LoginStatus(status="pending")

    return {
        "auth_url": auth_url,
        "state": state,
        "session_id": state,  # Use state as session_id for polling
        "message": "Browser opened on server. Please login there."
    }


@router.post("/twitter/browser-login")
async def start_browser_login() -> dict[str, str]:
    """
    Start Twitter login using Browserbase with username/password.
    User logs in via Browserbase debugger to capture session cookies.
    """
    from browserbase import Browserbase
    from playwright.async_api import async_playwright

    # Get Browserbase API key from config
    browserbase_api_key = BROWSERBASE_API_KEY
    browserbase_project_id = BROWSERBASE_PROJECT_ID

    if not browserbase_api_key:
        error("BROWSERBASE_API_KEY environment variable not set", status_code=500, function_name="oauth_browserbase", critical=True)
        raise ValueError("BROWSERBASE_API_KEY environment variable not set")

    if not browserbase_project_id:
        error("BROWSERBASE_PROJECT_ID environment variable not set", status_code=500, function_name="oauth_browserbase", critical=True)
        raise ValueError("BROWSERBASE_PROJECT_ID environment variable not set")

    # Generate session ID for tracking
    session_id = secrets.token_urlsafe(32)

    # Create Browserbase session
    notify("🌐 Creating Browserbase session for browser login...")
    browserbase = Browserbase(api_key=browserbase_api_key)

    # Create session with project ID and enable residential proxies
    notify("🔒 Enabling residential proxies for anti-bot protection...")
    session = browserbase.sessions.create(
        project_id=browserbase_project_id,
        proxies=True  # Enable US-based residential proxies
    )
    session_id_bb = session.id

    # Get debugger URLs
    debug_info = browserbase.sessions.debug(session_id_bb)
    debugger_url = debug_info.debugger_fullscreen_url

    notify(f"✅ Browserbase session created: {session_id_bb}")
    notify(f"🔗 Debugger URL: {debugger_url}")

    # Connect Playwright to Browserbase session
    playwright = await async_playwright().start()
    browser = await playwright.chromium.connect_over_cdp(session.connect_url)
    context = browser.contexts[0]
    page = context.pages[0] if context.pages else await context.new_page()

    # Navigate to Twitter login page
    notify("🔗 Navigating to Twitter login page...")
    await page.goto("https://x.com/i/flow/login")

    # Store browser session for later retrieval
    _browser_sessions[session_id] = {"playwright": playwright, "browser": browser, "context": context, "page": page, "browserbase_session_id": session_id_bb, "browserbase_client": browserbase}

    # Initialize login status as pending
    _login_status[session_id] = LoginStatus(status="pending")

    return {"session_id": session_id, "debugger_url": debugger_url, "login_url": "https://x.com/i/flow/login", "message": "Please log in via the Browserbase debugger window"}


@router.post("/twitter/browser-login/check/{session_id}")
async def check_browser_login(session_id: str) -> dict:
    """
    Check if user has successfully logged in and capture browser state.
    This endpoint should be polled by the frontend.
    """
    if session_id not in _browser_sessions:
        return {"status": "error", "error": "Session not found"}

    browser_session = _browser_sessions[session_id]
    page = browser_session["page"]
    context = browser_session["context"]

    try:
        # Check if we're on Twitter home page (successful login indicator)
        current_url = page.url
        notify(f"📍 Current URL: {current_url}")

        # Successful login redirects to /home
        if "/home" in current_url:
            notify("✅ Login successful! Capturing browser state...")

            # Give time for all cookies to be set
            await page.wait_for_timeout(2000)

            # Get username from page
            try:
                # Try to extract username from the page
                username_element = await page.query_selector('[data-testid="SideNav_AccountSwitcher_Button"]')
                if username_element:
                    username_text = await username_element.inner_text()
                    # Extract handle from "@username" format
                    username = username_text.split('@')[-1].split('\n')[0].strip()
                else:
                    # Fallback: ask user or extract from URL
                    username = "unknown_user"
                    notify("⚠️ Could not auto-detect username")
            except Exception as e:
                notify(f"Warning: Could not extract username: {e}")
                username = "unknown_user"

            # Save browser state with captured cookies
            await store_browser_state(username, context)
            notify(f"💾 Browser state saved for {username}")

            # Clean up browser session
            await cleanup_browser_session(browser_session)
            _browser_sessions.pop(session_id, None)

            # Update login status
            _login_status[session_id] = LoginStatus(status="complete", username=username)

            return {"status": "complete", "username": username, "message": f"Successfully logged in as @{username}"}

        # Check for error states
        elif "login_challenge" in current_url or "account/access" in current_url:
            return {"status": "pending", "message": "Please complete verification/2FA", "current_url": current_url}

        # Still on login page
        else:
            return {"status": "pending", "message": "Waiting for login...", "current_url": current_url}

    except Exception as e:
        notify(f"❌ Error checking login status: {e}")
        return {"status": "error", "error": str(e)}


def _get_frontend_url(oauth_data: dict | None, request: Request) -> str:
    """Get frontend URL from oauth_data or construct from request headers."""
    frontend_url = oauth_data.get("frontend_url") if oauth_data else None

    if frontend_url:
        return frontend_url.rstrip('/')

    # Fallback: construct from request headers
    host = request.headers.get("host", "localhost")
    scheme = "https" if request.headers.get("x-forwarded-proto") == "https" else "http"

    # If accessed directly on port 8000, redirect to port 80 (frontend)
    if ":8000" in host:
        host = host.replace(":8000", "")

    return f"{scheme}://{host}"


def _redirect_html(url: str) -> HTMLResponse:
    """minimal HTML that redirects to the given URL."""
    return HTMLResponse(
        content=f'<html><head><meta http-equiv="refresh" content="0; url={url}"></head></html>'
    )


def _update_session_error(session_id: str | None, error_code: str, error_detail: str | None = None):
    """Update cookie session with error status."""
    if session_id and session_id in _cookie_sessions:
        _cookie_sessions[session_id]["status"] = "error"
        _cookie_sessions[session_id]["error"] = error_code
        if error_detail:
            _cookie_sessions[session_id]["error_detail"] = error_detail


@router.get("/callback")
async def twitter_callback(
        request: Request,
        state: str = Query(...),
        code: str | None = Query(None),
        error_param: str | None = Query(None, alias="error"),
        error_description: str | None = Query(None),
):
    """
    Handle Twitter OAuth callback.
    Exchanges OAuth code for tokens, redirects to frontend with result.
    """
    oauth_data = _oauth_states.get(state)
    session_id = oauth_data.get("session_id") if oauth_data else None
    frontend_url = _get_frontend_url(oauth_data, request)

    def redirect_error(error_code: str) -> HTMLResponse:
        return _redirect_html(f"{frontend_url}/login-error?error={error_code}&session_id={session_id or ''}")

    def redirect_success(username: str) -> HTMLResponse:
        return _redirect_html(f"{frontend_url}/login-success?username={username}&session_id={session_id}")

    # Error from Twitter
    if error_param:
        _oauth_states.pop(state, None)
        _update_session_error(session_id, error_param, error_description)
        error(f"Twitter OAuth error: {error_param}: {error_description or ''}", status_code=400, function_name="twitter_callback")
        return redirect_error(error_param)

    # Missing authorization code
    if not code:
        _oauth_states.pop(state, None)
        _update_session_error(session_id, "missing_code")
        error("Missing authorization code from Twitter", status_code=400, function_name="twitter_callback")
        return redirect_error("missing_code")

    # Invalid/expired state
    if not oauth_data:
        error("Invalid or expired OAuth state", status_code=400, function_name="twitter_callback")
        return redirect_error("invalid_state")

    code_verifier = oauth_data["code_verifier"]

    # Exchange code for tokens
    notify("🔄 Exchanging OAuth code for tokens...")
    try:
        token_response = exchange_code_for_token(code, code_verifier)
    except Exception as e:
        _update_session_error(session_id, "token_exchange_failed", str(e))
        error("Twitter API rejected token exchange", status_code=500, function_name="twitter_callback", exception_text=str(e))
        return redirect_error("token_exchange_failed")

    access_token = token_response.get("access_token")
    refresh_token = token_response.get("refresh_token")
    expires_in = token_response.get("expires_in", 7200)

    if not access_token or not refresh_token:
        _update_session_error(session_id, "incomplete_tokens")
        error("Twitter returned incomplete token response", status_code=500, function_name="twitter_callback")
        return redirect_error("incomplete_tokens")

    # Get user info
    try:
        user_info = get_user_info(access_token)
        twitter_handle = user_info.get("handle") or user_info.get("username")
    except Exception as e:
        _update_session_error(session_id, "user_info_fetch_failed", str(e))
        error("Failed to fetch user info from Twitter API", status_code=500, function_name="twitter_callback", exception_text=str(e))
        return redirect_error("user_info_failed")

    if not twitter_handle:
        _update_session_error(session_id, "no_handle")
        error("Twitter API returned user info but username/handle is missing", status_code=500, function_name="twitter_callback")
        return redirect_error("no_handle")

    # Store tokens
    notify(f"✅ OAuth tokens obtained for @{twitter_handle}")
    store_token(twitter_handle, refresh_token, access_token, expires_in)

    # Update session for cookie extension
    if session_id and session_id in _cookie_sessions:
        _cookie_sessions[session_id]["oauth_complete"] = True
        _cookie_sessions[session_id]["username"] = twitter_handle
        _cookie_sessions[session_id]["status"] = "awaiting_cookies"
        _cookie_sessions[session_id]["oauth_complete_time"] = datetime.datetime.now(datetime.UTC).isoformat()
        notify(f"⏳ Session {session_id} awaiting browser cookies for @{twitter_handle}")

    notify(f"🔗 Redirecting to: {frontend_url}/login-success?username={twitter_handle}")
    return redirect_success(twitter_handle)


@router.get("/twitter/status/{session_id}")
async def get_login_status(session_id: str) -> LoginStatus:
    """
    Check login completion status for polling.
    Frontend should poll this endpoint after starting OAuth.
    """
    status = _login_status.get(session_id)
    if not status:
        return LoginStatus(status="not_found", error="Session not found")
    return status


class LoginUrlRequest(BaseModel):
    frontend_url: str | None = None


@router.post("/twitter/login-url")
async def get_login_url(payload: LoginUrlRequest | None = None) -> dict:
    """
    Generate a session ID and return Twitter OAuth URL.
    Frontend opens this URL in a new tab, user logs in via OAuth,
    extension sends cookies back after redirect.
    """
    import secrets

    # Generate session ID for tracking
    session_id = secrets.token_urlsafe(32)

    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)

    # Generate OAuth URL (same as /twitter/start endpoint)
    from backend.twitter.authentication import get_authorization_url
    auth_url, code_verifier = get_authorization_url(state)

    # Store frontend URL for redirect after OAuth
    frontend_url = payload.frontend_url if payload else None

    # Store OAuth state for potential callback handling
    _oauth_states[state] = {
        "code_verifier": code_verifier,
        "session_id": session_id,
        "frontend_url": frontend_url,  # Store for redirect
        "created_at": __import__('datetime').datetime.now().isoformat()
    }

    # Initialize session tracking
    _cookie_sessions[session_id] = {"status": "pending", "created_at": __import__('datetime').datetime.now().isoformat(), "state": state}

    notify(f"📝 Created login session: {session_id}")
    notify(f"🔗 OAuth URL: {auth_url}")
    if frontend_url:
        notify(f"🏠 Frontend URL: {frontend_url}")

    return {"login_url": auth_url, "session_id": session_id}


@router.get("/twitter/cookie-status/{session_id}")
async def check_cookie_status(session_id: str) -> dict:
    """
    Check if cookies have been imported for this session.
    Frontend polls this endpoint after opening login tab.

    If session is in "awaiting_cookies" state for more than 60 seconds,
    returns "extension_required" status to prompt user to install extension.
    """
    import datetime

    session = _cookie_sessions.get(session_id)

    if not session:
        return {"status": "not_found"}

    # Check if session is waiting too long for cookies (extension not installed)
    status = session.get("status", "pending")
    if status == "awaiting_cookies":
        # Session has completed OAuth and is waiting for extension
        oauth_complete_time = session.get("oauth_complete_time")
        if oauth_complete_time:
            # Parse ISO format timestamp
            completed_at = datetime.datetime.fromisoformat(oauth_complete_time)
            now = datetime.datetime.now(datetime.UTC)
            elapsed_seconds = (now - completed_at).total_seconds()

            # If waiting more than 60 seconds, likely extension is not installed
            if elapsed_seconds > 60:
                return {
                    "status": "extension_required",
                    "username": session.get("username"),
                    "verified": False,
                    "elapsed_seconds": int(elapsed_seconds),
                    "message": "Browser extension not detected. Please install the GhostPoster extension to continue."
                }

    return {"status": status, "username": session.get("username"), "verified": session.get("verified", False)}


class CookieData(BaseModel):
    username: str


class CookieImport(BaseModel):
    data: CookieData
    cookies: list[dict]
@router.post("/twitter/import-cookies")
async def import_cookies(payload: CookieImport) -> dict:
    # Extract username from new format
    username = payload.data.username
    cookies = payload.cookies

    notify(f"📦 Received {len(cookies)} cookies for @{username} from extension")

    # Security: Verify user exists in the system before storing cookies
    user_info = read_user_info(username)
    if not user_info:
        error_msg = f"User @{username} not found in system"
        notify(f"🚫 {error_msg} - rejecting cookie import")
        return {
            "success": False,
            "error": "user_not_found",
            "message": error_msg,
            "user_message": f"Account Error: @{username} is not registered with GhostPoster. Please sign up first at the GhostPoster website.",
            "username": username
        }

    # Validate cookies exist
    if not cookies or len(cookies) == 0:
        error_msg = f"No cookies provided for @{username}"
        notify(f"❌ {error_msg}")
        return {
            "success": False,
            "error": "no_cookies",
            "message": error_msg,
            "user_message": f"Extension Error: No cookies were captured for @{username}. Make sure you're logged into Twitter/X.",
            "username": username
        }

    # Check for critical auth_token cookie
    has_auth_token = any(c.get("name") == "auth_token" for c in cookies)
    if not has_auth_token:
        error_msg = f"Missing auth_token cookie for @{username}"
        notify(f"⚠️  {error_msg}")
        return {
            "success": False,
            "error": "missing_auth_token",
            "message": error_msg,
            "user_message": f"Authentication Error: The auth_token cookie is missing for @{username}. Please log out and log back into Twitter/X in your browser.",
            "username": username,
            "cookies_count": len(cookies)
        }

    # Sanitize cookies - fix sameSite values for Playwright
    sanitized_cookies = []
    for cookie in cookies:
        try:
            # Make a copy to avoid modifying original
            sanitized = dict(cookie)

            # Fix sameSite - Playwright only accepts "Strict", "Lax", or "None"
            same_site = sanitized.get("sameSite", "Lax")
            if same_site not in ["Strict", "Lax", "None"]:
                # Default to "Lax" for invalid values
                sanitized["sameSite"] = "Lax"

            sanitized_cookies.append(sanitized)
        except Exception as e:
            notify(f"⚠️  Warning: Could not sanitize cookie {cookie.get('name', 'unknown')}: {e}")
            continue

    if len(sanitized_cookies) == 0:
        error_msg = f"All cookies failed sanitization for @{username}"
        notify(f"❌ {error_msg}")
        return {
            "success": False,
            "error": "cookie_sanitization_failed",
            "message": error_msg,
            "user_message": f"Cookie Error: Unable to process cookies for @{username}. Please try logging in again.",
            "username": username
        }

    # Convert browser extension format to Playwright storage_state format
    import datetime
    try:
        storage_state = {"cookies": sanitized_cookies, "origins": [{"origin": "https://x.com", "localStorage": []}], "timestamp": datetime.datetime.now(datetime.UTC).isoformat()}
    except Exception as e:
        error_msg = f"Failed to create storage state for @{username}: {e}"
        notify(f"❌ {error_msg}")
        return {
            "success": False,
            "error": "storage_state_creation_failed",
            "message": error_msg,
            "user_message": f"Server Error: Failed to process cookies for @{username}. Please try again.",
            "username": username
        }

    # Load existing cache
    try:
        if BROWSER_STATE_FILE.exists():
            try:
                cache = json.loads(BROWSER_STATE_FILE.read_text())
            except json.JSONDecodeError as e:
                notify(f"⚠️  Warning: Corrupted cache file, creating new one: {e}")
                cache = {}
        else:
            cache = {}
    except Exception as e:
        error_msg = f"Failed to load browser state cache: {e}"
        notify(f"❌ {error_msg}")
        return {"success": False, "error": "cache_load_failed", "message": error_msg, "user_message": "Server Error: Failed to access cookie storage. Please contact support.", "username": username}

    # Add user's cookies with timestamp
    cache[username] = storage_state

    # Save to file
    try:
        atomic_file_update(BROWSER_STATE_FILE, cache)
        notify(f"✅ Imported {len(cookies)} cookies for @{username}")
    except Exception as e:
        error_msg = f"Failed to save browser state for @{username}: {e}"
        notify(f"❌ {error_msg}")
        return {"success": False, "error": "cache_save_failed", "message": error_msg, "user_message": f"Server Error: Failed to save cookies for @{username}. Please try again.", "username": username}

    # Verify cookies by visiting Twitter home
    verified = False
    verification_error = None

    try:
        notify(f"🔍 Verifying cookies for @{username}...")
        playwright = await async_playwright().start()

        try:
            browser = await playwright.chromium.launch(headless=(not SHOW_BROWSER))

            try:
                context = await browser.new_context(storage_state=storage_state)
                page = await context.new_page()

                try:
                    await page.goto("https://x.com/home", timeout=15000)
                    await page.wait_for_timeout(2000)

                    # Check if we're still on login page (cookies didn't work)
                    current_url = page.url
                    if "/login" in current_url or "/flow" in current_url:
                        notify(f"⚠️  Cookies for @{username} appear invalid (redirected to login)")
                        verified = False
                        verification_error = "Cookies appear invalid - Twitter redirected to login page"
                    else:
                        notify(f"✅ Cookies for @{username} verified successfully")
                        verified = True

                except Exception as e:
                    notify(f"⚠️  Could not navigate to Twitter: {e}")
                    verification_error = f"Navigation failed: {str(e)}"
                    verified = False

            finally:
                await browser.close()

        finally:
            await playwright.stop()

        # Update ONLY sessions waiting for THIS specific username
        # Security: Match by username to prevent cross-user session contamination
        sessions_updated = 0

        # Debug: Show all active sessions
        if _cookie_sessions:
            notify(f"🔍 Checking {len(_cookie_sessions)} active session(s):")
            for sid, sdata in _cookie_sessions.items():
                notify(f"   Session {sid[:8]}...: status={sdata.get('status')}, username={sdata.get('username')}")
        else:
            notify("🔍 No active sessions in memory")

        for session_id, session_data in _cookie_sessions.items():
            is_waiting = session_data.get("status") in ["pending", "awaiting_cookies"]
            expected_user = session_data.get("username")  # Set during OAuth callback
            is_correct_user = expected_user == username

            notify(f"   Session {session_id[:8]}...: waiting={is_waiting}, expected_user={expected_user}, match={is_correct_user}")

            if is_waiting and is_correct_user:
                _cookie_sessions[session_id] = {
                    "status": "success" if verified else "error",
                    "username": username,
                    "verified": verified,
                    "imported_at": __import__('datetime').datetime.now().isoformat(),
                    "error": verification_error if not verified else None
                }
                sessions_updated += 1
                notify(f"📢 ✅ Updated session {session_id[:8]}... → success for @{username}")

        if sessions_updated > 0:
            notify(f"✅ Updated {sessions_updated} session(s) for @{username}")
        else:
            notify(f"ℹ️  No sessions waiting for @{username} - cookies saved but no matching frontend")
            notify("    To test: Start login flow from frontend, not just extension")

    except Exception as e:
        error_msg = f"Cookie verification failed for @{username}: {e}"
        notify(f"❌ {error_msg}")
        verified = False
        verification_error = str(e)

        # Still update sessions even if verification failed
        # But ONLY for the correct username (security)
        for session_id, session_data in _cookie_sessions.items():
            is_waiting = session_data.get("status") in ["pending", "awaiting_cookies"]
            expected_user = session_data.get("username")
            is_correct_user = expected_user == username

            if is_waiting and is_correct_user:
                _cookie_sessions[session_id] = {
                    "status": "error",
                    "username": username,
                    "verified": False,
                    "imported_at": __import__('datetime').datetime.now().isoformat(),
                    "error": verification_error
                }

    return {
        "success": True,
        "message": f"Successfully imported cookies for @{username}",
        "cookies_count": len(cookies),
        "username": username,
        "verified": verified,
        "verification_error": verification_error if not verified else None,
        "user_message": f"Cookies imported for @{username}. " + ("Login verified successfully!" if verified else f"Warning: Could not verify login - {verification_error}")
    }
