"""Functions for reading and writing to the tweet cache."""

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from backend.utils import atomic_file_update, _cache_key

BACKEND_DIR = Path(__file__).resolve().parent
CACHE_DIR = BACKEND_DIR / "cache"
USERNAME = "proudlurker"


def notify(msg: str):
    print(msg)


def error(msg: str):
    raise RuntimeError(f"❌ {msg}")


def get_user_tweet_cache(username=USERNAME) -> Path:
    return CACHE_DIR / f"{_cache_key(username)}_tweets.json"


async def write_to_cache(tweets, description: str, *, username=USERNAME) -> Path:
    import uuid
    from backend.log_interactions import TweetAction, log_tweet_action

    # Add cache_id to each tweet if not present
    for tweet in tweets:
        if "cache_id" not in tweet:
            tweet["cache_id"] = str(uuid.uuid4())

    path = get_user_tweet_cache(username)
    atomic_file_update(path, tweets, ".tmp", ensure_ascii=False)
    notify(f"💾{description} and wrote to cache")

    # Log each tweet being written
    for tweet in tweets:
        tweet_id = tweet.get("id") or tweet.get("tweet_id")
        cache_id = tweet.get("cache_id")
        if tweet_id and cache_id:
            log_tweet_action(
                username,
                TweetAction.WRITTEN,
                str(tweet_id),
                metadata={"cache_id": cache_id}
            )

    return path


async def read_from_cache(username=USERNAME) -> list[dict[str, Any]]:
    path = get_user_tweet_cache(username)
    notify(f"💾 Reading tweets from cache ({path.name})")
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text())
    except Exception as exc:
        error(f"Error reading JSON file: {exc}")
        return []


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
    from backend.log_interactions import TweetAction, log_tweet_action

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

        log_tweet_action(
            username,
            TweetAction.DELETED,
            tweet_id,
            metadata=metadata if metadata else None
        )
    return True


async def edit_tweet_reply(username: str, tweet_id: str, new_reply: str) -> bool:
    """Edit the reply text for a specific tweet in the cache."""
    from backend.log_interactions import TweetAction, log_tweet_action
    import difflib

    tweets = await read_from_cache(username)

    tweet = get_tweet_by_id(tweets, tweet_id)
    if not tweet:
        return False

    old_reply = tweet.get("reply", "")
    cache_id = tweet.get("cache_id")
    original_tweet_id = tweet.get("id")  # The tweet this reply is responding to

    # Generate diff
    diff = list(difflib.unified_diff(
        old_reply.splitlines(keepends=True),
        new_reply.splitlines(keepends=True),
        lineterm='',
        fromfile='old_reply',
        tofile='new_reply'
    ))

    tweet["reply"] = new_reply

    # Write to cache without logging (to avoid duplicate WRITTEN logs)
    path = get_user_tweet_cache(username)
    atomic_file_update(path, tweets, ".tmp", ensure_ascii=False)
    notify(f"💾 Edited reply for tweet {tweet_id}")

    # Log the edit with comprehensive metadata
    metadata = {
        "cache_id": cache_id,
        "new_reply": new_reply,
        "diff": "".join(diff),
        "replying_to_tweet_id": original_tweet_id
    }

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
    deleted = await delete_tweet(username, tweet_id, log_deletion=log_deletion)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tweet {tweet_id} not found for user {username}",
        )


@router.patch("/{username}/{tweet_id}/reply")
async def edit_reply_endpoint(
    username: str, tweet_id: str, payload: EditReplyRequest
) -> dict[str, str]:
    """Edit the reply text for a specific tweet."""
    updated = await edit_tweet_reply(username, tweet_id, payload.new_reply)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tweet {tweet_id} not found for user {username}",
        )
    return {"message": "Reply updated successfully", "tweet_id": tweet_id}


@router.get("/{username}/{tweet_id}")
async def get_single_tweet_endpoint(username: str, tweet_id: str) -> dict[str, Any]:
    """Get a single tweet by ID."""
    tweet = await get_single_tweet(username, tweet_id)
    if not tweet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tweet {tweet_id} not found for user {username}",
        )
    return tweet