"""
Twitter Router - Centralized routing between API and browser automation.

This module provides a single interface for all Twitter operations,
routing them to either API or browser automation based on configuration.

This makes it easy to:
- See which operations use which method
- Switch between API and browser for specific operations
- Test different routing strategies
- Support hybrid approaches (try API, fallback to browser)
"""

from enum import Enum
from typing import Any, Literal

from backend.utlils.utils import notify


class ExecutionMethod(Enum):
    """Method to use for executing Twitter operations."""
    API = "api"                 # Use Twitter API v2
    BROWSER = "browser"         # Use headless browser automation
    AUTO = "auto"               # Try API first, fallback to browser on failure
    DISABLED = "disabled"       # Operation is disabled


# =============================================================================
# ROUTE CONFIGURATION
# =============================================================================
# This is the central configuration that controls which method is used for each operation.
# Change these values to route operations to API or browser.

ROUTE_CONFIG: dict[str, ExecutionMethod] = {
    # Discovery operations (finding tweets) - BROWSER MODE for bread accounts
    "search_tweets": ExecutionMethod.BROWSER,
    "fetch_home_timeline": ExecutionMethod.API,  # MUST use API - home timeline is user-specific, can't use bread account
    "fetch_user_timeline": ExecutionMethod.BROWSER,

    # Thread scraping (getting replies, context) - BROWSER MODE for bread accounts
    "get_thread": ExecutionMethod.BROWSER,
    "deep_scrape_thread": ExecutionMethod.BROWSER,
    "shallow_scrape_thread": ExecutionMethod.BROWSER,

    # Posting operations - KEEP API (uses user OAuth tokens)
    "post_tweet": ExecutionMethod.API,
    "like_tweet": ExecutionMethod.API,

    # User operations - KEEP API
    "lookup_user": ExecutionMethod.API,
    "get_user_mentions": ExecutionMethod.API,
}


def get_execution_method(operation: str) -> ExecutionMethod:
    """Get the configured execution method for an operation."""
    return ROUTE_CONFIG.get(operation, ExecutionMethod.API)


def set_execution_method(operation: str, method: ExecutionMethod):
    """Change the execution method for an operation at runtime."""
    ROUTE_CONFIG[operation] = method
    notify(f"🔄 Routing {operation} to {method.value}")


def get_route_summary() -> dict[str, str]:
    """
    Get a summary of all routes and their methods.

    Returns:
        Dict mapping operation names to their execution methods
    """
    return {operation: method.value for operation, method in ROUTE_CONFIG.items()}


def print_route_summary():
    """Print a formatted summary of all routes."""
    print("\n" + "="*70)
    print("TWITTER ROUTER CONFIGURATION")
    print("="*70)

    # Group by method
    by_method: dict[str, list[str]] = {}
    for operation, method in ROUTE_CONFIG.items():
        method_name = method.value
        if method_name not in by_method:
            by_method[method_name] = []
        by_method[method_name].append(operation)

    for method_name in sorted(by_method.keys()):
        operations = by_method[method_name]
        print(f"\n{method_name.upper()}: ({len(operations)} operations)")
        for op in sorted(operations):
            print(f"  • {op}")

    print("="*70 + "\n")


# =============================================================================
# ROUTER FUNCTIONS
# =============================================================================
# These functions route operations to the appropriate implementation.


async def search_tweets(
    query: str,
    ctx=None,  # Browser context (required for BROWSER mode)
    username: str | None = None,
    min_impressions_filter: int = 2000,
    since_id: str | None = None
) -> tuple[dict, Any]:
    """
    Search for tweets.

    Routes to API or browser based on configuration.

    Args:
        query: Search query
        ctx: Browser context (required for BROWSER mode)
        username: Username for data routing
        min_impressions_filter: Minimum impressions filter (not used in browser mode)
        since_id: Tweet ID for pagination (not used in browser mode yet)

    Returns:
        Tuple of (tweets dict, stats object)
    """
    method = get_execution_method("search_tweets")

    if method == ExecutionMethod.DISABLED:
        notify("⚠️ search_tweets is disabled")
        return {}, None

    if method == ExecutionMethod.BROWSER:
        notify("🌐 [BROWSER] Searching tweets via browser automation")
        from backend.browser_automation.twitter.timeline import fetch_search
        from backend.browser_automation.twitter.api import ScrapeStats

        if ctx is None:
            raise ValueError("Browser context (ctx) required for BROWSER mode")

        # Create stats object to match API return format
        stats = ScrapeStats(source_type="query", source_value=query, username=username or "unknown")

        # Call browser function
        tweets = await fetch_search(
            ctx=ctx,
            query=query,
            username=username,
            write_callback=None,  # No progressive writing for now
            stats=stats
        )

        # Stats already updated in collect_from_page
        # Update passed count (fetched is tracked in the loop)
        stats.passed = len(tweets)

        return tweets, stats

    elif method == ExecutionMethod.AUTO:
        try:
            notify("🔄 [AUTO] Trying API for search_tweets...")
            from backend.browser_automation.twitter.api import fetch_search_raw
            return await fetch_search_raw(query, username, min_impressions_filter, since_id)
        except Exception as e:
            notify(f"⚠️ [AUTO] API failed: {e}, falling back to browser")
            # TODO: Implement browser fallback
            raise NotImplementedError("Browser fallback not yet implemented")

    else:  # API (default)
        notify("🔌 [API] Searching tweets via Twitter API")
        from backend.browser_automation.twitter.api import fetch_search_raw
        return await fetch_search_raw(query, username, min_impressions_filter, since_id)


async def fetch_home_timeline(
    username: str,
    ctx=None,  # Browser context (required for BROWSER mode)
    max_tweets: int = 50,
    min_impressions_filter: int = 2000,
    since_id: str | None = None
) -> tuple[dict, Any]:
    """
    Fetch user's home timeline.

    Routes to API or browser based on configuration.

    Args:
        username: Username for data routing
        ctx: Browser context (required for BROWSER mode)
        max_tweets: Maximum tweets to fetch
        min_impressions_filter: Not used in browser mode
        since_id: Not used in browser mode yet

    Returns:
        Tuple of (tweets dict, stats object)
    """
    method = get_execution_method("fetch_home_timeline")

    if method == ExecutionMethod.DISABLED:
        notify("⚠️ fetch_home_timeline is disabled")
        return {}, None

    if method == ExecutionMethod.BROWSER:
        notify("🌐 [BROWSER] Fetching home timeline via browser")
        from backend.browser_automation.twitter.tools import collect_from_page
        from backend.browser_automation.twitter.api import ScrapeStats

        if ctx is None:
            raise ValueError("Browser context (ctx) required for BROWSER mode")

        # Create stats object
        stats = ScrapeStats(source_type="home_timeline", source_value="home", username=username)

        # Use collect_from_page to scrape home timeline
        url = "https://x.com/home"
        tweets = await collect_from_page(
            ctx=ctx,
            url=url,
            handle=None,  # No specific handle for home feed
            username=username,
            write_callback=None,
            stats=stats
        )

        # Stats already updated in collect_from_page
        # Update passed count (fetched is tracked in the loop)
        stats.passed = len(tweets)

        return tweets, stats

    elif method == ExecutionMethod.AUTO:
        try:
            notify("🔄 [AUTO] Trying API for home timeline...")
            from backend.browser_automation.twitter.api import fetch_home_timeline_raw
            return await fetch_home_timeline_raw(username, max_tweets, min_impressions_filter, since_id)
        except Exception as e:
            notify(f"⚠️ [AUTO] API failed: {e}, falling back to browser")
            raise NotImplementedError("Browser fallback not yet implemented")

    else:  # API (default)
        notify("🔌 [API] Fetching home timeline via Twitter API")
        from backend.browser_automation.twitter.api import fetch_home_timeline_raw
        return await fetch_home_timeline_raw(username, max_tweets, min_impressions_filter, since_id)


async def fetch_user_timeline(
    username: str,
    target_user: str,
    ctx=None,  # Browser context (required for BROWSER mode)
    max_tweets: int = 50,
    since_id: str | None = None,
    user_id: str | None = None
) -> tuple[dict, Any]:
    """
    Fetch a specific user's timeline.

    Routes to API or browser based on configuration.

    Args:
        username: Username for data routing
        target_user: Target user's handle to scrape
        ctx: Browser context (required for BROWSER mode)
        max_tweets: Maximum tweets (not enforced in browser mode)
        since_id: Not used in browser mode yet
        user_id: Not used in browser mode

    Returns:
        Tuple of (tweets dict, stats object)
    """
    method = get_execution_method("fetch_user_timeline")

    if method == ExecutionMethod.DISABLED:
        notify("⚠️ fetch_user_timeline is disabled")
        return {}, None

    if method == ExecutionMethod.BROWSER:
        notify(f"🌐 [BROWSER] Fetching @{target_user}'s timeline via browser")
        from backend.browser_automation.twitter.timeline import fetch_user_tweets
        from backend.browser_automation.twitter.api import ScrapeStats

        if ctx is None:
            raise ValueError("Browser context (ctx) required for BROWSER mode")

        # Create stats object
        stats = ScrapeStats(source_type="user_timeline", source_value=target_user, username=username)

        # Call browser function
        tweets = await fetch_user_tweets(
            ctx=ctx,
            handle=target_user,
            username=username,
            write_callback=None,
            stats=stats
        )

        # Stats already updated in collect_from_page
        # Update passed count (fetched is tracked in the loop)
        stats.passed = len(tweets)

        return tweets, stats

    elif method == ExecutionMethod.AUTO:
        try:
            notify(f"🔄 [AUTO] Trying API for @{target_user}'s timeline...")
            from backend.browser_automation.twitter.api import fetch_user_timeline_raw
            return await fetch_user_timeline_raw(username, target_user, max_tweets, since_id, user_id)
        except Exception as e:
            notify(f"⚠️ [AUTO] API failed: {e}, falling back to browser")
            raise NotImplementedError("Browser fallback not yet implemented")

    else:  # API (default)
        notify(f"🔌 [API] Fetching @{target_user}'s timeline via Twitter API")
        from backend.browser_automation.twitter.api import fetch_user_timeline_raw
        return await fetch_user_timeline_raw(username, target_user, max_tweets, since_id, user_id)


async def get_thread(
    ctx,
    tweet_url: str,
    root_id: str | None = None
) -> dict:
    """
    Get thread context for a tweet (author's thread tweets).

    Routes to API or browser based on configuration.

    Args:
        ctx: Browser context (required for BROWSER mode)
        tweet_url: URL of the tweet
        root_id: Root tweet ID (optional)

    Returns:
        Dict with thread, other_replies, author_handle, author_profile_pic_url, media
    """
    method = get_execution_method("get_thread")

    if method == ExecutionMethod.DISABLED:
        notify("⚠️ get_thread is disabled")
        return {
            "thread": [],
            "thread_ids": [],
            "other_replies": [],
            "author_handle": "",
            "author_profile_pic_url": "",
            "media": []
        }

    if method == ExecutionMethod.BROWSER:
        notify(f"🌐 [BROWSER] Getting thread via browser for {tweet_url}")
        from backend.browser_automation.twitter.thread import get_thread as browser_get_thread

        if ctx is None:
            raise ValueError("Browser context (ctx) required for BROWSER mode")

        return await browser_get_thread(ctx, tweet_url, root_id)

    elif method == ExecutionMethod.AUTO:
        try:
            notify(f"🔄 [AUTO] Trying API for get_thread...")
            from backend.browser_automation.twitter.api import get_thread as api_get_thread
            return await api_get_thread(ctx, tweet_url, root_id)
        except Exception as e:
            notify(f"⚠️ [AUTO] API failed: {e}, falling back to browser")
            raise NotImplementedError("Browser fallback not yet implemented")

    else:  # API (default)
        notify(f"🔌 [API] Getting thread via Twitter API for {tweet_url}")
        from backend.browser_automation.twitter.api import get_thread as api_get_thread
        return await api_get_thread(ctx, tweet_url, root_id)


async def deep_scrape_thread(
    ctx,
    tweet_url: str,
    tweet_id: str,
    author_handle: str
) -> dict[str, Any]:
    """
    Deep scrape a thread (get all replies, metrics, etc.).

    Routes to API or browser based on configuration.

    Returns:
        Dict with reply_count, like_count, replies, quote_tweets, etc.
    """
    method = get_execution_method("deep_scrape_thread")

    if method == ExecutionMethod.DISABLED:
        notify("⚠️ deep_scrape_thread is disabled")
        return {
            "reply_count": 0,
            "like_count": 0,
            "quote_count": 0,
            "retweet_count": 0,
            "replies": [],
            "quote_tweets": []
        }

    if method == ExecutionMethod.BROWSER:
        notify(f"🌐 [BROWSER] Deep scraping thread {tweet_id} via browser")
        from backend.browser_automation.twitter.thread import deep_scrape_thread as browser_deep_scrape

        if ctx is None:
            raise ValueError("Browser context (ctx) required for BROWSER mode")

        # Call browser version
        return await browser_deep_scrape(ctx, tweet_url, tweet_id, author_handle)

    elif method == ExecutionMethod.AUTO:
        try:
            notify(f"🔄 [AUTO] Trying API for deep scrape {tweet_id}...")
            from backend.browser_automation.twitter.api import deep_scrape_thread as api_deep_scrape
            return await api_deep_scrape(ctx, tweet_url, tweet_id, author_handle)
        except Exception as e:
            notify(f"⚠️ [AUTO] API failed: {e}, falling back to browser")
            raise NotImplementedError("Browser fallback not yet implemented")

    else:  # API (default)
        notify(f"🔌 [API] Deep scraping thread {tweet_id} via Twitter API")
        from backend.browser_automation.twitter.api import deep_scrape_thread as api_deep_scrape
        return await api_deep_scrape(ctx, tweet_url, tweet_id, author_handle)


async def shallow_scrape_thread(
    ctx,
    tweet_url: str,
    tweet_id: str
) -> dict[str, Any]:
    """
    Shallow scrape a thread (get basic metrics only).

    Routes to API or browser based on configuration.

    Returns:
        Dict with reply_count, like_count, quote_count, retweet_count, latest_reply_ids
    """
    method = get_execution_method("shallow_scrape_thread")

    if method == ExecutionMethod.DISABLED:
        notify("⚠️ shallow_scrape_thread is disabled")
        return {
            "reply_count": 0,
            "like_count": 0,
            "quote_count": 0,
            "retweet_count": 0,
            "latest_reply_ids": []
        }

    if method == ExecutionMethod.BROWSER:
        notify(f"🌐 [BROWSER] Shallow scraping thread {tweet_id} via browser")
        # For now, use deep_scrape and extract shallow metrics
        # TODO: Implement optimized shallow scrape for browser
        from backend.browser_automation.twitter.thread import deep_scrape_thread as browser_deep_scrape

        if ctx is None:
            raise ValueError("Browser context (ctx) required for BROWSER mode")

        # Call deep scrape and extract basic metrics
        full_result = await browser_deep_scrape(ctx, tweet_url, tweet_id, "unknown")

        # Return only shallow metrics
        return {
            "reply_count": full_result.get("reply_count", 0),
            "like_count": full_result.get("like_count", 0),
            "quote_count": full_result.get("quote_count", 0),
            "retweet_count": full_result.get("retweet_count", 0),
            "latest_reply_ids": [r.get("id") for r in full_result.get("replies", [])[:10]]
        }

    elif method == ExecutionMethod.AUTO:
        try:
            notify(f"🔄 [AUTO] Trying API for shallow scrape {tweet_id}...")
            from backend.browser_automation.twitter.api import shallow_scrape_thread as api_shallow_scrape
            return await api_shallow_scrape(ctx, tweet_url, tweet_id)
        except Exception as e:
            notify(f"⚠️ [AUTO] API failed: {e}, falling back to browser")
            raise NotImplementedError("Browser fallback not yet implemented")

    else:  # API (default)
        notify(f"🔌 [API] Shallow scraping thread {tweet_id} via Twitter API")
        from backend.browser_automation.twitter.api import shallow_scrape_thread as api_shallow_scrape
        return await api_shallow_scrape(ctx, tweet_url, tweet_id)


async def post_tweet(
    username: str,
    payload: dict,
    cache_id: str | None = None,
    reply_index: int | None = None,
    post_type: str = "reply"
) -> dict:
    """
    Post a tweet (reply, quote, or original).

    Routes to API or browser based on configuration.

    Returns:
        Dict with success status and posted tweet data
    """
    method = get_execution_method("post_tweet")

    if method == ExecutionMethod.DISABLED:
        notify("⚠️ post_tweet is disabled")
        raise Exception("Posting is disabled")

    if method == ExecutionMethod.BROWSER:
        notify(f"🌐 [BROWSER] Posting tweet via browser for @{username}")
        # TODO: Implement browser version
        raise NotImplementedError("Browser-based posting not yet implemented")

    elif method == ExecutionMethod.AUTO:
        try:
            notify(f"🔄 [AUTO] Trying API for posting @{username}...")
            from backend.twitter.posting import post as api_post
            return await api_post(username, payload, cache_id, reply_index, post_type)
        except Exception as e:
            notify(f"⚠️ [AUTO] API failed: {e}, falling back to browser")
            raise NotImplementedError("Browser fallback not yet implemented")

    else:  # API (default)
        notify(f"🔌 [API] Posting tweet via Twitter API for @{username}")
        from backend.twitter.posting import post as api_post
        return await api_post(username, payload, cache_id, reply_index, post_type)


async def like_tweet(username: str, tweet_id: str) -> bool:
    """
    Like a tweet.

    Routes to API or browser based on configuration.

    Returns:
        True if successful, False otherwise
    """
    method = get_execution_method("like_tweet")

    if method == ExecutionMethod.DISABLED:
        notify("⚠️ like_tweet is disabled")
        return False

    if method == ExecutionMethod.BROWSER:
        notify(f"🌐 [BROWSER] Liking tweet {tweet_id} via browser")
        # TODO: Implement browser version
        raise NotImplementedError("Browser-based liking not yet implemented")

    elif method == ExecutionMethod.AUTO:
        try:
            notify(f"🔄 [AUTO] Trying API for liking {tweet_id}...")
            from backend.twitter.posting import like_tweet as api_like
            return await api_like(username, tweet_id)
        except Exception as e:
            notify(f"⚠️ [AUTO] API failed: {e}, falling back to browser")
            raise NotImplementedError("Browser fallback not yet implemented")

    else:  # API (default)
        notify(f"🔌 [API] Liking tweet {tweet_id} via Twitter API")
        from backend.twitter.posting import like_tweet as api_like
        return await api_like(username, tweet_id)


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================


def enable_browser_mode_for_operation(operation: str):
    """Enable browser automation for a specific operation."""
    set_execution_method(operation, ExecutionMethod.BROWSER)


def enable_api_mode_for_operation(operation: str):
    """Enable API mode for a specific operation."""
    set_execution_method(operation, ExecutionMethod.API)


def enable_auto_mode_for_operation(operation: str):
    """Enable auto mode (API with browser fallback) for a specific operation."""
    set_execution_method(operation, ExecutionMethod.AUTO)


def enable_browser_mode_for_all():
    """Switch all operations to browser automation."""
    for operation in ROUTE_CONFIG.keys():
        ROUTE_CONFIG[operation] = ExecutionMethod.BROWSER
    notify("🌐 All operations switched to BROWSER mode")


def enable_api_mode_for_all():
    """Switch all operations to API."""
    for operation in ROUTE_CONFIG.keys():
        ROUTE_CONFIG[operation] = ExecutionMethod.API
    notify("🔌 All operations switched to API mode")


def enable_auto_mode_for_all():
    """Switch all operations to auto mode (API with browser fallback)."""
    for operation in ROUTE_CONFIG.keys():
        ROUTE_CONFIG[operation] = ExecutionMethod.AUTO
    notify("🔄 All operations switched to AUTO mode")


# Print configuration on import
if __name__ == "__main__":
    print_route_summary()
