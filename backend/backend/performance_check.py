"""
Endpoint to check performance metrics for posted tweets.
Fetches current likes, retweets, quotes, and replies from Twitter API.
"""
import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.oauth import ensure_access_token
from backend.posted_tweets_cache import read_posted_tweets_cache, update_tweet_metrics, write_posted_tweets_cache
from backend.utils import notify

router = APIRouter(prefix="/performance", tags=["performance"])


class TweetMetrics(BaseModel):
    id: str
    likes: int
    retweets: int
    quotes: int
    replies: int


class CheckPerformanceRequest(BaseModel):
    tweet_ids: list[str]  # List of posted tweet IDs to check


async def fetch_tweet_metrics_from_twitter(access_token: str, tweet_ids: list[str]) -> dict[str, TweetMetrics]:
    """
    Fetch metrics for multiple tweets from Twitter API.

    Args:
        access_token: Twitter OAuth access token
        tweet_ids: List of tweet IDs to fetch metrics for

    Returns:
        Dict mapping tweet_id to TweetMetrics
    """
    if not tweet_ids:
        return {}

    # Twitter API v2 endpoint for multiple tweets
    # Can fetch up to 100 tweets at once
    url = "https://api.twitter.com/2/tweets"

    # Build query params
    params = {
        "ids": ",".join(tweet_ids[:100]),  # Limit to 100 tweets per request
        "tweet.fields": "public_metrics"
    }

    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)

        if response.status_code == 401:
            raise HTTPException(status_code=401, detail="Twitter API authentication failed. Please re-authenticate.")

        if response.status_code == 429:
            raise HTTPException(status_code=429, detail="Twitter API rate limit exceeded. Please try again later.")

        if response.status_code >= 400:
            raise HTTPException(status_code=response.status_code, detail=f"Twitter API error: {response.text}")

        data = response.json()

        # Parse response
        metrics_map = {}

        if "data" in data and isinstance(data["data"], list):
            for tweet in data["data"]:
                tweet_id = tweet.get("id")
                public_metrics = tweet.get("public_metrics", {})

                if tweet_id:
                    metrics_map[tweet_id] = TweetMetrics(
                        id=tweet_id,
                        likes=public_metrics.get("like_count", 0),
                        retweets=public_metrics.get("retweet_count", 0),
                        quotes=public_metrics.get("quote_count", 0),
                        replies=public_metrics.get("reply_count", 0)
                    )

        return metrics_map

    except requests.RequestException as e:
        raise HTTPException(status_code=503, detail=f"Failed to reach Twitter API: {str(e)}")


@router.post("/{username}/check-performance")
async def check_tweet_performance(username: str, payload: CheckPerformanceRequest) -> dict:
    """
    Check performance metrics for posted tweets and update cache.

    Args:
        username: Twitter handle
        payload: List of tweet IDs to check

    Returns:
        Updated metrics and count
    """
    if not payload.tweet_ids:
        return {
            "message": "No tweet IDs provided",
            "updated_count": 0,
            "metrics": []
        }

    # Get user's access token
    access_token = await ensure_access_token(username)

    if not access_token:
        raise HTTPException(status_code=401, detail=f"No authentication token found for {username}")

    # Fetch metrics from Twitter
    notify(f"📊 Fetching metrics for {len(payload.tweet_ids)} tweets for @{username}...")
    metrics_map = await fetch_tweet_metrics_from_twitter(access_token, payload.tweet_ids)

    # Update cache with new metrics
    updated_count = 0
    updated_metrics = []

    for tweet_id, metrics in metrics_map.items():
        updated_tweet = update_tweet_metrics(
            username=username,
            posted_tweet_id=tweet_id,
            likes=metrics.likes,
            retweets=metrics.retweets,
            quotes=metrics.quotes,
            replies=metrics.replies
        )

        if updated_tweet:
            updated_count += 1
            updated_metrics.append({
                "id": tweet_id,
                "likes": metrics.likes,
                "retweets": metrics.retweets,
                "quotes": metrics.quotes,
                "replies": metrics.replies
            })

    notify(f"✅ Updated metrics for {updated_count}/{len(payload.tweet_ids)} tweets")

    return {
        "message": f"Updated metrics for {updated_count} tweets",
        "updated_count": updated_count,
        "metrics": updated_metrics
    }


@router.get("/{username}/posted-tweets")
async def get_posted_tweets_with_metrics(username: str, limit: int = 50, offset: int = 0) -> dict:
    """
    Get posted tweets from cache (with current metrics).
    This replaces the old endpoint that read from logs.

    Args:
        username: Twitter handle
        limit: Number of tweets to return
        offset: Number of tweets to skip

    Returns:
        Paginated list of posted tweets with metrics
    """
    tweets = read_posted_tweets_cache(username)

    # Apply pagination
    total_count = len(tweets)
    paginated_tweets = tweets[offset:offset + limit]

    return {
        "username": username,
        "total": total_count,
        "count": len(paginated_tweets),
        "limit": limit,
        "offset": offset,
        "tweets": paginated_tweets
    }
