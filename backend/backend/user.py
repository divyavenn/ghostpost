from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.tweets_cache import remove_user_cache
from backend.utils import BROWSER_STATE_FILE, TOKEN_FILE, _archive_interactions_log, _cache_key, notify, read_user_info, remove_entry_from_map, write_user_info


def get_validation_delay() -> int:
    return 310  # Free tier: 3 requests per 15 minutes


def get_all_users() -> list[str]:
    """
    Get list of all user handles from user_info.json.

    Returns:
        list[str]: List of Twitter handles for all users
    """
    import json
    from pathlib import Path

    user_info_path = Path(__file__).parent / "cache" / "user_info.json"

    try:
        if not user_info_path.exists():
            return []

        with open(user_info_path) as f:
            users = json.load(f)

        # Extract handles from user records
        if isinstance(users, list):
            handles = [user.get('handle') for user in users if user.get('handle')]
            return handles
        else:
            # Legacy format: single user object
            handle = users.get('handle')
            return [handle] if handle else []

    except Exception as e:
        notify(f"❌ Error reading user_info.json: {e}")
        return []


def get_user_info(access_token: str) -> dict[str, Any]:
    """Fetch the authenticated user's metadata and persist it locally."""
    import requests
    from backend.utils import read_user_info

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

    handle = data.get("username")
    new_follower_count = public_metrics.get("followers_count", 0)

    # Get existing user info to calculate follower delta
    existing_user = read_user_info(handle) if handle else None
    is_first_time_user = existing_user is None

    old_follower_count = existing_user.get("follower_count", 0) if existing_user else 0

    # Calculate new follows (only count increases, not decreases)
    follower_delta = max(0, new_follower_count - old_follower_count)

    # Get existing stats or initialize
    # For first-time users, set lifetime_new_follows to 0 to start tracking from now
    if is_first_time_user:
        lifetime_new_follows = 0
        lifetime_posts = 0
        scrolling_time_saved = 0
    else:
        lifetime_new_follows = existing_user.get("lifetime_new_follows", 0) + follower_delta
        lifetime_posts = existing_user.get("lifetime_posts", 0)
        scrolling_time_saved = existing_user.get("scrolling_time_saved", 0)

    user_record = {
        "handle": handle,
        "username": data.get("name"),
        "profile_pic_url": data.get("profile_image_url"),
        "follower_count": new_follower_count,
        "lifetime_new_follows": lifetime_new_follows,
        "lifetime_posts": lifetime_posts,
        "scrolling_time_saved": scrolling_time_saved,
    }

    write_user_info(user_record)

    if follower_delta > 0:
        notify(f"🎉 +{follower_delta} new followers for @{handle}! Total new follows: {user_record['lifetime_new_follows']}")

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
    filters_to_remove = ["-filter:links", "-filter:replies", "-is:retweet", "lang:en"]
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

    # relevant_accounts is a dict: {handle: validated}
    relevant_accounts = user_info.get("relevant_accounts", {})

    return {
        "queries": topics,  # Return topics, not full queries
        "relevant_accounts": relevant_accounts,
        "max_tweets_retrieve": user_info.get("max_tweets_retrieve", 30),
        "number_of_generations": user_info.get("number_of_generations", 1),
        "models": user_info.get("models", ["claude-3-5-sonnet-20241022"])  # Default to single model
    }


def write_user_settings(handle: str, queries: list[str] | None = None, relevant_accounts: dict[str, bool] | None = None, max_tweets_retrieve: int | None = None, number_of_generations: int | None = None, models: list[str] | None = None) -> None:
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
        # Store as dict {handle: validated}
        user_info["relevant_accounts"] = relevant_accounts
    if max_tweets_retrieve is not None:
        user_info["max_tweets_retrieve"] = max_tweets_retrieve
    if number_of_generations is not None:
        # Validate range 1-5
        if not 1 <= number_of_generations <= 5:
            raise ValueError("number_of_generations must be between 1 and 5")
        user_info["number_of_generations"] = number_of_generations
    if models is not None:
        # Validate models list is not empty
        if not models or not isinstance(models, list):
            raise ValueError("models must be a non-empty list of strings")
        user_info["models"] = models

    write_user_info(user_info)
    notify(f"✅ Updated settings for {handle}")


# API Router
router = APIRouter(prefix="/user", tags=["user"])


class RelevantAccountModel(BaseModel):
    handle: str
    validated: bool


class UpdateSettingsRequest(BaseModel):
    queries: list[str] | None = None
    relevant_accounts: dict[str, bool] | None = None
    max_tweets_retrieve: int | None = None
    number_of_generations: int | None = None
    models: list[str] | None = None


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


@router.get("/config/validation-delay")
async def get_validation_delay_endpoint() -> dict:
    """Get the validation delay configuration for Twitter API free tier."""
    delay = get_validation_delay()
    return {"delay_seconds": delay, "delay_ms": delay * 1000, "tier": "free"}


@router.put("/{handle}/settings")
async def update_settings_endpoint(handle: str, payload: UpdateSettingsRequest) -> dict:
    """Update scraping settings for a user."""
    try:
        # Get the old settings to check for changes in number_of_generations
        old_settings = read_user_settings(handle)
        old_num_generations = old_settings.get("number_of_generations", 1) if old_settings else 1
        new_num_generations = payload.number_of_generations if payload.number_of_generations is not None else old_num_generations

        notify(f"🔍 Settings update: old_num_generations={old_num_generations}, new_num_generations={new_num_generations}, payload.number_of_generations={payload.number_of_generations}")

        # Update the settings
        write_user_settings(handle=handle, queries=payload.queries, relevant_accounts=payload.relevant_accounts, max_tweets_retrieve=payload.max_tweets_retrieve, number_of_generations=payload.number_of_generations, models=payload.models)

        # Handle changes in number_of_generations
        generation_happened = False
        if payload.number_of_generations is not None and new_num_generations != old_num_generations:
            notify("✅ Number of generations changed! Starting automatic reply adjustment...")
            from backend.generate_replies import generate_replies_for_tweet
            from backend.tweets_cache import read_from_cache, write_to_cache

            tweets = await read_from_cache(username=handle)

            if tweets:
                if new_num_generations > old_num_generations:
                    generation_happened = True
                    # Generate additional replies for existing tweets
                    notify(f"📝 Generating additional replies (from {old_num_generations} to {new_num_generations})...")

                    user_info = read_user_info(handle)
                    models = user_info["models"] if "models" in user_info and user_info["models"] else ["claude-3-5-sonnet-20241022"]

                    tweets_to_update = 0
                    for tweet in tweets:
                        if "generated_replies" not in tweet or not tweet["generated_replies"]:
                            continue

                        current_reply_count = len(tweet.get("generated_replies", []))
                        needed_replies = new_num_generations - current_reply_count

                        if needed_replies <= 0:
                            continue

                        tweets_to_update += 1

                    notify(f"📊 Found {tweets_to_update} tweets that need additional replies")

                    # Initialize scraping status before starting generation
                    from backend.generate_replies import scraping_status
                    scraping_status[handle] = {
                        "type": "generating",
                        "value": f"0/{tweets_to_update}",
                        "phase": "generating"
                    }

                    updated_count = 0
                    for idx, tweet in enumerate(tweets):
                        if "generated_replies" not in tweet or not tweet["generated_replies"]:
                            continue

                        current_reply_count = len(tweet.get("generated_replies", []))
                        needed_replies = new_num_generations - current_reply_count

                        if needed_replies <= 0:
                            continue

                        # Update scraping status for frontend polling
                        from backend.generate_replies import scraping_status
                        scraping_status[handle] = {
                            "type": "generating",
                            "value": f"{updated_count + 1}/{tweets_to_update}",
                            "phase": "generating"
                        }

                        tweet_id = tweet.get('id', tweet.get('tweet_id', 'unknown'))
                        notify(f"🔄 Generating {needed_replies} additional replies for tweet {tweet_id} (currently has {current_reply_count})")

                        # Generate additional replies using the reusable function
                        new_replies = generate_replies_for_tweet(
                            tweet=tweet,
                            models=models,
                            needed_generations=needed_replies,
                            delay_seconds=1
                        )

                        # Append new replies to existing ones (new_replies is array of tuples)
                        if new_replies:
                            tweet["generated_replies"].extend(new_replies)
                            updated_count += 1
                            notify(f"✅ Updated tweet {tweet_id} - now has {len(tweet['generated_replies'])} replies")

                    notify(f"✅ Updated {updated_count} tweets with additional replies")

                    # Save updated cache
                    await write_to_cache(tweets, f"Updated replies (increased to {new_num_generations})", username=handle)

                    # Mark generation as complete
                    from backend.generate_replies import scraping_status
                    scraping_status[handle] = {"type": "complete", "value": "", "phase": "complete"}

                elif new_num_generations < old_num_generations:
                    # Note: We don't actually delete replies when count is reduced
                    # The frontend will just display fewer of them based on user settings
                    # This preserves all generated replies in the cache
                    notify(f"✂️ Settings reduced replies (from {old_num_generations} to {new_num_generations}) - existing replies preserved")
                    generation_happened = False  # No actual generation needed

        return {
            "message": "Settings updated successfully",
            "settings": read_user_settings(handle),
            "generation_happened": generation_happened
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating settings: {str(e)}") from e


@router.post("/{handle}/settings/account")
async def add_account_endpoint(handle: str, account: RelevantAccountModel) -> dict:
    """Add a new account to relevant_accounts."""
    from backend.utils import read_user_info, write_user_info

    try:
        user_info = read_user_info(handle)
        if not user_info:
            raise HTTPException(status_code=404, detail=f"User {handle} not found")

        relevant_accounts = user_info.get("relevant_accounts", {})

        # Check if account already exists
        if account.handle in relevant_accounts:
            return {"message": "Account already added", "settings": read_user_settings(handle)}

        # Add new account
        relevant_accounts[account.handle] = account.validated
        user_info["relevant_accounts"] = relevant_accounts
        write_user_info(user_info)

        return {"message": "Account added successfully", "settings": read_user_settings(handle)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error adding account: {str(e)}") from e


@router.patch("/{handle}/settings/account/{account}/validation")
async def update_account_validation_endpoint(handle: str, account: str, validated: bool) -> dict:
    """Update the validation status of a specific account."""
    from backend.utils import read_user_info, write_user_info

    try:
        user_info = read_user_info(handle)
        if not user_info:
            raise HTTPException(status_code=404, detail=f"User {handle} not found")

        relevant_accounts = user_info.get("relevant_accounts", {})

        # Check if account exists
        if account not in relevant_accounts:
            raise HTTPException(status_code=404, detail=f"Account @{account} not found")

        # Update validation status
        relevant_accounts[account] = validated
        user_info["relevant_accounts"] = relevant_accounts
        write_user_info(user_info)

        return {"message": f"Validation status for @{account} updated to {validated}", "settings": read_user_settings(handle)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating account validation: {str(e)}") from e


@router.delete("/{handle}/settings/account/{account}")
async def remove_account_endpoint(handle: str, account: str) -> dict:
    """Remove a specific account from relevant_accounts."""
    from backend.utils import read_user_info, write_user_info

    try:
        user_info = read_user_info(handle)
        if not user_info:
            raise HTTPException(status_code=404, detail=f"User {handle} not found")

        relevant_accounts = user_info.get("relevant_accounts", {})

        # Remove account if it exists
        if account in relevant_accounts:
            del relevant_accounts[account]
            user_info["relevant_accounts"] = relevant_accounts
            write_user_info(user_info)

        return {"message": "Account removed successfully", "settings": read_user_settings(handle)}
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

        return {"message": "Query removed successfully", "settings": read_user_settings(handle)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error removing query: {str(e)}") from e


@router.get("/{username}/validate/{twitter_handle}")
async def validate_twitter_handle(username: str, twitter_handle: str) -> dict:
    """Validate if a Twitter handle exists by checking Twitter's API with rate limit retry."""
    from time import sleep

    import requests

    from backend.oauth import ensure_access_token

    try:
        # Remove @ if present
        handle = twitter_handle.lstrip('@')

        # Get user access token
        access_token = await ensure_access_token(username)

        if not access_token:
            raise HTTPException(status_code=403, detail="User not authenticated")

        # Check if user exists with retry logic for rate limiting
        url = f"https://api.twitter.com/2/users/by/username/{handle}"
        headers = {"Authorization": f"Bearer {access_token}"}

        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            data = response.json()
            user_data = data.get("data")
            # Check if we got valid user data
            if user_data:
                return {"valid": True, "handle": handle, "data": user_data}
            else:
                return {"valid": False, "handle": handle, "error": "User not found"}
        elif response.status_code == 429:
            sleep(get_validation_delay())
            return await validate_twitter_handle(username, twitter_handle)

        return {"valid": False, "handle": handle, "error": f"{response.text} (status {response.status_code})"}
    except Exception as e:
        return {"valid": False, "handle": handle, "error": f"Unknown error occurred: {str(e)}"}
