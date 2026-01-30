"""Functions for reading and writing to the tweet cache (Supabase Storage)."""

import json
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from backend.config import MAX_TWEET_AGE_HOURS
from backend.utlils.utils import error, notify

USERNAME = "proudlurker"


async def write_to_cache(tweets, description: str, *, username=USERNAME) -> None:
    import uuid

    from pydantic import ValidationError

    from backend.data.twitter.data_validation import ScrapedTweet
    from backend.twitter.logging import TweetAction, log_tweet_action

    # Read existing cache
    existing_tweets = await read_from_cache(username)

    # Create a map of existing tweets by ID for quick lookup
    existing_map = {}
    for t in existing_tweets:
        tweet_id = t.get("id") or t.get("tweet_id")
        if tweet_id:
            existing_map[str(tweet_id)] = t

    # Add cache_id to each tweet if not present and merge with existing
    for tweet in tweets:
        tweet_id = tweet.get("id") or tweet.get("tweet_id")

        # If tweet exists, update it; otherwise add cache_id
        if tweet_id and str(tweet_id) in existing_map:
            # Update existing tweet
            existing_map[str(tweet_id)].update(tweet)
        else:
            # New tweet - add cache_id if not present
            if "cache_id" not in tweet:
                tweet["cache_id"] = str(uuid.uuid4())
            if tweet_id:
                existing_map[str(tweet_id)] = tweet

    # Convert back to list and validate each tweet
    all_tweets = []
    for tweet_data in existing_map.values():
        try:
            validated = ScrapedTweet(**tweet_data)
            all_tweets.append(validated.model_dump())
        except ValidationError as e:
            tweet_id = tweet_data.get("id", "unknown")
            error(f"Invalid tweet data for tweet {tweet_id}", status_code=500, exception_text=str(e), function_name="write_to_cache", username=username)
            # Still include the tweet but log the error
            all_tweets.append(tweet_data)

    # Write to Supabase Storage
    from backend.utlils.supabase_client import upload_scraped_tweets
    upload_scraped_tweets(username, json.dumps(all_tweets, ensure_ascii=False))
    # notify(f"💾{description} and wrote to Supabase Storage")

    # Track newly written tweets in seen_tweets (store only IDs)
    from backend.utlils.utils import add_to_seen_tweets
    tweet_ids = [t.get("id") or t.get("tweet_id") for t in tweets if t.get("id") or t.get("tweet_id")]
    add_to_seen_tweets(username, tweet_ids)


async def read_from_cache(username=USERNAME) -> list[dict[str, Any]]:
    from pydantic import ValidationError

    from backend.data.twitter.data_validation import ScrapedTweet
    from backend.utlils.supabase_client import download_scraped_tweets

    # Read from Supabase Storage
    data = download_scraped_tweets(username)
    if not data:
        return []

    try:
        raw_tweets = json.loads(data)
    except Exception as exc:
        error("Error parsing JSON from Supabase Storage", exception_text=str(exc), function_name="read_from_cache")
        return []

    # Validate each tweet
    validated_tweets = []
    for idx, tweet in enumerate(raw_tweets):
        try:
            validated = ScrapedTweet(**tweet)
            validated_tweets.append(validated.model_dump())
        except ValidationError as e:
            tweet_id = tweet.get("id", f"index_{idx}")
            error(f"Invalid tweet data for tweet {tweet_id}", status_code=500, exception_text=str(e), function_name="read_from_cache", username=username)
            # Include invalid tweet but log the error
            validated_tweets.append(tweet)

    return validated_tweets


async def purge_unedited_tweets(username: str, only_seen: bool = False) -> int:
    """Purge unedited tweets from cache.

    Args:
        username: The username whose cache to clean
        only_seen: If True, only purge tweets that are BOTH unedited AND seen.
                   If False, purge ALL unedited tweets (original behavior).

    Returns:
        Number of tweets removed
    """
    from backend.twitter.logging import TweetAction, log_tweet_action

    tweets = await read_from_cache(username)

    if not tweets:
        return 0

    # Separate tweets into kept and removed
    kept_tweets = []
    removed_tweets = []

    for tweet in tweets:
        is_edited = tweet.get("edited", False)
        is_seen = tweet.get("seen", False)

        # Keep tweets that have been edited
        if is_edited:
            kept_tweets.append(tweet)
        # If only_seen mode, only remove if BOTH unedited AND seen
        elif only_seen and not is_seen:
            kept_tweets.append(tweet)  # Keep unseen tweets
        else:
            removed_tweets.append(tweet)

    removed_count = len(removed_tweets)

    # Write back if any were removed
    if removed_count > 0:
        from backend.utlils.supabase_client import upload_scraped_tweets
        upload_scraped_tweets(username, json.dumps(kept_tweets, ensure_ascii=False))
        notify(f"🧹 Purged {removed_count} unedited tweet(s) from cache")

        # Log deletion for each removed tweet
        for tweet in removed_tweets:
            tweet_id = tweet.get("id") or tweet.get("tweet_id")
            cache_id = tweet.get("cache_id")
            if tweet_id:
                metadata = {"reason": "unedited"}
                if cache_id:
                    metadata["cache_id"] = cache_id
                # Add original tweet info for intent filtering examples
                original_thread = tweet.get("thread", [])
                if original_thread:
                    metadata["original_tweet_text"] = " | ".join(original_thread)
                original_handle = tweet.get("handle", "")
                if original_handle:
                    metadata["original_handle"] = original_handle
                log_tweet_action(username, TweetAction.DELETED, str(tweet_id), metadata=metadata)

    return removed_count


async def purge_empty_thread_tweets(username: str) -> int:
    """Purge tweets that have no thread content from cache and seen_tweets.

    These tweets cannot have replies generated for them, so they should be
    removed to allow re-scraping with proper thread content.

    Args:
        username: The username whose cache to clean

    Returns:
        Number of tweets removed
    """
    from backend.twitter.logging import TweetAction, log_tweet_action
    from backend.utlils.utils import remove_from_seen_tweets

    tweets = await read_from_cache(username)

    if not tweets:
        return 0

    # Separate tweets into kept and removed
    kept_tweets = []
    removed_tweets = []
    removed_ids = []

    for tweet in tweets:
        thread = tweet.get("thread", [])
        has_thread_content = thread and len(thread) > 0

        if has_thread_content:
            kept_tweets.append(tweet)
        else:
            removed_tweets.append(tweet)
            tweet_id = tweet.get("id") or tweet.get("tweet_id")
            if tweet_id:
                removed_ids.append(str(tweet_id))

    removed_count = len(removed_tweets)

    # Write back if any were removed
    if removed_count > 0:
        from backend.utlils.supabase_client import upload_scraped_tweets
        upload_scraped_tweets(username, json.dumps(kept_tweets, ensure_ascii=False))
        notify(f"🧹 Purged {removed_count} tweet(s) with empty thread from cache")

        # Also remove from seen_tweets so they can be re-scraped
        if removed_ids:
            remove_from_seen_tweets(username, removed_ids)

        # Log deletion for each removed tweet
        for tweet in removed_tweets:
            tweet_id = tweet.get("id") or tweet.get("tweet_id")
            cache_id = tweet.get("cache_id")
            if tweet_id:
                metadata = {"reason": "empty_thread"}
                if cache_id:
                    metadata["cache_id"] = cache_id
                original_handle = tweet.get("handle", "")
                if original_handle:
                    metadata["original_handle"] = original_handle
                log_tweet_action(username, TweetAction.DELETED, str(tweet_id), metadata=metadata)

    return removed_count


async def cleanup_old_tweets(username: str, hours: int = MAX_TWEET_AGE_HOURS) -> int:
    """Remove tweets older than the specified hours from cache.

    Args:
        username: The username whose cache to clean
        hours: Age threshold in hours (default: MAX_TWEET_AGE_HOURS)

    Returns:
        Number of tweets removed
    """
    from datetime import datetime, timedelta

    from backend.twitter.logging import TweetAction, log_tweet_action

    try:  # Python 3.11+
        from datetime import UTC  # type: ignore[attr-defined]
    except ImportError:  # Python <3.11
        from datetime import timezone
        UTC = timezone.utc

    def parse_twitter_date(s: str) -> datetime:
        """Parse Twitter's date format: 'Sat Oct 11 15:07:12 +0000 2025'"""
        return datetime.strptime(s, "%a %b %d %H:%M:%S %z %Y")

    tweets = await read_from_cache(username)

    if not tweets:
        return 0

    now = datetime.now(UTC)
    cutoff = now - timedelta(hours=hours)

    # Separate tweets into kept and removed
    kept_tweets = []
    removed_tweets = []

    for tweet in tweets:
        created_at = tweet.get("created_at")
        if not created_at:
            # Keep tweets without a created_at timestamp
            kept_tweets.append(tweet)
            continue

        try:
            tweet_date = parse_twitter_date(created_at)
            if tweet_date >= cutoff:
                kept_tweets.append(tweet)
            else:
                removed_tweets.append(tweet)
        except Exception:
            # If we can't parse the date, keep the tweet
            kept_tweets.append(tweet)

    removed_count = len(removed_tweets)

    # Write back if any were removed
    if removed_count > 0:
        from backend.utlils.supabase_client import upload_scraped_tweets
        upload_scraped_tweets(username, json.dumps(kept_tweets, ensure_ascii=False))
        notify(f"🧹 Cleaned {removed_count} tweet(s) older than {hours}h from cache")

        # Log deletion for each removed tweet
        for tweet in removed_tweets:
            tweet_id = tweet.get("id") or tweet.get("tweet_id")
            cache_id = tweet.get("cache_id")
            if tweet_id:
                metadata = {"reason": "aged_out", "age_threshold_hours": hours}
                if cache_id:
                    metadata["cache_id"] = cache_id
                # Add original tweet info for intent filtering examples
                original_thread = tweet.get("thread", [])
                if original_thread:
                    metadata["original_tweet_text"] = " | ".join(original_thread)
                original_handle = tweet.get("handle", "")
                if original_handle:
                    metadata["original_handle"] = original_handle
                log_tweet_action(username, TweetAction.DELETED, str(tweet_id), metadata=metadata)

    return removed_count


def get_tweet_by_id(tweets: list[dict[str, Any]], tweet_id: str) -> dict[str, Any] | None:
    """Find a tweet in the list by its ID."""
    for tweet in tweets:
        if tweet.get("id") == tweet_id or tweet.get("tweet_id") == tweet_id:
            return tweet
    return None


async def delete_tweet(username: str, tweet_id: str, log_deletion: bool = True) -> bool:
    """Delete a tweet from the user's cache by tweet_id.

    Args:
        username: The username who owns the cache
        tweet_id: The ID of the tweet to delete
        log_deletion: Whether to log this deletion (False when deleting after posting)
    """
    from backend.twitter.logging import TweetAction, log_tweet_action

    tweets = await read_from_cache(username)

    # Find the tweet to get its cache_id and reply before deletion
    tweet_to_delete = None
    for t in tweets:
        if t.get("id") == tweet_id or t.get("tweet_id") == tweet_id or t.get("cache_id") == tweet_id:
            tweet_to_delete = t
            break

    if not tweet_to_delete:
        return False  # Tweet not found

    cache_id = tweet_to_delete.get("cache_id")
    deleted_reply = tweet_to_delete.get("reply", "")

    # Remove the tweet
    tweets = [t for t in tweets if t.get("id") != tweet_id and t.get("tweet_id") != tweet_id and t.get("cache_id") != tweet_id]

    # Write to cache without logging (to avoid duplicate WRITTEN logs)
    from backend.utlils.supabase_client import upload_scraped_tweets
    upload_scraped_tweets(username, json.dumps(tweets, ensure_ascii=False))
    notify(f"💾 Deleted tweet {tweet_id}")

    # Log the deletion only if requested (skip when deleting after posting)
    if log_deletion:
        metadata = {}
        if cache_id:
            metadata["cache_id"] = cache_id
        if deleted_reply:
            metadata["deleted_reply"] = deleted_reply

        # Add original tweet info for intent filtering examples
        original_thread = tweet_to_delete.get("thread", [])
        if original_thread:
            metadata["original_tweet_text"] = " | ".join(original_thread)
        original_handle = tweet_to_delete.get("handle", "")
        if original_handle:
            metadata["original_handle"] = original_handle

        log_tweet_action(username, TweetAction.DELETED, tweet_id, metadata=metadata if metadata else None)
    return True


async def edit_tweet_reply(username: str, tweet_id: str, new_reply: str, reply_index: int = 0) -> bool:
    """Edit the reply text for a specific tweet in the cache at a specific index."""
    import difflib

    from backend.twitter.logging import TweetAction, log_tweet_action

    tweets = await read_from_cache(username)

    tweet = get_tweet_by_id(tweets, tweet_id)
    if not tweet:
        return False

    # Handle tuple format: [(reply_text, model_name), ...]
    generated_replies = tweet.get("generated_replies", [])
    if not generated_replies:
        # Backward compatibility: check for old "reply" field
        old_single_reply = tweet.get("reply")
        if old_single_reply:
            generated_replies = [(old_single_reply, "unknown", "unknown")]
        else:
            return False

    if reply_index < 0 or reply_index >= len(generated_replies):
        return False

    # Extract old reply, model, and prompt variant from tuple
    reply_data = generated_replies[reply_index]
    if isinstance(reply_data, (list, tuple)) and len(reply_data) >= 2:
        old_reply = reply_data[0]
        model_name = reply_data[1]
        prompt_variant = reply_data[2] if len(reply_data) >= 3 else "unknown"
    else:
        # Fallback for legacy format
        old_reply = reply_data
        model_name = "unknown"
        prompt_variant = "unknown"

    cache_id = tweet.get("cache_id")
    original_tweet_id = tweet.get("id")  # The tweet this reply is responding to

    # Generate diff
    diff = list(difflib.unified_diff(old_reply.splitlines(keepends=True), new_reply.splitlines(keepends=True), lineterm='', fromfile='old_reply', tofile='new_reply'))

    # Update the specific reply - keep the model name and prompt variant, update the text
    generated_replies[reply_index] = (new_reply, model_name, prompt_variant)
    tweet["generated_replies"] = generated_replies

    # Mark tweet as edited
    tweet["edited"] = True

    # Write to cache without logging (to avoid duplicate WRITTEN logs)
    from backend.utlils.supabase_client import upload_scraped_tweets
    upload_scraped_tweets(username, json.dumps(tweets, ensure_ascii=False))
    notify(f"💾 Edited reply {reply_index} for tweet {tweet_id}")

    return True


async def update_tweet_field(username: str, tweet_id: str, field: str, value: Any) -> bool:
    """Update any field in a specific tweet in the cache."""
    tweets = await read_from_cache(username)

    tweet = get_tweet_by_id(tweets, tweet_id)
    if not tweet:
        return False

    tweet[field] = value

    await write_to_cache(tweets, f"Updated {field} for tweet {tweet_id}", username=username)
    return True


async def get_single_tweet(username: str, tweet_id: str) -> dict[str, Any] | None:
    """Get a single tweet from the cache by tweet_id."""
    tweets = await read_from_cache(username)
    return get_tweet_by_id(tweets, tweet_id)


def remove_user_cache(username: str) -> bool:
    """Remove user's scraped tweets from Supabase Storage."""
    from backend.utlils.supabase_client import delete_scraped_tweets
    return delete_scraped_tweets(username)


# API Router
router = APIRouter(prefix="/tweets", tags=["tweets"])


class EditReplyRequest(BaseModel):
    new_reply: str
    reply_index: int = 0


@router.get("/{username}")
async def get_tweets(username: str) -> list[dict[str, Any]]:
    """Get all cached tweets for a given username."""
    tweets = await read_from_cache(username)
    return tweets


@router.delete("/{username}/{tweet_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tweet_endpoint(username: str, tweet_id: str, log_deletion: bool = True) -> None:
    """Delete a tweet from the user's cache.

    Args:
        username: The username who owns the cache
        tweet_id: The ID of the tweet to delete
        log_deletion: Whether to log this deletion (default True, use False when deleting after posting)
    """
    from backend.utlils.utils import error
    deleted = await delete_tweet(username, tweet_id, log_deletion=log_deletion)
    if not deleted:
        error(f"Tweet {tweet_id} not found for user {username}", status_code=404, function_name="delete_tweet_endpoint", username=username)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tweet {tweet_id} not found for user {username}",
        )


@router.patch("/{username}/{tweet_id}/reply")
async def edit_reply_endpoint(username: str, tweet_id: str, payload: EditReplyRequest) -> dict[str, Any]:
    """Edit the reply text for a specific tweet at a specific index."""
    from backend.utlils.utils import error
    updated = await edit_tweet_reply(username, tweet_id, payload.new_reply, payload.reply_index)
    if not updated:
        error(f"Tweet {tweet_id} not found for user {username} or invalid reply index", status_code=404, function_name="edit_reply_endpoint", username=username, critical=True)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tweet {tweet_id} not found for user {username} or invalid reply index",
        )
    return {"message": "Reply updated successfully", "tweet_id": tweet_id, "reply_index": payload.reply_index}


@router.get("/{username}/{tweet_id}")
async def get_single_tweet_endpoint(username: str, tweet_id: str) -> dict[str, Any]:
    """Get a single tweet by ID."""
    from backend.utlils.utils import error
    tweet = await get_single_tweet(username, tweet_id)
    if not tweet:
        error(f"Tweet {tweet_id} not found for user {username}", status_code=404, function_name="get_single_tweet_endpoint", username=username)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tweet {tweet_id} not found for user {username}",
        )
    return tweet


@router.post("/{username}/cleanup")
async def cleanup_tweets_endpoint(username: str, hours: int = MAX_TWEET_AGE_HOURS) -> dict[str, Any]:
    removed_count = await cleanup_old_tweets(username, hours)
    return {
        "message": f"Cleanup completed for user {username}",
        "removed_count": removed_count,
        "age_threshold_hours": hours,
    }


class MarkSeenRequest(BaseModel):
    tweet_ids: list[str]


@router.post("/{username}/mark-seen")
async def mark_tweets_seen_endpoint(username: str, payload: MarkSeenRequest) -> dict[str, Any]:
    """Mark multiple tweets as seen (user scrolled past them in the UI)."""
    tweets = await read_from_cache(username)

    if not tweets:
        return {"message": "No tweets in cache", "marked_count": 0}

    # Build a map for quick lookup
    tweet_map = {}
    for t in tweets:
        tid = t.get("id") or t.get("tweet_id")
        if tid:
            tweet_map[str(tid)] = t

    marked_count = 0
    for tweet_id in payload.tweet_ids:
        if tweet_id in tweet_map and not tweet_map[tweet_id].get("seen", False):
            tweet_map[tweet_id]["seen"] = True
            marked_count += 1

    if marked_count > 0:
        from backend.utlils.supabase_client import upload_scraped_tweets
        upload_scraped_tweets(username, json.dumps(tweets, ensure_ascii=False))

    return {"message": f"Marked {marked_count} tweets as seen", "marked_count": marked_count}


@router.post("/{username}/mark-unseen")
async def mark_tweets_unseen_endpoint(username: str, payload: MarkSeenRequest) -> dict[str, Any]:
    """Mark multiple tweets as NOT seen (e.g., freshly scraped tweets).

    This is used to protect newly scraped tweets from being removed by 'clear seen'.
    """
    tweets = await read_from_cache(username)

    if not tweets:
        return {"message": "No tweets in cache", "marked_count": 0}

    # Build a map for quick lookup
    tweet_map = {}
    for t in tweets:
        tid = t.get("id") or t.get("tweet_id")
        if tid:
            tweet_map[str(tid)] = t

    marked_count = 0
    for tweet_id in payload.tweet_ids:
        if tweet_id in tweet_map and tweet_map[tweet_id].get("seen", False):
            tweet_map[tweet_id]["seen"] = False
            marked_count += 1

    if marked_count > 0:
        from backend.utlils.supabase_client import upload_scraped_tweets
        upload_scraped_tweets(username, json.dumps(tweets, ensure_ascii=False))

    return {"message": f"Marked {marked_count} tweets as unseen", "marked_count": marked_count}


@router.post("/{username}/purge-seen")
async def purge_seen_tweets_endpoint(username: str) -> dict[str, Any]:
    """Purge tweets that are both seen AND unedited.

    This is the user-triggered cleanup - only removes tweets the user has
    scrolled past and not interacted with.
    """
    removed_count = await purge_unedited_tweets(username, only_seen=True)
    return {
        "message": f"Purged {removed_count} seen and unedited tweets",
        "removed_count": removed_count,
    }
