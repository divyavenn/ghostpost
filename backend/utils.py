import json
import time
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parent
CACHE_DIR = BACKEND_DIR / "cache"
ARCHIVE_DIR = CACHE_DIR / "archive"
AUTH_COOKIE = "auth_token"
BROWSER_STATE_FILE = CACHE_DIR / "storage_state.json"
TOKEN_FILE = CACHE_DIR / "tokens.json"
USER_INFO_FILE = CACHE_DIR / "user_info.json"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
USERNAME = "proudlurker"


def notify(msg: str):
    print(msg)


def error(msg: str):
    raise RuntimeError(f"❌ {msg}")


def cookie_still_valid(state: Dict[str, Any]) -> bool:
    if not isinstance(state, dict):
        return False
    for c in state.get("cookies", []):
        if c.get("name") == AUTH_COOKIE:
            return c.get("expires", 0) == 0 or c["expires"] > time.time() + 60
    return False


def _cache_key(username: Optional[str]) -> str:
    key = (username or "default").strip()
    key = key or "default"
    sanitized = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in key)
    return sanitized or "default"


def get_user_tweet_cache(username=USERNAME) -> Path:
    return CACHE_DIR / f"{_cache_key(username)}" / "tweets_cache.json"


def get_user_interactions_log(username=USERNAME) -> Path:
    return CACHE_DIR / f"{_cache_key(username)}" / "log.json"


def _archive_interactions_log(username: str, key: str) -> Optional[Path]:
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


def remove_user_cache(username: str, key: str) -> bool:
    cache_removed = False
    tweet_cache = get_user_tweet_cache(username)
    user_dir = tweet_cache.parent

    if tweet_cache.exists():
        tweet_cache.unlink(missing_ok=True)
        cache_removed = True

    if user_dir.exists() and user_dir.is_dir():
        for child in user_dir.iterdir():
            if child.is_file():
                child.unlink(missing_ok=True)
                cache_removed = True
        try:
            user_dir.rmdir()
        except OSError:
            pass
    return cache_removed


def atomic_file_update(
    path: Path, data: Any, tmp_suffix: str = ".tmp", *, ensure_ascii: bool = False
) -> None:
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


def delete_user_info(username=USERNAME) -> None:
    """Delete cached data, tokens, and browser state for the user, archiving logs."""
    key = _cache_key(username)
    archived_log = _archive_interactions_log(username, key)
    if archived_log:
        notify(f"📦 Archived interaction log for {username} -> {archived_log.name}")

    if remove_user_cache(username, key):
        notify(f"🗑️ Deleted cached tweet data for {username}")

    if remove_entry_from_map(BROWSER_STATE_FILE, username, ".tmp"):
        notify(f"🗑️ Removed browser state for {username}")

    if remove_entry_from_map(TOKEN_FILE, username, ".json.tmp"):
        notify(f"🗑️ Removed OAuth token for {username}")


async def write_to_cache(tweets, description: str, *, username=USERNAME) -> Path:
    path = get_user_tweet_cache(username)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(tweets, indent=2, ensure_ascii=False))
    notify(f"💾{description} and wrote to cache")
    return path


async def read_from_cache(username=USERNAME):
    path = get_user_tweet_cache(username)
    notify(f"💾 Reading tweets from cache ({path.name})")
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text())
    except Exception as exc:
        error(f"Error reading JSON file: {exc}")
        return []


async def store_browser_state(username: str, context) -> None:
    state = await context.storage_state()
    path = BROWSER_STATE_FILE
    cache: Dict[str, Any] = {}
    if path.exists():
        try:
            cached = json.loads(path.read_text())
            if isinstance(cached, dict):
                cache = cached
        except Exception:
            pass

    cache[username] = state

    atomic_file_update(path, cache)
    notify(f"✅ Browser state saved for {username}")


async def read_browser_state(browser, username: str) -> Optional[Tuple[Any, Any]]:
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
    if not cookie_still_valid(state):
        cache.pop(username, None)
        atomic_file_update(path, cache)
        notify(f"🔐 Relogging for {username} (missing/expired cookie)")
        return None

    ctx = await browser.new_context(storage_state=state)
    notify(f"✅ Retrieved browser state for {username}")
    return browser, ctx


def load_user_info_entries() -> List[Dict[str, Any]]:
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


def find_user_info(
    entries: Iterable[Dict[str, Any]], handle: str
) -> Optional[Dict[str, Any]]:
    for entry in entries:
        entry_handle = entry.get("handle") or entry.get("username")
        if entry_handle == handle:
            return entry
    return None


def write_user_info(user_info: Dict[str, Any]) -> Path:
    # Persist user metadata to disk, updating the entry matching the handle/username."""
    handle = user_info.get("handle") or user_info.get("username")

    entries = load_user_info_entries()
    target = find_user_info(entries, handle) if handle else None

    if target is None:
        target = {}
        entries.append(target)

    for key, value in user_info.items():
        if value is not None:
            target[key] = value

    if handle:
        target.setdefault("handle", handle)
        target.setdefault("username", handle)

    atomic_file_update(USER_INFO_FILE, entries, ".tmp", ensure_ascii=False)
    notify("💾 Updated user info")
    return USER_INFO_FILE


def read_user_info(handle: str) -> Optional[Dict[str, Any]]:
    # Return cached user metadata for the provided handle/username."""
    if not handle:
        return None

    entries = load_user_info_entries()
    return find_user_info(entries, handle)


def read_tokens() -> Dict[str, Any]:
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


def read_user_token(username: str) -> Optional[str]:
    """Return the refresh token for the given user, or None if not found."""
    tokens = read_tokens()
    token = tokens.get(username)
    if isinstance(token, str):
        return token
    else:
        error(f"No token found for user {username}")
        return None


def store_token(username: str, refresh_token: str):
    """Persist the refresh token to a shared JSON map keyed by user identifier."""
    tokens = read_tokens()
    path = TOKEN_FILE

    tokens[username] = refresh_token

    atomic_file_update(path, tokens, ".json.tmp")
    notify(f"💾 Stored OAuth refresh token for {username}")
