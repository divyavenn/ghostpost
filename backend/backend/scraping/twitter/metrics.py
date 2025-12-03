"""
Endpoint to check performance metrics for posted tweets.
Fetches current likes, retweets, quotes, and replies from Twitter API.
Also provides shallow scraping for quick metrics detection.
"""
import asyncio
import re
from typing import Any

import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.data.twitter.posted_tweets_cache import get_posted_tweets_list, read_posted_tweets_cache, update_tweet_metrics
from backend.scraping.twitter.scraping_utils import extract_metrics
from backend.twitter.authentication import ensure_access_token
from backend.utlils.utils import notify

# Match TweetDetail GraphQL calls
TWEET_DETAIL_RE = re.compile(r"/i/api/graphql/[^/]+/TweetDetail")

router = APIRouter(prefix="/performance", tags=["performance"])


class TweetMetrics(BaseModel):
    id: str
    likes: int
    retweets: int
    quotes: int
    replies: int
    impressions: int = 0


class CheckPerformanceRequest(BaseModel):
    tweet_ids: list[str]  # List of posted tweet IDs to check


async def fetch_tweet_metrics_from_twitter(access_token: str, tweet_ids: list[str]) -> dict[str, TweetMetrics]:
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

    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)

        if response.status_code == 401:
            raise HTTPException(status_code=401, detail="AUTHENTICATION_REQUIRED")

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
                    metrics_map[tweet_id] = TweetMetrics(id=tweet_id,
                                                         likes=public_metrics.get("like_count", 0),
                                                         retweets=public_metrics.get("retweet_count", 0),
                                                         quotes=public_metrics.get("quote_count", 0),
                                                         replies=public_metrics.get("reply_count", 0),
                                                         impressions=public_metrics.get("impression_count", 0))

        return metrics_map

    except requests.RequestException as e:
        raise HTTPException(status_code=503, detail=f"Failed to reach Twitter API: {str(e)}") from e


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
        return {"message": "No tweet IDs provided", "updated_count": 0, "metrics": []}

    # Get user's access token
    access_token = await ensure_access_token(username)

    if not access_token:
        raise HTTPException(status_code=401, detail="AUTHENTICATION_REQUIRED")

    # Fetch metrics from Twitter
    notify(f"📊 Fetching metrics for {len(payload.tweet_ids)} tweets for @{username}...")
    metrics_map = await fetch_tweet_metrics_from_twitter(access_token, payload.tweet_ids)

    # Update cache with new metrics
    updated_count = 0
    updated_metrics = []

    for tweet_id, metrics in metrics_map.items():
        updated_tweet = update_tweet_metrics(username=username, posted_tweet_id=tweet_id, likes=metrics.likes, retweets=metrics.retweets, quotes=metrics.quotes, replies=metrics.replies)

        if updated_tweet:
            updated_count += 1
            updated_metrics.append({"id": tweet_id, "likes": metrics.likes, "retweets": metrics.retweets, "quotes": metrics.quotes, "replies": metrics.replies})

    notify(f"✅ Updated metrics for {updated_count}/{len(payload.tweet_ids)} tweets")

    return {"message": f"Updated metrics for {updated_count} tweets", "updated_count": updated_count, "metrics": updated_metrics}


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
    # Get the raw cache to count total tweets
    tweets_cache = read_posted_tweets_cache(username)
    total_count = len(tweets_cache.get("_order", []))

    # Use the helper function that handles the new map format correctly
    paginated_tweets = get_posted_tweets_list(username, limit=limit, offset=offset)

    return {"username": username, "total": total_count, "count": len(paginated_tweets), "limit": limit, "offset": offset, "tweets": paginated_tweets}


async def shallow_scrape_thread(ctx, tweet_url: str, tweet_id: str) -> dict[str, Any]:
    """
    Perform a shallow scrape to detect activity with minimal cost.
    No scrolling - just gets initial metrics and top few replies.
    Used for warm tweet monitoring.

    Args:
        ctx: Playwright browser context
        tweet_url: URL of the tweet to scrape
        tweet_id: ID of the main tweet

    Returns:
        {
            "reply_count": int,
            "like_count": int,
            "quote_count": int,
            "retweet_count": int,
            "latest_reply_ids": list[str]
        }
    """
    page = await ctx.new_page()

    result = {
        "reply_count": 0,
        "like_count": 0,
        "quote_count": 0,
        "retweet_count": 0,
        "latest_reply_ids": []
    }

    seen_reply_ids: list[str] = []

    async def on_response(resp):
        nonlocal result, seen_reply_ids
        if not (TWEET_DETAIL_RE.search(resp.url) and resp.ok):
            return
        try:
            data = await resp.json()
        except Exception:
            return

        instructions = []
        tc_v2 = (data.get("data") or {}).get("threaded_conversation_with_injections_v2") or {}
        instructions.extend(tc_v2.get("instructions", []) or [])
        tc_v1 = (data.get("data") or {}).get("threaded_conversation_with_injections") or {}
        instructions.extend(tc_v1.get("instructions", []) or [])

        for inst in instructions:
            for entry in inst.get("entries", []) or []:
                content = entry.get("content") or {}

                candidates = []
                ic = content.get("itemContent") or {}
                if ic:
                    candidates.append(ic)
                ic2 = (content.get("item") or {}).get("itemContent") or {}
                if ic2:
                    candidates.append(ic2)
                for it in (content.get("items") or content.get("moduleItems") or []):
                    cand = (it.get("item") or {}).get("itemContent") or it.get("itemContent") or {}
                    if cand:
                        candidates.append(cand)

                for cand in candidates:
                    raw = (cand.get("tweet_results") or {}).get("result")
                    if not isinstance(raw, dict):
                        continue
                    node = raw.get("tweet") or raw
                    legacy = node.get("legacy") or {}
                    if not legacy:
                        continue

                    tid = legacy.get("id_str") or str(node.get("rest_id") or "")
                    if not tid:
                        continue

                    # If this is the main tweet, get metrics
                    if tid == tweet_id:
                        metrics = extract_metrics(node)
                        result["reply_count"] = metrics["replies"]
                        result["like_count"] = metrics["likes"]
                        result["quote_count"] = metrics["quotes"]
                        result["retweet_count"] = metrics["retweets"]
                    else:
                        # This is a reply
                        in_reply_to = legacy.get("in_reply_to_status_id_str")
                        if in_reply_to and tid not in seen_reply_ids:
                            seen_reply_ids.append(tid)

    page.on("response", lambda r: asyncio.create_task(on_response(r)))

    try:
        await page.goto(tweet_url, wait_until="domcontentloaded")
        try:
            await page.wait_for_event(
                "response",
                predicate=lambda r: TWEET_DETAIL_RE.search(r.url),
                timeout=30_000,
            )
        except Exception:
            pass

        # Brief wait but no scrolling
        await asyncio.sleep(2)

    finally:
        await page.close()

    result["latest_reply_ids"] = seen_reply_ids[:10]  # Cap at 10
    return result
