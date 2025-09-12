"""
OAuth 2.0 PKCE utilities for X (Twitter) authentication
"""

import base64
import hashlib
import secrets
import os
from typing import Dict, Optional, Tuple
from urllib.parse import urlencode


class TwitterPKCE:
    """Handles X (Twitter) OAuth 2.0 PKCE flow"""
    
    def __init__(self):
        self.client_id = os.getenv("TWITTER_CLIENT_ID")
        self.client_secret = os.getenv("TWITTER_CLIENT_SECRET")
        self.redirect_uri = os.getenv("TWITTER_REDIRECT_URI", "http://localhost:8000/auth/callback")
        self.base_url = "https://api.x.com/2"
        
        if not self.client_id:
            raise ValueError("TWITTER_CLIENT_ID environment variable is required")
        if not self.client_secret:
            raise ValueError("TWITTER_CLIENT_SECRET environment variable is required")
    
    def generate_code_verifier(self) -> str:
        """Generate a cryptographically random code verifier (43-128 characters)"""
        return base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b'=').decode('utf-8')
    
    def generate_code_challenge(self, code_verifier: str) -> str:
        """Generate code challenge from verifier using SHA256"""
        sha256 = hashlib.sha256(code_verifier.encode('utf-8')).digest()
        return base64.urlsafe_b64encode(sha256).rstrip(b'=').decode('utf-8')
    
    def get_authorization_url(self, state: Optional[str] = None) -> Tuple[str, str]:
        """
        Generate authorization URL and code verifier
        
        Args:
            state: Optional state parameter. If not provided, will generate one.
        
        Returns:
            Tuple of (authorization_url, code_verifier)
        """
        code_verifier = self.generate_code_verifier()
        code_challenge = self.generate_code_challenge(code_verifier)
        
        if not state:
            state = secrets.token_urlsafe(32)
        
        params = {
            'response_type': 'code',
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'scope': 'tweet.read tweet.write users.read offline.access',
            'state': state,
            'code_challenge': code_challenge,
            'code_challenge_method': 'S256'
        }
        
        auth_url = f"https://x.com/i/oauth2/authorize?{urlencode(params)}"
        return auth_url, code_verifier
    
    def exchange_code_for_token(self, code: str, code_verifier: str) -> Dict:
        """
        Exchange authorization code for access token
        
        Args:
            code: Authorization code from callback
            code_verifier: Code verifier used to generate challenge
            
        Returns:
            Dict containing access token and refresh token
        """
        import requests
        
        url = f"{self.base_url}/oauth2/token"
        
        data = {
            'grant_type': 'authorization_code',
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'code': code,
            'code_verifier': code_verifier
        }
        
        # Create Basic Authentication header
        import base64
        credentials = f"{self.client_id}:{self.client_secret}"
        encoded_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
        headers = {
            'Authorization': f'Basic {encoded_credentials}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        response = requests.post(url, data=data, headers=headers)
        response.raise_for_status()
        return response.json()
    
    def refresh_access_token(self, refresh_token: str) -> Dict:
        """
        Refresh access token using refresh token
        
        Args:
            refresh_token: Refresh token from initial token exchange
            
        Returns:
            Dict containing new access token
        """
        import requests
        
        url = f"{self.base_url}/oauth2/token"
        
        data = {
            'grant_type': 'refresh_token',
            'client_id': self.client_id,
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


# Load environment variables from root .env file
from dotenv import load_dotenv
import os
from pathlib import Path

# Load .env from project root (parent directory)
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# Global instance
pkce_client = TwitterPKCE()
