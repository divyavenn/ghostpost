from typing import Any
from backend.tweets_cache import remove_user_cache
from backend.utils import remove_entry_from_map, _cache_key, ARCHIVE_DIR, BROWSER_STATE_FILE, TOKEN_FILE, notify
from backend.utils import _archive_interactions_log
from utils import write_user_info

def get_user_info(access_token: str) -> dict[str, Any]:
    """Fetch the authenticated user's metadata and persist it locally."""
    import requests

    url = "https://api.twitter.com/2/users/me"
    fields = [
        "name",
        "profile_image_url",
        "public_metrics",
        "username",
    ]
    params = {"user.fields": ",".join(fields)}
    headers = {"Authorization": f"Bearer {access_token}"}

    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()

    payload = response.json()
    data = payload.get("data", {}) if isinstance(payload, dict) else {}
    public_metrics = data.get("public_metrics") or {}

    user_record = {
        "handle": data.get("username"),
        "username": data.get("name"),
        "profile_pic_url": data.get("profile_image_url"),
        "follower_count": public_metrics.get("followers_count"),
    }

    write_user_info(user_record)
    return user_record


def delete_user_info(username) -> None:
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