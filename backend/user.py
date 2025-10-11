from typing import Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.tweets_cache import remove_user_cache
from backend.utils import remove_entry_from_map, _cache_key, ARCHIVE_DIR, BROWSER_STATE_FILE, TOKEN_FILE, notify
from backend.utils import _archive_interactions_log, write_user_info
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


def topic_to_query(topic: str) -> str:
    """Convert a simple topic/keyword to a Twitter search query."""
    # Add filters: no links, no replies, no retweets, English only
    return f"{topic} -filter:links -filter:replies -is:retweet lang:en"


def query_to_topic(query: str) -> str:
    """Extract the topic/keyword from a Twitter search query."""
    # Remove common filters to get the base topic
    topic = query
    filters_to_remove = [
        "-filter:links",
        "-filter:replies",
        "-is:retweet",
        "lang:en"
    ]
    for filter_str in filters_to_remove:
        topic = topic.replace(filter_str, "")
    return topic.strip()


def read_user_settings(handle: str) -> dict[str, Any] | None:
    """Return the scraping settings for a user (queries, relevant_accounts, max_tweets_retrieve)."""
    from backend.utils import read_user_info

    user_info = read_user_info(handle)
    if not user_info:
        return None

    # Convert stored queries to topics for display
    stored_queries = user_info.get("queries", [])
    topics = [query_to_topic(q) for q in stored_queries]

    return {
        "queries": topics,  # Return topics, not full queries
        "relevant_accounts": user_info.get("relevant_accounts", []),
        "max_tweets_retrieve": user_info.get("max_tweets_retrieve", 30)
    }


def write_user_settings(handle: str, queries: list[str] | None = None,
                       relevant_accounts: list[str] | None = None,
                       max_tweets_retrieve: int | None = None) -> None:
    """Update scraping settings for a user in user_info.json."""
    from backend.utils import read_user_info, write_user_info

    user_info = read_user_info(handle)
    if not user_info:
        # Create new entry if user doesn't exist
        user_info = {"handle": handle}

    # Update only the provided settings
    if queries is not None:
        # Convert topics to full queries before storing
        full_queries = [topic_to_query(q) for q in queries]
        user_info["queries"] = full_queries
    if relevant_accounts is not None:
        user_info["relevant_accounts"] = relevant_accounts
    if max_tweets_retrieve is not None:
        user_info["max_tweets_retrieve"] = max_tweets_retrieve

    write_user_info(user_info)
    notify(f"✅ Updated settings for {handle}")


# API Router
router = APIRouter(prefix="/user", tags=["user"])


class UpdateSettingsRequest(BaseModel):
    queries: list[str] | None = None
    relevant_accounts: list[str] | None = None
    max_tweets_retrieve: int | None = None


@router.get("/{handle}/info")
async def get_user_info_endpoint(handle: str) -> dict:
    """Get user information."""
    from backend.utils import read_user_info as get_cached_user_info

    user_info = get_cached_user_info(handle)
    if not user_info:
        raise HTTPException(status_code=404, detail=f"User {handle} not found")
    return user_info


@router.get("/{handle}/settings")
async def get_settings_endpoint(handle: str) -> dict:
    """Get scraping settings for a user."""
    settings = read_user_settings(handle)
    if settings is None:
        raise HTTPException(status_code=404, detail=f"User {handle} not found")
    return settings


@router.put("/{handle}/settings")
async def update_settings_endpoint(handle: str, payload: UpdateSettingsRequest) -> dict:
    """Update scraping settings for a user."""
    try:
        write_user_settings(
            handle=handle,
            queries=payload.queries,
            relevant_accounts=payload.relevant_accounts,
            max_tweets_retrieve=payload.max_tweets_retrieve
        )
        return {
            "message": "Settings updated successfully",
            "settings": read_user_settings(handle)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating settings: {str(e)}") from e


@router.delete("/{handle}/settings/account/{account}")
async def remove_account_endpoint(handle: str, account: str) -> dict:
    """Remove a specific account from relevant_accounts."""
    from backend.utils import read_user_info, write_user_info

    try:
        user_info = read_user_info(handle)
        if not user_info:
            raise HTTPException(status_code=404, detail=f"User {handle} not found")

        relevant_accounts = user_info.get("relevant_accounts", [])
        if account in relevant_accounts:
            relevant_accounts.remove(account)
            user_info["relevant_accounts"] = relevant_accounts
            write_user_info(user_info)

        return {
            "message": "Account removed successfully",
            "settings": read_user_settings(handle)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error removing account: {str(e)}") from e


class RemoveQueryRequest(BaseModel):
    query: str


@router.delete("/{handle}/settings/query")
async def remove_query_endpoint(handle: str, payload: RemoveQueryRequest) -> dict:
    """Remove a specific query from queries (accepts topic, converts to query internally)."""
    from backend.utils import read_user_info, write_user_info

    try:
        user_info = read_user_info(handle)
        if not user_info:
            raise HTTPException(status_code=404, detail=f"User {handle} not found")

        # Convert the topic to full query for matching
        full_query = topic_to_query(payload.query)

        queries = user_info.get("queries", [])
        if full_query in queries:
            queries.remove(full_query)
            user_info["queries"] = queries
            write_user_info(user_info)

        return {
            "message": "Query removed successfully",
            "settings": read_user_settings(handle)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error removing query: {str(e)}") from e


@router.get("/validate/{twitter_handle}")
async def validate_twitter_handle(twitter_handle: str) -> dict:
    """Validate if a Twitter handle exists by checking Twitter's API."""
    import requests
    from backend.oauth import refresh_access_token
    from backend.utils import read_tokens

    try:
        # Remove @ if present
        handle = twitter_handle.lstrip('@')

        # Get refresh token from any authenticated user to make the API call
        tokens = read_tokens()
        if not tokens:
            raise HTTPException(status_code=503, 
                                detail="No authenticated users available to validate handle")

        # Use the first available token
        refresh_token = next(iter(tokens.values()))

        # Get access token
        token_response = refresh_access_token(refresh_token)
        access_token = token_response.get("access_token")

        if not access_token:
            raise HTTPException(status_code=503, 
                                detail="Failed to get access token")

        # Check if user exists
        url = f"https://api.twitter.com/2/users/by/username/{handle}"
        headers = {"Authorization": f"Bearer {access_token}"}

        response = requests.get(url, 
                                headers=headers,
                                timeout=10)

        if response.status_code == 200:
            data = response.json()
            user_data = data.get("data")
            # Check if we got valid user data
            if user_data:
                return {"valid": True, 
                        "handle": handle, 
                        "data": user_data}
            else:
                return {"valid": False, 
                        "handle": handle, 
                        "error": "User not found"}
        elif response.status_code == 404:
            return {"valid": False, 
                    "handle": handle, 
                    "error": "User not found"}
        else:
            # For any other error, still return valid=False instead of raising
            return {"valid": False, 
                    "handle": handle, 
                    "error": f"Could not validate handle (status {response.status_code})"}

    except HTTPException:
        raise
    except requests.RequestException as e:
        # Return invalid instead of raising error
        return {"valid": False, "handle": handle, "error": f"Network error: {str(e)}"}
    except Exception as e:
        # Return invalid instead of raising error
        return {"valid": False, "handle": handle, "error": f"Error: {str(e)}"}