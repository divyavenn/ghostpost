import json
import time
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.config import (
    ARCHIVE_DIR,
    AUTH_COOKIE,
    BROWSER_STATE_FILE,
    CACHE_DIR,
    MAX_TWEET_AGE_HOURS,
    TOKEN_FILE,
    USER_INFO_FILE,
)
from backend.config import (
    DEFAULT_TWITTER_USERNAME as USERNAME,
)

# Ensure cache directory exists
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def notify(msg: str):
    print(msg)


def error(msg: str, status_code: int = 500, exception_text: str | None = None, function_name: str | None = None, username: str | None = None, critical: bool = False):
    """
    Log the error to errors.jsonl. If critical, raise a RunTimeError as well (user gets notified/process gets interrupted).

    Args:
        msg: Error message
        status_code: HTTP status code (default: 500)
        exception_text: The original exception message if called from try-except
        function_name: Name of the function where the error originated
        username: Current user handle
    """
    import inspect

    # Auto-detect function name if not provided
    if function_name is None:
        frame = inspect.currentframe()
        if frame and frame.f_back:
            function_name = frame.f_back.f_code.co_name

    timestamp = datetime.utcnow().isoformat() + "Z"
    # Create error log entry
    error_entry = {"message": msg, "status_code": status_code, "function_name": function_name or "unknown", "timestamp": timestamp, "user": username or "unknown", "exception": exception_text}

    # Append to errors.jsonl (create if doesn't exist)
    errors_log_path = CACHE_DIR / "errors.jsonl"

    try:
        with open(errors_log_path, "a") as f:
            f.write(json.dumps(error_entry) + "\n")
    except Exception as e:
        # Don't let logging failures prevent error from being raised
        print(f"⚠️ Failed to log error to errors.jsonl: {e}")

    if critical:
        message_devs(f"❌ Critical error in {function_name} for user {username}: {msg}. timestamp: {timestamp}")
        raise RuntimeError(f"❌ {msg}")


def message_devs(text: str):
    """
    Send an urgent email notification to developers.

    Args:
        text: The message content to send
    """
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    from backend.config import DEV_EMAIL, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_USER

    # Check if email is configured
    if not SMTP_USER or not SMTP_PASSWORD:
        notify("⚠️ Email not configured (missing SMTP_USER or SMTP_PASSWORD)")
        return
    if not DEV_EMAIL:
        notify("⚠️ Developer email not configured (missing DEV_EMAIL)")
        return
    try:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = SMTP_USER
        msg['To'] = DEV_EMAIL
        msg['Subject'] = "URGENT: Ghostpost Issue"

        # Add body
        msg.attach(MIMEText(text, 'plain'))

        # Connect to SMTP server and send
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()  # Enable TLS encryption
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)

        notify(f"📧 Alert sent to developers: {DEV_EMAIL}")
    except Exception as e:
        notify(f"⚠️ Failed to send developer alert: {e}")


def cookie_still_valid(state: dict[str, Any]) -> bool:
    if not isinstance(state, dict):
        return False
    for c in state.get("cookies", []):
        if c.get("name") == AUTH_COOKIE:
            # Check both 'expires' and 'expirationDate' fields (different cookie formats)
            expiry = c.get("expires") or c.get("expirationDate", 0)
            return expiry == 0 or expiry > time.time() + 60
    return False


def _cache_key(username: str | None) -> str:
    key = (username or "default").strip()
    key = key or "default"
    sanitized = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in key)
    return sanitized or "default"


def get_user_interactions_log(username: str | None = None) -> Path:
    if username is None:
        username = USERNAME
    return CACHE_DIR / f"{_cache_key(username)}_log.json"


def _archive_interactions_log(username: str, key: str) -> Path | None:
    log_path = get_user_interactions_log(username)
    if not log_path.exists() or not log_path.is_file():
        return None

    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
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


async def store_browser_state(username: str, context) -> None:
    from pydantic import ValidationError

    from backend.data.twitter.data_validation import BrowserState

    state = await context.storage_state()
    path = BROWSER_STATE_FILE
    cache: dict[str, Any] = {}
    if path.exists():
        try:
            cached = json.loads(path.read_text())
            if isinstance(cached, dict):
                cache = cached
        except Exception as e:
            error("Failed to read existing browser state file", status_code=500, exception_text=str(e), function_name="store_browser_state")

    # Add timestamp to track when the state was last updated
    state["timestamp"] = datetime.utcnow().isoformat() + "Z"

    # Validate browser state before storing
    try:
        validated = BrowserState(**state)
        cache[username] = validated.model_dump()
    except ValidationError as e:
        error(f"Invalid browser state data for {username}", status_code=500, exception_text=str(e), function_name="store_browser_state", username=username)
        # Store anyway but log the validation error
        cache[username] = state

    atomic_file_update(path, cache)
    notify(f"✅ Browser state saved for {username}")


async def read_browser_state(browser, username: str, validate_session: bool = False) -> tuple[Any, Any] | None:
    """
    Read and restore browser state for a user.

    Args:
        browser: Playwright browser instance
        username: Twitter username/handle
        validate_session: If True, verify session is still valid by checking Twitter

    Returns:
        Tuple of (browser, context) if session exists and is valid, None otherwise
    """
    from pydantic import ValidationError

    from backend.data.twitter.data_validation import BrowserState

    path = BROWSER_STATE_FILE
    if not path.exists():
        return None

    try:
        cache = json.loads(path.read_text())
    except Exception as e:
        path.unlink(missing_ok=True)
        error("Could not parse browser state cache", status_code=500, exception_text=str(e), function_name="read_browser_state")
        notify("⚠️ Could not parse browser state cache; starting fresh")
        return None

    if not isinstance(cache, dict):
        path.unlink(missing_ok=True)
        error("Invalid browser state cache format: expected dict", status_code=500, function_name="read_browser_state")
        notify("⚠️ Invalid browser state cache format; starting fresh")
        return None

    state = cache.get(username)
    if not state:
        notify(f"⚠️ No saved browser state for {username}")
        return None

    # Validate browser state
    try:
        validated = BrowserState(**state)
        state = validated.model_dump()
    except ValidationError as e:
        error(f"Invalid browser state data for {username}", status_code=500, exception_text=str(e), function_name="read_browser_state", username=username)
        # Continue with invalid state but log the error

    # Check for auth_token cookie validity
    if not cookie_still_valid(state):
        cache.pop(username, None)
        atomic_file_update(path, cache)
        notify(f"🔐 Relogging for {username} (missing/expired cookie)")
        return None

    # Restore browser context with saved state
    ctx = await browser.new_context(storage_state=state)
    notify(f"✅ Retrieved browser state for {username}")

    # Optional: Validate session is still authenticated
    if validate_session:
        page = await ctx.new_page()
        try:
            await page.goto("https://twitter.com/home", timeout=10000)
            await page.wait_for_timeout(2000)

            # Check if we're actually logged in (not redirected to login page)
            current_url = page.url
            if "login" in current_url.lower() or "oauth" in current_url.lower():
                notify(f"⚠️ Session expired for {username} (redirected to login)")
                await ctx.close()
                cache.pop(username, None)
                atomic_file_update(path, cache)
                return None

            notify(f"✅ Session validated for {username}")
        except Exception as e:
            notify(f"⚠️ Could not validate session for {username}: {e}")
            await ctx.close()
            cache.pop(username, None)
            atomic_file_update(path, cache)
            return None
        finally:
            await page.close()

    return browser, ctx


def load_user_info_entries() -> list[dict[str, Any]]:
    from pydantic import ValidationError

    from backend.data.twitter.data_validation import User

    if not USER_INFO_FILE.exists():
        return []

    try:
        raw = json.loads(USER_INFO_FILE.read_text())
    except Exception as e:
        error("Failed to parse user_info.json", status_code=500, exception_text=str(e), function_name="load_user_info_entries")
        return []

    entries = []
    if isinstance(raw, dict):
        raw = [raw]
    elif isinstance(raw, list):
        raw = [entry for entry in raw if isinstance(entry, dict)]
    else:
        error("Invalid user_info.json format: expected dict or list", status_code=500, function_name="load_user_info_entries")
        return []

    # Validate each entry
    for entry in raw:
        try:
            validated = User(**entry)
            entries.append(validated.model_dump())
        except ValidationError as e:
            handle = entry.get("handle", "unknown")
            error(f"Invalid user data for {handle}", status_code=500, exception_text=str(e), function_name="load_user_info_entries", username=handle)
            # Still include the entry but log the validation error
            entries.append(entry)

    return entries


def find_user_info(entries: Iterable[dict[str, Any]], handle: str) -> dict[str, Any] | None:
    for entry in entries:
        entry_handle = entry.get("handle") or entry.get("username")
        if entry_handle == handle:
            return entry
    return None


def write_user_info(user_info: dict[str, Any]) -> Path:
    # Persist user metadata to disk, updating the entry matching the handle/username."""
    from pydantic import ValidationError

    from backend.data.twitter.data_validation import User

    handle = user_info.get("handle") or user_info.get("username")

    entries = load_user_info_entries()
    target = find_user_info(entries, handle) if handle else None

    is_new_user = target is None
    if is_new_user:
        target = {}
        entries.append(target)

    for key, value in user_info.items():
        if value is not None:
            target[key] = value

    if handle:
        target.setdefault("handle", handle)
        target.setdefault("username", handle)

    # Set default values for new users
    if is_new_user:
        target.setdefault("account_type", "trial")
        # Trial users start with 3 scrapes and 3 posts
        target.setdefault("scrapes_left", 3)
        target.setdefault("posts_left", 3)
        target.setdefault("intent", "")  # Initialize intent field

        # Auto-generate uid if not provided
        if "uid" not in target or target["uid"] is None:
            # Find max uid and add 1
            existing_uids = [e.get("uid") for e in entries if e.get("uid") is not None]
            max_uid = max(existing_uids) if existing_uids else 0
            target["uid"] = max_uid + 1
            notify(f"🆔 Auto-generated uid={target['uid']} for new user @{handle}")

    # Ensure intent field exists for all users (backward compatibility)
    target.setdefault("intent", "")

    # Validate the updated user data before writing
    try:
        validated = User(**target)
        # Replace target with validated data
        target.clear()
        target.update(validated.model_dump())
    except ValidationError as e:
        error(f"Invalid user data for {handle}", status_code=500, exception_text=str(e), function_name="write_user_info", username=handle)
        # Continue anyway to not break existing functionality, but log the error

    atomic_file_update(USER_INFO_FILE, entries, ".tmp", ensure_ascii=False)
    notify("💾 Updated user info")
    return USER_INFO_FILE


def read_user_info(handle: str) -> dict[str, Any] | None:
    # Return cached user metadata for the provided handle/username."""
    if not handle:
        return None

    entries = load_user_info_entries()
    user_info = find_user_info(entries, handle)

    # Ensure intent field exists for backward compatibility
    if user_info and "intent" not in user_info:
        user_info["intent"] = ""

    return user_info


# NOTE: Example caching for LLM prompts is now handled by posted_tweets_cache.py
# Examples are stored with post_type ("reply", "comment_reply", "original")
# and sorted by engagement score. See:
# - get_top_posts_by_type(username, post_type, limit)
# - build_examples_from_posts(posts, post_type)


def read_tokens() -> dict[str, Any]:
    """Return the existing token map from disk (empty dict if missing/invalid)."""
    from pydantic import ValidationError

    from backend.data.twitter.data_validation import Token

    path = TOKEN_FILE
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
        if not isinstance(data, dict):
            error("Invalid tokens file format: expected dict", status_code=500, function_name="read_tokens")
            return {}

        # Validate each user's token data
        validated_data = {}
        for username, token_data in data.items():
            # Handle legacy format (string) - just store as-is without validation
            if isinstance(token_data, str):
                validated_data[username] = token_data
                continue

            # Validate new format (dict with Token model)
            if isinstance(token_data, dict):
                try:
                    validated = Token(**token_data)
                    validated_data[username] = validated.model_dump()
                except ValidationError as e:
                    error(f"Invalid token data for user {username}", status_code=500, exception_text=str(e), function_name="read_tokens", username=username)
                    # Include invalid token but log the error
                    validated_data[username] = token_data

        return validated_data
    except Exception as e:
        error("Could not parse existing token file", status_code=500, exception_text=str(e), function_name="read_tokens")
        return {}


def read_user_token(username: str) -> str | None:
    """Return the refresh token for the given user, or None if not found."""
    tokens = read_tokens()
    token_data = tokens.get(username)

    # Handle legacy format (string) and new format (dict)
    if isinstance(token_data, str):
        return token_data
    elif isinstance(token_data, dict):
        return token_data.get("refresh_token")
    else:
        error(f"No token found for user {username}")
        return None


def read_user_access_token(username: str) -> tuple[str | None, float | None]:
    """Return the cached access token and expiration timestamp for the user."""
    tokens = read_tokens()
    token_data = tokens.get(username)

    if isinstance(token_data, dict):
        access_token = token_data.get("access_token")
        expires_at = token_data.get("expires_at")
        return access_token, expires_at

    return None, None


def store_token(username: str, refresh_token: str, access_token: str | None = None, expires_in: int | None = None):
    """Persist the refresh token and optionally access token with expiration to a shared JSON map."""
    from pydantic import ValidationError

    from backend.data.twitter.data_validation import Token

    tokens = read_tokens()
    path = TOKEN_FILE

    # Calculate expiration timestamp (with 60 second buffer)
    expires_at = None
    if access_token and expires_in:
        expires_at = time.time() + expires_in - 60

    token_data = {"refresh_token": refresh_token, "access_token": access_token, "expires_at": expires_at}

    # Validate token data before storing
    try:
        validated = Token(**token_data)
        tokens[username] = validated.model_dump()
    except ValidationError as e:
        error(f"Invalid token data for user {username}", status_code=500, exception_text=str(e), function_name="store_token", username=username)
        # Store anyway but log the validation error
        tokens[username] = token_data

    atomic_file_update(path, tokens, ".json.tmp")
    notify(f"💾 Stored OAuth tokens for {username}")


def _cache_key(username: str | None) -> str:
    key = (username or "default").strip()
    key = key or "default"
    sanitized = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in key)
    return sanitized or "default"


def log_background_task(username: str, task_type: str, tweets_scraped: int = 0, replies_generated: int = 0, **extra_data):
    """
    Log background task execution to append-only log file.

    Args:
        username: Twitter handle of the user
        task_type: Type of task (e.g., "tweet_scraping", "reply_generation")
        tweets_scraped: Number of tweets scraped
        replies_generated: Number of replies generated
        **extra_data: Any additional data to log
    """
    log_file = CACHE_DIR / "background_tasks.jsonl"

    # Create log entry
    log_entry = {"timestamp": datetime.utcnow().isoformat() + "Z", "username": username, "task_type": task_type, "tweets_scraped": tweets_scraped, "replies_generated": replies_generated, **extra_data}

    try:
        # Append to log file (create if doesn't exist)
        with open(log_file, "a") as f:
            f.write(json.dumps(log_entry) + "\n")

        notify(f"📝 Logged background task: {task_type} for @{username}")

    except Exception as e:
        error("Failed to log background task", status_code=500, exception_text=str(e), function_name="log_background_task", username=username)
        notify(f"⚠️ Failed to log background task: {e}")


def add_to_seen_tweets(username: str, tweet_ids: list[str]) -> None:
    """
    Add tweet IDs to the seen_tweets map in user_info with current timestamp.

    Args:
        username: Twitter handle of the user
        tweet_ids: List of tweet IDs to mark as seen
    """
    user_info = read_user_info(username)
    if not user_info:
        notify(f"⚠️ Cannot add to seen_tweets: user {username} not found")
        return

    # Initialize seen_tweets if it doesn't exist
    seen_tweets = user_info.get("seen_tweets", {})
    if not isinstance(seen_tweets, dict):
        seen_tweets = {}

    # Add new tweet IDs with current timestamp
    current_time = datetime.utcnow().isoformat() + "Z"
    for tweet_id in tweet_ids:
        if tweet_id:
            seen_tweets[str(tweet_id)] = current_time

    # Update user_info
    user_info["seen_tweets"] = seen_tweets
    write_user_info(user_info)
    notify(f"👁️ Added {len(tweet_ids)} tweet(s) to seen_tweets for {username}")


def remove_from_seen_tweets(username: str, tweet_ids: list[str]) -> int:
    """
    Remove tweet IDs from the seen_tweets map.

    Args:
        username: Twitter handle of the user
        tweet_ids: List of tweet IDs to remove

    Returns:
        Number of tweet IDs actually removed
    """
    user_info = read_user_info(username)
    if not user_info:
        return 0

    seen_tweets = user_info.get("seen_tweets", {})
    if not isinstance(seen_tweets, dict):
        return 0

    removed_count = 0
    for tweet_id in tweet_ids:
        str_id = str(tweet_id)
        if str_id in seen_tweets:
            del seen_tweets[str_id]
            removed_count += 1

    if removed_count > 0:
        user_info["seen_tweets"] = seen_tweets
        write_user_info(user_info)
        notify(f"🗑️ Removed {removed_count} tweet(s) from seen_tweets for {username}")

    return removed_count


def cleanup_seen_tweets(username: str, hours: int = MAX_TWEET_AGE_HOURS) -> int:
    """
    Remove tweet IDs older than specified hours from seen_tweets map.

    Args:
        username: Twitter handle of the user
        hours: Age threshold in hours (default: MAX_TWEET_AGE_HOURS)

    Returns:
        Number of tweet IDs removed
    """
    from datetime import timedelta

    try:  # Python 3.11+
        from datetime import UTC  # type: ignore[attr-defined]
    except ImportError:  # Python <3.11
        UTC = UTC

    user_info = read_user_info(username)
    if not user_info:
        return 0

    seen_tweets = user_info.get("seen_tweets", {})
    if not isinstance(seen_tweets, dict) or not seen_tweets:
        return 0

    now = datetime.now(UTC)
    cutoff = now - timedelta(hours=hours)

    # Filter out old entries
    original_count = len(seen_tweets)
    filtered_seen_tweets = {}

    for tweet_id, timestamp_str in seen_tweets.items():
        try:
            # Parse ISO format timestamp
            timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            if timestamp >= cutoff:
                filtered_seen_tweets[tweet_id] = timestamp_str
        except Exception:
            # If we can't parse the timestamp, keep the entry (better safe than sorry)
            filtered_seen_tweets[tweet_id] = timestamp_str

    removed_count = original_count - len(filtered_seen_tweets)

    # Update user_info if anything was removed
    if removed_count > 0:
        user_info["seen_tweets"] = filtered_seen_tweets
        write_user_info(user_info)
        notify(f"🧹 Cleaned {removed_count} old tweet ID(s) from seen_tweets for {username}")

    return removed_count


def is_tweet_seen(username: str, tweet_id: str) -> bool:
    """
    Check if a tweet ID exists in the seen_tweets map.

    Args:
        username: Twitter handle of the user
        tweet_id: Tweet ID to check

    Returns:
        True if tweet has been seen before, False otherwise
    """
    user_info = read_user_info(username)
    if not user_info:
        return False

    seen_tweets = user_info.get("seen_tweets", {})
    if not isinstance(seen_tweets, dict):
        return False

    return str(tweet_id) in seen_tweets


if __name__ == "__main__":
    message_devs("This is a test message to developers.")
