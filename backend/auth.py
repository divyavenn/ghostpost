import os
from typing import Optional, Dict, Any
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import create_client, Client
from dotenv import load_dotenv
import jwt
from datetime import datetime

load_dotenv()

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    raise ValueError(
        "SUPABASE_URL and SUPABASE_ANON_KEY must be set in environment variables"
    )

# Create Supabase clients
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
supabase_admin: Client = (
    create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    if SUPABASE_SERVICE_ROLE_KEY
    else None
)

security = HTTPBearer(auto_error=False)


class SupabaseAuthManager:
    """Handles authentication using Supabase Auth"""

    def __init__(self):
        self.supabase = supabase
        self.supabase_admin = supabase_admin

    def verify_jwt_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify Supabase JWT token and return user info"""
        try:
            # Verify token with Supabase
            response = self.supabase.auth.get_user(token)

            if response.user:
                return {
                    "user_id": response.user.id,
                    "email": response.user.email,
                    "role": response.user.user_metadata.get("role", "user"),
                    "username": response.user.user_metadata.get(
                        "username", response.user.email
                    ),
                    "created_at": response.user.created_at,
                }

            return None

        except Exception as e:
            print(f"Error verifying JWT token: {e}")
            return None

    def get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user profile from profiles table"""
        try:
            response = (
                self.supabase.table("profiles").select("*").eq("id", user_id).execute()
            )

            if response.data and len(response.data) > 0:
                return response.data[0]

            return None

        except Exception as e:
            print(f"Error getting user profile: {e}")
            return None

    def create_user_profile(
        self, user_id: str, email: str, username: str = None, role: str = "user"
    ) -> bool:
        """Create user profile in profiles table"""
        try:
            profile_data = {
                "id": user_id,
                "email": email,
                "username": username or email.split("@")[0],
                "role": role,
                "created_at": datetime.now().isoformat(),
                "is_active": True,
            }

            response = self.supabase.table("profiles").insert(profile_data).execute()
            return len(response.data) > 0

        except Exception as e:
            print(f"Error creating user profile: {e}")
            return False

    def update_user_profile(self, user_id: str, updates: Dict[str, Any]) -> bool:
        """Update user profile"""
        try:
            response = (
                self.supabase.table("profiles")
                .update(updates)
                .eq("id", user_id)
                .execute()
            )
            return len(response.data) > 0

        except Exception as e:
            print(f"Error updating user profile: {e}")
            return False

    def get_user_stats(self) -> Dict[str, int]:
        """Get user statistics from Supabase"""
        try:
            # Get total active users
            active_users_response = (
                self.supabase.table("profiles")
                .select("id", count="exact")
                .eq("is_active", True)
                .execute()
            )
            active_users = active_users_response.count or 0

            # Get admin users
            admin_users_response = (
                self.supabase.table("profiles")
                .select("id", count="exact")
                .eq("role", "admin")
                .execute()
            )
            admin_users = admin_users_response.count or 0

            return {
                "active_users": active_users,
                "admin_users": admin_users,
                "total_users": active_users,  # Supabase doesn't expose session info easily
            }

        except Exception as e:
            print(f"Error getting user stats: {e}")
            return {"active_users": 0, "admin_users": 0, "total_users": 0}

    def is_admin(self, user_id: str) -> bool:
        """Check if user is admin"""
        try:
            profile = self.get_user_profile(user_id)
            return profile and profile.get("role") == "admin"
        except:
            return False


# Global auth manager instance
auth_manager = SupabaseAuthManager()


def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Dict[str, Any]:
    """Verify Supabase JWT token and return user info"""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_info = auth_manager.verify_jwt_token(credentials.credentials)

    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get additional profile info
    profile = auth_manager.get_user_profile(user_info["user_id"])
    if profile:
        user_info.update(profile)

    return user_info


def require_admin(
    current_user: Dict[str, Any] = Depends(verify_token),
) -> Dict[str, Any]:
    """Require admin role"""
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required"
        )
    return current_user


def optional_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[Dict[str, Any]]:
    """Optional authentication - returns user info if authenticated, None otherwise"""
    if not credentials:
        return None

    user_info = auth_manager.verify_jwt_token(credentials.credentials)

    if user_info:
        # Get additional profile info
        profile = auth_manager.get_user_profile(user_info["user_id"])
        if profile:
            user_info.update(profile)

    return user_info
