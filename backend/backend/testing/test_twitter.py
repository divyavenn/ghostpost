"""
Unused API endpoints moved here for testing/future use.

These endpoints are not currently used by the frontend but may be useful for:
- Testing browser session management
- Admin account management
- Future features
"""

import io

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.browser_management.sessions import (
    cleanup_expired_sessions,
    close_session,
    create_browser_session,
    get_session_screenshot,
    get_session_status,
    save_and_close_session,
)
from backend.twitter.account_limits import (
    AccountType,
    check_account_limit,
    get_account_info,
    increment_usage,
    reset_usage,
    update_account_type,
)
from backend.utlils.utils import error

# =============================================================================
# BROWSER AUTH ENDPOINTS (from browser_management/routes.py)
# =============================================================================
# These endpoints use Playwright to manage browser sessions for OAuth login.
# Currently not used - frontend uses /auth/twitter/login-url flow instead.

browser_auth_router = APIRouter(prefix="/auth/browser", tags=["browser-auth-test"])


class BrowserSessionRequest(BaseModel):
    username: str


class SaveSessionRequest(BaseModel):
    session_id: str


@browser_auth_router.post("/start")
async def start_browser_session(request: BrowserSessionRequest):
    """
    Start a new browser session for OAuth login.
    Returns session ID for tracking.
    """
    try:
        # Cleanup expired sessions first
        await cleanup_expired_sessions()

        session_info = await create_browser_session(request.username)
        return session_info
    except Exception as e:
        error("Failed to start browser session", status_code=500, exception_text=str(e), function_name="start_browser_session", username=request.username)
        raise HTTPException(status_code=500, detail=f"Failed to start browser session: {str(e)}") from e


@browser_auth_router.get("/status/{session_id}")
async def check_session_status(session_id: str):
    """
    Check if user has completed login in the browser.
    Frontend should poll this endpoint.
    """
    try:
        status = await get_session_status(session_id)
        return status
    except Exception as e:
        error("Failed to check session status", status_code=500, exception_text=str(e), function_name="check_session_status")
        raise HTTPException(status_code=500, detail=f"Failed to check session status: {str(e)}") from e


@browser_auth_router.post("/save")
async def save_browser_session(request: SaveSessionRequest):
    """
    Save browser state and close session after successful login.
    """
    try:
        result = await save_and_close_session(request.session_id)
        return result
    except ValueError as e:
        error("Session not found", status_code=404, exception_text=str(e), function_name="save_browser_session")
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        error("Failed to save session", status_code=500, exception_text=str(e), function_name="save_browser_session")
        raise HTTPException(status_code=500, detail=f"Failed to save session: {str(e)}") from e


@browser_auth_router.delete("/cancel/{session_id}")
async def cancel_browser_session(session_id: str):
    """
    Cancel and close a browser session without saving.
    """
    try:
        await close_session(session_id)
        return {"status": "cancelled"}
    except Exception as e:
        error("Failed to cancel session", status_code=500, exception_text=str(e), function_name="cancel_browser_session")
        raise HTTPException(status_code=500, detail=f"Failed to cancel session: {str(e)}") from e


@browser_auth_router.get("/screenshot/{session_id}")
async def get_browser_screenshot(session_id: str):
    """
    Get a screenshot of the current browser state.
    Useful for showing user what the browser looks like.
    """
    try:
        screenshot_bytes = await get_session_screenshot(session_id)
        if not screenshot_bytes:
            error("Session not found", status_code=404, function_name="get_browser_screenshot")
            raise HTTPException(status_code=404, detail="Session not found")

        return StreamingResponse(io.BytesIO(screenshot_bytes), media_type="image/png")
    except HTTPException:
        raise
    except Exception as e:
        error("Failed to get screenshot", status_code=500, exception_text=str(e), function_name="get_browser_screenshot")
        raise HTTPException(status_code=500, detail=f"Failed to get screenshot: {str(e)}") from e


# =============================================================================
# ACCOUNT MANAGEMENT ENDPOINTS (from twitter/account_routes.py)
# =============================================================================
# These endpoints manage account types and usage limits.
# Currently not used by the frontend.

account_router = APIRouter(prefix="/account", tags=["account-test"])


class UpdateAccountTypeRequest(BaseModel):
    account_type: AccountType
    model: str | None = None


class CheckLimitRequest(BaseModel):
    action: str  # "scrape", "post", "generate_reply", "add_account", "add_query"


class IncrementUsageRequest(BaseModel):
    action: str  # "scrape", "post"


@account_router.get("/{handle}/info")
async def get_account_info_endpoint(handle: str) -> dict:
    """Get account type, limits, and usage for a user."""
    account_info = get_account_info(handle)
    if "error" in account_info and account_info["error"] == "user_not_found":
        error("User not found", status_code=404, function_name="get_account_info_endpoint", username=handle)
        raise HTTPException(status_code=404, detail="User not found")
    return account_info


@account_router.post("/{handle}/check-limit")
async def check_limit_endpoint(handle: str, payload: CheckLimitRequest) -> dict:
    """Check if user can perform an action."""
    result = check_account_limit(handle, payload.action)
    if "error" in result and result["error"] == "user_not_found":
        error("User not found", status_code=404, function_name="check_limit_endpoint", username=handle)
        raise HTTPException(status_code=404, detail="User not found")
    return result


@account_router.post("/{handle}/increment-usage")
async def increment_usage_endpoint(handle: str, payload: IncrementUsageRequest) -> dict:
    """Increment usage counter for an action."""
    result = increment_usage(handle, payload.action)
    if "error" in result:
        error("User not found", status_code=404, function_name="increment_usage_endpoint", username=handle)
        raise HTTPException(status_code=404, detail="User not found")
    return {"usage": result}


@account_router.post("/{handle}/reset-usage")
async def reset_usage_endpoint(handle: str) -> dict:
    """Reset usage counters (admin only)."""
    result = reset_usage(handle)
    if "error" in result:
        error("User not found", status_code=404, function_name="reset_usage_endpoint", username=handle)
        raise HTTPException(status_code=404, detail="User not found")
    return {"usage": result}


@account_router.put("/{handle}/account-type")
async def update_account_type_endpoint(handle: str, payload: UpdateAccountTypeRequest) -> dict:
    """Update account type for a user (admin only)."""
    result = update_account_type(handle, payload.account_type, payload.model)
    if "error" in result:
        if result["error"] == "user_not_found":
            error("User not found", status_code=404, function_name="update_account_type_endpoint", username=handle)
            raise HTTPException(status_code=404, detail="User not found")
        else:
            error(f"Invalid request: {result.get('message', 'Unknown error')}", status_code=400, function_name="update_account_type_endpoint", username=handle)
            raise HTTPException(status_code=400, detail=result.get("message", "Invalid request"))
    return result
