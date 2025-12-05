"""
Twitter API v2 based implementations of scraping functions.
These functions have the same interface as the browser-based scraping functions
but use the official Twitter API instead of scraping.

Rate limits (Basic plan):
- Search: 60 requests/15 min
- Tweet lookup: 15 requests/15 min
- User timeline: 5 requests/15 min (we avoid this by using search with from:)
"""
import asyncio
from datetime import datetime
from typing import Any
from urllib.parse import quote_plus

import requests

from backend.config import MAX_TWEET_AGE_HOURS, TEST_USER
from backend.twitter.authentication import ensure_access_token
from backend.utlils.utils import error, notify

# Default user for API authentication (user with valid OAuth tokens)
DEFAULT_AUTH_USER = TEST_USER

try:
    from datetime import UTC
except ImportError:
    from datetime import timezone
    UTC = timezone.utc


# Twitter API v2 base URL
API_BASE = "https://api.twitter.com/2"

# Default tweet fields to request
TWEET_FIELDS = "id,text,created_at,public_metrics,conversation_id,in_reply_to_user_id,referenced_tweets,author_id"
USER_FIELDS = "id,name,username,profile_image_url,public_metrics"
EXPANSIONS = "author_id,referenced_tweets.id,referenced_tweets.id.author_id,attachments.media_keys"
MEDIA_FIELDS = "type,url,preview_image_url,alt_text"


def _get_headers(access_token: str) -> dict:
    """Get authorization headers for API requests."""
    return {"Authorization": f"Bearer {access_token}"}


def _parse_twitter_date(date_str: str) -> datetime:
    """Parse Twitter API date format (ISO 8601)."""
    # Twitter API v2 uses ISO 8601: 2024-01-01T12:00:00.000Z
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except Exception:
        return datetime.now(UTC)


def _is_within_hours(created_at: str, hours: int = MAX_TWEET_AGE_HOURS) -> bool:
    """Check if tweet is within the specified hours."""
    from datetime import timedelta
    try:
        dt = _parse_twitter_date(created_at)
        now = datetime.now(UTC)
        return dt >= now - timedelta(hours=hours)
    except Exception:
        return False


def _calculate_engagement_score(metrics: dict) -> int:
    """Calculate engagement score from public metrics."""
    likes = metrics.get("like_count", 0)
    retweets = metrics.get("retweet_count", 0)
    quotes = metrics.get("quote_count", 0)
    replies = metrics.get("reply_count", 0)
    return likes + 2 * retweets + 3 * quotes + replies


def _extract_media_from_includes(tweet_id: str, includes: dict, tweet_data: dict) -> list[dict]:
    """Extract media URLs from includes for a specific tweet."""
    media_items = []
    media_map = {}

    # Build media map from includes
    for media in includes.get("media", []):
        media_key = media.get("media_key")
        if media_key:
            media_map[media_key] = media

    # Get media keys for this tweet (from attachments if available)
    # Note: attachments info might be in the tweet data or we need to check referenced tweets
    attachments = tweet_data.get("attachments", {})
    media_keys = attachments.get("media_keys", [])

    for media_key in media_keys:
        media = media_map.get(media_key)
        if media and media.get("type") == "photo":
            media_items.append({
                "type": "photo",
                "url": media.get("url", ""),
                "alt_text": media.get("alt_text", "")
            })

    return media_items


def _build_user_map(includes: dict) -> dict:
    """Build a map of user_id -> user_data from includes."""
    user_map = {}
    for user in includes.get("users", []):
        user_id = user.get("id")
        if user_id:
            user_map[user_id] = {
                "handle": user.get("username", ""),
                "username": user.get("name", ""),
                "author_profile_pic_url": (user.get("profile_image_url", "").replace("_normal", "_400x400")),
                "followers": user.get("public_metrics", {}).get("followers_count", 0)
            }
    return user_map


def _tweet_to_dict(tweet: dict, user_map: dict, includes: dict) -> dict:
    """Convert API tweet response to the same format as scraping."""
    author_id = tweet.get("author_id", "")
    user_info = user_map.get(author_id, {})

    metrics = tweet.get("public_metrics", {})
    created_at = tweet.get("created_at", "")

    # Convert to ISO format if not already
    try:
        dt = _parse_twitter_date(created_at)
        created_at_iso = dt.isoformat()
    except Exception:
        created_at_iso = created_at

    handle = user_info.get("handle", "")
    tid = tweet.get("id", "")

    return {
        "id": tid,
        "text": tweet.get("text", ""),
        "likes": metrics.get("like_count", 0),
        "retweets": metrics.get("retweet_count", 0),
        "quotes": metrics.get("quote_count", 0),
        "replies": metrics.get("reply_count", 0),
        "impressions": metrics.get("impression_count", 0),
        "score": _calculate_engagement_score(metrics),
        "followers": user_info.get("followers", 0),
        "created_at": created_at_iso,
        "url": f"https://x.com/{handle}/status/{tid}" if handle else f"https://x.com/i/web/status/{tid}",
        "username": user_info.get("username", ""),
        "handle": handle,
        "author_profile_pic_url": user_info.get("author_profile_pic_url", ""),
        "media": _extract_media_from_includes(tid, includes, tweet),
        "quoted_tweet": None,  # TODO: Extract from referenced_tweets if needed
        "in_reply_to_status_id": _get_in_reply_to(tweet),
        "conversation_id": tweet.get("conversation_id"),
    }


def _get_in_reply_to(tweet: dict) -> str | None:
    """Extract in_reply_to_status_id from referenced_tweets."""
    referenced = tweet.get("referenced_tweets", [])
    for ref in referenced:
        if ref.get("type") == "replied_to":
            return ref.get("id")
    return None


async def _search_tweets(
    access_token: str,
    query: str,
    max_results: int = 100,
    next_token: str | None = None
) -> dict:
    """
    Search for tweets using Twitter API v2.

    Args:
        access_token: User's access token
        query: Search query (can include operators like from:, to:, etc.)
        max_results: Max results per request (10-100)
        next_token: Pagination token

    Returns:
        API response dict with data, includes, and meta
    """
    url = f"{API_BASE}/tweets/search/recent"

    params = {
        "query": query,
        "max_results": min(max_results, 100),
        "tweet.fields": TWEET_FIELDS,
        "user.fields": USER_FIELDS,
        "expansions": EXPANSIONS,
        "media.fields": MEDIA_FIELDS,
    }

    if next_token:
        params["next_token"] = next_token

    headers = _get_headers(access_token)

    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)

        if response.status_code == 401:
            error("Twitter API authentication failed", status_code=401, function_name="_search_tweets", critical=False)
            return {"data": [], "includes": {}, "meta": {}}

        if response.status_code == 429:
            error("Twitter API rate limit exceeded", status_code=429, function_name="_search_tweets", critical=False)
            return {"data": [], "includes": {}, "meta": {}}

        if response.status_code >= 400:
            error(f"Twitter API error: {response.text}", status_code=response.status_code, function_name="_search_tweets", critical=False)
            return {"data": [], "includes": {}, "meta": {}}

        return response.json()

    except requests.RequestException as e:
        error(f"Twitter API request failed: {e}", status_code=503, function_name="_search_tweets", critical=False)
        return {"data": [], "includes": {}, "meta": {}}


async def _get_tweet_by_id(access_token: str, tweet_id: str) -> dict:
    """
    Get a single tweet by ID with expansions.

    Args:
        access_token: User's access token
        tweet_id: Tweet ID to fetch

    Returns:
        API response dict with data and includes
    """
    url = f"{API_BASE}/tweets/{tweet_id}"

    params = {
        "tweet.fields": TWEET_FIELDS,
        "user.fields": USER_FIELDS,
        "expansions": EXPANSIONS,
        "media.fields": MEDIA_FIELDS,
    }

    headers = _get_headers(access_token)

    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)

        if response.status_code == 401:
            return {"data": None, "includes": {}}

        if response.status_code == 429:
            error("Twitter API rate limit exceeded", status_code=429, function_name="_get_tweet_by_id", critical=False)
            return {"data": None, "includes": {}}

        if response.status_code >= 400:
            return {"data": None, "includes": {}}

        return response.json()

    except requests.RequestException as e:
        error(f"Twitter API request failed: {e}", status_code=503, function_name="_get_tweet_by_id", critical=False)
        return {"data": None, "includes": {}}


# ============================================================================
# Main API functions - same interface as scraping functions
# ============================================================================

async def fetch_user_tweets(ctx, handle: str, username: str | None = None, write_callback=None, **kwargs) -> dict:
    """
    Fetch tweets from a user's timeline using search API with from: operator.

    Same interface as timeline.fetch_user_tweets but uses API instead of scraping.

    Args:
        ctx: Browser context (ignored - kept for interface compatibility)
        handle: Twitter handle to fetch tweets from
        username: Username for cache operations
        write_callback: Async callback for progressive writes
        **kwargs: Additional arguments (ignored)

    Returns:
        Dict of tweet_id -> tweet_data
    """
    # Get access token for the authenticated user
    access_token = await ensure_access_token(DEFAULT_AUTH_USER)

    if not access_token:
        error("No access token available", status_code=401, function_name="fetch_user_tweets", critical=False)
        return {}

    # Build query: from:handle -is:retweet -is:reply (to get original posts only)
    query = f"from:{handle} -is:retweet -is:reply"

    notify(f"[API] Fetching tweets from @{handle} using search API")

    tweets = {}
    response = await _search_tweets(access_token, query, max_results=100)

    data = response.get("data", [])
    includes = response.get("includes", {})
    user_map = _build_user_map(includes)

    for tweet in data:
        # Filter by age
        created_at = tweet.get("created_at", "")
        if not _is_within_hours(created_at, MAX_TWEET_AGE_HOURS):
            continue

        # Filter by minimum likes
        metrics = tweet.get("public_metrics", {})
        if metrics.get("like_count", 0) < 5:
            continue

        tweet_dict = _tweet_to_dict(tweet, user_map, includes)
        tweets[tweet_dict["id"]] = tweet_dict

    # Progressive write if callback provided
    if write_callback and username and tweets:
        await write_callback(list(tweets.values()), username)

    notify(f"[API] Fetched {len(tweets)} tweets from @{handle}")
    return tweets


async def fetch_search(ctx, query: str, username: str | None = None, write_callback=None, **kwargs) -> dict:
    """
    Search for tweets using Twitter API v2.

    Same interface as timeline.fetch_search but uses API instead of scraping.

    Args:
        ctx: Browser context (ignored - kept for interface compatibility)
        query: Search query
        username: Username for cache operations
        write_callback: Async callback for progressive writes
        **kwargs: Additional arguments (ignored)

    Returns:
        Dict of tweet_id -> tweet_data
    """
    # Get access token for the authenticated user
    access_token = await ensure_access_token(DEFAULT_AUTH_USER)

    if not access_token:
        error("No access token available", status_code=401, function_name="fetch_search", critical=False)
        return {}

    # Ensure query excludes retweets and replies
    if "-is:retweet" not in query:
        query = f"{query} -is:retweet"
    if "-is:reply" not in query:
        query = f"{query} -is:reply"

    notify(f"[API] Searching tweets with query: {query}")

    tweets = {}
    response = await _search_tweets(access_token, query, max_results=100)

    data = response.get("data", [])
    includes = response.get("includes", {})
    user_map = _build_user_map(includes)

    for tweet in data:
        # Filter by age
        created_at = tweet.get("created_at", "")
        if not _is_within_hours(created_at, MAX_TWEET_AGE_HOURS):
            continue

        # Filter by minimum likes
        metrics = tweet.get("public_metrics", {})
        if metrics.get("like_count", 0) < 5:
            continue

        tweet_dict = _tweet_to_dict(tweet, user_map, includes)
        tweets[tweet_dict["id"]] = tweet_dict

    # Progressive write if callback provided
    if write_callback and username and tweets:
        await write_callback(list(tweets.values()), username)

    notify(f"[API] Found {len(tweets)} tweets for query")
    return tweets


async def get_thread(ctx, tweet_url: str, root_id: str | None = None) -> dict:
    """
    Get thread context for a tweet using Twitter API.

    Same interface as thread.get_thread but uses API instead of scraping.

    Args:
        ctx: Browser context (ignored - kept for interface compatibility)
        tweet_url: URL of the tweet
        root_id: Root tweet ID

    Returns:
        Dict with thread, other_replies, author_handle, author_profile_pic_url, media
    """
    # Extract tweet ID from URL if not provided
    if not root_id:
        # URL format: https://x.com/username/status/1234567890
        import re
        match = re.search(r"/status/(\d+)", tweet_url)
        if match:
            root_id = match.group(1)

    if not root_id:
        return {
            "thread": [],
            "other_replies": [],
            "author_handle": "",
            "author_profile_pic_url": "",
            "media": []
        }

    # Get access token - use a default user for thread fetching
    access_token = await ensure_access_token(DEFAULT_AUTH_USER)

    if not access_token:
        return {
            "thread": [],
            "other_replies": [],
            "author_handle": "",
            "author_profile_pic_url": "",
            "media": []
        }

    # Fetch the root tweet
    response = await _get_tweet_by_id(access_token, root_id)

    data = response.get("data")
    if not data:
        return {
            "thread": [],
            "other_replies": [],
            "author_handle": "",
            "author_profile_pic_url": "",
            "media": []
        }

    includes = response.get("includes", {})
    user_map = _build_user_map(includes)

    author_id = data.get("author_id", "")
    author_info = user_map.get(author_id, {})

    # Get the main tweet text
    thread_texts = [data.get("text", "")]

    # Get top replies using search
    conversation_id = data.get("conversation_id", root_id)
    reply_query = f"conversation_id:{conversation_id} -from:{author_info.get('handle', '')} is:reply"

    reply_response = await _search_tweets(access_token, reply_query, max_results=10)

    other_replies = []
    reply_data = reply_response.get("data", [])
    reply_includes = reply_response.get("includes", {})
    reply_user_map = _build_user_map(reply_includes)

    for reply in reply_data[:5]:  # Max 5 replies
        reply_author_id = reply.get("author_id", "")
        reply_user_info = reply_user_map.get(reply_author_id, {})

        other_replies.append({
            "text": reply.get("text", ""),
            "author_handle": reply_user_info.get("handle", ""),
            "author_name": reply_user_info.get("username", ""),
            "likes": reply.get("public_metrics", {}).get("like_count", 0)
        })

    return {
        "thread": thread_texts,
        "other_replies": other_replies,
        "author_handle": author_info.get("handle", ""),
        "author_profile_pic_url": author_info.get("author_profile_pic_url", ""),
        "media": _extract_media_from_includes(root_id, includes, data)
    }


async def deep_scrape_thread(ctx, tweet_url: str, tweet_id: str, author_handle: str) -> dict[str, Any]:
    """
    Get full thread with all replies using Twitter API.

    Same interface as thread.deep_scrape_thread but uses API instead of scraping.

    Args:
        ctx: Browser context (ignored - kept for interface compatibility)
        tweet_url: URL of the tweet
        tweet_id: Tweet ID
        author_handle: Handle of the tweet author

    Returns:
        Dict with reply_count, like_count, quote_count, retweet_count, all_reply_ids, replies
    """
    result = {
        "reply_count": 0,
        "like_count": 0,
        "quote_count": 0,
        "retweet_count": 0,
        "all_reply_ids": [],
        "replies": []
    }

    # Get access token
    access_token = await ensure_access_token(DEFAULT_AUTH_USER)

    if not access_token:
        return result

    # Fetch the main tweet for metrics
    response = await _get_tweet_by_id(access_token, tweet_id)

    data = response.get("data")
    if data:
        metrics = data.get("public_metrics", {})
        result["reply_count"] = metrics.get("reply_count", 0)
        result["like_count"] = metrics.get("like_count", 0)
        result["quote_count"] = metrics.get("quote_count", 0)
        result["retweet_count"] = metrics.get("retweet_count", 0)

    # Search for replies to this tweet
    conversation_id = data.get("conversation_id", tweet_id) if data else tweet_id
    reply_query = f"conversation_id:{conversation_id} is:reply"

    all_replies = []
    next_token = None

    # Paginate through replies (up to 3 pages for deep scrape)
    for _ in range(3):
        reply_response = await _search_tweets(access_token, reply_query, max_results=100, next_token=next_token)

        reply_data = reply_response.get("data", [])
        reply_includes = reply_response.get("includes", {})
        reply_user_map = _build_user_map(reply_includes)

        for reply in reply_data:
            reply_author_id = reply.get("author_id", "")
            reply_user_info = reply_user_map.get(reply_author_id, {})

            # Skip author's own replies (thread continuations)
            if reply_user_info.get("handle", "").lower() == author_handle.lower():
                continue

            reply_id = reply.get("id", "")
            result["all_reply_ids"].append(reply_id)

            metrics = reply.get("public_metrics", {})
            created_at = reply.get("created_at", "")

            try:
                dt = _parse_twitter_date(created_at)
                created_at_iso = dt.isoformat()
            except Exception:
                created_at_iso = created_at

            reply_handle = reply_user_info.get("handle", "")

            all_replies.append({
                "id": reply_id,
                "text": reply.get("text", ""),
                "handle": reply_handle,
                "username": reply_user_info.get("username", ""),
                "author_profile_pic_url": reply_user_info.get("author_profile_pic_url", ""),
                "followers": reply_user_info.get("followers", 0),
                "in_reply_to_status_id": _get_in_reply_to(reply),
                "created_at": created_at_iso,
                "url": f"https://x.com/{reply_handle}/status/{reply_id}",
                "likes": metrics.get("like_count", 0),
                "retweets": metrics.get("retweet_count", 0),
                "quotes": metrics.get("quote_count", 0),
                "replies": metrics.get("reply_count", 0),
                "impressions": metrics.get("impression_count", 0),
            })

        # Check for more pages
        next_token = reply_response.get("meta", {}).get("next_token")
        if not next_token:
            break

    result["replies"] = all_replies
    return result


async def shallow_scrape_thread(ctx, tweet_url: str, tweet_id: str) -> dict[str, Any]:
    """
    Quick metrics check for a tweet using Twitter API.

    Same interface as metrics.shallow_scrape_thread but uses API instead of scraping.

    Args:
        ctx: Browser context (ignored - kept for interface compatibility)
        tweet_url: URL of the tweet
        tweet_id: Tweet ID

    Returns:
        Dict with reply_count, like_count, quote_count, retweet_count, latest_reply_ids
    """
    result = {
        "reply_count": 0,
        "like_count": 0,
        "quote_count": 0,
        "retweet_count": 0,
        "latest_reply_ids": []
    }

    # Get access token
    access_token = await ensure_access_token(DEFAULT_AUTH_USER)

    if not access_token:
        return result

    # Fetch the tweet for metrics
    response = await _get_tweet_by_id(access_token, tweet_id)

    data = response.get("data")
    if data:
        metrics = data.get("public_metrics", {})
        result["reply_count"] = metrics.get("reply_count", 0)
        result["like_count"] = metrics.get("like_count", 0)
        result["quote_count"] = metrics.get("quote_count", 0)
        result["retweet_count"] = metrics.get("retweet_count", 0)

        # Get a few recent reply IDs
        conversation_id = data.get("conversation_id", tweet_id)
        reply_query = f"conversation_id:{conversation_id} is:reply"

        reply_response = await _search_tweets(access_token, reply_query, max_results=10)
        reply_data = reply_response.get("data", [])

        result["latest_reply_ids"] = [r.get("id") for r in reply_data[:10] if r.get("id")]

    return result


async def scrape_user_recent_tweets(ctx, username: str, max_tweets: int = 50) -> list[dict[str, Any]]:
    """
    Get user's recent tweets using Twitter API search.

    Same interface as posted_tweets.scrape_user_recent_tweets but uses API.

    Args:
        ctx: Browser context (ignored - kept for interface compatibility)
        username: Twitter handle to scrape
        max_tweets: Maximum tweets to collect

    Returns:
        List of tweet dicts
    """
    # Get access token
    access_token = await ensure_access_token(DEFAULT_AUTH_USER)

    if not access_token:
        return []

    # Search for user's tweets (including replies)
    query = f"from:{username}"

    notify(f"[API] Fetching recent tweets from @{username}")

    tweets = []
    next_token = None

    while len(tweets) < max_tweets:
        remaining = max_tweets - len(tweets)
        batch_size = min(remaining, 100)

        response = await _search_tweets(access_token, query, max_results=batch_size, next_token=next_token)

        data = response.get("data", [])
        includes = response.get("includes", {})
        user_map = _build_user_map(includes)

        for tweet in data:
            tweet_dict = _tweet_to_dict(tweet, user_map, includes)
            tweets.append(tweet_dict)

            if len(tweets) >= max_tweets:
                break

        # Check for more pages
        next_token = response.get("meta", {}).get("next_token")
        if not next_token or not data:
            break

    notify(f"[API] Fetched {len(tweets)} tweets from @{username}")
    return tweets


async def collect_from_page(ctx, url: str, handle: str | None, *, username=None, write_callback=None):
    """
    Collect tweets from a URL using Twitter API.

    Same interface as tools.collect_from_page but uses API.
    This function determines whether it's a user timeline or search based on URL.

    Args:
        ctx: Browser context (ignored - kept for interface compatibility)
        url: URL to scrape (user profile or search results)
        handle: Twitter handle (if scraping user timeline)
        username: Username for cache operations
        write_callback: Async callback for progressive writes

    Returns:
        Dict of tweet_id -> tweet_data
    """
    if handle:
        # User timeline
        tweets = await fetch_user_tweets(ctx, handle, username=username, write_callback=write_callback)
    else:
        # Search - extract query from URL
        from urllib.parse import parse_qs, urlparse
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        query = query_params.get("q", [""])[0]

        if query:
            tweets = await fetch_search(ctx, query, username=username, write_callback=write_callback)
        else:
            tweets = {}

    # Collect thread data for each tweet
    for tid, t in tweets.items():
        thread_data = await get_thread(ctx, t["url"], root_id=t["id"])
        t["thread"] = thread_data.get("thread", [])
        t["other_replies"] = thread_data.get("other_replies", [])

        # Replace truncated text with full text from thread
        if t["thread"] and len(t["thread"]) > 0:
            t["text"] = t["thread"][0]

        # Progressive write
        if write_callback and username:
            await write_callback([t], username)

    return tweets
