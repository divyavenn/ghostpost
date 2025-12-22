"""Supabase authentication routes for JWT verification and user sync."""

import json
from typing import Any

import jwt
from jwt import PyJWK
from fastapi import APIRouter, Depends, Header, HTTPException

from backend.config import SUPABASE_JWT_KEY
from backend.utlils.supabase_client import (
    create_user,
    get_twitter_profiles_for_user,
    get_user_by_id,
)

router = APIRouter(prefix="/auth/supabase", tags=["supabase-auth"])

# Cache the parsed JWK
_jwk_cache = None


def get_public_key():
    """Get the public key from the JWK configuration."""
    global _jwk_cache
    if _jwk_cache is None:
        if not SUPABASE_JWT_KEY:
            raise ValueError("SUPABASE_JWT_KEY not configured")
        # Parse the JWK (can be JSON string or already a dict)
        if isinstance(SUPABASE_JWT_KEY, str):
            jwk_data = json.loads(SUPABASE_JWT_KEY)
        else:
            jwk_data = SUPABASE_JWT_KEY
        _jwk_cache = PyJWK.from_dict(jwk_data)
    return _jwk_cache.key


async def verify_supabase_token(authorization: str = Header(...)) -> dict[str, Any]:
    """Verify Supabase JWT and return user data."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = authorization.replace("Bearer ", "")

    if not SUPABASE_JWT_KEY:
        raise HTTPException(status_code=500, detail="Supabase JWT key not configured")

    try:
        # Get the public key from JWK
        public_key = get_public_key()

        # Verify JWT with Supabase's ES256 public key
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["ES256"],
            audience="authenticated",
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")


async def get_optional_user(
    authorization: str | None = Header(None),
) -> dict[str, Any] | None:
    """
    Optionally verify JWT. Returns None if no token provided.
    Use for routes that work with or without auth.
    """
    if not authorization:
        return None

    try:
        return await verify_supabase_token(authorization)
    except HTTPException:
        return None


@router.post("/sync")
async def sync_user(user_data: dict = Depends(verify_supabase_token)):
    """
    Sync Supabase user to local database.
    Creates user if not exists, returns user info including any connected Twitter profile.
    """
    user_id = user_data.get("sub")  # Supabase user ID (UUID)

    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found in token")

    # Look up user by their auth.users ID
    existing_user = get_user_by_id(user_id)

    if existing_user:
        # Check if user has a connected Twitter profile
        profiles = get_twitter_profiles_for_user(user_id)
        twitter_handle = profiles[0]["handle"] if profiles else None

        return {
            "user_id": user_id,
            "account_type": existing_user.get("account_type", "trial"),
            "is_new": False,
            "twitter_handle": twitter_handle,
        }

    # Create new user with the auth.users ID
    new_user = create_user(user_id, {"account_type": "trial"})

    return {
        "user_id": user_id,
        "account_type": "trial",
        "is_new": True,
        "twitter_handle": None,
    }


@router.get("/profile")
async def get_user_profile(user_data: dict = Depends(verify_supabase_token)):
    """Get user profile including connected Twitter accounts."""
    user_id = user_data.get("sub")  # Supabase user ID (UUID)
    email = user_data.get("email")  # From JWT, not stored in users table

    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found in token")

    # Find user by their auth.users ID
    user = get_user_by_id(user_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get Twitter profiles
    profiles = get_twitter_profiles_for_user(user_id)
    twitter_handle = profiles[0]["handle"] if profiles else None

    return {
        "user_id": user_id,
        "email": email,
        "account_type": user.get("account_type", "trial"),
        "twitter_handle": twitter_handle,
    }
