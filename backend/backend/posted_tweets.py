"""
Endpoint for retrieving posted tweets with pagination.
Combines log data with cached tweet information.
"""
import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query

from backend.log_interactions import TweetAction, get_user_log_path
from backend.tweets_cache import get_user_tweet_cache
from backend.utils import _cache_key

router = APIRouter(prefix="/posted", tags=["posted"])


def get_posted_tweets(username: str, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    """
    Get posted tweets for a user from logs, enriched with full tweet data from cache.

    Args:
        username: Twitter handle
        limit: Number of tweets to return (default 50)
        offset: Number of tweets to skip from the end (default 0)

    Returns:
        List of tweet objects with full data, sorted by post time (newest first)
    """
    log_path = get_user_log_path(username)

    if not log_path.exists():
        return []

    # Read all posted actions from log
    posted_entries = []
    try:
        with open(log_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entry = json.loads(line)
                        if entry.get("action") == TweetAction.POSTED.value:
                            posted_entries.append(entry)
                    except json.JSONDecodeError:
                        continue
    except Exception:
        return []

    # Reverse to get newest first, then apply pagination
    posted_entries.reverse()

    # Apply offset and limit
    start_idx = offset
    end_idx = offset + limit
    paginated_entries = posted_entries[start_idx:end_idx]

    # Load tweet cache to enrich data
    cache_path = get_user_tweet_cache(username)
    tweets_by_cache_id = {}

    if cache_path.exists():
        try:
            with open(cache_path, encoding="utf-8") as f:
                tweets = json.load(f)
                for tweet in tweets:
                    cache_id = tweet.get("cache_id")
                    if cache_id:
                        tweets_by_cache_id[cache_id] = tweet
        except Exception:
            pass

    # Enrich posted entries with full tweet data
    result = []
    for entry in paginated_entries:
        metadata = entry.get("metadata", {})
        cache_id = metadata.get("cache_id")
        posted_tweet_id = metadata.get("posted_tweet_id")
        posted_text = metadata.get("text", "")
        timestamp = entry.get("timestamp")

        # Try to get full tweet data from cache
        tweet_data = tweets_by_cache_id.get(cache_id, {})

        # Build the response object
        posted_tweet = {
            "id": entry.get("tweet_id"),  # Original tweet ID that was replied to
            "posted_tweet_id": posted_tweet_id,  # Twitter's ID for the posted reply
            "cache_id": cache_id,
            "reply": posted_text,  # The text that was posted
            "posted_at": timestamp,
            # Include full tweet data if available
            **tweet_data
        }

        result.append(posted_tweet)

    return result


@router.get("/{username}/tweets")
async def get_posted_tweets_endpoint(
    username: str,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
) -> dict[str, Any]:
    """
    Get posted tweets for a user with pagination.

    Args:
        username: Twitter handle
        limit: Number of tweets to return (1-100, default 50)
        offset: Number of tweets to skip from most recent (default 0)

    Returns:
        Dict with username, count, limit, offset, and tweets list
    """
    tweets = get_posted_tweets(username, limit=limit, offset=offset)

    return {
        "username": username,
        "count": len(tweets),
        "limit": limit,
        "offset": offset,
        "tweets": tweets
    }
