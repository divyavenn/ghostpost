"""Functions for reading and writing to the tweet cache."""

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from backend.config import CACHE_DIR, MAX_TWEET_AGE_HOURS
from backend.utlils.utils import _cache_key, atomic_file_update, error, notify

USERNAME = "proudlurker"


def get_user_tweet_cache(username=USERNAME) -> Path:
    return CACHE_DIR / f"{_cache_key(username)}_tweets.json"


async def write_to_cache(tweets, description: str, *, username=USERNAME) -> Path:
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

    path = get_user_tweet_cache(username)
    atomic_file_update(path, all_tweets, ".tmp", ensure_ascii=False)
    # notify(f"💾{description} and wrote to cache")

    # Track newly written tweets in seen_tweets
    from backend.utlils.utils import add_to_seen_tweets
    tweet_ids_to_track = []
    for tweet in tweets:
        tweet_id = tweet.get("id") or tweet.get("tweet_id")
        if tweet_id:
            tweet_ids_to_track.append(str(tweet_id))

    if tweet_ids_to_track:
        add_to_seen_tweets(username, tweet_ids_to_track)

    # Log each tweet being written
    for tweet in tweets:
        tweet_id = tweet.get("id") or tweet.get("tweet_id")
        cache_id = tweet.get("cache_id")
        if tweet_id and cache_id:
            metadata = {"cache_id": cache_id}

            # If this tweet has generated_replies, include first 250 chars of original tweet + all replies with model info
            # generated_replies is now an array of tuples: [(reply_text, model_name), ...]
            generated_replies = tweet.get("generated_replies")
            if generated_replies:
                thread = tweet.get("thread", [])
                # Join thread parts and get first 250 characters
                original_text = " ".join(thread) if isinstance(thread, list) else str(thread)
                original_text_preview = original_text[:250]

                metadata["original_tweet_preview"] = original_text_preview

                # Include model information for each reply
                replies_with_models = []
                for idx, reply_data in enumerate(generated_replies):
                    # Handle tuple format: (reply_text, model_name)
                    if isinstance(reply_data, tuple) and len(reply_data) >= 2:
                        reply_text, model_name = reply_data[0], reply_data[1]
                    else:
                        # Fallback for any legacy format
                        reply_text = reply_data
                        model_name = "unknown"

                    replies_with_models.append({"reply_index": idx, "model": model_name, "text": reply_text})

                metadata["generated_replies"] = replies_with_models

            log_tweet_action(username, TweetAction.WRITTEN, str(tweet_id), metadata=metadata)

    return path


async def read_from_cache(username=USERNAME) -> list[dict[str, Any]]:
    from pydantic import ValidationError

    from backend.data.twitter.data_validation import ScrapedTweet

    path = get_user_tweet_cache(username)
    # notify(f"💾 Reading tweets from cache ({path.name})")
    if not path.exists():
        return []
    try:
        raw_tweets = json.loads(path.read_text())

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
    except Exception as exc:
        error("Error reading JSON file", exception_text=str(exc), function_name="read_from_cache")
        return []


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
        path = get_user_tweet_cache(username)
        atomic_file_update(path, kept_tweets, ".tmp", ensure_ascii=False)
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
        path = get_user_tweet_cache(username)
        atomic_file_update(path, kept_tweets, ".tmp", ensure_ascii=False)
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
        path = get_user_tweet_cache(username)
        atomic_file_update(path, kept_tweets, ".tmp", ensure_ascii=False)
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
        if t.get("id") == tweet_id or t.get("tweet_id") == tweet_id:
            tweet_to_delete = t
            break

    if not tweet_to_delete:
        return False  # Tweet not found

    cache_id = tweet_to_delete.get("cache_id")
    deleted_reply = tweet_to_delete.get("reply", "")

    # Remove the tweet
    tweets = [t for t in tweets if t.get("id") != tweet_id and t.get("tweet_id") != tweet_id]

    # Write to cache without logging (to avoid duplicate WRITTEN logs)
    path = get_user_tweet_cache(username)
    atomic_file_update(path, tweets, ".tmp", ensure_ascii=False)
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
            generated_replies = [(old_single_reply, "unknown")]
        else:
            return False

    if reply_index < 0 or reply_index >= len(generated_replies):
        return False

    # Extract old reply and model from tuple
    reply_data = generated_replies[reply_index]
    if isinstance(reply_data, tuple) and len(reply_data) >= 2:
        old_reply, model_name = reply_data[0], reply_data[1]
    else:
        # Fallback for legacy format
        old_reply = reply_data
        model_name = "unknown"

    cache_id = tweet.get("cache_id")
    original_tweet_id = tweet.get("id")  # The tweet this reply is responding to

    # Generate diff
    diff = list(difflib.unified_diff(old_reply.splitlines(keepends=True), new_reply.splitlines(keepends=True), lineterm='', fromfile='old_reply', tofile='new_reply'))

    # Update the specific reply - keep the model name, update the text
    generated_replies[reply_index] = (new_reply, model_name)
    tweet["generated_replies"] = generated_replies

    # Mark tweet as edited
    tweet["edited"] = True

    # Write to cache without logging (to avoid duplicate WRITTEN logs)
    path = get_user_tweet_cache(username)
    atomic_file_update(path, tweets, ".tmp", ensure_ascii=False)
    notify(f"💾 Edited reply {reply_index} for tweet {tweet_id}")

    # Log the edit with comprehensive metadata including reply index and model
    metadata = {"cache_id": cache_id, "reply_index": reply_index, "model": model_name, "new_reply": new_reply, "diff": "".join(diff), "replying_to_tweet_id": original_tweet_id}

    log_tweet_action(username, TweetAction.EDITED, tweet_id, metadata=metadata)
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


def remove_user_cache(username: str, key: str) -> bool:
    cache_removed = False
    tweet_cache = CACHE_DIR / f"{_cache_key(username)}_tweets.json"
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
        path = get_user_tweet_cache(username)
        atomic_file_update(path, tweets, ".tmp", ensure_ascii=False)

    return {"message": f"Marked {marked_count} tweets as seen", "marked_count": marked_count}


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
