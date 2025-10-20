"""Authentication routes for Twitter OAuth without requiring pre-authentication."""

import secrets

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

from backend.oauth import exchange_code_for_token, get_authorization_url
from backend.user import get_user_info
from backend.utils import store_browser_state, store_token

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
        args=['--disable-blink-features=AutomationControlled']
    )
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


@router.get("/callback")
async def twitter_callback(
        state: str = Query(...),
        code: str | None = Query(None),
        error: str | None = Query(None),
        error_description: str | None = Query(None),
):
    """Handle Twitter OAuth callback and save browser state."""
    redirect_to = "http://localhost:5173"

    if error:
        # Update login status
        if state in _login_status:
            _login_status[state] = LoginStatus(status="error", error=f"{error}: {error_description or ''}")

        # Clean up browser session if exists
        browser_session = _browser_sessions.pop(state, None)
        if browser_session:
            await _cleanup_browser(browser_session)

        # Return HTML response that closes the window
        return HTMLResponse(content=f"<html><body><h1>Login Error</h1><p>{error}: {error_description or ''}</p><script>window.close();</script></body></html>")

    if not code:
        browser_session = _browser_sessions.pop(state, None)
        if browser_session:
            await _cleanup_browser(browser_session)

        return RedirectResponse(url=f"{redirect_to}?status=error&error=missing_code", status_code=303)

    # Verify state
    oauth_data = _oauth_states.pop(state, None)
    browser_session = _browser_sessions.pop(state, None)

    if not oauth_data:
        if browser_session:
            await _cleanup_browser(browser_session)
        return RedirectResponse(url=f"{redirect_to}?status=error&error=invalid_state", status_code=303)

    code_verifier = oauth_data["code_verifier"]
    redirect_to = oauth_data.get("redirect_to") or redirect_to

    try:
        # Exchange code for tokens
        token_response = exchange_code_for_token(code, code_verifier)
        access_token = token_response.get("access_token")
        refresh_token = token_response.get("refresh_token")
        expires_in = token_response.get("expires_in", 7200)

        if not access_token or not refresh_token:
            if browser_session:
                await _cleanup_browser(browser_session)
            return RedirectResponse(url=f"{redirect_to}?status=error&error=no_tokens", status_code=303)

        # Get user info
        user_info = get_user_info(access_token)
        twitter_handle = user_info.get("handle") or user_info.get("username")

        if not twitter_handle:
            if browser_session:
                await _cleanup_browser(browser_session)
            return RedirectResponse(url=f"{redirect_to}?status=error&error=no_handle", status_code=303)

        # Store OAuth tokens
        store_token(twitter_handle, refresh_token, access_token, expires_in)

        # Save browser state if we have a browser session
        # CRITICAL: Save state BEFORE closing browser to capture all cookies/localStorage
        if browser_session:
            context = browser_session["context"]
            page = browser_session["page"]

            # Navigate to Twitter home to ensure all session cookies are set
            try:
                await page.goto("https://twitter.com/home", timeout=10000)
                # Give time for any additional cookies/storage to be set
                await page.wait_for_timeout(2000)
            except Exception as e:
                print(f"Warning: Could not navigate to Twitter home: {e}")

            # Now save the complete browser state with all cookies
            await store_browser_state(twitter_handle, context)

            # Close browser after state is saved
            await _cleanup_browser(browser_session)

        # Update login status to complete
        if state in _login_status:
            _login_status[state] = LoginStatus(status="complete", username=twitter_handle)

        # Return HTML that closes the browser window
        return HTMLResponse(content=f"""
            <html>
            <body>
                <h1>Login Successful!</h1>
                <p>Welcome @{twitter_handle}</p>
                <p>This window will close automatically...</p>
                <script>
                    setTimeout(() => window.close(), 2000);
                </script>
            </body>
            </html>
            """)

    except Exception as e:
        if browser_session:
            await _cleanup_browser(browser_session)
        return RedirectResponse(url=f"{redirect_to}?status=error&error=exception&error_description={str(e)}", status_code=303)


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


async def _cleanup_browser(browser_session: dict):
    """Helper to cleanup browser session"""
    try:
        await browser_session["context"].close()
        await browser_session["browser"].close()
        await browser_session["playwright"].stop()
    except Exception as e:
        print(f"Error cleaning up browser: {e}")
