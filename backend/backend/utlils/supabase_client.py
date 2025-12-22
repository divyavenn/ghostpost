"""
Supabase client singleton and helper functions.
"""
from functools import lru_cache
from typing import Any

from supabase import Client, create_client

# Import from config (which loads .env file)
from backend.config import SUPABASE_URL, SUPABASE_API_KEY


@lru_cache(maxsize=1)
def get_supabase_client() -> Client:
    """
    Get singleton Supabase client instance.
    Cached to avoid creating multiple connections.
    """
    if not SUPABASE_URL or not SUPABASE_API_KEY:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_API_KEY must be set in environment variables"
        )
    return create_client(SUPABASE_URL, SUPABASE_API_KEY)


def get_db() -> Client:
    """Alias for get_supabase_client for convenience."""
    return get_supabase_client()


# =============================================================================
# USER FUNCTIONS (account-level)
# =============================================================================

def get_user_by_id(user_id: str) -> dict[str, Any] | None:
    """Get a user by their ID (UUID from auth.users)."""
    db = get_db()
    result = db.table("users").select("*").eq("uid", user_id).execute()
    if result.data and len(result.data) > 0:
        return result.data[0]
    return None


def get_all_users() -> list[dict[str, Any]]:
    """Get all users."""
    db = get_db()
    result = db.table("users").select("*").execute()
    return result.data or []


def create_user(user_id: str, user_data: dict[str, Any] | None = None) -> dict[str, Any]:
    """Create a new user account with the given auth.users ID."""
    db = get_db()
    data = {"uid": user_id}
    if user_data:
        data.update(user_data)
    result = db.table("users").insert(data).execute()
    if result.data and len(result.data) > 0:
        return result.data[0]
    raise RuntimeError("Failed to create user")


def update_user(user_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
    """Update a user by ID."""
    db = get_db()
    result = db.table("users").update(updates).eq("uid", user_id).execute()
    if result.data and len(result.data) > 0:
        return result.data[0]
    return None


def delete_user(user_id: str) -> bool:
    """Delete a user and all related data (cascade)."""
    db = get_db()
    result = db.table("users").delete().eq("uid", user_id).execute()
    return len(result.data) > 0 if result.data else False


# =============================================================================
# TWITTER PROFILE FUNCTIONS (per-Twitter-account)
# =============================================================================

def get_twitter_profile(handle: str) -> dict[str, Any] | None:
    """Get a Twitter profile by handle."""
    db = get_db()
    result = db.table("twitter_profiles").select("*").eq("handle", handle).execute()
    if result.data and len(result.data) > 0:
        return result.data[0]
    return None


def get_twitter_profiles_for_user(user_id: str) -> list[dict[str, Any]]:
    """Get all Twitter profiles for a user."""
    db = get_db()
    result = db.table("twitter_profiles").select("*").eq("user_id", user_id).execute()
    return result.data or []


def get_all_twitter_profiles() -> list[dict[str, Any]]:
    """Get all Twitter profiles."""
    db = get_db()
    result = db.table("twitter_profiles").select("*").execute()
    return result.data or []


def create_twitter_profile(profile_data: dict[str, Any]) -> dict[str, Any]:
    """Create a new Twitter profile."""
    db = get_db()
    result = db.table("twitter_profiles").insert(profile_data).execute()
    if result.data and len(result.data) > 0:
        return result.data[0]
    raise RuntimeError("Failed to create Twitter profile")


def update_twitter_profile(handle: str, updates: dict[str, Any]) -> dict[str, Any] | None:
    """Update a Twitter profile by handle."""
    db = get_db()
    result = db.table("twitter_profiles").update(updates).eq("handle", handle).execute()
    if result.data and len(result.data) > 0:
        return result.data[0]
    return None


def delete_twitter_profile(handle: str) -> bool:
    """Delete a Twitter profile and all related data (cascade)."""
    db = get_db()
    result = db.table("twitter_profiles").delete().eq("handle", handle).execute()
    return len(result.data) > 0 if result.data else False


def get_user_for_profile(handle: str) -> dict[str, Any] | None:
    """Get the user account that owns a Twitter profile."""
    profile = get_twitter_profile(handle)
    if profile:
        return get_user_by_id(profile["user_id"])
    return None


# =============================================================================
# RELEVANT ACCOUNTS FUNCTIONS (per Twitter profile)
# =============================================================================

def get_relevant_accounts(handle: str) -> dict[str, bool]:
    """Get relevant accounts for a Twitter profile as a dict."""
    db = get_db()
    result = db.table("twitter_relevant_accounts").select("account_handle, enabled").eq("handle", handle).execute()
    return {row["account_handle"]: row["enabled"] for row in (result.data or [])}


def set_relevant_accounts(handle: str, accounts: dict[str, bool]) -> None:
    """Set relevant accounts for a Twitter profile (replaces existing)."""
    db = get_db()
    # Delete existing
    db.table("twitter_relevant_accounts").delete().eq("handle", handle).execute()
    # Insert new
    if accounts:
        rows = [
            {"handle": handle, "account_handle": acct_handle, "enabled": enabled}
            for acct_handle, enabled in accounts.items()
        ]
        db.table("twitter_relevant_accounts").insert(rows).execute()


def add_relevant_account(handle: str, account_handle: str, enabled: bool = True) -> None:
    """Add or update a single relevant account."""
    db = get_db()
    db.table("twitter_relevant_accounts").upsert(
        {"handle": handle, "account_handle": account_handle, "enabled": enabled},
        on_conflict="handle,account_handle"
    ).execute()


def remove_relevant_account(handle: str, account_handle: str) -> bool:
    """Remove a relevant account."""
    db = get_db()
    result = db.table("twitter_relevant_accounts").delete().eq("handle", handle).eq("account_handle", account_handle).execute()
    return len(result.data) > 0 if result.data else False


# =============================================================================
# QUERIES FUNCTIONS (per Twitter profile)
# =============================================================================

def get_queries(handle: str) -> list[list[str]]:
    """Get queries for a Twitter profile as list of [query, summary] pairs."""
    db = get_db()
    result = db.table("twitter_queries").select("query, summary").eq("handle", handle).execute()
    return [[row["query"], row["summary"] or ""] for row in (result.data or [])]


def set_queries(handle: str, queries: list[str | list[str]]) -> None:
    """Set queries for a Twitter profile (replaces existing)."""
    db = get_db()
    # Delete existing
    db.table("twitter_queries").delete().eq("handle", handle).execute()
    # Insert new
    if queries:
        rows = []
        for q in queries:
            if isinstance(q, list) and len(q) >= 2:
                rows.append({"handle": handle, "query": q[0], "summary": q[1]})
            elif isinstance(q, list) and len(q) == 1:
                rows.append({"handle": handle, "query": q[0], "summary": None})
            else:
                rows.append({"handle": handle, "query": str(q), "summary": None})
        db.table("twitter_queries").insert(rows).execute()


def add_query(handle: str, query: str, summary: str | None = None) -> None:
    """Add a single query (no-op if already exists)."""
    db = get_db()
    db.table("twitter_queries").upsert(
        {"handle": handle, "query": query, "summary": summary},
        on_conflict="handle,query"
    ).execute()


def remove_query(handle: str, query: str) -> bool:
    """Remove a query."""
    db = get_db()
    result = db.table("twitter_queries").delete().eq("handle", handle).eq("query", query).execute()
    return len(result.data) > 0 if result.data else False


# =============================================================================
# SEEN TWEETS FUNCTIONS (per Twitter profile)
# =============================================================================

def get_seen_tweets(handle: str) -> dict[str, str]:
    """Get seen tweets for a Twitter profile as dict of tweet_id -> timestamp."""
    db = get_db()
    result = db.table("twitter_seen_tweets").select("tweet_id, seen_at").eq("handle", handle).execute()
    return {row["tweet_id"]: row["seen_at"] for row in (result.data or [])}


def add_seen_tweets(handle: str, tweet_ids: list[str]) -> None:
    """Add tweet IDs to seen tweets."""
    if not tweet_ids:
        return
    db = get_db()
    rows = [{"handle": handle, "tweet_id": tid} for tid in tweet_ids]
    # Use upsert to avoid duplicates
    db.table("twitter_seen_tweets").upsert(rows, on_conflict="handle,tweet_id").execute()


def remove_seen_tweets(handle: str, tweet_ids: list[str]) -> int:
    """Remove tweet IDs from seen tweets. Returns count removed."""
    if not tweet_ids:
        return 0
    db = get_db()
    result = db.table("twitter_seen_tweets").delete().eq("handle", handle).in_("tweet_id", tweet_ids).execute()
    return len(result.data) if result.data else 0


def cleanup_old_seen_tweets(handle: str, hours: int = 48) -> int:
    """Remove seen tweets older than specified hours."""
    from datetime import datetime, timedelta
    try:
        from datetime import UTC
    except ImportError:
        from datetime import timezone
        UTC = timezone.utc

    cutoff = (datetime.now(UTC) - timedelta(hours=hours)).isoformat()
    db = get_db()
    result = db.table("twitter_seen_tweets").delete().eq("handle", handle).lt("seen_at", cutoff).execute()
    return len(result.data) if result.data else 0


def is_tweet_seen(handle: str, tweet_id: str) -> bool:
    """Check if a tweet has been seen."""
    db = get_db()
    result = db.table("twitter_seen_tweets").select("tweet_id").eq("handle", handle).eq("tweet_id", tweet_id).execute()
    return len(result.data) > 0 if result.data else False


# =============================================================================
# TOKEN FUNCTIONS (per Twitter profile)
# =============================================================================

def get_token(handle: str) -> dict[str, Any] | None:
    """Get token data for a Twitter profile."""
    db = get_db()
    result = db.table("twitter_tokens").select("*").eq("handle", handle).execute()
    if result.data and len(result.data) > 0:
        return result.data[0]
    return None


def store_token(handle: str, refresh_token: str, access_token: str | None = None, expires_at: float | None = None) -> None:
    """Store or update token for a Twitter profile."""
    db = get_db()
    data = {
        "handle": handle,
        "refresh_token": refresh_token,
        "access_token": access_token,
        "expires_at": expires_at
    }
    db.table("twitter_tokens").upsert(data, on_conflict="handle").execute()


def invalidate_token(handle: str) -> None:
    """Invalidate a Twitter profile's token."""
    db = get_db()
    db.table("twitter_tokens").update({
        "refresh_token": None,
        "access_token": None,
        "expires_at": 0
    }).eq("handle", handle).execute()


def delete_token(handle: str) -> bool:
    """Delete a Twitter profile's token."""
    db = get_db()
    result = db.table("twitter_tokens").delete().eq("handle", handle).execute()
    return len(result.data) > 0 if result.data else False


# =============================================================================
# POSTED TWEETS FUNCTIONS (per Twitter profile)
# =============================================================================

def get_posted_tweets(handle: str, limit: int | None = None, offset: int = 0) -> list[dict[str, Any]]:
    """Get posted tweets for a Twitter profile, sorted by created_at desc."""
    db = get_db()
    query = db.table("twitter_posted_tweets").select("*").eq("handle", handle).order("created_at", desc=True)
    if offset > 0:
        query = query.range(offset, offset + (limit or 1000) - 1)
    elif limit:
        query = query.limit(limit)
    result = query.execute()
    return result.data or []


def get_posted_tweet(handle: str, tweet_id: str) -> dict[str, Any] | None:
    """Get a single posted tweet by ID."""
    db = get_db()
    result = db.table("twitter_posted_tweets").select("*").eq("handle", handle).eq("tweet_id", tweet_id).execute()
    if result.data and len(result.data) > 0:
        return result.data[0]
    return None


def add_posted_tweet(tweet_data: dict[str, Any]) -> dict[str, Any]:
    """Add a new posted tweet."""
    db = get_db()
    result = db.table("twitter_posted_tweets").insert(tweet_data).execute()
    if result.data and len(result.data) > 0:
        return result.data[0]
    raise RuntimeError("Failed to add posted tweet")


def update_posted_tweet(tweet_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
    """Update a posted tweet."""
    db = get_db()
    result = db.table("twitter_posted_tweets").update(updates).eq("tweet_id", tweet_id).execute()
    if result.data and len(result.data) > 0:
        return result.data[0]
    return None


def delete_posted_tweet(tweet_id: str) -> bool:
    """Delete a posted tweet."""
    db = get_db()
    result = db.table("twitter_posted_tweets").delete().eq("tweet_id", tweet_id).execute()
    return len(result.data) > 0 if result.data else False


def get_posted_tweets_by_state(handle: str, states: list[str]) -> list[dict[str, Any]]:
    """Get posted tweets filtered by monitoring state."""
    db = get_db()
    result = db.table("twitter_posted_tweets").select("*").eq("handle", handle).in_("monitoring_state", states).order("last_activity_at", desc=True).execute()
    return result.data or []


def get_top_posted_tweets(handle: str, post_type: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
    """Get top posted tweets by score."""
    db = get_db()
    query = db.table("twitter_posted_tweets").select("*").eq("handle", handle)
    if post_type:
        query = query.eq("post_type", post_type)
    result = query.order("score", desc=True).limit(limit).execute()
    return result.data or []


def get_user_posted_tweet_ids(handle: str) -> set[str]:
    """Get set of all posted tweet IDs for a Twitter profile."""
    db = get_db()
    result = db.table("twitter_posted_tweets").select("tweet_id").eq("handle", handle).execute()
    return {row["tweet_id"] for row in (result.data or [])}


# =============================================================================
# COMMENTS FUNCTIONS (per Twitter profile)
# =============================================================================

def get_comments(handle: str, limit: int | None = None, offset: int = 0, status_filter: str | None = None) -> list[dict[str, Any]]:
    """Get comments for a Twitter profile."""
    db = get_db()
    query = db.table("twitter_comments").select("*").eq("handle", handle).order("created_at", desc=True)
    if status_filter:
        query = query.eq("status", status_filter)
    if offset > 0:
        query = query.range(offset, offset + (limit or 1000) - 1)
    elif limit:
        query = query.limit(limit)
    result = query.execute()
    return result.data or []


def get_comment(handle: str, comment_id: str) -> dict[str, Any] | None:
    """Get a single comment by ID."""
    db = get_db()
    result = db.table("twitter_comments").select("*").eq("handle", handle).eq("tweet_id", comment_id).execute()
    if result.data and len(result.data) > 0:
        return result.data[0]
    return None


def add_comment(comment_data: dict[str, Any]) -> dict[str, Any]:
    """Add a new comment."""
    db = get_db()
    result = db.table("twitter_comments").insert(comment_data).execute()
    if result.data and len(result.data) > 0:
        return result.data[0]
    raise RuntimeError("Failed to add comment")


def update_comment(comment_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
    """Update a comment."""
    db = get_db()
    result = db.table("twitter_comments").update(updates).eq("tweet_id", comment_id).execute()
    if result.data and len(result.data) > 0:
        return result.data[0]
    return None


def delete_comment(comment_id: str) -> bool:
    """Delete a comment."""
    db = get_db()
    result = db.table("twitter_comments").delete().eq("tweet_id", comment_id).execute()
    return len(result.data) > 0 if result.data else False


def get_pending_comments_count(handle: str) -> int:
    """Get count of pending comments."""
    db = get_db()
    result = db.table("twitter_comments").select("tweet_id", count="exact").eq("handle", handle).eq("status", "pending").execute()
    return result.count or 0


# =============================================================================
# ACTIVITY LOGS FUNCTIONS (per Twitter profile)
# =============================================================================

def log_activity(handle: str, action: str, tweet_id: str | None = None, metadata: dict[str, Any] | None = None) -> None:
    """Log an activity."""
    db = get_db()
    db.table("twitter_activity_log").insert({
        "handle": handle,
        "action": action,
        "tweet_id": tweet_id,
        "metadata": metadata or {}
    }).execute()


def get_activity_logs(handle: str, limit: int = 100, action_filter: str | None = None) -> list[dict[str, Any]]:
    """Get activity logs for a Twitter profile."""
    db = get_db()
    query = db.table("twitter_activity_log").select("*").eq("handle", handle).order("timestamp", desc=True)
    if action_filter:
        query = query.eq("action", action_filter)
    result = query.limit(limit).execute()
    return result.data or []


# =============================================================================
# ERROR LOGS FUNCTIONS (linked to users, not twitter profiles)
# =============================================================================

def log_error(message: str, status_code: int = 500, function_name: str | None = None, handle: str | None = None, exception: str | None = None, user_id: str | None = None) -> None:
    """Log an error. If handle is provided, looks up the user_id for that profile. user_id can also be passed directly."""
    db = get_db()
    # Use provided user_id, or look up from handle
    if not user_id and handle:
        profile = get_twitter_profile(handle)
        if profile:
            user_id = profile.get("user_id")
    db.table("error_logs").insert({
        "message": message,
        "status_code": status_code,
        "function_name": function_name,
        "user_id": user_id,
        "exception": exception
    }).execute()


def get_error_logs(limit: int = 100, user_id: str | None = None) -> list[dict[str, Any]]:
    """Get error logs."""
    db = get_db()
    query = db.table("error_logs").select("*").order("timestamp", desc=True)
    if user_id:
        query = query.eq("user_id", user_id)
    result = query.limit(limit).execute()
    return result.data or []


# =============================================================================
# BACKGROUND TASKS LOG FUNCTIONS (per Twitter profile)
# =============================================================================

def log_background_task(handle: str, task_type: str, **details) -> None:
    """Log a background task execution. All task-specific info goes in details."""
    db = get_db()
    db.table("twitter_background_tasks_log").insert({
        "handle": handle,
        "task_type": task_type,
        "details": details
    }).execute()


# =============================================================================
# BROWSER STATE FUNCTIONS (per user, with site field)
# =============================================================================

def get_browser_state(handle: str, site: str = "twitter") -> dict[str, Any] | None:
    """Get browser state for a user (looks up user_id from handle)."""
    db = get_db()
    profile = get_twitter_profile(handle)
    if not profile:
        return None
    user_id = profile.get("user_id")
    result = db.table("browser_states").select("state, timestamp").eq("user_id", user_id).eq("site", site).execute()
    if result.data and len(result.data) > 0:
        return result.data[0]["state"]
    return None


def store_browser_state(handle: str, state: dict[str, Any], site: str = "twitter") -> None:
    """Store browser state for a user (looks up user_id from handle)."""
    from datetime import datetime
    try:
        from datetime import UTC
    except ImportError:
        from datetime import timezone
        UTC = timezone.utc

    db = get_db()
    profile = get_twitter_profile(handle)
    if not profile:
        return
    user_id = profile.get("user_id")
    state["timestamp"] = datetime.now(UTC).isoformat()
    db.table("browser_states").upsert({
        "user_id": user_id,
        "site": site,
        "state": state
    }, on_conflict="user_id,site").execute()


def delete_browser_state(handle: str, site: str = "twitter") -> bool:
    """Delete browser state for a user (looks up user_id from handle)."""
    db = get_db()
    profile = get_twitter_profile(handle)
    if not profile:
        return False
    user_id = profile.get("user_id")
    result = db.table("browser_states").delete().eq("user_id", user_id).eq("site", site).execute()
    return len(result.data) > 0 if result.data else False


def get_browser_state_by_user_id(user_id: str, site: str = "twitter") -> dict[str, Any] | None:
    """Get browser state for a user by user_id directly."""
    db = get_db()
    result = db.table("browser_states").select("state, timestamp").eq("user_id", user_id).eq("site", site).execute()
    if result.data and len(result.data) > 0:
        return result.data[0]["state"]
    return None


def store_browser_state_by_user_id(user_id: str, state: dict[str, Any], site: str = "twitter") -> None:
    """Store browser state for a user by user_id directly."""
    from datetime import datetime
    try:
        from datetime import UTC
    except ImportError:
        from datetime import timezone
        UTC = timezone.utc

    db = get_db()
    state["timestamp"] = datetime.now(UTC).isoformat()
    db.table("browser_states").upsert({
        "user_id": user_id,
        "site": site,
        "state": state
    }, on_conflict="user_id,site").execute()


def delete_browser_state_by_user_id(user_id: str, site: str = "twitter") -> bool:
    """Delete browser state for a user by user_id directly."""
    db = get_db()
    result = db.table("browser_states").delete().eq("user_id", user_id).eq("site", site).execute()
    return len(result.data) > 0 if result.data else False


# =============================================================================
# STORAGE FUNCTIONS (for scraped tweets JSON blobs)
# =============================================================================

def get_storage_client():
    """Get the Supabase storage client."""
    return get_db().storage


def upload_scraped_tweets(user_handle: str, tweets_json: str) -> str:
    """Upload scraped tweets JSON to storage. Returns the path."""
    storage = get_storage_client()
    path = f"{user_handle}/tweets.json"

    # Try to update existing, or create new
    try:
        storage.from_("tweet-cache").update(path, tweets_json.encode(), {"content-type": "application/json", "upsert": "true"})
    except Exception:
        # File might not exist, try upload
        storage.from_("tweet-cache").upload(path, tweets_json.encode(), {"content-type": "application/json"})

    return path


def download_scraped_tweets(user_handle: str) -> str | None:
    """Download scraped tweets JSON from storage. Returns None if not found."""
    storage = get_storage_client()
    path = f"{user_handle}/tweets.json"

    try:
        data = storage.from_("tweet-cache").download(path)
        return data.decode() if data else None
    except Exception:
        return None


def delete_scraped_tweets(user_handle: str) -> bool:
    """Delete scraped tweets from storage."""
    storage = get_storage_client()
    path = f"{user_handle}/tweets.json"

    try:
        storage.from_("tweet-cache").remove([path])
        return True
    except Exception:
        return False
