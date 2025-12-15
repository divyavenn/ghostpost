"""FastAPI routes for billing."""

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

from backend.billing.stripe_service import (
    create_checkout_session,
    get_subscription_status,
    handle_webhook,
)
from backend.utlils.email import message_devs
from backend.utlils.utils import notify

router = APIRouter(prefix="/billing", tags=["billing"])


from backend.twitter.account_limits import update_account_type


class PremiumContactRequest(BaseModel):
    email: str
    phone: str | None = None
    twitter_handle: str | None = None


class UpgradeToPremiumRequest(BaseModel):
    model_name: str


@router.post("/{username}/create-checkout-session")
async def create_checkout_session_endpoint(username: str):
    """Create a Stripe Checkout Session for subscription."""
    result = create_checkout_session(username)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/webhook")
async def webhook_endpoint(request: Request, stripe_signature: str = Header(None)):
    """Handle Stripe webhook events."""
    if not stripe_signature:
        raise HTTPException(status_code=400, detail="Missing Stripe signature")

    payload = await request.body()
    result = handle_webhook(payload, stripe_signature)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/{username}/status")
async def get_status_endpoint(username: str):
    """Get subscription status for a user."""
    result = get_subscription_status(username)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/contact-premium")
async def contact_premium_endpoint(payload: PremiumContactRequest):
    """Send a premium plan inquiry email."""
    if not payload.email or not payload.email.strip():
        raise HTTPException(status_code=400, detail="Email is required")

    # Build email content
    body = f"""New Premium Plan Inquiry

Contact Email: {payload.email}
Phone: {payload.phone or 'Not provided'}
Twitter: {payload.twitter_handle or 'Not logged in'}

This person is interested in the Premium plan with custom AI training.
"""

    # Use the same email function as error notifications
    success = message_devs(body, subject="Premium Plan Inquiry")
    if not success:
        raise HTTPException(status_code=500, detail="Failed to send inquiry email. Please try again or contact divya@aibread.com directly.")
    notify(f"📧 Premium inquiry sent from {payload.email}")
    return {"message": "Contact request sent successfully"}


@router.post("/{handle}/upgrade-to-paid")
async def upgrade_to_paid_endpoint(handle: str):
    """Upgrade a user to the paid tier."""
    result = update_account_type(handle, "paid")
    if "error" in result:
        raise HTTPException(status_code=400, detail=result.get("message", result["error"]))
    notify(f"✅ Upgraded {handle} to paid tier")
    return {"message": f"Successfully upgraded {handle} to paid", "account_info": result}


@router.post("/{handle}/upgrade-to-premium")
async def upgrade_to_premium_endpoint(handle: str, payload: UpgradeToPremiumRequest):
    """Upgrade a user to the premium tier with a custom model."""
    if not payload.model_name or not payload.model_name.strip():
        raise HTTPException(status_code=400, detail="model_name is required for premium tier")

    result = update_account_type(handle, "premium", model=payload.model_name)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result.get("message", result["error"]))
    notify(f"✅ Upgraded {handle} to premium tier with model: {payload.model_name}")
    return {"message": f"Successfully upgraded {handle} to premium", "account_info": result}
