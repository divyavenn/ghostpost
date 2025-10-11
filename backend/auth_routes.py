"""Authentication routes for Twitter OAuth without requiring pre-authentication."""

import secrets
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

from backend.oauth import get_authorization_url, exchange_code_for_token
from backend.user import get_user_info
from backend.utils import store_token, read_user_info

router = APIRouter(prefix="/auth", tags=["auth"])

# Store state temporarily (in production, use Redis or database)
_oauth_states = {}


class StartOAuthRequest(BaseModel):
    redirect_to: str | None = None


@router.post("/twitter/start")
async def start_oauth(payload: StartOAuthRequest | None = None) -> dict[str, str]:
    """Start Twitter OAuth flow - no authentication required."""
    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)

    # Generate OAuth URL with state
    auth_url, code_verifier = get_authorization_url(state)

    # Store state and code_verifier for later verification
    _oauth_states[state] = {
        "code_verifier": code_verifier,
        "redirect_to": payload.redirect_to if payload else None
    }

    return {
        "auth_url": auth_url,
        "state": state,
    }


@router.get("/callback")
async def twitter_callback(
    state: str = Query(...),
    code: str | None = Query(None),
    error: str | None = Query(None),
    error_description: str | None = Query(None),
):
    """Handle Twitter OAuth callback."""
    redirect_to = "http://localhost:5173"

    if error:
        # Redirect back to frontend with error
        return RedirectResponse(
            url=f"{redirect_to}?status=error&error={error}&error_description={error_description or ''}",
            status_code=303
        )

    if not code:
        return RedirectResponse(
            url=f"{redirect_to}?status=error&error=missing_code",
            status_code=303
        )

    # Verify state
    oauth_data = _oauth_states.pop(state, None)
    if not oauth_data:
        return RedirectResponse(
            url=f"{redirect_to}?status=error&error=invalid_state",
            status_code=303
        )

    code_verifier = oauth_data["code_verifier"]
    redirect_to = oauth_data.get("redirect_to") or redirect_to

    try:
        # Exchange code for tokens
        token_response = exchange_code_for_token(code, code_verifier)
        access_token = token_response.get("access_token")
        refresh_token = token_response.get("refresh_token")

        if not access_token or not refresh_token:
            return RedirectResponse(
                url=f"{redirect_to}?status=error&error=no_tokens",
                status_code=303
            )

        # Get user info
        user_info = get_user_info(access_token)
        twitter_handle = user_info.get("handle") or user_info.get("username")

        if not twitter_handle:
            return RedirectResponse(
                url=f"{redirect_to}?status=error&error=no_handle",
                status_code=303
            )

        # Store the refresh token for this user
        store_token(twitter_handle, refresh_token)

        # Check if user has a trained model
        cached_user = read_user_info(twitter_handle)
        if not cached_user or not cached_user.get("model"):
            return RedirectResponse(
                url=f"{redirect_to}/no-model",
                status_code=303
            )

        # Redirect back to frontend with username
        return RedirectResponse(
            url=f"{redirect_to}?username={twitter_handle}&status=success",
            status_code=303
        )

    except Exception as e:
        return RedirectResponse(
            url=f"{redirect_to}?status=error&error=exception&error_description={str(e)}",
            status_code=303
        )
