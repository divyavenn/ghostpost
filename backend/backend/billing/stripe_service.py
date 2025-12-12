"""Stripe integration service for billing."""

import stripe

from backend.config import (
    FRONTEND_URL,
    STRIPE_PAID_PRICE_ID,
    STRIPE_SECRET_KEY,
    STRIPE_WEBHOOK_SECRET,
)
from backend.twitter.account_limits import update_account_type
from backend.utlils.utils import error, notify, read_user_info

# Initialize Stripe with secret key
if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY


def create_checkout_session(username: str) -> dict:
    """
    Create a Stripe Checkout Session for the paid tier subscription.

    Args:
        username: Twitter handle of the user

    Returns:
        Dict with checkout_url or error
    """
    if not STRIPE_SECRET_KEY:
        error("Stripe is not configured", status_code=500, function_name="create_checkout_session", username=username, critical=True)
        return {"error": "Stripe is not configured"}

    if not STRIPE_PAID_PRICE_ID:
        error("Stripe price ID not configured", status_code=500, function_name="create_checkout_session", username=username, critical=True)
        return {"error": "Stripe price ID not configured"}

    # Verify user exists
    user_info = read_user_info(username)
    if not user_info:
        error(f"User {username} not found", status_code=404, function_name="create_checkout_session", username=username, critical=True)
        return {"error": "User not found"}

    try:
        # Create Checkout Session
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[
                {
                    "price": STRIPE_PAID_PRICE_ID,
                    "quantity": 1,
                },
            ],
            mode="subscription",
            success_url=f"{FRONTEND_URL}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{FRONTEND_URL}/pricing",
            metadata={
                "username": username,
            },
            client_reference_id=username,
        )

        notify(f"Created checkout session for {username}")
        return {"checkout_url": checkout_session.url, "session_id": checkout_session.id}

    except stripe.error.StripeError as e:
        error(f"Stripe error: {e}", status_code=500, function_name="create_checkout_session", username=username, critical=True)
        return {"error": str(e)}


def handle_webhook(payload: bytes, signature: str) -> dict:
    """
    Handle Stripe webhook events.

    Args:
        payload: Raw request body
        signature: Stripe signature header

    Returns:
        Dict with status or error
    """
    if not STRIPE_WEBHOOK_SECRET:
        error("Stripe webhook secret not configured", status_code=500, function_name="handle_webhook", username="webhook", critical=False)
        return {"error": "Webhook secret not configured"}

    try:
        event = stripe.Webhook.construct_event(payload, signature, STRIPE_WEBHOOK_SECRET)
    except ValueError:
        error("Invalid webhook payload", status_code=400, function_name="handle_webhook", username="webhook", critical=False)
        return {"error": "Invalid payload"}
    except stripe.error.SignatureVerificationError:
        error("Invalid webhook signature", status_code=400, function_name="handle_webhook", username="webhook", critical=False)
        return {"error": "Invalid signature"}

    # Handle checkout.session.completed event
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        username = session.get("client_reference_id") or session.get("metadata", {}).get("username")

        if username:
            notify(f"Payment completed for {username}, upgrading to paid tier")
            result = update_account_type(username, "paid")
            if "error" in result:
                error(f"Failed to upgrade {username}: {result['error']}", status_code=500, function_name="handle_webhook", username=username, critical=True)
                return {"error": result["error"]}
            notify(f"Successfully upgraded {username} to paid tier")
        else:
            error("No username in checkout session", status_code=400, function_name="handle_webhook", username="webhook", critical=False)
            return {"error": "No username found"}

    # Handle subscription cancellation
    elif event["type"] == "customer.subscription.deleted":
        subscription = event["data"]["object"]
        # Get username from subscription metadata if available
        username = subscription.get("metadata", {}).get("username")
        if username:
            notify(f"Subscription cancelled for {username}, downgrading to trial")
            update_account_type(username, "trial")

    return {"status": "success"}


def get_subscription_status(username: str) -> dict:
    """
    Get the current subscription status for a user.

    Args:
        username: Twitter handle

    Returns:
        Dict with subscription info
    """
    user_info = read_user_info(username)
    if not user_info:
        return {"error": "User not found"}

    account_type = user_info.get("account_type", "trial")

    return {
        "username": username,
        "account_type": account_type,
        "is_subscribed": account_type in ["paid", "premium"],
    }
