"""
DEPRECATED: This endpoint is replaced by /performance/{username}/posted-tweets
Kept for backward compatibility.

Endpoint for retrieving posted tweets with pagination.
Now redirects to the new posted_tweets.json cache.
"""
from typing import Any

from fastapi import APIRouter, Query

from backend.posted_tweets_cache import read_posted_tweets_cache

router = APIRouter(prefix="/posted", tags=["posted"])


def get_posted_tweets(username: str, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    """
    Get posted tweets for a user from posted_tweets.json cache.

    Args:
        username: Twitter handle
        limit: Number of tweets to return (default 50)
        offset: Number of tweets to skip from the start (default 0)

    Returns:
        List of tweet objects with metrics, sorted by post time (newest first)
    """
    # Read from new posted_tweets.json cache
    tweets = read_posted_tweets_cache(username)

    # Apply pagination
    start_idx = offset
    end_idx = offset + limit
    return tweets[start_idx:end_idx]


@router.get("/{username}/tweets")
async def get_posted_tweets_endpoint(username: str, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)) -> dict[str, Any]:
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

    return {"username": username, "count": len(tweets), "limit": limit, "offset": offset, "tweets": tweets}
