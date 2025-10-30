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
    DEFAULT_TWITTER_USERNAME as USERNAME,
    TOKEN_FILE,
    USER_INFO_FILE,
)

# Ensure cache directory exists
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def notify(msg: str):
    print(msg)


def error(msg: str, status_code: int = 500, exception_text : str | None = None, function_name: str | None = None, username: str | None = None, critical: bool = False):
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
    error_entry = {
        "message": msg,
        "status_code": status_code,
        "function_name": function_name or "unknown",
        "timestamp": timestamp,
        "user": username or "unknown",
        "exception" : exception_text
    }

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
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    from backend.config import DEV_EMAIL, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_USER

    # Check if email is configured
    if not SMTP_USER or not SMTP_PASSWORD:
        notify("⚠️ Email not configured (missing SMTP_USER or SMTP_PASSWORD)")
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
    from backend.data_validation import BrowserState
    from pydantic import ValidationError

    state = await context.storage_state()
    path = BROWSER_STATE_FILE
    cache: dict[str, Any] = {}
    if path.exists():
        try:
            cached = json.loads(path.read_text())
            if isinstance(cached, dict):
                cache = cached
        except Exception as e:
            error(f"Failed to read existing browser state file", status_code=500, exception_text=str(e), function_name="store_browser_state")

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
    from backend.data_validation import BrowserState
    from pydantic import ValidationError

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
    from backend.data_validation import User
    from pydantic import ValidationError

    if not USER_INFO_FILE.exists():
        return []

    try:
        raw = json.loads(USER_INFO_FILE.read_text())
    except Exception as e:
        error(f"Failed to parse user_info.json", status_code=500, exception_text=str(e), function_name="load_user_info_entries")
        return []

    entries = []
    if isinstance(raw, dict):
        raw = [raw]
    elif isinstance(raw, list):
        raw = [entry for entry in raw if isinstance(entry, dict)]
    else:
        error(f"Invalid user_info.json format: expected dict or list", status_code=500, function_name="load_user_info_entries")
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
    from backend.data_validation import User
    from pydantic import ValidationError

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

        # Auto-generate uid if not provided
        if "uid" not in target or target["uid"] is None:
            # Find max uid and add 1
            existing_uids = [e.get("uid") for e in entries if e.get("uid") is not None]
            max_uid = max(existing_uids) if existing_uids else 0
            target["uid"] = max_uid + 1
            notify(f"🆔 Auto-generated uid={target['uid']} for new user @{handle}")

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
    return find_user_info(entries, handle)


def read_tokens() -> dict[str, Any]:
    """Return the existing token map from disk (empty dict if missing/invalid)."""
    from backend.data_validation import Token
    from pydantic import ValidationError

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
    from backend.data_validation import Token
    from pydantic import ValidationError

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

 
if __name__ == "__main__":
    message_devs("This is a test message to developers.")