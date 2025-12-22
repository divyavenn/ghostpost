from typing import Any

from fastapi import APIRouter, HTTPException

from backend.data.twitter.data_validation import (
    RelevantAccountModel,
    RemoveQueryRequest,
    UpdateEmailRequest,
    UpdateModelsRequest,
    UpdateSettingsRequest,
)
from backend.utlils.utils import notify, read_user_info, write_user_info


def get_validation_delay() -> int:
    return 310  # Free tier: 3 requests per 15 minutes


async def get_user_info(access_token: str) -> dict[str, Any]:
    """Fetch the authenticated user's metadata and persist it locally."""
    import requests

    from backend.twitter.rate_limiter import EndpointType, twitter_rate_limiter
    from backend.utlils.utils import read_user_info

    url = "https://api.twitter.com/2/users/me"
    fields = [
        "name",
        "profile_image_url",
        "public_metrics",
        "username",
    ]
    params = {"user.fields": ",".join(fields)}
    headers = {"Authorization": f"Bearer {access_token}"}

    # Wait for rate limiter (USER_LOOKUP endpoint: 100 req/15min)
    await twitter_rate_limiter.wait_if_needed(EndpointType.USER_LOOKUP)

    response = requests.get(url, headers=headers, params=params)
    twitter_rate_limiter.update_last_request(EndpointType.USER_LOOKUP)

    # Handle rate limiting with retry
    if response.status_code == 429:
        reset_time = response.headers.get("x-rate-limit-reset")
        if reset_time:
            await twitter_rate_limiter.wait_for_reset(int(reset_time), EndpointType.USER_LOOKUP)
            return await get_user_info(access_token)

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


def topic_to_query(topic: str) -> str:
    """Convert a simple topic/keyword to a Twitter search query."""
    # Add filters: no links, no replies, no retweets, English only
    return f"{topic} -filter:links -filter:replies -is:retweet lang:en"


def read_user_settings(handle: str) -> dict[str, Any] | None:
    """Return the scraping settings for a user (queries, relevant_accounts, ideal_num_posts)."""
    from backend.utlils.utils import read_user_info

    user_info = read_user_info(handle)
    if not user_info:
        return None

    # Return queries as-is - can be list of strings (legacy) or list of [query, summary] pairs (new format)
    # Frontend handles both formats
    queries = user_info.get("queries", [])

    # relevant_accounts is a dict: {handle: validated}
    relevant_accounts = user_info.get("relevant_accounts", {})

    return {
        "queries": queries,  # Return queries with summaries intact
        "relevant_accounts": relevant_accounts,
        "ideal_num_posts": user_info.get("ideal_num_posts", 30),
        "number_of_generations": user_info.get("number_of_generations", 1),
        "min_impressions_filter": user_info.get("min_impressions_filter", 2000),
        "manual_minimum_impressions": user_info.get("manual_minimum_impressions"),  # Can be None
        "models": user_info.get("models", ["claude-3-5-sonnet-20241022"]),  # Default to single model
        "intent": user_info.get("intent", "")
    }


def write_user_settings(handle: str,
                        queries: list | None = None,  # Can be list of strings or [query, summary] pairs
                        relevant_accounts: dict[str, bool] | None = None,
                        ideal_num_posts: int | None = None,
                        number_of_generations: int | None = None,
                        min_impressions_filter: int | None = None,
                        manual_minimum_impressions: int | None = False,  # Use False as sentinel, None means "clear override"
                        models: list[str] | None = None) -> None:
    """Update scraping settings for a user in user_info.json."""
    from backend.utlils.utils import read_user_info, write_user_info

    user_info = read_user_info(handle)
    if not user_info:
        # Create new entry if user doesn't exist
        user_info = {"handle": handle}

    # Update only the provided settings
    if queries is not None:
        # Frontend sends queries as either:
        # - Plain strings (manually added)
        # - [query, summary] arrays (edited or generated from intent)
        # Store as-is to preserve format
        user_info["queries"] = queries
    if relevant_accounts is not None:
        # Store as dict {handle: validated}
        user_info["relevant_accounts"] = relevant_accounts
    if ideal_num_posts is not None:
        user_info["ideal_num_posts"] = ideal_num_posts
    if number_of_generations is not None:
        # Validate range 1-5
        if not 1 <= number_of_generations <= 5:
            from backend.utlils.utils import error
            error("Invalid number_of_generations: must be between 1 and 5", status_code=400, function_name="write_user_settings", username=handle)
            raise ValueError("number_of_generations must be between 1 and 5")
        user_info["number_of_generations"] = number_of_generations
    if min_impressions_filter is not None:
        # Validate it's a positive integer
        if not isinstance(min_impressions_filter, int) or min_impressions_filter < 0:
            from backend.utlils.utils import error
            error("Invalid min_impressions_filter: must be a non-negative integer", status_code=400, function_name="write_user_settings", username=handle)
            raise ValueError("min_impressions_filter must be a non-negative integer")
        user_info["min_impressions_filter"] = min_impressions_filter
    # Track if we need to delete manual_minimum_impressions key
    delete_manual_override = False

    if manual_minimum_impressions is not False:  # False is our sentinel value meaning "not provided"
        # manual_minimum_impressions can be None (to clear) or an int (to set)
        if manual_minimum_impressions is None:
            # Mark for deletion after write
            delete_manual_override = True
        else:
            # Set the manual override - validate it's a positive integer
            if not isinstance(manual_minimum_impressions, int) or manual_minimum_impressions < 0:
                from backend.utlils.utils import error
                error("Invalid manual_minimum_impressions: must be a non-negative integer", status_code=400, function_name="write_user_settings", username=handle)
                raise ValueError("manual_minimum_impressions must be a non-negative integer")
            user_info["manual_minimum_impressions"] = manual_minimum_impressions
    if models is not None:
        # Validate models list is not empty
        if not models or not isinstance(models, list):
            from backend.utlils.utils import error
            error("Invalid models: must be a non-empty list of strings", status_code=400, function_name="write_user_settings", username=handle)
            raise ValueError("models must be a non-empty list of strings")
        user_info["models"] = models

    write_user_info(user_info)

    # Handle clearing manual override by explicitly setting to NULL in database
    if delete_manual_override:
        from backend.utlils.supabase_client import update_twitter_profile
        update_twitter_profile(handle, {"manual_minimum_impressions": None})
        notify(f"🧹 Cleared manual impressions override for {handle}")

    notify(f"✅ Updated settings for {handle}")


# API Router
router = APIRouter(prefix="/user", tags=["user"])


@router.get("/{handle}/info")
async def get_user_info_endpoint(handle: str) -> dict:
    """Get user information."""
    from backend.utlils.utils import error
    from backend.utlils.utils import read_user_info as get_cached_user_info

    user_info = get_cached_user_info(handle)
    if not user_info:
        error(f"User {handle} not found", status_code=404, function_name="get_user_info_endpoint", username=handle)
        raise HTTPException(status_code=404, detail=f"User {handle} not found")
    return user_info


@router.patch("/{handle}/email")
async def update_user_email_endpoint(handle: str, payload: UpdateEmailRequest) -> dict:
    """Update user email address (typically used by first-time users)."""
    from backend.utlils.utils import error, read_user_info, write_user_info

    try:
        user_info = read_user_info(handle)
        if not user_info:
            error(f"User {handle} not found", status_code=404, function_name="update_user_email_endpoint", username=handle)
            raise HTTPException(status_code=404, detail=f"User {handle} not found")

        # Update email
        user_info["email"] = payload.email
        write_user_info(user_info)

        notify(f"✅ Updated email for @{handle}")

        return {"message": "Email updated successfully", "email": payload.email}
    except HTTPException:
        raise
    except Exception as e:
        error("Error updating email", status_code=500, exception_text=str(e), function_name="update_user_email_endpoint", username=handle)
        raise HTTPException(status_code=500, detail=f"Error updating email: {str(e)}") from e


@router.get("/{handle}/settings")
async def get_settings_endpoint(handle: str) -> dict:
    """Get scraping settings for a user."""
    from backend.utlils.utils import error
    settings = read_user_settings(handle)
    if settings is None:
        error(f"User {handle} not found", status_code=404, function_name="get_settings_endpoint", username=handle)
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

        # Update the settings (models parameter removed - use dedicated endpoint)
        write_user_settings(handle=handle,
                            queries=payload.queries,
                            relevant_accounts=payload.relevant_accounts,
                            ideal_num_posts=payload.ideal_num_posts,
                            number_of_generations=payload.number_of_generations,
                            min_impressions_filter=payload.min_impressions_filter,
                            manual_minimum_impressions=payload.manual_minimum_impressions if hasattr(payload, 'manual_minimum_impressions') else False,
                            models=None)

        # Handle changes in number_of_generations
        generation_happened = False
        if payload.number_of_generations is not None and new_num_generations != old_num_generations:
            notify("✅ Number of generations changed! Starting automatic reply adjustment...")
            from backend.data.twitter.edit_cache import read_from_cache, write_to_cache
            from backend.twitter.generate_replies import generate_replies_for_tweet

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

                    updated_count = 0
                    for _idx, tweet in enumerate(tweets):
                        if "generated_replies" not in tweet or not tweet["generated_replies"]:
                            continue

                        current_reply_count = len(tweet.get("generated_replies", []))
                        needed_replies = new_num_generations - current_reply_count

                        if needed_replies <= 0:
                            continue

                        tweet_id = tweet.get('id', tweet.get('tweet_id', 'unknown'))
                        notify(f"🔄 Generating {needed_replies} additional replies for tweet {tweet_id} (currently has {current_reply_count})")

                        # Generate additional replies using the reusable function
                        new_replies = await generate_replies_for_tweet(tweet=tweet, models=models, needed_generations=needed_replies, delay_seconds=1, username=handle)

                        # Append new replies to existing ones (new_replies is array of tuples)
                        if new_replies:
                            tweet["generated_replies"].extend(new_replies)
                            updated_count += 1
                            notify(f"✅ Updated tweet {tweet_id} - now has {len(tweet['generated_replies'])} replies")

                    notify(f"✅ Updated {updated_count} tweets with additional replies")

                    # Save updated cache
                    await write_to_cache(tweets, f"Updated replies (increased to {new_num_generations})", username=handle)

                elif new_num_generations < old_num_generations:
                    # Note: We don't actually delete replies when count is reduced
                    # The frontend will just display fewer of them based on user settings
                    # This preserves all generated replies in the cache
                    notify(f"✂️ Settings reduced replies (from {old_num_generations} to {new_num_generations}) - existing replies preserved")
                    generation_happened = False  # No actual generation needed

        return {"message": "Settings updated successfully", "settings": read_user_settings(handle), "generation_happened": generation_happened}
    except Exception as e:
        from backend.utlils.utils import error
        error("Error updating settings", status_code=500, exception_text=str(e), function_name="update_settings_endpoint", username=handle)
        raise HTTPException(status_code=500, detail=f"Error updating settings: {str(e)}") from e


@router.post("/{handle}/settings/account")
async def add_account_endpoint(handle: str, account: RelevantAccountModel) -> dict:
    """Add a new account to relevant_accounts."""
    from backend.utlils.utils import error, read_user_info, write_user_info

    try:
        user_info = read_user_info(handle)
        if not user_info:
            error(f"User {handle} not found", status_code=404, function_name="add_account_endpoint", username=handle)
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
        error("Error adding account", status_code=500, exception_text=str(e), function_name="add_account_endpoint", username=handle, critical=True)
        raise HTTPException(status_code=500, detail=f"Error adding account: {str(e)}") from e


@router.patch("/{handle}/settings/account/{account}/validation")
async def update_account_validation_endpoint(handle: str, account: str, validated: bool) -> dict:
    """Update the validation status of a specific account."""
    from backend.utlils.utils import error, read_user_info, write_user_info

    try:
        user_info = read_user_info(handle)
        if not user_info:
            error(f"User {handle} not found", status_code=404, function_name="update_account_validation_endpoint", username=handle)
            raise HTTPException(status_code=404, detail=f"User {handle} not found")

        relevant_accounts = user_info.get("relevant_accounts", {})

        # Check if account exists
        if account not in relevant_accounts:
            error(f"Account @{account} not found", status_code=404, function_name="update_account_validation_endpoint", username=handle)
            raise HTTPException(status_code=404, detail=f"Account @{account} not found")

        # Update validation status
        relevant_accounts[account] = validated
        user_info["relevant_accounts"] = relevant_accounts
        write_user_info(user_info)

        return {"message": f"Validation status for @{account} updated to {validated}", "settings": read_user_settings(handle)}
    except HTTPException:
        raise
    except Exception as e:
        error("Error updating account validation", status_code=500, exception_text=str(e), function_name="update_account_validation_endpoint", username=handle)
        raise HTTPException(status_code=500, detail=f"Error updating account validation: {str(e)}") from e


@router.delete("/{handle}/settings/account/{account}")
async def remove_account_endpoint(handle: str, account: str) -> dict:
    """Remove a specific account from relevant_accounts."""
    from backend.utlils.utils import error, read_user_info, write_user_info

    try:
        user_info = read_user_info(handle)
        if not user_info:
            error(f"User {handle} not found", status_code=404, function_name="remove_account_endpoint", username=handle)
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
        error("Error removing account", status_code=500, exception_text=str(e), function_name="remove_account_endpoint", username=handle, critical=True)
        raise HTTPException(status_code=500, detail=f"Error removing account: {str(e)}") from e


@router.delete("/{handle}/settings/query")
async def remove_query_endpoint(handle: str, payload: RemoveQueryRequest) -> dict:
    """Remove a specific query from queries. Handles both plain strings and [query, summary] format."""
    from backend.utlils.utils import error, read_user_info, write_user_info

    try:
        user_info = read_user_info(handle)
        if not user_info:
            error(f"User {handle} not found", status_code=404, function_name="remove_query_endpoint", username=handle)
            raise HTTPException(status_code=404, detail=f"User {handle} not found")

        # The query to remove (the full query string)
        query_to_remove = payload.query

        queries = user_info.get("queries", [])
        updated_queries = []
        removed = False

        for q in queries:
            # Check if this is the query to remove
            query_str = q[0] if isinstance(q, list) and len(q) == 2 else q
            if query_str == query_to_remove:
                removed = True
                continue  # Skip this query (removes it)
            updated_queries.append(q)

        if removed:
            user_info["queries"] = updated_queries
            write_user_info(user_info)

        return {"message": "Query removed successfully", "settings": read_user_settings(handle)}
    except HTTPException:
        raise
    except Exception as e:
        error("Error removing query", status_code=500, exception_text=str(e), function_name="remove_query_endpoint", username=handle, critical=True)
        raise HTTPException(status_code=500, detail=f"Error removing query: {str(e)}") from e


# Model Management Endpoints
@router.put("/{handle}/models")
async def update_models_endpoint(handle: str, payload: UpdateModelsRequest) -> dict:
    """Update the list of models for content generation. Admin-only endpoint."""
    from backend.utlils.utils import error, read_user_info, write_user_info

    try:
        user_info = read_user_info(handle)
        if not user_info:
            error(f"User {handle} not found", status_code=404, function_name="update_models_endpoint", username=handle)
            raise HTTPException(status_code=404, detail=f"User {handle} not found")

        # Validate models list
        if not payload.models or not isinstance(payload.models, list):
            error("Invalid models: must be a non-empty list", status_code=400, function_name="update_models_endpoint", username=handle)
            raise HTTPException(status_code=400, detail="models must be a non-empty list of strings")

        # Update models
        user_info["models"] = payload.models
        write_user_info(user_info)

        notify(f"✅ Updated models for @{handle}: {payload.models}")

        return {"message": "Models updated successfully", "models": payload.models}
    except HTTPException:
        raise
    except Exception as e:
        error("Error updating models", status_code=500, exception_text=str(e), function_name="update_models_endpoint", username=handle, critical=True)
        raise HTTPException(status_code=500, detail="Error updating models: " + str(e)) from e


@router.get("/{handle}/models")
async def get_models_endpoint(handle: str) -> dict:
    """Get the list of models configured for a user."""
    from backend.utlils.utils import error, read_user_info

    try:
        user_info = read_user_info(handle)
        if not user_info:
            error(f"User {handle} not found", status_code=404, function_name="get_models_endpoint", username=handle)
            raise HTTPException(status_code=404, detail=f"User {handle} not found")

        models = user_info.get("models", ["claude-3-5-sonnet-20241022"])

        return {"models": models}
    except HTTPException:
        raise
    except Exception as e:
        error("Error getting models", status_code=500, exception_text=str(e), function_name="get_models_endpoint", username=handle)
        raise HTTPException(status_code=500, detail="Error getting models: " + str(e)) from e


@router.get("/{username}/validate/{twitter_handle}")
async def validate_twitter_handle(username: str, twitter_handle: str) -> dict:
    """Validate if a Twitter handle exists by checking Twitter's API with rate limit retry."""
    from time import sleep

    import requests

    from backend.twitter.authentication import ensure_access_token
    from backend.twitter.rate_limiter import EndpointType, twitter_rate_limiter
    from backend.utlils.utils import error

    try:
        # Remove @ if present
        handle = twitter_handle.lstrip('@')

        # Get user access token
        access_token = await ensure_access_token(username)

        if not access_token:
            error("User not authenticated", status_code=401, function_name="validate_twitter_handle", username=username, critical=False)
            raise HTTPException(status_code=401, detail="AUTHENTICATION_REQUIRED")

        # Wait for rate limiter (USER_LOOKUP endpoint: 100 req/15min)
        await twitter_rate_limiter.wait_if_needed(EndpointType.USER_LOOKUP)

        # Check if user exists with retry logic for rate limiting
        url = f"https://api.twitter.com/2/users/by/username/{handle}"
        headers = {"Authorization": f"Bearer {access_token}"}

        response = requests.get(url, headers=headers, timeout=10)
        twitter_rate_limiter.update_last_request(EndpointType.USER_LOOKUP)

        if response.status_code == 200:
            data = response.json()
            user_data = data.get("data")
            # Check if we got valid user data
            if user_data:
                return {"valid": True, "handle": handle, "data": user_data}
            else:
                return {"valid": False, "handle": handle, "error": "User not found"}
        elif response.status_code == 429:
            # Rate limited - wait and retry
            reset_time = response.headers.get("x-rate-limit-reset")
            if reset_time:
                await twitter_rate_limiter.wait_for_reset(int(reset_time), EndpointType.USER_LOOKUP)
            return await validate_twitter_handle(username, twitter_handle)

        return {"valid": False, "handle": handle, "error": f"{response.text} (status {response.status_code})"}
    except Exception as e:
        return {"valid": False, "handle": handle, "error": f"Unknown error occurred: {str(e)}"}
