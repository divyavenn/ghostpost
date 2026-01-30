import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.config import (
    AUTH_COOKIE,
    CACHE_DIR,
    MAX_TWEET_AGE_HOURS,
    TOKEN_FILE,
    USER_INFO_FILE,
    DEFAULT_TWITTER_USERNAME as USERNAME,
)

# Ensure cache directory exists (for any legacy files)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Check DEBUG_LOGS env variable once at module load
DEBUG_LOGS = os.getenv("DEBUG_LOGS", "").lower() in ("true", "1", "yes")


# =============================================================================
# Custom Authentication Exceptions
# =============================================================================

class AuthenticationError(Exception):
    """Base class for authentication errors that should stop background jobs."""
    pass


class BrowserSessionExpired(AuthenticationError):
    """
    Raised when browser session cookies are invalid or missing.
    User needs to re-login via the browser flow.
    """
    pass


class OAuthTokenExpired(AuthenticationError):
    """
    Raised when OAuth refresh token is invalid, missing, or refresh failed.
    User needs to re-authenticate via OAuth flow.
    """
    pass


def notify(msg: str):
    """Print message to console only if DEBUG_LOGS is enabled."""
    # if DEBUG_LOGS:
    print(msg)


def error(msg: str, status_code: int = 500, exception_text: str | None = None, function_name: str | None = None, username: str | None = None, user_id: str | None = None, critical: bool = False, platform: str = "Twitter"):
    """
    Log the error to Supabase using ErrorLog Pydantic model. If critical, raise a RuntimeError as well.

    Args:
        msg: Error message
        status_code: HTTP status code
        exception_text: Exception details
        function_name: Name of the function where error occurred
        username: Twitter handle (profile_handle) for the error context
        user_id: Supabase user UUID (use when twitter profile doesn't exist yet)
        critical: If True, raise RuntimeError and notify devs
        critical: Whether to raise RuntimeError and message devs
        platform: Platform where error occurred (default: "Twitter")
    """
    import inspect
    from backend.twitter.logging import ErrorLog

    try:
        from datetime import UTC
    except ImportError:
        from datetime import timezone
        UTC = timezone.utc

    from backend.utlils.supabase_client import log_error as sb_log_error

    # Auto-detect function name if not provided
    if function_name is None:
        frame = inspect.currentframe()
        if frame and frame.f_back:
            function_name = frame.f_back.f_code.co_name

    # Create ErrorLog Pydantic model
    error_log = ErrorLog(
        message=msg,
        status_code=status_code,
        calling_function=function_name or "unknown",
        timestamp=datetime.now(UTC),
        user_id=username,
        platform=platform,  # type: ignore
        raw_exception=exception_text or "",
    )

    # Append to errors.jsonl (create if doesn't exist)
    errors_log_path = CACHE_DIR / "errors.jsonl"

    try:
        with open(errors_log_path, "a") as f:
            f.write(error_log.model_dump_json() + "\n")
    except Exception as e:
        print(f"⚠️ Failed to write error to local log: {e}")

    try:
        sb_log_error(
            message=msg,
            status_code=status_code,
            function_name=function_name or "unknown",
            handle=username,
            exception=exception_text,
            user_id=user_id
        )
    except Exception as e:
        print(f"⚠️ Failed to log error to Supabase: {e}")

    if critical:
        from backend.utlils.email import message_devs
        timestamp_str = error_log.timestamp.isoformat()
        message_devs(f"❌ Critical error in {function_name} for user {username}: {msg}. timestamp: {timestamp_str}")
        raise RuntimeError(f"❌ {msg}")


def cookie_still_valid(state: dict[str, Any]) -> bool:
    if not isinstance(state, dict):
        return False
    for c in state.get("cookies", []):
        if c.get("name") == AUTH_COOKIE:
            expiry = c.get("expires") or c.get("expirationDate", 0)
            return expiry == 0 or expiry > time.time() + 60
    return False


def _cache_key(username: str | None) -> str:
    """Sanitize username for use as cache key."""
    key = (username or "default").strip()
    key = key or "default"
    sanitized = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in key)
    return sanitized or "default"


def get_user_interactions_log(username: str) -> Path:
    """Legacy function - returns path for compatibility."""
    return CACHE_DIR / f"{_cache_key(username)}_log.json"


def _archive_interactions_log(username: str, key: str) -> Path | None:
    from backend.utlils.date_utils import now_utc

    log_path = get_user_interactions_log(username)
    if not log_path.exists() or not log_path.is_file():
        return None

    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = now_utc().strftime("%Y%m%dT%H%M%SZ")
    archive_path = ARCHIVE_DIR / f"{key}_{timestamp}_{log_path.name}"
    if archive_path.exists():
        archive_path = ARCHIVE_DIR / f"{key}_{time.time_ns()}_{log_path.name}"

    log_path.rename(archive_path)
    return archive_path


def atomic_file_update(path: Path, data: Any, tmp_suffix: str = ".tmp", *, ensure_ascii: bool = False) -> None:
    if data:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(tmp_suffix)
        tmp_path.write_text(json.dumps(data, indent=2, ensure_ascii=ensure_ascii))
        tmp_path.replace(path)
    else:
        path.unlink(missing_ok=True)


def remove_entry_from_map(path: Path, username: str, tmp_suffix: str) -> bool:
    if not path.exists():
        return False

    try:
        data = json.loads(path.read_text())
    except Exception:
        path.unlink(missing_ok=True)
        return False

    if not isinstance(data, dict) or username not in data:
        return False

    data.pop(username, None)
    atomic_file_update(path, data, tmp_suffix)
    return True

# =============================================================================
# BROWSER STATE FUNCTIONS
# =============================================================================

async def store_browser_state(username: str, context, account_type: str = "user") -> None:
    """
    Store browser state for user or bread account.

    Args:
        username: Username/handle to store state for
        context: Playwright browser context
        account_type: Either "user" or "bread" to determine storage location
    """
    from pydantic import ValidationError

    from backend.data.twitter.data_validation import BrowserState
    from backend.utlils.supabase_client import store_browser_state as sb_store_browser_state
    from backend.utlils.date_utils import utc_iso_string

    state = await context.storage_state()
    state["timestamp"] = datetime.utcnow().isoformat() + "Z"

    # Validate browser state
    try:
        validated = BrowserState(**state)
        state = validated.model_dump()
    except ValidationError as e:
        error(f"Invalid browser state data for {username}", status_code=500, exception_text=str(e), function_name="store_browser_state", username=username)

    sb_store_browser_state(username, state)
    notify(f"✅ Browser state saved for {username}")


async def read_browser_state(browser, username: str, validate_session: bool = False, account_type: str = "user") -> tuple[Any, Any] | None:
    """Read and restore browser state for a user or bread account."""
    from pydantic import ValidationError

    from backend.data.twitter.data_validation import BrowserState
    from backend.utlils.supabase_client import (
        delete_browser_state,
        get_browser_state as sb_get_browser_state,
        get_bread_account_state,
        delete_bread_account_state,
    )

    # Use appropriate function based on account type
    if account_type == "bread":
        state = get_bread_account_state(username)
    else:
        state = sb_get_browser_state(username)

    if not state:
        notify(f"⚠️ No saved {account_type} browser state for {username}")
        return None

    # Validate browser state
    try:
        validated = BrowserState(**state)
        state = validated.model_dump()
    except ValidationError as e:
        error(f"Invalid browser state data for {username}", status_code=500, exception_text=str(e), function_name="read_browser_state", username=username)

    # Check for auth_token cookie validity
    if not cookie_still_valid(state):
        if account_type == "bread":
            delete_bread_account_state(username)
        else:
            delete_browser_state(username)
        notify(f"🔐 Relogging for {username} (missing/expired cookie)")
        return None

    # Restore browser context with saved state
    ctx = await browser.new_context(storage_state=state)
    notify(f"✅ Retrieved {account_type} browser state for {username}")

    # Optional: Validate session is still authenticated (only for user accounts)
    if validate_session and account_type == "user":
        page = await ctx.new_page()
        try:
            await page.goto("https://twitter.com/home", timeout=10000)
            await page.wait_for_timeout(2000)

            current_url = page.url
            if "login" in current_url.lower() or "oauth" in current_url.lower():
                notify(f"⚠️ Session expired for {username} (redirected to login)")
                await ctx.close()
                delete_browser_state(username)
                return None

            notify(f"✅ Session validated for {username}")
        except Exception as e:
            notify(f"⚠️ Could not validate session for {username}: {e}")
            await ctx.close()
            return None
        finally:
            await page.close()

    return browser, ctx


# =============================================================================
# USER INFO FUNCTIONS
# =============================================================================

def load_twitter_profile_entries() -> list[dict[str, Any]]:
    """Load all Twitter profiles from Supabase with their user data."""
    from backend.utlils.supabase_client import (
        get_all_twitter_profiles,
        get_queries,
        get_relevant_accounts,
        get_seen_tweets,
        get_user_by_id,
    )

    profiles = get_all_twitter_profiles()

    # Reconstruct full profile objects with denormalized data and user info
    entries = []
    for profile in profiles:
        # Add denormalized data
        profile["relevant_accounts"] = get_relevant_accounts(profile["handle"])
        profile["queries"] = get_queries(profile["handle"])
        profile["seen_tweets"] = get_seen_tweets(profile["handle"])

        # Add user-level data
        user = get_user_by_id(profile["user_id"])
        if user:
            profile["email"] = user.get("email")
            profile["account_type"] = user.get("account_type", "trial")
            profile["models"] = user.get("models", [])
            profile["knowledge_base"] = user.get("knowledge_base")
            profile["intent"] = user.get("intent", "")

        entries.append(profile)

    return entries


# Alias for backwards compatibility
load_user_info_entries = load_twitter_profile_entries


def write_twitter_profile(profile_info: dict[str, Any], user_id: str | None = None) -> None:
    """
    Persist Twitter profile metadata to Supabase.

    If the profile doesn't exist, a user_id (UUID from auth.users) must be provided.
    """
    from backend.utlils.supabase_client import (
        create_twitter_profile,
        get_twitter_profile,
        get_user_by_id,
        set_queries,
        set_relevant_accounts,
        update_twitter_profile,
        update_user,
    )

    handle = profile_info.get("handle") or profile_info.get("username")
    if not handle:
        raise ValueError("handle is required for Twitter profile")

    existing_profile = get_twitter_profile(handle)

    # Extract normalized fields (per-profile)
    relevant_accounts = profile_info.pop("relevant_accounts", None)
    queries = profile_info.pop("queries", None)
    profile_info.pop("seen_tweets", None)  # Handled separately via add_to_seen_tweets

    # Extract user-level fields (these go to users table, not twitter_profiles)
    profile_info.pop("email", None)  # Email is in auth.users, not our users table
    user_account_type = profile_info.pop("account_type", None)
    user_models = profile_info.pop("models", None)
    user_knowledge_base = profile_info.pop("knowledge_base", None)
    user_intent = profile_info.pop("intent", None)

    if existing_profile:
        # Update existing profile
        profile_data = {k: v for k, v in profile_info.items() if v is not None and k != "user_id"}
        if profile_data:
            update_twitter_profile(handle, profile_data)

        # Update user-level data if provided
        profile_user_id = existing_profile.get("user_id")
        if profile_user_id:
            user = get_user_by_id(profile_user_id)
            if user:
                user_updates = {}
                if user_account_type is not None:
                    user_updates["account_type"] = user_account_type
                if user_models is not None:
                    user_updates["models"] = user_models
                if user_knowledge_base is not None:
                    user_updates["knowledge_base"] = user_knowledge_base
                if user_intent is not None:
                    user_updates["intent"] = user_intent
                if user_updates:
                    update_user(profile_user_id, user_updates)
    else:
        # Need to create new profile - must have a user_id (UUID from Supabase auth)
        if not user_id:
            # For backwards compatibility during Twitter OAuth without Supabase session,
            # just log a warning and skip profile creation - it will be created later
            # when the user connects their Twitter after Supabase login
            notify(f"⚠️ Cannot create Twitter profile @{handle} without user_id - skipping")
            return

        user = get_user_by_id(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found - must sign up via Supabase first")

        # Create the Twitter profile
        profile_data = {k: v for k, v in profile_info.items() if v is not None}
        profile_data["handle"] = handle
        profile_data["user_id"] = user_id
        profile_data.setdefault("username", handle)
        profile_data.setdefault("scrapes_left", 3)
        profile_data.setdefault("posts_left", 3)

        create_twitter_profile(profile_data)
        notify(f"🆔 Created new Twitter profile @{handle}")

    # Update normalized tables (per-profile)
    if relevant_accounts is not None:
        set_relevant_accounts(handle, relevant_accounts)
    if queries is not None:
        set_queries(handle, queries)

    notify("💾 Updated Twitter profile info")


# Alias for backwards compatibility
def write_user_info(user_info: dict[str, Any]) -> None:
    """Persist user metadata to Supabase (backwards compatible wrapper)."""
    write_twitter_profile(user_info)


def read_twitter_profile(handle: str) -> dict[str, Any] | None:
    """Return Twitter profile metadata for the provided handle."""
    if not handle:
        return None

    from backend.utlils.supabase_client import (
        get_queries,
        get_relevant_accounts,
        get_seen_tweets,
        get_twitter_profile,
        get_user_by_id,
    )

    profile = get_twitter_profile(handle)
    if profile:
        # Add denormalized data
        profile["relevant_accounts"] = get_relevant_accounts(handle)
        profile["queries"] = get_queries(handle)
        profile["seen_tweets"] = get_seen_tweets(handle)

        # Add user-level data
        user = get_user_by_id(profile["user_id"])
        if user:
            profile["email"] = user.get("email")
            profile["account_type"] = user.get("account_type", "trial")
            profile["models"] = user.get("models", [])
            profile["knowledge_base"] = user.get("knowledge_base")
            profile["intent"] = user.get("intent", "")

        return profile

    return None


# Alias for backwards compatibility
def read_user_info(handle: str) -> dict[str, Any] | None:
    """Return cached user metadata for the provided handle (backwards compatible wrapper)."""
    return read_twitter_profile(handle)


# =============================================================================
# TOKEN FUNCTIONS
# =============================================================================

def read_user_token(username: str) -> str | None:
    """Return the refresh token for the given user."""
    from backend.utlils.supabase_client import get_token

    token_data = get_token(username)
    if token_data:
        return token_data.get("refresh_token")
    return None


def read_user_access_token(username: str) -> tuple[str | None, float | None]:
    """Return the cached access token and expiration timestamp for the user."""
    from backend.utlils.supabase_client import get_token

    token_data = get_token(username)
    if token_data:
        return token_data.get("access_token"), token_data.get("expires_at")
    return None, None


def store_token(username: str, refresh_token: str, access_token: str | None = None, expires_in: int | None = None):
    """Persist the refresh token and optionally access token with expiration."""
    from backend.utlils.supabase_client import store_token as sb_store_token

    # Calculate expiration timestamp (with buffer from config)
    expires_at = None
    if access_token and expires_in:
        expires_at = time.time() + expires_in - 60

    sb_store_token(username, refresh_token, access_token, expires_at)
    notify(f"💾 Stored OAuth tokens for {username}")


def invalidate_user_token(username: str):
    """Invalidate a user's OAuth token."""
    from backend.utlils.supabase_client import invalidate_token

    invalidate_token(username)
    notify(f"🔒 Invalidated OAuth token for {username} - re-authentication required")


# =============================================================================
# BACKGROUND TASK LOGGING
# =============================================================================

def log_background_task(username: str, task_type: str, **details):
    """Log background task execution to Supabase. All task-specific info goes in details."""
    from backend.utlils.supabase_client import log_background_task as sb_log_task

    sb_log_task(username, task_type, **details)
    notify(f"📝 Logged background task: {task_type} for @{username}")


# =============================================================================
# SEEN TWEETS FUNCTIONS
# =============================================================================

def add_to_seen_tweets(username: str, tweet_ids: list[str]) -> None:
    """Add tweet IDs to the seen_tweets tracking."""
    if not tweet_ids:
        return

    from backend.utlils.supabase_client import add_seen_tweets

    add_seen_tweets(username, tweet_ids)
    notify(f"👁️ Added {len(tweet_ids)} tweet(s) to seen_tweets for {username}")


def remove_from_seen_tweets(username: str, tweet_ids: list[str]) -> int:
    """Remove tweet IDs from seen_tweets."""
    if not tweet_ids:
        return 0

    from backend.utlils.supabase_client import remove_seen_tweets

    count = remove_seen_tweets(username, tweet_ids)
    if count > 0:
        notify(f"🗑️ Removed {count} tweet(s) from seen_tweets for {username}")
    return count


def cleanup_seen_tweets(username: str, hours: int = MAX_TWEET_AGE_HOURS) -> int:
    """Remove tweet IDs older than specified hours from seen_tweets."""
    from backend.utlils.supabase_client import cleanup_old_seen_tweets

    count = cleanup_old_seen_tweets(username, hours)
    if count > 0:
        notify(f"🧹 Cleaned {count} old tweet ID(s) from seen_tweets for {username}")
    return count


def is_tweet_seen(username: str, tweet_id: str) -> bool:
    """Check if a tweet ID exists in the seen_tweets map."""
    from backend.utlils.supabase_client import is_tweet_seen as sb_is_tweet_seen

    return sb_is_tweet_seen(username, tweet_id)


if __name__ == "__main__":
    from backend.utlils.email import message_devs
    message_devs("This is a test message to developers.")
