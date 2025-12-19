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

# Import centralized rate limiter
from backend.twitter.rate_limiter import EndpointType, TWITTER_HOME_TIMELINE, twitter_rate_limiter as _rate_limiter

# Default tweet fields to request
# note_tweet contains full text for tweets > 280 characters
TWEET_FIELDS = "id,text,created_at,public_metrics,conversation_id,in_reply_to_user_id,referenced_tweets,author_id,note_tweet"

# Engagement thresholds for discovery (FYP/queries, not user timelines)
MIN_IMPRESSIONS_FOR_DISCOVERY = 2000
USER_FIELDS = "id,name,username,profile_image_url,public_metrics"
EXPANSIONS = "author_id,referenced_tweets.id,referenced_tweets.id.author_id,attachments.media_keys"
MEDIA_FIELDS = "type,url,preview_image_url,alt_text"


from dataclasses import dataclass, field


@dataclass
class ScrapeStats:
    """Track filtering stats during scraping for logging."""
    source_type: str = ""  # "account", "query", "home_timeline"
    source_value: str = ""  # handle, query text, or "following"
    username: str = ""  # User running the scrape (for logging to file)
    fetched: int = 0  # Total tweets from API
    filtered_old: int = 0  # Filtered due to age
    filtered_impressions: int = 0  # Filtered due to low impressions
    filtered_no_thread: int = 0  # Filtered due to no thread content
    filtered_intent: int = 0  # Filtered due to intent mismatch
    filtered_seen: int = 0  # Already seen tweets
    filtered_replies: int = 0  # Filtered because it's a reply
    filtered_retweets: int = 0  # Filtered because it's a retweet
    passed: int = 0  # Final count that passed all filters

    def log_summary(self) -> None:
        """Log a formatted summary of the scrape stats to console and file."""
        from backend.twitter.logging import log_scrape_stats

        source_display = f"@{self.source_value}" if self.source_type == "account" else self.source_value
        if self.source_type == "home_timeline":
            source_display = "Home Timeline"

        # Build filter breakdown
        filters = []
        if self.filtered_old > 0:
            filters.append(f"old:{self.filtered_old}")
        if self.filtered_impressions > 0:
            filters.append(f"low_impressions:{self.filtered_impressions}")
        if self.filtered_replies > 0:
            filters.append(f"replies:{self.filtered_replies}")
        if self.filtered_retweets > 0:
            filters.append(f"retweets:{self.filtered_retweets}")
        if self.filtered_intent > 0:
            filters.append(f"intent:{self.filtered_intent}")
        if self.filtered_no_thread > 0:
            filters.append(f"no_thread:{self.filtered_no_thread}")
        if self.filtered_seen > 0:
            filters.append(f"seen:{self.filtered_seen}")

        filter_str = ", ".join(filters) if filters else "none"
        total_filtered = self.fetched - self.passed

        # Log to console
        notify(f"📊 [{self.source_type.upper()}] {source_display}: {self.fetched} fetched → {self.passed} passed | Filtered ({total_filtered}): {filter_str}")

        # Log to file if username is provided
        if self.username:
            log_scrape_stats(
                username=self.username,
                source_type=self.source_type,
                source_value=self.source_value,
                fetched=self.fetched,
                passed=self.passed,
                filtered_old=self.filtered_old,
                filtered_impressions=self.filtered_impressions,
                filtered_no_thread=self.filtered_no_thread,
                filtered_intent=self.filtered_intent,
                filtered_seen=self.filtered_seen,
                filtered_replies=self.filtered_replies,
                filtered_retweets=self.filtered_retweets,
            )


def _get_headers(access_token: str) -> dict:
    """Get authorization headers for API requests."""
    return {"Authorization": f"Bearer {access_token}"}


def _get_full_text(tweet: dict) -> str:
    """
    Extract full text from a tweet, handling long tweets (> 280 chars).

    Twitter API v2 truncates long tweets in the 'text' field.
    The full text is available in 'note_tweet.text' for long tweets.

    Args:
        tweet: Tweet data from API

    Returns:
        Full tweet text with HTML entities decoded
    """
    import html

    # Check for note_tweet (long tweets > 280 chars)
    note_tweet = tweet.get("note_tweet", {})
    if note_tweet and note_tweet.get("text"):
        text = note_tweet.get("text", "")
    else:
        # Fall back to regular text field
        text = tweet.get("text", "")

    # Decode HTML entities (&gt; -> >, &lt; -> <, &amp; -> &, etc.)
    return html.unescape(text)


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


def _build_media_map(includes: dict) -> dict:
    """Build a map of media_key -> media_data from includes."""
    media_map = {}
    for media in includes.get("media", []):
        media_key = media.get("media_key")
        if media_key:
            media_map[media_key] = media
    return media_map


def _extract_media_from_includes(tweet_id: str, includes: dict, tweet_data: dict, media_map: dict | None = None) -> list[dict]:
    """Extract media URLs from includes for a specific tweet."""
    media_items = []

    # Build media map if not provided
    if media_map is None:
        media_map = _build_media_map(includes)

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


def _build_tweets_map(includes: dict) -> dict:
    """Build a map of tweet_id -> tweet_data from includes.tweets (for referenced tweets)."""
    tweets_map = {}
    for tweet in includes.get("tweets", []):
        tweet_id = tweet.get("id")
        if tweet_id:
            tweets_map[tweet_id] = tweet
    return tweets_map


def _extract_quoted_tweet(tweet: dict, user_map: dict, includes: dict) -> dict | None:
    """
    Extract quoted tweet data from referenced_tweets and includes.

    Args:
        tweet: Main tweet data
        user_map: Map of user_id -> user_data
        includes: API includes with tweets and users

    Returns:
        Quoted tweet dict or None if no quoted tweet
    """
    referenced = tweet.get("referenced_tweets", [])

    # Find the quoted tweet reference
    quoted_ref = None
    for ref in referenced:
        if ref.get("type") == "quoted":
            quoted_ref = ref
            break

    if not quoted_ref:
        return None

    quoted_id = quoted_ref.get("id")
    if not quoted_id:
        return None

    # Look up the quoted tweet in includes.tweets
    tweets_map = _build_tweets_map(includes)
    quoted_tweet_data = tweets_map.get(quoted_id)

    if not quoted_tweet_data:
        # Tweet data not in includes (might be deleted/private)
        return None

    # Get author info
    quoted_author_id = quoted_tweet_data.get("author_id", "")
    quoted_author_info = user_map.get(quoted_author_id, {})
    quoted_handle = quoted_author_info.get("handle", "")

    # Build media map for extracting quoted tweet media
    media_map = _build_media_map(includes)
    quoted_media = _extract_media_from_includes(quoted_id, includes, quoted_tweet_data, media_map)

    # Build URL for the quoted tweet
    quoted_url = f"https://x.com/{quoted_handle}/status/{quoted_id}" if quoted_handle else f"https://x.com/i/web/status/{quoted_id}"

    return {
        "text": _get_full_text(quoted_tweet_data),
        "author_handle": quoted_handle,
        "author_name": quoted_author_info.get("username", ""),
        "author_profile_pic_url": quoted_author_info.get("author_profile_pic_url", ""),
        "url": quoted_url,
        "media": quoted_media
    }


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
        "text": _get_full_text(tweet),
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
        "quoted_tweet": _extract_quoted_tweet(tweet, user_map, includes),
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
    next_token: str | None = None,
    _retry_count: int = 0
) -> dict:
    """
    Search for tweets using Twitter API v2.

    Args:
        access_token: User's access token
        query: Search query (can include operators like from:, to:, etc.)
        max_results: Max results per request (10-100)
        next_token: Pagination token
        _retry_count: Internal retry counter (do not pass)

    Returns:
        API response dict with data, includes, and meta
    """
    import time

    # Wait for rate limiter before making request (SEARCH endpoint: 60 req/15min)
    await _rate_limiter.wait_if_needed(EndpointType.SEARCH)

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
        _rate_limiter.update_last_request(EndpointType.SEARCH)

        if response.status_code == 401:
            error("Twitter API authentication failed", status_code=401, function_name="_search_tweets", critical=False)
            return {"data": [], "includes": {}, "meta": {}}

        if response.status_code == 429:
            # Rate limited - wait and retry
            reset_time = response.headers.get("x-rate-limit-reset")
            if reset_time and _retry_count < 3:
                await _rate_limiter.wait_for_reset(int(reset_time), EndpointType.SEARCH)
                return await _search_tweets(access_token, query, max_results, next_token, _retry_count + 1)
            else:
                error("Twitter API rate limit exceeded after retries", status_code=429, function_name="_search_tweets", critical=False)
                return {"data": [], "includes": {}, "meta": {}}

        if response.status_code >= 400:
            error(f"Twitter API error: {response.text}", status_code=response.status_code, function_name="_search_tweets", critical=False)
            return {"data": [], "includes": {}, "meta": {}}

        return response.json()

    except requests.RequestException as e:
        error(f"Twitter API request failed: {e}", status_code=503, function_name="_search_tweets", critical=False)
        return {"data": [], "includes": {}, "meta": {}}


async def _get_tweet_by_id(access_token: str, tweet_id: str, _retry_count: int = 0) -> dict:
    """
    Get a single tweet by ID with expansions.

    Args:
        access_token: User's access token
        tweet_id: Tweet ID to fetch
        _retry_count: Internal retry counter (do not pass)

    Returns:
        API response dict with data and includes
    """
    import time

    # Wait for rate limiter before making request (TWEET_LOOKUP endpoint: 300 req/15min)
    await _rate_limiter.wait_if_needed(EndpointType.TWEET_LOOKUP)

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
        _rate_limiter.update_last_request(EndpointType.TWEET_LOOKUP)

        if response.status_code == 401:
            notify(f"⚠️ _get_tweet_by_id: Auth failed (401) for tweet {tweet_id}")
            return {"data": None, "includes": {}, "errors": [{"detail": "Authentication failed"}]}

        if response.status_code == 429:
            # Rate limited - wait and retry
            reset_time = response.headers.get("x-rate-limit-reset")
            if reset_time and _retry_count < 3:
                await _rate_limiter.wait_for_reset(int(reset_time), EndpointType.TWEET_LOOKUP)
                return await _get_tweet_by_id(access_token, tweet_id, _retry_count + 1)
            else:
                error("Twitter API rate limit exceeded after retries", status_code=429, function_name="_get_tweet_by_id", critical=False)
                return {"data": None, "includes": {}, "errors": [{"detail": "Rate limit exceeded"}]}

        if response.status_code >= 400:
            # Try to get error details from response
            try:
                error_data = response.json()
                errors = error_data.get("errors", [{"detail": f"HTTP {response.status_code}"}])
            except Exception:
                errors = [{"detail": f"HTTP {response.status_code}: {response.text[:200]}"}]
            notify(f"⚠️ _get_tweet_by_id: API error ({response.status_code}) for tweet {tweet_id}")
            return {"data": None, "includes": {}, "errors": errors}

        return response.json()

    except requests.RequestException as e:
        error(f"Twitter API request failed: {e}", status_code=503, function_name="_get_tweet_by_id", critical=False)
        return {"data": None, "includes": {}, "errors": [{"detail": str(e)}]}


# ============================================================================
# Main API functions
# ============================================================================

async def populate_thread(raw_tweets: dict) -> tuple[dict, int]:
    """
    Fetch thread data for each tweet and filter out tweets without thread content.

    Args:
        raw_tweets: Dict of tweet_id -> tweet_data (without thread data)

    Returns:
        Tuple of (tweets dict, skipped_count)
    """
    tweets = {}
    skipped_count = 0

    for tid, t in raw_tweets.items():
        # Pass prefetched data to avoid redundant _get_tweet_by_id API call
        prefetched_data = {
            "handle": t.get("handle", ""),
            "conversation_id": t.get("conversation_id", tid),
            "text": t.get("text", ""),
            "author_profile_pic_url": t.get("author_profile_pic_url", ""),
            "media": t.get("media", []),
        }
        thread_data = await get_thread(None, t["url"], root_id=t["id"], prefetched_data=prefetched_data)
        t["thread"] = thread_data.get("thread", [])
        t["thread_ids"] = thread_data.get("thread_ids", [])
        t["other_replies"] = thread_data.get("other_replies", [])

        # Update author info from thread data if available
        if thread_data.get("author_profile_pic_url"):
            t["author_profile_pic_url"] = thread_data["author_profile_pic_url"]
        if thread_data.get("media"):
            t["media"] = thread_data["media"]

        # Skip tweets without thread content
        if not t["thread"] or len(t["thread"]) == 0:
            skipped_count += 1
            continue

        # Replace truncated text with full text from thread
        t["text"] = t["thread"][0]
        tweets[tid] = t

    return tweets, skipped_count


def _convert_web_query_to_api(query: str) -> str:
    """
    Convert Twitter web search operators to API v2 operators.

    Web search (twitter.com) uses different operators than the API v2.

    Web -> API conversions:
    - -filter:replies -> -is:reply
    - -filter:links -> -has:links
    - -filter:retweets -> -is:retweet
    - lang:en -> lang:en (same)
    """
    conversions = [
        ("-filter:replies", "-is:reply"),
        ("-filter:retweets", "-is:retweet"),
        ("-filter:links", "-has:links"),
        ("filter:links", "has:links"),
    ]

    for web_op, api_op in conversions:
        query = query.replace(web_op, api_op)

    return query


async def fetch_search_raw(query: str, username: str | None = None, min_impressions_filter: int = MIN_IMPRESSIONS_FOR_DISCOVERY) -> tuple[dict, ScrapeStats]:
    """
    Search for tweets using Twitter API v2 WITHOUT thread population.

    Use this when you want to populate threads separately (e.g., for progress tracking).
    Call populate_thread_for_tweet() on each tweet afterward.

    Args:
        query: Search query (supports both web-style and API-style operators)
        username: Username for authentication
        min_impressions_filter: Minimum impressions required for discovery tweets (default: MIN_IMPRESSIONS_FOR_DISCOVERY)

    Returns:
        Tuple of (raw_tweets dict without thread data, ScrapeStats)
    """
    # Determine source type from query (before conversion for logging)
    original_query = query
    if query.startswith("from:"):
        source_type = "account"
        source_value = query.split("from:")[1].split()[0]  # Extract handle
    else:
        source_type = "query"
        source_value = query

    # Convert web-style operators to API-style BEFORE making request
    query = _convert_web_query_to_api(query)

    # Ensure query excludes retweets and replies
    if "-is:retweet" not in query:
        query = f"{query} -is:retweet"
    if "-is:reply" not in query:
        query = f"{query} -is:reply"

    # Log the converted query for debugging
    if query != original_query:
        notify(f"🔄 Query converted: {original_query[:50]}... → {query[:50]}...")

    auth_user = username or DEFAULT_AUTH_USER
    stats = ScrapeStats(source_type=source_type, source_value=source_value, username=auth_user)
    access_token = await ensure_access_token(auth_user)

    if not access_token:
        error("No access token available", status_code=401, function_name="fetch_search_raw", critical=False)
        return {}, stats

    raw_tweets = {}
    response = await _search_tweets(access_token, query, max_results=100)

    data = response.get("data", [])
    includes = response.get("includes", {})
    user_map = _build_user_map(includes)

    stats.fetched = len(data)

    for tweet in data:
        created_at = tweet.get("created_at", "")
        if not _is_within_hours(created_at, MAX_TWEET_AGE_HOURS):
            stats.filtered_old += 1
            continue

        # Filter by minimum impressions for discovery (use user-specific filter)
        metrics = tweet.get("public_metrics", {})
        impressions = metrics.get("impression_count", 0)

        if impressions < min_impressions_filter:
            stats.filtered_impressions += 1
            continue

        tweet_dict = _tweet_to_dict(tweet, user_map, includes)
        raw_tweets[tweet_dict["id"]] = tweet_dict

    stats.passed = len(raw_tweets)  # Before thread filtering
    stats.log_summary()

    return raw_tweets, stats


async def fetch_user_timeline_raw(
    username: str,
    target_user: str,
    max_tweets: int = 50
) -> tuple[dict, ScrapeStats]:
    """
    Fetch tweets from a user's timeline WITHOUT thread population.
    No impressions filter applied (curated source).

    Args:
        username: Username for authentication
        target_user: Handle of user whose timeline to fetch
        max_tweets: Maximum tweets to fetch

    Returns:
        Tuple of (raw_tweets dict without thread data, ScrapeStats)
    """
    query = f"from:{target_user}"
    # No impressions filter for curated sources (user timelines)
    return await fetch_search_raw(query, username, min_impressions_filter=0)


async def fetch_home_timeline_raw(
    username: str,
    max_tweets: int = 50,
    min_impressions_filter: int = MIN_IMPRESSIONS_FOR_DISCOVERY
) -> tuple[dict, ScrapeStats]:
    """
    Fetch home timeline WITHOUT thread population or intent filtering.
    Returns lightweight tweet objects for later selection.

    Args:
        username: Username for authentication
        max_tweets: Maximum tweets to fetch
        min_impressions_filter: Minimum impressions filter

    Returns:
        Tuple of (raw_tweets dict without thread data, ScrapeStats)
    """
    from backend.utlils.utils import is_tweet_seen

    stats = ScrapeStats(source_type="home_timeline", source_value="following", username=username)

    # Get access token
    access_token = await ensure_access_token(username)
    if not access_token:
        error("No access token available for home timeline", status_code=401, function_name="fetch_home_timeline_raw", critical=False)
        return {}, stats

    # Get user ID
    user_id = await _get_authenticated_user_id(access_token)
    if not user_id:
        error("Could not get user ID for home timeline", status_code=400, function_name="fetch_home_timeline_raw", critical=False)
        return {}, stats

    # Fetch timeline
    response = await _fetch_home_timeline_raw(access_token, user_id, max_results=min(max_tweets, 100))

    data = response.get("data", [])
    includes = response.get("includes", {})
    user_map = _build_user_map(includes)

    stats.fetched = len(data)

    # Process tweets (lightweight - no threads, no intent filtering)
    raw_tweets = {}

    for tweet in data:
        tweet_id = tweet.get("id")

        # Skip already seen tweets
        if tweet_id and is_tweet_seen(username, str(tweet_id)):
            stats.filtered_seen += 1
            continue

        # Skip old tweets
        created_at = tweet.get("created_at", "")
        if not _is_within_hours(created_at, MAX_TWEET_AGE_HOURS):
            stats.filtered_old += 1
            continue

        # Skip replies
        if _get_in_reply_to(tweet):
            stats.filtered_replies += 1
            continue

        # Skip retweets
        referenced = tweet.get("referenced_tweets", [])
        is_retweet = any(ref.get("type") == "retweeted" for ref in referenced)
        if is_retweet:
            stats.filtered_retweets += 1
            continue

        # Filter by minimum impressions
        metrics = tweet.get("public_metrics", {})
        impressions = metrics.get("impression_count", 0)

        if impressions < min_impressions_filter:
            stats.filtered_impressions += 1
            continue

        # Convert to dict WITHOUT thread data
        tweet_dict = _tweet_to_dict(tweet, user_map, includes)
        raw_tweets[tweet_dict["id"]] = tweet_dict

    stats.passed = len(raw_tweets)
    stats.log_summary()

    return raw_tweets, stats


async def populate_thread_for_tweet(tweet: dict) -> dict | None:
    """
    Populate thread data for a single tweet.

    Args:
        tweet: Tweet dict from fetch_search_raw (must have id, url, handle, conversation_id, text, etc.)

    Returns:
        Tweet dict with thread data populated, or None if thread is empty (should be filtered)
    """
    tid = tweet.get("id")
    prefetched_data = {
        "handle": tweet.get("handle", ""),
        "conversation_id": tweet.get("conversation_id", tid),
        "text": tweet.get("text", ""),
        "author_profile_pic_url": tweet.get("author_profile_pic_url", ""),
        "media": tweet.get("media", []),
    }

    thread_data = await get_thread(None, tweet["url"], root_id=tid, prefetched_data=prefetched_data)
    tweet["thread"] = thread_data.get("thread", [])
    tweet["thread_ids"] = thread_data.get("thread_ids", [])
    tweet["other_replies"] = thread_data.get("other_replies", [])

    # Update author info from thread data if available
    if thread_data.get("author_profile_pic_url"):
        tweet["author_profile_pic_url"] = thread_data["author_profile_pic_url"]
    if thread_data.get("media"):
        tweet["media"] = thread_data["media"]

    # Skip tweets without thread content
    if not tweet["thread"] or len(tweet["thread"]) == 0:
        return None

    # Replace truncated text with full text from thread
    tweet["text"] = tweet["thread"][0]
    return tweet


async def fetch_search(query: str, username: str | None = None) -> tuple[dict, ScrapeStats]:
    """
    Search for tweets using Twitter API v2 and populate thread data.

    NOTE: For granular progress tracking, use fetch_search_raw() + populate_thread_for_tweet() instead.

    Args:
        query: Search query (supports both web-style and API-style operators)
        username: Username for authentication

    Returns:
        Tuple of (tweets dict, ScrapeStats)
    """
    # Get raw tweets without thread data
    raw_tweets, stats = await fetch_search_raw(query, username)

    # Populate thread data and filter out empty threads
    tweets, no_thread_count = await populate_thread(raw_tweets)
    stats.filtered_no_thread = no_thread_count
    stats.passed = len(tweets)

    # Log the summary
    stats.log_summary()

    return tweets, stats


async def get_thread(ctx, tweet_url: str, root_id: str | None = None, prefetched_data: dict | None = None) -> dict:
    """
    Get thread context for a tweet using Twitter API.

    Same interface as thread.get_thread but uses API instead of scraping.
    Fetches multi-tweet threads (author's continuation tweets).

    Args:
        ctx: Browser context (ignored - kept for interface compatibility)
        tweet_url: URL of the tweet
        root_id: Root tweet ID
        prefetched_data: Optional dict with tweet data already fetched (from _tweet_to_dict).
                        If provided, skips the _get_tweet_by_id API call.
                        Expected keys: handle, conversation_id, text, author_profile_pic_url, media

    Returns:
        Dict with thread, other_replies, author_handle, author_profile_pic_url, media
    """
    empty_result = {
        "thread": [],
        "other_replies": [],
        "author_handle": "",
        "author_profile_pic_url": "",
        "media": []
    }

    # Extract tweet ID from URL if not provided
    if not root_id:
        # URL format: https://x.com/username/status/1234567890
        import re
        match = re.search(r"/status/(\d+)", tweet_url)
        if match:
            root_id = match.group(1)

    if not root_id:
        notify(f"⚠️ get_thread: Could not extract tweet ID from URL: {tweet_url}")
        return empty_result

    # Get access token - use a default user for thread fetching
    access_token = await ensure_access_token(DEFAULT_AUTH_USER)

    if not access_token:
        notify(f"⚠️ get_thread: No access token available for {DEFAULT_AUTH_USER}")
        return empty_result

    # Use prefetched data if available, otherwise fetch the tweet
    if prefetched_data:
        # We already have the data from the initial search - skip _get_tweet_by_id
        author_handle = prefetched_data.get("handle", "")
        conversation_id = prefetched_data.get("conversation_id", root_id)
        root_text = prefetched_data.get("text", "")
        author_profile_pic_url = prefetched_data.get("author_profile_pic_url", "")
        media = prefetched_data.get("media", [])
    else:
        # Fetch the root tweet (slow path - makes API call)
        response = await _get_tweet_by_id(access_token, root_id)

        data = response.get("data")
        if not data:
            # Check if there's error info in the response
            errors = response.get("errors", [])
            if errors:
                error_msg = errors[0].get("detail", errors[0].get("message", "Unknown error"))
                notify(f"⚠️ get_thread: API error for tweet {root_id}: {error_msg}")
            else:
                notify(f"⚠️ get_thread: No data returned for tweet {root_id} (may be deleted/private)")
            return empty_result

        includes = response.get("includes", {})
        user_map = _build_user_map(includes)

        author_id = data.get("author_id", "")
        author_info = user_map.get(author_id, {})
        author_handle = author_info.get("handle", "")
        conversation_id = data.get("conversation_id", root_id)
        root_text = _get_full_text(data)
        author_profile_pic_url = author_info.get("author_profile_pic_url", "")
        media = _extract_media_from_includes(root_id, includes, data)

    # Build the thread: fetch all tweets by the author in this conversation
    thread_texts = []
    thread_tweet_ids = {root_id}  # Track IDs that are part of the thread chain

    # Add root tweet first
    thread_texts.append(root_text)

    # Search for author's other tweets in this conversation (thread continuations)
    if author_handle:
        thread_query = f"from:{author_handle} conversation_id:{conversation_id}"
        thread_response = await _search_tweets(access_token, thread_query, max_results=100)

        thread_data = thread_response.get("data", [])

        # Build a map of tweet_id -> tweet for chain building
        tweet_map = {}
        for tweet in thread_data:
            tweet_map[tweet.get("id")] = tweet

        # Find tweets that are part of the thread chain (replies to root or to other thread tweets)
        # We iterate multiple times to catch nested replies within the thread
        changed = True
        while changed:
            changed = False
            for tweet in thread_data:
                tweet_id = tweet.get("id")
                if tweet_id in thread_tweet_ids:
                    continue  # Already in thread

                # Check if this tweet replies to a tweet in the thread chain
                in_reply_to = _get_in_reply_to(tweet)
                if in_reply_to and in_reply_to in thread_tweet_ids:
                    thread_tweet_ids.add(tweet_id)
                    changed = True

        # Sort thread tweets by ID (chronological order) and extract texts
        # Skip root since we already added it
        sorted_thread_tweets = sorted(
            [tweet_map[tid] for tid in thread_tweet_ids if tid != root_id and tid in tweet_map],
            key=lambda t: int(t.get("id", 0))
        )

        for tweet in sorted_thread_tweets:
            thread_texts.append(_get_full_text(tweet))

    # Get top replies from OTHER users (not the author)
    reply_query = f"conversation_id:{conversation_id} -from:{author_handle} is:reply"
    reply_response = await _search_tweets(access_token, reply_query, max_results=10)

    other_replies = []
    reply_data = reply_response.get("data", [])
    reply_includes = reply_response.get("includes", {})
    reply_user_map = _build_user_map(reply_includes)

    for reply in reply_data[:5]:  # Max 5 replies
        reply_author_id = reply.get("author_id", "")
        reply_user_info = reply_user_map.get(reply_author_id, {})

        other_replies.append({
            "text": _get_full_text(reply),
            "author_handle": reply_user_info.get("handle", ""),
            "author_name": reply_user_info.get("username", ""),
            "likes": reply.get("public_metrics", {}).get("like_count", 0)
        })

    # Convert thread_tweet_ids to sorted list (chronological order)
    sorted_thread_ids = sorted(thread_tweet_ids, key=lambda x: int(x))

    return {
        "thread": thread_texts,
        "thread_ids": sorted_thread_ids,  # For auto-liking all tweets in thread
        "other_replies": other_replies,
        "author_handle": author_handle,
        "author_profile_pic_url": author_profile_pic_url,
        "media": media
    }


async def deep_scrape_thread(ctx, tweet_url: str, tweet_id: str, author_handle: str) -> dict[str, Any]:
    """
    Get full thread with all replies and quote tweets using Twitter API.

    Same interface as thread.deep_scrape_thread but uses API instead of scraping.

    Args:
        ctx: Browser context (ignored - kept for interface compatibility)
        tweet_url: URL of the tweet
        tweet_id: Tweet ID
        author_handle: Handle of the tweet author

    Returns:
        Dict with reply_count, like_count, quote_count, retweet_count, all_reply_ids, replies, quote_tweets
    """
    result = {
        "reply_count": 0,
        "like_count": 0,
        "quote_count": 0,
        "retweet_count": 0,
        "all_reply_ids": [],
        "all_quote_tweet_ids": [],
        "replies": [],
        "quote_tweets": []
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

            # Extract media and quoted tweet from reply
            reply_media = _extract_media_from_includes(reply_id, reply_includes, reply)
            reply_quoted_tweet = _extract_quoted_tweet(reply, reply_user_map, reply_includes)

            all_replies.append({
                "id": reply_id,
                "text": _get_full_text(reply),
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
                "media": reply_media,
                "quoted_tweet": reply_quoted_tweet,
            })

        # Check for more pages
        next_token = reply_response.get("meta", {}).get("next_token")
        if not next_token:
            break

    result["replies"] = all_replies

    # Search for quote tweets of this tweet
    qt_query = f"quoted_tweet_id:{tweet_id}"
    all_quote_tweets = []
    next_token = None

    # Paginate through quote tweets (up to 2 pages)
    for _ in range(2):
        qt_response = await _search_tweets(access_token, qt_query, max_results=100, next_token=next_token)

        qt_data = qt_response.get("data", [])
        qt_includes = qt_response.get("includes", {})
        qt_user_map = _build_user_map(qt_includes)

        for qt in qt_data:
            qt_author_id = qt.get("author_id", "")
            qt_user_info = qt_user_map.get(qt_author_id, {})

            # Skip author's own quote tweets
            if qt_user_info.get("handle", "").lower() == author_handle.lower():
                continue

            qt_id = qt.get("id", "")
            result["all_quote_tweet_ids"].append(qt_id)

            metrics = qt.get("public_metrics", {})
            created_at = qt.get("created_at", "")

            try:
                dt = _parse_twitter_date(created_at)
                created_at_iso = dt.isoformat()
            except Exception:
                created_at_iso = created_at

            qt_handle = qt_user_info.get("handle", "")

            # Extract media from quote tweet
            qt_media = _extract_media_from_includes(qt_id, qt_includes, qt)

            all_quote_tweets.append({
                "id": qt_id,
                "text": _get_full_text(qt),
                "handle": qt_handle,
                "username": qt_user_info.get("username", ""),
                "author_profile_pic_url": qt_user_info.get("author_profile_pic_url", ""),
                "followers": qt_user_info.get("followers", 0),
                "quoted_tweet_id": tweet_id,  # The tweet being quoted
                "created_at": created_at_iso,
                "url": f"https://x.com/{qt_handle}/status/{qt_id}",
                "likes": metrics.get("like_count", 0),
                "retweets": metrics.get("retweet_count", 0),
                "quotes": metrics.get("quote_count", 0),
                "replies": metrics.get("reply_count", 0),
                "impressions": metrics.get("impression_count", 0),
                "media": qt_media,
                "engagement_type": "quote_tweet",
            })

        # Check for more pages
        next_token = qt_response.get("meta", {}).get("next_token")
        if not next_token:
            break

    result["quote_tweets"] = all_quote_tweets
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

    notify(f"[API] Fetching recent tweets from @{username} with query: {query}")

    tweets = []
    next_token = None
    page = 0

    while len(tweets) < max_tweets:
        page += 1
        remaining = max_tweets - len(tweets)
        batch_size = min(remaining, 100)

        response = await _search_tweets(access_token, query, max_results=batch_size, next_token=next_token)

        data = response.get("data", [])
        includes = response.get("includes", {})
        meta = response.get("meta", {})
        user_map = _build_user_map(includes)

        notify(f"[API] Page {page}: Got {len(data)} tweets, meta: {meta}")

        for tweet in data:
            tweet_dict = _tweet_to_dict(tweet, user_map, includes)
            tweets.append(tweet_dict)

            if len(tweets) >= max_tweets:
                break

        # Check for more pages
        next_token = meta.get("next_token")
        if not next_token or not data:
            notify(f"[API] Stopping pagination: next_token={next_token}, data_len={len(data)}")
            break

    notify(f"[API] Fetched {len(tweets)} total tweets from @{username}")
    return tweets


async def _generate_reply_for_tweet_background(tweet: dict, username: str):
    """
    Background task to generate replies for a single tweet.

    This runs in parallel with scraping, so each tweet gets its replies
    generated immediately after being written to cache.

    Args:
        tweet: Tweet data with thread content
        username: Username for user settings and cache operations
    """
    from backend.data.twitter.edit_cache import write_to_cache
    from backend.twitter.generate_replies import generate_replies_for_tweet
    from backend.utlils.utils import read_user_info

    try:
        # Check if user is premium (only generate for premium users)
        user_info = read_user_info(username)
        if not user_info:
            return

        account_type = user_info.get("account_type", "trial")
        if account_type != "premium":
            return

        # Get user settings for models
        models = user_info.get("models", ["claude-3-5-sonnet-20241022"])
        number_of_generations = user_info.get("number_of_generations", 1)

        # Check if tweet already has enough replies
        existing_replies = len(tweet.get("generated_replies", []))
        needed_generations = number_of_generations - existing_replies

        if needed_generations <= 0:
            return

        tweet_id = tweet.get("id") or tweet.get("tweet_id")
        notify(f"🚀 [Parallel] Starting reply generation for tweet {tweet_id}...")

        # Generate replies
        replies = await generate_replies_for_tweet(
            tweet=tweet,
            models=models,
            needed_generations=needed_generations,
            delay_seconds=0.5,  # Shorter delay for parallel generation
            batch=True,  # Don't raise critical errors
            username=username
        )

        if replies:
            # Update tweet with generated replies
            tweet["generated_replies"] = tweet.get("generated_replies", []) + replies

            # Write updated tweet to cache
            await write_to_cache([tweet], f"[Parallel] Generated {len(replies)} replies for tweet {tweet_id}", username=username)
            notify(f"✅ [Parallel] Generated {len(replies)} replies for tweet {tweet_id}")

    except Exception as e:
        tweet_id = tweet.get("id") or tweet.get("tweet_id", "unknown")
        notify(f"⚠️ [Parallel] Error generating replies for tweet {tweet_id}: {e}")


async def _get_authenticated_user_id(access_token: str, _retry_count: int = 0) -> str | None:
    """
    Get the authenticated user's Twitter ID from their access token.

    Args:
        access_token: User's OAuth access token
        _retry_count: Internal retry counter

    Returns:
        User's Twitter ID or None if failed
    """
    await _rate_limiter.wait_if_needed(EndpointType.USER_LOOKUP)

    url = f"{API_BASE}/users/me"
    headers = _get_headers(access_token)

    try:
        response = requests.get(url, headers=headers, timeout=30)
        _rate_limiter.update_last_request(EndpointType.USER_LOOKUP)

        if response.status_code == 429:
            reset_time = response.headers.get("x-rate-limit-reset")
            if reset_time and _retry_count < 3:
                await _rate_limiter.wait_for_reset(int(reset_time), EndpointType.USER_LOOKUP)
                return await _get_authenticated_user_id(access_token, _retry_count + 1)
            return None

        if response.status_code >= 400:
            notify(f"⚠️ Failed to get user ID: HTTP {response.status_code}")
            return None

        data = response.json()
        return data.get("data", {}).get("id")

    except requests.RequestException as e:
        notify(f"⚠️ Failed to get user ID: {e}")
        return None


async def _fetch_home_timeline_raw(
    access_token: str,
    user_id: str,
    max_results: int = 100,
    pagination_token: str | None = None,
    _retry_count: int = 0
) -> dict:
    """
    Fetch the authenticated user's home timeline (reverse chronological).

    This is the "Following" tab - tweets from accounts the user follows.

    Args:
        access_token: User's OAuth access token
        user_id: User's Twitter ID
        max_results: Max results per request (1-100)
        pagination_token: Pagination token for next page
        _retry_count: Internal retry counter

    Returns:
        API response dict with data, includes, and meta
    """
    await _rate_limiter.wait_if_needed(TWITTER_HOME_TIMELINE)

    url = f"{API_BASE}/users/{user_id}/timelines/reverse_chronological"

    params = {
        "max_results": min(max_results, 100),
        "tweet.fields": TWEET_FIELDS,
        "user.fields": USER_FIELDS,
        "expansions": EXPANSIONS,
        "media.fields": MEDIA_FIELDS,
    }

    if pagination_token:
        params["pagination_token"] = pagination_token

    headers = _get_headers(access_token)

    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        _rate_limiter.update_last_request(TWITTER_HOME_TIMELINE)

        if response.status_code == 401:
            error("Twitter API authentication failed for home timeline", status_code=401, function_name="_fetch_home_timeline_raw", critical=False)
            return {"data": [], "includes": {}, "meta": {}}

        if response.status_code == 429:
            reset_time = response.headers.get("x-rate-limit-reset")
            if reset_time and _retry_count < 3:
                await _rate_limiter.wait_for_reset(int(reset_time), TWITTER_HOME_TIMELINE)
                return await _fetch_home_timeline_raw(access_token, user_id, max_results, pagination_token, _retry_count + 1)
            else:
                error("Twitter API rate limit exceeded for home timeline", status_code=429, function_name="_fetch_home_timeline_raw", critical=False)
                return {"data": [], "includes": {}, "meta": {}}

        if response.status_code >= 400:
            error(f"Twitter API error for home timeline: {response.text}", status_code=response.status_code, function_name="_fetch_home_timeline_raw", critical=False)
            return {"data": [], "includes": {}, "meta": {}}

        return response.json()

    except requests.RequestException as e:
        error(f"Twitter API request failed for home timeline: {e}", status_code=503, function_name="_fetch_home_timeline_raw", critical=False)
        return {"data": [], "includes": {}, "meta": {}}


async def fetch_home_timeline_with_intent_filter(
    username: str,
    max_tweets: int = 50,
    min_impressions_filter: int = MIN_IMPRESSIONS_FOR_DISCOVERY
) -> tuple[dict, ScrapeStats]:
    """
    Fetch tweets from the user's home timeline and filter by intent.

    This fetches the "Following" tab (reverse chronological timeline) and
    filters tweets through the user's intent filter.

    Args:
        username: Username for authentication
        max_tweets: Maximum tweets to fetch and filter
        min_impressions_filter: Minimum impressions required for discovery tweets (default: MIN_IMPRESSIONS_FOR_DISCOVERY)

    Returns:
        Tuple of (tweets dict, ScrapeStats)
    """
    from backend.twitter.filtering import check_tweet_matches_intent_initial
    from backend.utlils.utils import is_tweet_seen

    stats = ScrapeStats(source_type="home_timeline", source_value="following", username=username)

    # Get access token for the user
    access_token = await ensure_access_token(username)

    if not access_token:
        error("No access token available for home timeline", status_code=401, function_name="fetch_home_timeline_with_intent_filter", critical=False)
        return {}, stats

    # Get user's Twitter ID
    user_id = await _get_authenticated_user_id(access_token)
    if not user_id:
        error("Could not get user ID for home timeline", status_code=400, function_name="fetch_home_timeline_with_intent_filter", critical=False)
        return {}, stats

    # Fetch timeline
    response = await _fetch_home_timeline_raw(access_token, user_id, max_results=min(max_tweets, 100))

    data = response.get("data", [])
    includes = response.get("includes", {})
    user_map = _build_user_map(includes)

    stats.fetched = len(data)

    # Process tweets and filter by intent
    tweets = {}

    for tweet in data:
        tweet_id = tweet.get("id")

        # Skip already seen tweets
        if tweet_id and is_tweet_seen(username, str(tweet_id)):
            stats.filtered_seen += 1
            continue

        # Skip old tweets
        created_at = tweet.get("created_at", "")
        if not _is_within_hours(created_at, MAX_TWEET_AGE_HOURS):
            stats.filtered_old += 1
            continue

        # Skip replies (we want original posts only)
        if _get_in_reply_to(tweet):
            stats.filtered_replies += 1
            continue

        # Skip retweets
        referenced = tweet.get("referenced_tweets", [])
        is_retweet = any(ref.get("type") == "retweeted" for ref in referenced)
        if is_retweet:
            stats.filtered_retweets += 1
            continue

        # Filter by minimum impressions for discovery (home timeline = FYP, use user-specific filter)
        metrics = tweet.get("public_metrics", {})
        impressions = metrics.get("impression_count", 0)

        if impressions < min_impressions_filter:
            stats.filtered_impressions += 1
            continue

        tweet_dict = _tweet_to_dict(tweet, user_map, includes)

        # Check intent filter
        passes_intent = await check_tweet_matches_intent_initial(tweet_dict, username)

        if not passes_intent:
            stats.filtered_intent += 1
            continue

        # Get thread data
        thread_data = await get_thread(None, tweet_dict["url"], root_id=tweet_dict["id"])
        tweet_dict["thread"] = thread_data.get("thread", [])
        tweet_dict["thread_ids"] = thread_data.get("thread_ids", [])
        tweet_dict["other_replies"] = thread_data.get("other_replies", [])

        if thread_data.get("author_profile_pic_url"):
            tweet_dict["author_profile_pic_url"] = thread_data["author_profile_pic_url"]
        if thread_data.get("media"):
            tweet_dict["media"] = thread_data["media"]

        # Skip tweets without thread content
        if not tweet_dict["thread"] or len(tweet_dict["thread"]) == 0:
            stats.filtered_no_thread += 1
            continue

        # Replace truncated text with full text from thread
        tweet_dict["text"] = tweet_dict["thread"][0]

        # Mark where this tweet came from
        tweet_dict["scraped_from"] = {"type": "home_timeline", "value": "following"}

        tweets[tweet_dict["id"]] = tweet_dict

    stats.passed = len(tweets)

    # Log the summary
    stats.log_summary()

    return tweets, stats
