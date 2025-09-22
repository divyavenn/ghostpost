"""OAuth 2.0 PKCE utilities for X (Twitter) authentication."""

import base64
import hashlib
import json
import os
import secrets
import threading
from pathlib import Path
from typing import Dict, Optional, Tuple
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import dotenv

dotenv.load_dotenv()

client_id = os.getenv("TWITTER_CLIENT_ID")
client_secret = os.getenv("TWITTER_CLIENT_SECRET")
redirect_uri = os.getenv("TWITTER_REDIRECT_URI", "http://localhost:8000/auth/callback")
base_url = "https://api.x.com/2"

    
def generate_code_verifier() -> str:
        """Generate a cryptographically random code verifier (43-128 characters)"""
        return base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b'=').decode('utf-8')
    
def generate_code_challenge(code_verifier: str) -> str:
        """Generate code challenge from verifier using SHA256"""
        sha256 = hashlib.sha256(code_verifier.encode('utf-8')).digest()
        return base64.urlsafe_b64encode(sha256).rstrip(b'=').decode('utf-8')
    
def get_authorization_url(state: Optional[str] = None) -> Tuple[str, str]:
        """
        Generate authorization URL and code verifier
        
        Args:
            state: Optional state parameter. If not provided, will generate one.
        
        Returns:
            Tuple of (authorization_url, code_verifier)
        """
        code_verifier = generate_code_verifier()
        code_challenge = generate_code_challenge(code_verifier)
        
        if not state:
            state = secrets.token_urlsafe(32)
        
        params = {
            'response_type': 'code',
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'scope': 'tweet.read tweet.write users.read offline.access',
            'state': state,
            'code_challenge': code_challenge,
            'code_challenge_method': 'S256'
        }
        
        auth_url = f"https://x.com/i/oauth2/authorize?{urlencode(params)}"
        return auth_url, code_verifier
    
def exchange_code_for_token(code: str, code_verifier: str) -> Dict:
        """
        Exchange authorization code for access token
        
        Args:
            code: Authorization code from callback
            code_verifier: Code verifier used to generate challenge
            
        Returns:
            Dict containing access token and refresh token
        """
        import requests
        
        url = f"{base_url}/oauth2/token"
        
        data = {
            'grant_type': 'authorization_code',
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'code': code,
            'code_verifier': code_verifier
        }
        
        # Create Basic Authentication header
        import base64
        credentials = f"{client_id}:{client_secret}"
        encoded_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
        headers = {
            'Authorization': f'Basic {encoded_credentials}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        response = requests.post(url, data=data, headers=headers)
        response.raise_for_status()
        return response.json()
    
def refresh_access_token(refresh_token: str) -> Dict:
        """
        Refresh access token using refresh token
        
        Args:
            refresh_token: Refresh token from initial token exchange
            
        Returns:
            Dict containing new access token
        """
        import requests
        
        url = f"{base_url}/oauth2/token"
        
        data = {
            'grant_type': 'refresh_token',
            'client_id': client_id,
            'refresh_token': refresh_token
        }
        
        response = requests.post(url, data=data)
        response.raise_for_status()
        return response.json()
    
def get_user_info(self, access_token: str) -> Dict:
        """
        Get user information using access token
        
        Args:
            access_token: User access token
            
        Returns:
            Dict containing user information
        """
        import requests
        
        url = "https://api.twitter.com/2/users/me"
        params = {
            'user.fields': 'id,username,name,public_metrics'
        }
        headers = {
            'Authorization': f'Bearer {access_token}'
        }
        
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()




def _start_callback_server(redirect_uri: str, expected_state: str) -> Tuple[HTTPServer, threading.Event]:
    """Spin up a local HTTP server to capture the OAuth redirect."""
    parsed = urlparse(redirect_uri)
    if parsed.scheme != "http":
        raise ValueError("Redirect URI must use http scheme for local testing.")

    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 80
    path = parsed.path or "/"

    authorization_event = threading.Event()

    class OAuthCallbackHandler(BaseHTTPRequestHandler):  # type: ignore[misc]
        def log_message(self, format: str, *args) -> None:  # pragma: no cover - silence HTTP logs
            return

        def do_GET(self) -> None:  # pragma: no cover - invoked via browser callback
            parsed_path = urlparse(self.path)
            if parsed_path.path != path:
                self.send_error(404, "Not Found")
                return

            params = parse_qs(parsed_path.query)
            self.server.authorization_params = params  # type: ignore[attr-defined]

            # Surface provider errors directly to the user
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
    except OSError as exc:  # pragma: no cover - depends on runtime environment
        raise SystemExit(
            f"Could not start callback server on {host}:{port}. Update TWITTER_REDIRECT_URI to a free port."
        ) from exc

    server.authorization_params = None  # type: ignore[attr-defined]

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    return server, authorization_event


def main() -> None:
    """Run the full PKCE login flow and post a tweet on behalf of the user."""
    print("Starting X OAuth 2.0 PKCE login flow...")

    state = secrets.token_urlsafe(32)
    server, auth_event = _start_callback_server(redirect_uri, state)

    try:
        auth_url, code_verifier = get_authorization_url(state)
        print("1. Open the following URL in your browser and authenticate:")
        print(auth_url)
        print("2. Approve the request. This script is waiting for the callback...")

        if not auth_event.wait(timeout=300):
            raise SystemExit("Timed out waiting for authorization response. Try again.")

        params = getattr(server, "authorization_params", {}) or {}
    finally:
        server.shutdown()
        server.server_close()

    if "error" in params:
        error = params.get("error", ["unknown_error"])[0]
        description = params.get("error_description", [""])[0]
        raise SystemExit(f"Authorization failed: {error} {description}".strip())

    code = params.get("code", [""])[0]
    if not code:
        raise SystemExit("Authorization code missing from callback response.")

    print("Exchanging authorization code for access token...")
    token_response = exchange_code_for_token(code, code_verifier)

    access_token = token_response.get("access_token")
    if not access_token:
        raise SystemExit("Access token not returned by X API.")

    refresh_token = token_response.get("refresh_token")
    expires_in = token_response.get("expires_in")
    if expires_in:
        print(f"Access token expires in {expires_in} seconds")
    if refresh_token:
        print("Refresh token received. Store it securely if you want to reuse it.")

    try:
        user_info = get_user_info(access_token)
        username = user_info.get("data", {}).get("username")
        if username:
            print(f"Authenticated as @{username}")
    except Exception as exc:  # pragma: no cover - network required
        print(f"Warning: could not fetch user info ({exc})")

    tweet_text = input("Tweet text to post: ").strip()
    while not tweet_text:
        tweet_text = input("Tweet text cannot be empty. Enter tweet text: ").strip()

    from post_takes import post_take_with_token

    print("Posting tweet...")
    result = post_take_with_token(tweet_text, access_token)
    print("Tweet posted. Response:")
    print(json.dumps(result, indent=2))

    if refresh_token:
        print("Reminder: refresh tokens rotate. Update your stored credentials if a new one was returned.")


if __name__ == "__main__":
    main()
