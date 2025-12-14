import asyncio
import os
import re
import time

from fastapi import APIRouter, HTTPException, status
from playwright.async_api import async_playwright
from pydantic import BaseModel

from backend.config import (
    DEFAULT_MAX_TWEETS_RETRIEVE as MAX_TWEETS_RETRIEVE,
)
from backend.config import (
    DEFAULT_TWITTER_USERNAME as USERNAME,
)
from backend.config import (
    MAX_TWEET_AGE_HOURS,
    SHOW_BROWSER,
    USE_BROWSERBASE_FOR_SCRAPING,
)
from backend.utlils.resolve_imports import ensure_standalone_imports

ensure_standalone_imports(globals())

try:
    from backend.browser_automation.twitter.tools import collect_from_page
    from backend.twitter.logging import log_scrape_action
    from backend.utlils.utils import error, notify, read_user_info, write_user_info
except ImportError:
    from backend.browser_automation.twitter.tools import collect_from_page
    from backend.twitter.logging import log_scrape_action
    from backend.utlils.utils import error, notify, read_user_info, write_user_info



def should_use_browserbase_for_scraping() -> bool:
    """
    Return True if scraping should use Browserbase instead of local browser.
    Uses USE_BROWSERBASE_FOR_SCRAPING config variable (can be overridden by env var).
    """
    browserbase_env = os.getenv("USE_BROWSERBASE_FOR_SCRAPING")
    if browserbase_env is not None:
        return browserbase_env.lower() in ("true", "1", "yes")
    # Use config value
    return USE_BROWSERBASE_FOR_SCRAPING


see_browser = SHOW_BROWSER

# NOTE: Status tracking is now handled by job_status in twitter_jobs.py
# The scraping_status global has been removed - use get_scraping_status_from_job_status() instead


def get_scraping_status_from_job_status(username: str) -> dict:
    """
    Get scraping status by translating from job_status.
    Provides backward compatibility for frontend polling.
    """
    from backend.twitter.twitter_jobs import get_job_status

    # Get the find_and_reply_to_new_posts job status (main scraping job)
    job = get_job_status(username, "find_and_reply_to_new_posts")

    if job["status"] == "idle":
        return {"type": "idle", "value": "", "phase": "idle"}

    if job["status"] == "complete":
        return {"type": "complete", "value": "", "phase": "complete"}

    if job["status"] == "error":
        return {"type": "error", "value": job.get("error", ""), "phase": "error"}

    # Running - translate phase to type/value format
    phase = job.get("phase", "")

    # Phase format: "scraping_account:handle" or "scraping_query:text" or "scanning_home_timeline"
    if ":" in phase:
        action, target = phase.split(":", 1)
        if action == "scraping_account":
            return {"type": "account", "value": target, "phase": "scraping_api"}
        elif action == "scraping_query":
            return {"type": "query", "value": target, "summary": target, "phase": "scraping_api"}

    if phase == "scanning_home_timeline":
        return {"type": "home_timeline", "value": "following", "phase": "scraping_api"}

    if phase == "generating_replies":
        return {"type": "generating", "value": "", "phase": "generating"}

    if phase == "cleanup":
        return {"type": "cleanup", "value": "", "phase": "cleanup"}

    # Default - show as running
    return {"type": "scraping", "value": "", "phase": phase or "running"}


# headless login, legacy code, currently use oAuth instead
async def log_in(username: str, password: str, browser=None):
    from backend.utlils.utils import store_browser_state

    if browser is None:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=(not see_browser))
    ctx = await browser.new_context()
    page = await ctx.new_page()

    await page.goto("https://x.com/i/flow/login?lang=en")
    await page.fill('input[name="text"]', username)
    await page.press('input[name="text"]', "Enter")
    await page.fill('input[name="password"]', password)
    await page.press('input[name="password"]', "Enter")
    await page.wait_for_url("https://x.com/home", timeout=60_000)

    await store_browser_state(username, ctx)
    return browser, ctx


async def get_home(browser=None, username=None):
    from backend.utlils.utils import read_browser_state

    if browser is None:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=(not see_browser))
    # Use provided username or fall back to default
    user = username or USERNAME
    session = await read_browser_state(browser, user)
    if session:
        return session
    error("No authorization found; user needs to log in.", critical=True)


# -------- Core collectors --------
GRAPHQL_TWEET_RE = re.compile(r"/i/api/graphql/[^/]+/(UserTweets|SearchTimeline|SearchTimelineV2|HomeTimeline|HomeLatestTimeline)")


async def fetch_user_tweets(ctx, handle: str, username=None, write_callback=None, **kwargs):
    url = f"https://x.com/{handle}"
    return await collect_from_page(ctx, url, handle=handle, username=username, write_callback=write_callback, **kwargs)


async def fetch_search(ctx, query: str, username=None, write_callback=None, **kwargs):
    from urllib.parse import quote_plus

    q = quote_plus(query)  # encodes spaces, quotes, parens, etc.
    url = f"https://x.com/search?q={q}&src=typed_query"
    return await collect_from_page(ctx, url, handle=None, username=username, write_callback=write_callback, **kwargs)


# -------- Orchestration --------
async def gather_trending(usernames, queries, username=None, write_callback=None, use_browserbase=False, query_summary_map=None):
    """
    Gather trending tweets using Twitter API v2, including full thread content.

    Args:
        usernames: List of Twitter handles to scrape
        queries: List of search queries
        username: Username for cache writes and API authentication
        write_callback: Async function to call for incremental writes
        use_browserbase: Ignored - kept for backwards compatibility
        query_summary_map: Map of query -> summary for display

    Returns:
        dict: Scraped tweets with thread content
    """
    from backend.browser_automation.twitter.api import collect_from_page as api_collect_from_page

    # Helper to set scraped_from on tweets before writing
    async def _set_source_and_write(batch, user, source, original_callback):
        for tweet in batch:
            tweet["scraped_from"] = source
        await original_callback(batch, user)

    notify(f"🚀 [gather_trending] Starting API scraping for {username}: {len(usernames)} accounts, {len(queries)} queries")
    results = {}

    # Scrape user timelines via API (collect_from_page includes thread fetching)
    for u in usernames:
        try:
            notify(f"📍 Scraping from @{u} via API")

            url = f"https://x.com/{u}"
            account_source = {"type": "account", "value": u}
            # Create wrapper callback that sets scraped_from before writing
            wrapped_callback = (
                (lambda batch, user, src=account_source: _set_source_and_write(batch, user, src, write_callback))
                if write_callback else None
            )
            tweets = await api_collect_from_page(None, url, handle=u, username=username, write_callback=wrapped_callback)
            for tweet_data in tweets.values():
                tweet_data["scraped_from"] = account_source
            results.update(tweets)
            notify(f"✅ [API] Fetched {len(tweets)} tweets with threads from @{u}")
        except Exception as e:
            notify(f"❌ [API] Error fetching @{u}: {e}")

    # Scrape queries via API (collect_from_page includes thread fetching)
    for q in queries:
        try:
            summary = query_summary_map.get(q, q) if query_summary_map else q
            notify(f"📍 Scraping query [{q}] via API")

            from urllib.parse import quote_plus
            url = f"https://x.com/search?q={quote_plus(q)}"
            query_source = {"type": "query", "value": q, "summary": summary}
            # Create wrapper callback that sets scraped_from before writing
            wrapped_callback = (
                (lambda batch, user, src=query_source: _set_source_and_write(batch, user, src, write_callback))
                if write_callback else None
            )
            tweets = await api_collect_from_page(None, url, handle=None, username=username, write_callback=wrapped_callback)
            for tweet_data in tweets.values():
                tweet_data["scraped_from"] = query_source
            results.update(tweets)
            notify(f"✅ [API] Fetched {len(tweets)} tweets with threads for query [{q}]")
        except Exception as e:
            notify(f"❌ [API] Error searching [{q}]: {e}")

    notify(f"✅ [gather_trending] Completed for {username}: {len(results)} tweets scraped via API")
    return results


async def read_tweets(username=USERNAME, relevant_accounts=None, queries=None, max_tweets=None):
    from backend.data.twitter.edit_cache import cleanup_old_tweets, purge_unedited_tweets, write_to_cache
    from backend.user.user import read_user_settings
    from backend.utlils.utils import read_user_info

    user_settings = read_user_settings(username)

    # Check if user settings exist (required for per-user configuration)
    if not user_settings:
        error(f"No settings found for user {username}. Please configure settings first.", critical=True)

    if relevant_accounts is None:
        # Extract only accounts where validated is True, as a list of handles
        accounts_dict = user_settings.get("relevant_accounts", {})
        relevant_accounts = [handle for handle, validated in accounts_dict.items() if validated]

    # Build query summary map from user_info (stores full [query, summary] pairs)
    query_summary_map = {}
    user_info = read_user_info(username)

    if queries is None:
        if user_info:
            stored_queries = user_info.get("queries", [])
            queries = []
            for q in stored_queries:
                if isinstance(q, list) and len(q) == 2:
                    # New format: [query, summary]
                    queries.append(q[0])
                    query_summary_map[q[0]] = q[1]
                elif isinstance(q, str):
                    # Legacy format: just query string
                    queries.append(q)
                    query_summary_map[q] = q  # Use query itself as summary for legacy
        else:
            # Fallback to user_settings if user_info not available
            queries = user_settings.get("queries", [])
            for q in queries:
                query_summary_map[q] = q  # No summaries available in this path
    else:
        # If queries provided externally, use them as-is without summaries
        for q in queries:
            query_summary_map[q] = q

    if max_tweets is None:
        max_tweets = user_settings.get("max_tweets_retrieve", MAX_TWEETS_RETRIEVE)

    # NOTE: We no longer auto-purge unedited tweets before scraping.
    # Instead, the user is prompted via modal after scraping completes.
    # Only clean up OLD tweets (beyond age threshold) - these are stale regardless
    await cleanup_old_tweets(username, hours=MAX_TWEET_AGE_HOURS)

    # Clean up old seen_tweets entries
    from backend.utlils.utils import cleanup_seen_tweets
    cleanup_seen_tweets(username, hours=MAX_TWEET_AGE_HOURS)

    # Define progressive write callback for incremental updates
    async def progressive_write(tweets_batch, target_username):
        """Write tweets incrementally as they're discovered, filtering out already-seen tweets"""
        from backend.utlils.utils import is_tweet_seen

        # Filter out tweets that were already seen
        filtered_batch = []
        for tweet in tweets_batch:
            tweet_id = tweet.get("id") or tweet.get("tweet_id")
            if tweet_id and not is_tweet_seen(target_username, str(tweet_id)):
                filtered_batch.append(tweet)

        if filtered_batch:
            await write_to_cache(filtered_batch, "Progressive tweet scraping", username=target_username)

    sorted_items = []
    # Check if we should use Browserbase for all scraping
    use_browserbase = should_use_browserbase_for_scraping()
    if use_browserbase:
        notify("🌐 Environment configured to use Browserbase for all scraping")
    else:
        notify("💻 Using local scraping with Browserbase fallback on bot detection")

    # Gather tweets with progressive writing enabled
    trending = await gather_trending(relevant_accounts, queries, username=username, write_callback=progressive_write, use_browserbase=use_browserbase, query_summary_map=query_summary_map)

    # Filter out tweets that were already seen
    from backend.utlils.utils import is_tweet_seen
    original_count = len(trending)
    filtered_trending = {}
    filtered_out_count = 0

    for tweet_id, tweet_data in trending.items():
        if not is_tweet_seen(username, tweet_id):
            filtered_trending[tweet_id] = tweet_data
        else:
            filtered_out_count += 1

    if filtered_out_count > 0:
        notify(f"🔍 Filtered out {filtered_out_count} previously seen tweet(s) from {original_count} scraped")

    # sort by score desc
    sorted_items = sorted(filtered_trending.values(), key=lambda x: x["score"], reverse=True)
    if max_tweets:
        sorted_items = sorted_items[:max_tweets]

    # Final write with sorting/filtering applied
    await write_to_cache(sorted_items, "Final sorted tweets", username=username)
    return sorted_items


# API Router
router = APIRouter(prefix="/read", tags=["read"])


class ReadTweetsRequest(BaseModel):
    usernames: list[str] | None = None
    queries: list[str] | None = None
    max_tweets: int | None = None


async def _scrape_and_generate_background(username: str, relevant_accounts: list[str] | None, queries: list[str] | None, max_tweets: int | None):
    """
    Background task that handles both scraping and reply generation using browser automation.
    This allows the endpoint to return immediately while work continues in background.

    NOTE: Currently not used - endpoint uses find_and_reply_to_new_posts job instead.
    Kept for potential future use if we need to switch back to browser automation.
    """
    try:
        # Track scraping time
        start_time = time.time()

        notify(f"🔍 [Background] Starting tweet scrape for {username}...")

        # Scrape tweets
        if relevant_accounts is None and queries is None and max_tweets is None:
            tweets = await read_tweets(username=username)
        else:
            tweets = await read_tweets(username=username, relevant_accounts=relevant_accounts, queries=queries, max_tweets=max_tweets)

        # Calculate time saved (time spent scraping)
        end_time = time.time()
        scraping_duration = int(end_time - start_time)  # in seconds

        notify(f"✅ [Background] Scraping completed in {scraping_duration}s. Found {len(tweets)} tweets for {username}")

        # Update user's scrolling_time_saved
        user_info = read_user_info(username)
        if user_info:
            current_time_saved = user_info.get("scrolling_time_saved", 0)
            user_info["scrolling_time_saved"] = current_time_saved + scraping_duration
            write_user_info(user_info)
            notify(f"⏱️ Total time saved for {username}: {user_info['scrolling_time_saved']}s")

        # Log the scraping action
        log_scrape_action(username, len(tweets))

        # Generate replies only for premium users (this will also update status to complete/idle when done)
        account_type = user_info.get("account_type", "trial") if user_info else "trial"
        if account_type == "premium":
            notify(f"💬 [Background] Generating replies for {username} (premium user)...")
            from backend.twitter.generate_replies import generate_replies
            result = await generate_replies(username=username, overwrite=False)
            reply_count = sum(1 for t in result if t.get('generated_replies'))
            notify(f"✅ [Background] Generated {reply_count} replies for {username}")
        else:
            notify(f"⏭️ [Background] Skipping reply generation for {username} (account type: {account_type}, premium required)")

    except Exception as e:
        error(f"Error in background scraping/generation for {username}: {e}", status_code=500, function_name="_scrape_and_generate_background", username=username, critical=False)


async def _run_find_and_reply_with_error_handling(username: str, triggered_by: str = "user"):
    """
    Wrapper that catches and logs any exceptions from find_and_reply_to_new_posts.
    asyncio.create_task() silently swallows exceptions, so we need explicit handling.
    """
    try:
        from backend.twitter.twitter_jobs import find_and_reply_to_new_posts
        await find_and_reply_to_new_posts(username, triggered_by)
    except Exception as e:
        import traceback
        error_msg = f"find_and_reply_to_new_posts crashed: {e}\n{traceback.format_exc()}"
        notify(f"❌ [Background] {error_msg}")
        error(error_msg, status_code=500, function_name="find_and_reply_to_new_posts", username=username, critical=False)


@router.post("/{username}/tweets")
async def read_tweets_endpoint(username: str, payload: ReadTweetsRequest | None = None) -> dict:
    """
    Start tweet scraping and reply generation in background. Returns immediately.
    Frontend should poll /jobs/{username}/status to track progress.

    Uses find_and_reply_to_new_posts job which fetches full thread context for each tweet.
    Uses asyncio.create_task() for true parallel execution with other background jobs.
    """
    from backend.twitter.authentication import ensure_access_token

    try:
        notify(f"📋 [API] Received scrape request for {username}")

        # Verify OAuth token is valid before starting background job
        # This lets the frontend know immediately if re-auth is needed
        await ensure_access_token(username, raise_on_failure=True)

        # Check user account type
        user_info = read_user_info(username)
        if not user_info:
            error(f"User not found: {username}", status_code=404, function_name="read_tweets_endpoint", username=username)
            raise HTTPException(status_code=404, detail=f"User not found: {username}")

        account_type = user_info.get("account_type", "trial")
        notify(f"📋 [API] User {username} has account type: {account_type}")

        # Use asyncio.create_task with error handling wrapper for true parallel execution
        asyncio.create_task(_run_find_and_reply_with_error_handling(username, "user"))

        notify(f"✅ [API] Background job scheduled for {username}")

        message = "Job started in background. Poll /jobs/{username}/status to track progress."
        if account_type != "premium":
            message += " (Reply generation requires premium account)"

        return {"message": message, "status": "scraping_started", "background_task": "find_and_reply_to_new_posts", "account_type": account_type}
    except Exception as e:
        notify(f"❌ [API] Error scheduling job for {username}: {str(e)}")
        print(str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error starting job: {str(e)}") from e


@router.get("/{username}/status")
async def get_scraping_status_endpoint(username: str) -> dict:
    """Get the current scraping status for a user (from job_status)."""
    return get_scraping_status_from_job_status(username)


if __name__ == "__main__":

    async def main():
        import json
        from pathlib import Path

        sorted_items = []

        relevant_accounts = [
            "jamilball", "sarthakgh", "jaltma", "mamoonha", "villi", "Jasonlk", "Nbt", "Chetanp", "Edsim", "Gokulr", "Km", "Semil", "Mvernal", "Dauber", "Garrytan", "Eladgil", "Pitdesi", "bznotes"
        ]
        relevant_accounts = []
        queries = [
            "startups -filter:links -filter:replies -is:retweet lang:en", "founders -filter:links -filter:replies -is:retweet lang:en",
            "entrepreneur -filter:links -filter:replies -is:retweet lang:en", "venture capital -filter:links -filter:replies -is:retweet lang:en",
            "vc -filter:links -filter:replies -is:retweet lang:en", "funding -filter:links -filter:replies -is:retweet lang:en", "fundraising -filter:links -filter:replies -is:retweet lang:en",
            "seed round -filter:links -filter:replies -is:retweet lang:en", "GTM for startups filter:links -filter:replies -is:retweet lang",
            "startup recruiting -filter:links -filter:replies -is:retweet lang:en", "tech recruiting -filter:links -filter:replies -is:retweet lang:en",
            "immigrant careers -filter:links -filter:replies -is:retweet lang:en", "entreprise software -filter:links -filter:replies -is:retweet lang:en"
        ]

        trending = await gather_trending(relevant_accounts, queries)
        # sort by score desc
        sorted_items = sorted(trending.values(), key=lambda x: x["score"], reverse=True)
        sorted_items = sorted_items[:10]

        # Write to .jsonl file
        output_file = Path(__file__).parent / "cache" / "scraped_tweets_2.jsonl"
        with open(output_file, "w") as f:
            for item in sorted_items:
                f.write(json.dumps(item) + "\n")

        notify(f"✅ Wrote {len(sorted_items)} tweets to {output_file}")

    asyncio.run(main())
