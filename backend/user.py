from utils import write_user_info
from typing import Any, Dict


def get_user_info_from_API(access_token: str) -> Dict[str, Any]:
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


def get_user_info(access_token: str) -> Dict[str, Any]:
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
