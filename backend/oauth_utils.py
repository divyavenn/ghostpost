"""OAuth 2.0 PKCE utilities for X (Twitter) authentication."""

import base64
import hashlib
import os
import secrets
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, Optional, Tuple
from urllib.parse import parse_qs, urlencode, urlparse

import dotenv

from persist_token import load_token_cache, persist_token_to_file
from utils import error, notify


dotenv.load_dotenv()

client_id = os.getenv("TWITTER_CLIENT_ID")
client_secret = os.getenv("TWITTER_CLIENT_SECRET")
redirect_uri = os.getenv("TWITTER_REDIRECT_URI", "http://localhost:8000/auth/callback")
BASE_URL = "https://api.x.com/2"


def generate_code_verifier() -> str:
    """Generate a cryptographically random code verifier (43-128 characters)."""
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode("utf-8")


def generate_code_challenge(code_verifier: str) -> str:
    """Generate the PKCE code challenge from a verifier using SHA256."""
    digest = hashlib.sha256(code_verifier.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("utf-8")


def get_authorization_url(state: Optional[str] = None) -> Tuple[str, str]:
    """Return the authorize URL and the code verifier used to build it."""
    code_verifier = generate_code_verifier()
    code_challenge = generate_code_challenge(code_verifier)

    if not state:
        state = secrets.token_urlsafe(32)

    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": "tweet.read tweet.write users.read offline.access",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }

    auth_url = f"https://x.com/i/oauth2/authorize?{urlencode(params)}"
    return auth_url, code_verifier


def exchange_code_for_token(code: str, code_verifier: str) -> Dict[str, Any]:
    """Exchange an authorization code + verifier for an access token payload."""
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


def refresh_access_token(refresh_token: str) -> Dict[str, Any]:
    """Refresh the access token using the long-lived refresh token."""
    import requests

    url = f"{BASE_URL}/oauth2/token"
    data = {
        "grant_type": "refresh_token",
        "client_id": client_id,
        "refresh_token": refresh_token,
    }

    response = requests.post(url, data=data)
    response.raise_for_status()
    return response.json()


def get_user_info(access_token: str) -> Dict[str, Any]:
    """Fetch the authenticated user's metadata."""
    import requests

    url = "https://api.twitter.com/2/users/me"
    params = {"user.fields": "id,username,name,public_metrics"}
    headers = {"Authorization": f"Bearer {access_token}"}

    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    return response.json()


def _start_callback_server(redirect_uri: str, expected_state: str) -> Tuple[HTTPServer, threading.Event]:
    """Spin up a local HTTP server to capture the OAuth redirect."""
    parsed = urlparse(redirect_uri)
    if parsed.scheme != "http":
        error("Redirect URI must use http scheme for local testing.")

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
                message = params.get("error_description", [""])[0] or "Authorization failed."
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
            self.wfile.write(
                b"<html><body><h1>Authorization complete.</h1><p>You may close this window.</p></body></html>"
            )

            authorization_event.set()
            threading.Thread(target=self.server.shutdown, daemon=True).start()  # type: ignore[arg-type]

    try:
        server = HTTPServer((host, port), OAuthCallbackHandler)
    except OSError as exc:  # pragma: no cover - depends on environment
        raise SystemExit(
            f"Could not start callback server on {host}:{port}. Update TWITTER_REDIRECT_URI to a free port."
        ) from exc

    server.authorization_params = None  # type: ignore[attr-defined]

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    return server, authorization_event


async def oauth_login(username: str, state_file: str = "storage_state.json") -> str:
    """Complete the OAuth flow via Playwright and persist the resulting tokens."""
    from playwright.async_api import async_playwright

    state = secrets.token_urlsafe(32)
    server, auth_event = _start_callback_server(redirect_uri, state)
    auth_url, code_verifier = get_authorization_url(state)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()
            await page.goto(auth_url)

            if not auth_event.wait(timeout=300):
                error("OAuth browser flow timed out")
                raise RuntimeError("OAuth flow timed out waiting for callback")

            await context.storage_state(path=state_file)
            await context.close()
            await browser.close()

        params = getattr(server, "authorization_params", {}) or {}
    finally:
        server.shutdown()
        server.server_close()

    code = params.get("code", [""])[0]
    if not code:
        error("Authorization code missing from callback response.")
        raise RuntimeError("Authorization code missing from callback response.")

    token_response = exchange_code_for_token(code, code_verifier)
    access_token = token_response.get("access_token")
    if not access_token:
        error("Access token not returned by X API.")

    refresh_token = token_response.get("refresh_token")
    if not refresh_token:
        error("Refresh token not returned by X API.")

    persist_token_to_file(username, refresh_token)
    notify(f"💾 Stored OAuth refresh token for {username}")

    return access_token


async def ensure_access_token(username: str, state_file: str = "storage_state.json") -> str:
    """Return an access token for the user, refreshing or re-authenticating as needed."""
    refresh_token = load_token_cache().get(username)

    if isinstance(refresh_token, str) and refresh_token:
        try:
            refreshed = refresh_access_token(refresh_token)
            access_token = refreshed.get("access_token")
            if access_token:
                new_refresh = refreshed.get("refresh_token") or refresh_token
                persist_token_to_file(username, new_refresh)
                notify(f"🔄 Refreshed OAuth token for {username}")
                return access_token
            notify(f"⚠️ Refresh response missing access token for {username}")
        except Exception as exc:  # pragma: no cover - network errors
            notify(f"⚠️ Failed to refresh token for {username}: {exc}")

    notify(f"🔐 Launching OAuth login for {username}")
    return await oauth_login(username=username, state_file=state_file)


def main() -> None:
    """CLI helper to obtain an access token and optional tweet."""
    import asyncio

    username = os.getenv("TWITTER_USERNAME") or input("Twitter username (storage key): ").strip()
    if not username:
        raise SystemExit("Username required to store tokens.")

    access_token = asyncio.run(ensure_access_token(username))
    print("Access token ready.")

    try:
        user_info = get_user_info(access_token)
        handle = user_info.get("data", {}).get("username")
        if handle:
            print(f"Authenticated as @{handle}")
    except Exception as exc:  # pragma: no cover - network required
        print(f"Warning: could not fetch user info ({exc})")


if __name__ == "__main__":
    main()
