"""OAuth 2.0 PKCE utilities for X (Twitter) authentication."""

import base64
import hashlib
import os
import secrets
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import dotenv

from backend.config import (
    BACKEND_URL,
)
from backend.config import (
    TWITTER_API_BASE_URL as BASE_URL,
)
from backend.config import (
    TWITTER_CLIENT_ID as client_id,
)
from backend.config import (
    TWITTER_CLIENT_SECRET as client_secret,
)
from backend.user.user import get_user_info
from backend.utlils.utils import error, notify

# Load .env from backend/ directory (one level up from backend/backend/)
dotenv.load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

redirect_uri = BACKEND_URL + "/auth/callback"


def generate_code_verifier() -> str:
    """Generate a cryptographically random code verifier (43-128 characters)."""
    return (base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode("utf-8"))


def generate_code_challenge(code_verifier: str) -> str:
    """Generate the PKCE code challenge from a verifier using SHA256."""
    digest = hashlib.sha256(code_verifier.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("utf-8")


# Return the authorize URL and the code verifier used to build it.
def get_authorization_url(state: str | None = None) -> tuple[str, str]:
    code_verifier = generate_code_verifier()
    code_challenge = generate_code_challenge(code_verifier)

    if not state:
        state = secrets.token_urlsafe(32)

    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": "tweet.read tweet.write users.read follows.read follows.write offline.access",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }

    auth_url = f"https://x.com/i/oauth2/authorize?{urlencode(params)}"
    return auth_url, code_verifier


# Exchange an authorization code + verifier for an access token payload.
def exchange_code_for_token(code: str, code_verifier: str) -> dict[str, Any]:
    import requests

    url = f"{BASE_URL}/oauth2/token"
    data = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "code": code,
        "code_verifier": code_verifier,
    }

    credentials = f"{client_id}:{client_secret}"
    encoded_credentials = base64.b64encode(credentials.encode("utf-8")).decode("utf-8")
    headers = {
        "Authorization": f"Basic {encoded_credentials}",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    response = requests.post(url, data=data, headers=headers)
    response.raise_for_status()
    return response.json()


def refresh_access_token(refresh_token: str, username: str | None = None) -> dict[str, Any]:
    import requests

    url = f"{BASE_URL}/oauth2/token"
    data = {
        "grant_type": "refresh_token",
        "client_id": client_id,
        "refresh_token": refresh_token,
    }

    credentials = f"{client_id}:{client_secret}"
    encoded_credentials = base64.b64encode(credentials.encode("utf-8")).decode("utf-8")
    headers = {
        "Authorization": f"Basic {encoded_credentials}",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    try:
        response = requests.post(url, data=data, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError:
        from backend.utlils.utils import error
        # Log the error but don't mark as critical - this is a user auth issue, not a system failure
        # The calling code (ensure_access_token) will handle notifying the user
        error("Failed to refresh access token", status_code=401, exception_text=response.text, function_name="refresh_access_token", username=username, critical=False)
        raise RuntimeError(f"Token refresh failed for {username or 'unknown user'}")


def _start_callback_server(redirect_uri: str, expected_state: str) -> tuple[HTTPServer, threading.Event]:
    """
    Spin up a local HTTP server to capture the OAuth redirect.

    NOTE: This is ONLY used by the standalone oauth_login() function.
    In production, auth_routes.py handles callbacks via FastAPI (no separate server needed).
    """
    parsed = urlparse(redirect_uri)
    if parsed.scheme != "http":
        error("Redirect URI must use http scheme for local testing.", status_code=400, function_name="oauth_dance")

    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 80
    path = parsed.path or "/"

    authorization_event = threading.Event()

    class OAuthCallbackHandler(BaseHTTPRequestHandler):  # type: ignore[misc]

        def log_message(self, format: str, *args) -> None:  # pragma: no cover
            return

        def do_GET(self) -> None:  # pragma: no cover - triggered by browser callback
            parsed_path = urlparse(self.path)
            if parsed_path.path != path:
                self.send_error(404, "Not Found")
                return

            params = parse_qs(parsed_path.query)
            self.server.authorization_params = params  # type: ignore[attr-defined]

            if "error" in params:
                message = (params.get("error_description", [""])[0] or "Authorization failed.")
                self.send_response(400)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(message.encode("utf-8"))
                authorization_event.set()
                threading.Thread(target=self.server.shutdown, daemon=True).start()  # type: ignore[arg-type]
                return

            state_param = params.get("state", [""])[0]
            if state_param != expected_state:
                self.send_error(400, "Invalid state parameter")
                return

            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"<html><body><h1>Authorization complete.</h1><p>You may close this window.</p></body></html>")

            authorization_event.set()
            threading.Thread(target=self.server.shutdown, daemon=True).start()  # type: ignore[arg-type]

    try:
        server = HTTPServer((host, port), OAuthCallbackHandler)
    except OSError as exc:  # pragma: no cover - depends on environment
        raise SystemExit(f"Could not start callback server on {host}:{port}. Update TWITTER_REDIRECT_URI to a free port.") from exc

    server.authorization_params = None  # type: ignore[attr-defined]

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    return server, authorization_event


async def oauth_login(username: str, state_file: str = "storage_state.json") -> str:
    from playwright.async_api import async_playwright

    from backend.utlils.utils import store_browser_state, store_token

    notify(f"🔐 Launching OAuth login for {username}")
    state = secrets.token_urlsafe(32)
    server, auth_event = _start_callback_server(redirect_uri, state)
    auth_url, code_verifier = get_authorization_url(state)

    try:
        async with async_playwright() as p:
            # OAuth MUST be visible so user can log in - never use headless!
            # Chrome extension monitors browser state and sends updates to backend
            browser = await p.chromium.launch(
                headless=False,
                args=[
                    '--remote-debugging-port=9222',  # Enable CDP for remote access
                    '--no-sandbox',  # Required for Docker
                    '--disable-dev-shm-usage',  # Overcome limited resource problems
                ])
            context = await browser.new_context()
            page = await context.new_page()
            await page.goto(auth_url)

            if not auth_event.wait(timeout=300):
                error("OAuth browser flow timed out", status_code=408, function_name="oauth_dance", username=username)

            await store_browser_state(username, context)
            await context.close()
            await browser.close()

        params = getattr(server, "authorization_params", {}) or {}
    finally:
        server.shutdown()
        server.server_close()

    code = params.get("code", [""])[0]
    if not code:
        error("Authorization code missing from callback response.", status_code=400, function_name="oauth_dance", username=username, critical=True)

    token_response = exchange_code_for_token(code, code_verifier)
    access_token = token_response.get("access_token")
    if not access_token:
        error("Access token not returned by X API.", status_code=500, function_name="oauth_dance", username=username, critical=True)

    refresh_token = token_response.get("refresh_token")
    if not refresh_token:
        error("Refresh token not returned by X API.", status_code=500, function_name="oauth_dance", username=username, critical=True)

    expires_in = token_response.get("expires_in", 7200)  # Default 2 hours
    store_token(username, refresh_token, access_token, expires_in)

    return access_token


async def ensure_access_token(username: str, state_file: str = "storage_state.json", raise_on_failure: bool = False) -> str:
    """
    Return an access token for the user, refreshing or re-authenticating as needed.

    Args:
        username: The username to get token for
        state_file: State file name (default: storage_state.json)
        raise_on_failure: If True, raise HTTPException 401 on failure (for API routes).
                         If False, raise OAuthTokenExpired (for background jobs).

    Returns:
        Access token string

    Raises:
        OAuthTokenExpired: When token is missing/invalid and raise_on_failure is False
        HTTPException: When token is missing/invalid and raise_on_failure is True
    """
    import time

    from backend.utlils.utils import OAuthTokenExpired, read_user_access_token, read_user_token, store_token

    try:
        # Check if we have a cached access token that's still valid
        cached_access_token, expires_at = read_user_access_token(username)
        if cached_access_token and expires_at and time.time() < expires_at:
            notify(f"♻️ Using cached access token for {username} (expires in {int(expires_at - time.time())}s)")
            return cached_access_token

        # Token expired or missing, try to refresh it
        refresh_token = read_user_token(username)

        # If no refresh token exists (invalidated or never set), user needs to re-authenticate
        if not refresh_token:
            notify(f"⚠️ No refresh token found for {username} - re-authentication required")
            if raise_on_failure:
                from fastapi import HTTPException
                raise HTTPException(
                    status_code=401,
                    detail="Twitter authentication expired. Please log in again."
                )
            raise OAuthTokenExpired(f"No valid OAuth token for {username}")

        refreshed = refresh_access_token(refresh_token, username=username)
        access_token = refreshed.get("access_token")
        new_refresh = refreshed.get("refresh_token") or refresh_token
        expires_in = refreshed.get("expires_in", 7200)  # Default 2 hours
        store_token(username, new_refresh, access_token, expires_in)
        notify(f"🔄 Refreshed access token for {username}")
        return access_token
    except OAuthTokenExpired:
        # Re-raise OAuthTokenExpired without modification
        raise
    except (RuntimeError, Exception) as e:
        # Token refresh failed - user needs to re-authenticate
        notify(f"⚠️ OAuth token refresh failed for {username}: {e}")

        # Invalidate the token so we don't keep trying
        # This prevents repeated refresh attempts until user re-authenticates
        try:
            from backend.utlils.email import notify_user_reauth_needed
            from backend.utlils.utils import invalidate_user_token
            invalidate_user_token(username)
            notify_user_reauth_needed(username)
        except Exception as notify_err:
            notify(f"⚠️ Failed to notify user {username} about re-auth: {notify_err}")

        if raise_on_failure:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=401,
                detail="Twitter authentication expired. Please log in again."
            )
        raise OAuthTokenExpired(f"OAuth token refresh failed for {username}")


def main() -> None:
    import asyncio

    async def _main():
        username = "proudlurker"

        access_token = await ensure_access_token(username)
        try:
            user_info = await get_user_info(access_token)
            handle = user_info.get("data", {}).get("username")
            if handle:
                notify(f"Authenticated as @{handle}")
        except Exception as exc:  # pragma: no cover - network required
            error("Warning: could not fetch user info", exception_text=str(exc), status_code=500, function_name="oauth_dance", username=username)

    asyncio.run(_main())


if __name__ == "__main__":
    main()
