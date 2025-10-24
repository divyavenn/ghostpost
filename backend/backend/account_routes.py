"""API routes for account management and limits."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.account_limits import (
    AccountType,
    check_account_limit,
    get_account_info,
    increment_usage,
    reset_usage,
    update_account_type,
)

router = APIRouter(prefix="/account", tags=["account"])


class UpdateAccountTypeRequest(BaseModel):
    account_type: AccountType
    model: str | None = None


class CheckLimitRequest(BaseModel):
    action: str  # "scrape", "post", "generate_reply", "add_account", "add_query"


class IncrementUsageRequest(BaseModel):
    action: str  # "scrape", "post"


@router.get("/{handle}/info")
async def get_account_info_endpoint(handle: str) -> dict:
    """Get account type, limits, and usage for a user."""
    account_info = get_account_info(handle)
    if "error" in account_info and account_info["error"] == "user_not_found":
        raise HTTPException(status_code=404, detail="User not found")
    return account_info


@router.post("/{handle}/check-limit")
async def check_limit_endpoint(handle: str, payload: CheckLimitRequest) -> dict:
    """Check if user can perform an action."""
    result = check_account_limit(handle, payload.action)
    if "error" in result and result["error"] == "user_not_found":
        raise HTTPException(status_code=404, detail="User not found")
    return result


@router.post("/{handle}/increment-usage")
async def increment_usage_endpoint(handle: str, payload: IncrementUsageRequest) -> dict:
    """Increment usage counter for an action."""
    result = increment_usage(handle, payload.action)
    if "error" in result:
        raise HTTPException(status_code=404, detail="User not found")
    return {"usage": result}


@router.post("/{handle}/reset-usage")
async def reset_usage_endpoint(handle: str) -> dict:
    """Reset usage counters (admin only)."""
    result = reset_usage(handle)
    if "error" in result:
        raise HTTPException(status_code=404, detail="User not found")
    return {"usage": result}


@router.put("/{handle}/account-type")
async def update_account_type_endpoint(handle: str, payload: UpdateAccountTypeRequest) -> dict:
    """Update account type for a user (admin only)."""
    result = update_account_type(handle, payload.account_type, payload.model)
    if "error" in result:
        if result["error"] == "user_not_found":
            raise HTTPException(status_code=404, detail="User not found")
        else:
            raise HTTPException(status_code=400, detail=result.get("message", "Invalid request"))
    return result
