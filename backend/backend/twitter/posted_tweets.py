
from typing import Any

from fastapi import APIRouter, Query

from backend.data.twitter.posted_tweets_cache import read_posted_tweets_cache

router = APIRouter(prefix="/posted", tags=["posted"])


def get_posted_tweets(username: str, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    # Read from new posted_tweets.json cache
    tweets = read_posted_tweets_cache(username)

    # Apply pagination
    start_idx = offset
    end_idx = offset + limit
    return tweets[start_idx:end_idx]


@router.get("/{username}/tweets")
async def get_posted_tweets_endpoint(username: str, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)) -> dict[str, Any]:
    tweets = get_posted_tweets(username, limit=limit, offset=offset)

    return {"username": username, "count": len(tweets), "limit": limit, "offset": offset, "tweets": tweets}
