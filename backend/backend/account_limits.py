"""Account tier limits and usage tracking."""

from typing import Any, Literal

from backend.utils import read_user_info, write_user_info

AccountType = Literal["trial", "paid", "premium"]


class AccountLimits:
    """Define limits for each account tier."""

    TRIAL = {
        "max_accounts": 5,
        "max_queries": 1,
        "initial_scrapes": 3,
        "initial_posts": 3,
        "can_generate_replies": False,
    }

    PAID = {
        "max_accounts": 20,
        "max_queries": 2,
        "initial_scrapes": None,  # Unlimited - don't track
        "initial_posts": None,  # Unlimited - don't track
        "can_generate_replies": False,  # Premium feature
    }

    PREMIUM = {
        "max_accounts": None,  # Unlimited
        "max_queries": None,  # Unlimited
        "initial_scrapes": None,  # Unlimited - don't track
        "initial_posts": None,  # Unlimited - don't track
        "can_generate_replies": True,
        "requires_model": True,  # Premium accounts must have a model configured
    }

    @classmethod
    def get_limits(cls, account_type: AccountType) -> dict[str, Any]:
        """Get limits for a specific account type."""
        limits_map = {
            "trial": cls.TRIAL,
            "paid": cls.PAID,
            "premium": cls.PREMIUM,
        }
        return limits_map.get(account_type, cls.TRIAL)


def get_account_info(handle: str) -> dict[str, Any]:
    """Get account type and remaining usage for a user."""
    user_info = read_user_info(handle)
    if not user_info:
        return {
            "account_type": "trial",
            "scrapes_left": 3,
            "posts_left": 3,
            "limits": AccountLimits.TRIAL,
        }

    account_type = user_info.get("account_type", "trial")
    scrapes_left = user_info.get("scrapes_left", 0)
    posts_left = user_info.get("posts_left", 0)
    limits = AccountLimits.get_limits(account_type)

    # Premium accounts require a model
    if account_type == "premium":
        has_model = "model" in user_info and user_info["model"]
        if not has_model:
            return {
                "error": "premium_requires_model",
                "message": "Premium accounts must have a model configured.",
                "account_type": account_type,
                "scrapes_left": scrapes_left,
                "posts_left": posts_left,
                "limits": limits,
            }

    return {
        "account_type": account_type,
        "scrapes_left": scrapes_left,
        "posts_left": posts_left,
        "limits": limits,
        "model": user_info.get("model"),
    }


def check_account_limit(handle: str, action: str) -> dict[str, Any]:
    """
    Check if user has reached their limit for a specific action.

    Args:
        handle: Twitter handle
        action: One of "scrape", "post", "generate_reply", "add_account", "add_query"

    Returns:
        Dict with "allowed" (bool) and optional "error", "message", "upgrade_required"
    """
    account_info = get_account_info(handle)

    if "error" in account_info:
        return {"allowed": False, **account_info}

    account_type = account_info["account_type"]
    scrapes_left = account_info["scrapes_left"]
    posts_left = account_info["posts_left"]
    limits = account_info["limits"]

    user_info = read_user_info(handle)
    if not user_info:
        return {"allowed": False, "error": "user_not_found"}

    # Check limits based on action
    if action == "scrape":
        # For paid/premium accounts, scrapes_left might be None (unlimited)
        if scrapes_left is None or (isinstance(scrapes_left, (int, float)) and scrapes_left > 0):
            return {"allowed": True, "scrapes_left": scrapes_left}

        return {
            "allowed": False,
            "error": "scrape_limit_reached",
            "message": f"You've used all your scrapes.",
            "upgrade_required": account_type == "trial",
            "upgrade_message": "To keep using, upgrade." if account_type == "trial" else None,
            "scrapes_left": 0,
        }

    elif action == "post":
        # For paid/premium accounts, posts_left might be None (unlimited)
        if posts_left is None or (isinstance(posts_left, (int, float)) and posts_left > 0):
            return {"allowed": True, "posts_left": posts_left}

        return {
            "allowed": False,
            "error": "post_limit_reached",
            "message": f"You've used all your posts.",
            "upgrade_required": account_type == "trial",
            "upgrade_message": "To keep using, upgrade." if account_type == "trial" else None,
            "posts_left": 0,
        }

    elif action == "generate_reply":
        if not limits["can_generate_replies"]:
            if account_type == "paid":
                return {
                    "allowed": False,
                    "error": "premium_feature",
                    "message": "This is a premium feature, contact divya_venn.",
                    "premium_required": True,
                }
            else:
                return {
                    "allowed": False,
                    "error": "premium_feature",
                    "message": "This is a premium feature, contact divya_venn.",
                    "upgrade_required": True,
                }
        return {"allowed": True}

    elif action == "add_account":
        current_accounts = len(user_info.get("relevant_accounts", {}))
        max_allowed = limits["max_accounts"]

        # Premium accounts have unlimited accounts (max_allowed is None)
        if max_allowed is None:
            return {"allowed": True}

        if current_accounts >= max_allowed:
            return {
                "allowed": False,
                "error": "account_limit_reached",
                "message": f"You've added {current_accounts}/{max_allowed} accounts.",
                "upgrade_required": account_type in ["trial", "paid"],
            }
        return {"allowed": True}

    elif action == "add_query":
        current_queries = len(user_info.get("queries", []))
        max_allowed = limits["max_queries"]

        # Premium accounts have unlimited queries (max_allowed is None)
        if max_allowed is None:
            return {"allowed": True}

        if current_queries >= max_allowed:
            return {
                "allowed": False,
                "error": "query_limit_reached",
                "message": f"You've added {current_queries}/{max_allowed} queries.",
                "upgrade_required": account_type in ["trial", "paid"],
            }
        return {"allowed": True}

    return {"allowed": True}


def increment_usage(handle: str, action: str) -> dict[str, Any]:
    """
    Decrement remaining usage for a specific action.

    Args:
        handle: Twitter handle
        action: One of "scrape", "post"

    Returns:
        Updated remaining usage dict
    """
    user_info = read_user_info(handle)
    if not user_info:
        return {"error": "user_not_found"}

    if action == "scrape":
        current = user_info.get("scrapes_left")
        # Only decrement if it's a finite number (not None for unlimited)
        if current is not None and isinstance(current, (int, float)):
            user_info["scrapes_left"] = max(0, current - 1)
    elif action == "post":
        current = user_info.get("posts_left")
        # Only decrement if it's a finite number (not None for unlimited)
        if current is not None and isinstance(current, (int, float)):
            user_info["posts_left"] = max(0, current - 1)

    write_user_info(user_info)

    return {
        "scrapes_left": user_info.get("scrapes_left"),
        "posts_left": user_info.get("posts_left"),
    }


def reset_usage(handle: str) -> dict[str, Any]:
    """Reset remaining usage to initial limits (for testing or manual reset)."""
    user_info = read_user_info(handle)
    if not user_info:
        return {"error": "user_not_found"}

    account_type = user_info.get("account_type", "trial")
    limits = AccountLimits.get_limits(account_type)

    # Set remaining usage based on account type
    user_info["scrapes_left"] = limits["initial_scrapes"]
    user_info["posts_left"] = limits["initial_posts"]

    write_user_info(user_info)

    return {
        "scrapes_left": user_info["scrapes_left"],
        "posts_left": user_info["posts_left"],
    }


def update_account_type(handle: str, account_type: AccountType, model: str | None = None) -> dict[str, Any]:
    """
    Update user's account type and reset usage limits.

    Args:
        handle: Twitter handle
        account_type: New account type
        model: Required for premium accounts

    Returns:
        Updated account info
    """
    user_info = read_user_info(handle)
    if not user_info:
        return {"error": "user_not_found"}

    # Premium accounts require a model
    if account_type == "premium":
        if not model:
            return {
                "error": "premium_requires_model",
                "message": "Premium accounts must have a model configured.",
            }
        user_info["model"] = model

    user_info["account_type"] = account_type

    # Reset usage limits based on new account type
    limits = AccountLimits.get_limits(account_type)
    user_info["scrapes_left"] = limits["initial_scrapes"]
    user_info["posts_left"] = limits["initial_posts"]

    write_user_info(user_info)

    return get_account_info(handle)
