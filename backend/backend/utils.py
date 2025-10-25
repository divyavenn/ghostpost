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


def error(msg: str, status_code: int = 500):
    raise RuntimeError(f"❌ {msg}")
    


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
    state = await context.storage_state()
    path = BROWSER_STATE_FILE
    cache: dict[str, Any] = {}
    if path.exists():
        try:
            cached = json.loads(path.read_text())
            if isinstance(cached, dict):
                cache = cached
        except Exception:
            pass

    # Add timestamp to track when the state was last updated
    state["timestamp"] = datetime.utcnow().isoformat() + "Z"
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
    path = BROWSER_STATE_FILE
    if not path.exists():
        return None

    try:
        cache = json.loads(path.read_text())
    except Exception:
        path.unlink(missing_ok=True)
        notify("⚠️ Could not parse browser state cache; starting fresh")
        return None

    if not isinstance(cache, dict):
        path.unlink(missing_ok=True)
        notify("⚠️ Invalid browser state cache format; starting fresh")
        return None

    state = cache.get(username)
    if not state:
        notify(f"⚠️ No saved browser state for {username}")
        return None

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
    if not USER_INFO_FILE.exists():
        return []

    try:
        raw = json.loads(USER_INFO_FILE.read_text())
    except Exception:
        return []

    if isinstance(raw, dict):
        return [raw]
    if isinstance(raw, list):
        return [entry for entry in raw if isinstance(entry, dict)]
    return []


def find_user_info(entries: Iterable[dict[str, Any]], handle: str) -> dict[str, Any] | None:
    for entry in entries:
        entry_handle = entry.get("handle") or entry.get("username")
        if entry_handle == handle:
            return entry
    return None


def write_user_info(user_info: dict[str, Any]) -> Path:
    # Persist user metadata to disk, updating the entry matching the handle/username."""
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
    path = TOKEN_FILE
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
        if isinstance(data, dict):
            return data
    except Exception:
        error("⚠️ could not parse existing token file")
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
    tokens = read_tokens()
    path = TOKEN_FILE

    # Calculate expiration timestamp (with 60 second buffer)
    expires_at = None
    if access_token and expires_in:
        expires_at = time.time() + expires_in - 60

    tokens[username] = {"refresh_token": refresh_token, "access_token": access_token, "expires_at": expires_at}

    atomic_file_update(path, tokens, ".json.tmp")
    notify(f"💾 Stored OAuth tokens for {username}")


def _cache_key(username: str | None) -> str:
    key = (username or "default").strip()
    key = key or "default"
    sanitized = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in key)
    return sanitized or "default"
