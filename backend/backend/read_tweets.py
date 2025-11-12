import asyncio
import re
import time

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from playwright.async_api import async_playwright
from pydantic import BaseModel

# Handle imports for both package and standalone execution
try:
    from backend.config import SHOW_BROWSER
    from backend.resolve_imports import ensure_standalone_imports
except ModuleNotFoundError:  # Running from inside backend/
    from config import SHOW_BROWSER
    from resolve_imports import ensure_standalone_imports

ensure_standalone_imports(globals())

try:
    from backend.headless_fetch import collect_from_page
    from backend.log_interactions import log_scrape_action
    from backend.utils import error, notify, read_user_info, write_user_info
except ImportError:
    from headless_fetch import collect_from_page
    from log_interactions import log_scrape_action
    from utils import error, notify, read_user_info, write_user_info

# -------- Config --------
import os

from backend.config import (
    DEFAULT_MAX_TWEETS_RETRIEVE as MAX_TWEETS_RETRIEVE,
)
from backend.config import (
    DEFAULT_TWITTER_USERNAME as USERNAME,
)
from backend.config import (
    SHOW_BROWSER,
    USE_BROWSERBASE_FOR_SCRAPING,
)


def should_use_headless_for_scraping() -> bool:
    """
    Return True if browser should run in headless mode for AUTOMATED SCRAPING.
    Uses SHOW_BROWSER config variable (can be overridden by HEADLESS_BROWSER env var).
    """
    headless_env = os.getenv("HEADLESS_BROWSER")
    if headless_env is not None:
        # Environment variable override
        return headless_env.lower() in ("true", "1", "yes")
    # Use config value (inverted - SHOW_BROWSER=True means headless=False)
    return not SHOW_BROWSER


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


see_browser = not should_use_headless_for_scraping()  # Show browser only if not in headless mode

# Global status tracker for scraping progress
scraping_status = {}  # {username: {"type": "account"/"query", "value": "handle/query", "phase": "scraping"/"complete"}}


async def update_status_to_reflect_finished_scraping(username: str):
    """
    Update status to complete, then reset to idle after 5 seconds.
    Used when scraping/generation finishes (including when there are no tweets to process).
    """
    scraping_status[username] = {"type": "complete", "value": "", "phase": "complete"}
    notify(f"✅ Status set to complete for {username}")

    # Reset to idle after 5 seconds
    await asyncio.sleep(5)
    if username in scraping_status and scraping_status[username]["type"] == "complete":
        scraping_status[username] = {"type": "idle", "value": "", "phase": "idle"}
        notify(f"🔄 Status reset to idle for {username}")


# headless login, legacy code, currently use oAuth instead
async def log_in(username: str, password: str, browser=None):
    from backend.utils import store_browser_state

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
    from backend.utils import read_browser_state

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
async def gather_trending(usernames, queries, username=None, write_callback=None, use_browserbase=False):
    """
    Gather trending tweets with progressive writing and Browserbase fallback.

    Args:
        usernames: List of Twitter handles to scrape
        queries: List of search queries
        username: Username for cache writes
        write_callback: Async function to call for incremental writes
        use_browserbase: If True, skip local scraping and use Browserbase directly

    Returns:
        dict: Scraped tweets
    """
    from backend.browserbase_scraper import fetch_search_browserbase, fetch_user_tweets_browserbase
    from backend.exceptions import CaptchaError, RateLimitError

    notify(f"🚀 [gather_trending] Starting for {username}: {len(usernames)} accounts, {len(queries)} queries, use_browserbase={use_browserbase}")
    results = {}

    # If explicitly requesting Browserbase, skip local scraping
    if use_browserbase:
        notify("🌐 Using Browserbase for scraping (direct mode)")

        # Scrape user timelines
        for u in usernames:
            try:
                if username:
                    scraping_status[username] = {"type": "account", "value": u, "phase": "scraping_browserbase"}
                    notify(f"📍 Status: Scraping from @{u} via Browserbase")

                tweets = await fetch_user_tweets_browserbase(username or "proudlurker", u, write_callback=write_callback)
                for tweet_data in tweets.values():
                    tweet_data["scraped_from"] = {"type": "account", "value": u}
                results.update(tweets)
            except Exception as e:
                notify(f"❌ [Browserbase] Error fetching @{u}: {e}")

        # Scrape queries
        for q in queries:
            try:
                if username:
                    scraping_status[username] = {"type": "query", "value": q, "phase": "scraping_browserbase"}
                    notify(f"📍 Status: Scraping query [{q}] via Browserbase")

                tweets = await fetch_search_browserbase(username or "proudlurker", q, write_callback=write_callback)
                for tweet_data in tweets.values():
                    tweet_data["scraped_from"] = {"type": "query", "value": q}
                results.update(tweets)
            except Exception as e:
                notify(f"❌ [Browserbase] Error searching [{q}]: {e}")

        if username:
            scraping_status[username] = {"type": "generating", "value": "", "phase": "generating"}
        notify(f"✅ [gather_trending] Completed for {username}: {len(results)} tweets scraped (Browserbase mode)")
        return results

    # Try local scraping first (cost-effective)
    async with async_playwright() as p:
        browser = None
        ctx = None
        try:
            browser = await p.chromium.launch(headless=(not see_browser))
            browser, ctx = await get_home(browser=browser, username=username)

            # user timelines
            for u in usernames:
                try:
                    # Update status
                    if username:
                        scraping_status[username] = {"type": "account", "value": u, "phase": "scraping"}
                        notify(f"📍 Status updated: Scraping from @{u}")

                    tweets = await fetch_user_tweets(ctx, u, username=username, write_callback=write_callback)
                    # Add source metadata to each tweet
                    for tweet_data in tweets.values():
                        tweet_data["scraped_from"] = {"type": "account", "value": u}
                    results.update(tweets)
                except (RateLimitError, CaptchaError) as e:
                    # Bot detection! Fall back to Browserbase
                    notify(f"🤖 Bot detection for @{u}: {e}")
                    notify(f"🔄 Falling back to Browserbase for @{u}...")

                    try:
                        tweets = await fetch_user_tweets_browserbase(username or "proudlurker", u, write_callback=write_callback)
                        for tweet_data in tweets.values():
                            tweet_data["scraped_from"] = {"type": "account", "value": u}
                        results.update(tweets)
                        notify(f"✅ Successfully scraped @{u} via Browserbase fallback")
                    except Exception as fallback_error:
                        notify(f"❌ Browserbase fallback also failed for @{u}: {fallback_error}")
                except Exception as e:
                    notify(f"⚠️ error fetching @{u}: {e}")

            # topic searches
            for q in queries:
                try:
                    # Update status
                    if username:
                        scraping_status[username] = {"type": "query", "value": q, "phase": "scraping"}
                        notify(f"📍 Status updated: Scraping query [{q}]")

                    tweets = await fetch_search(ctx, q, username=username, write_callback=write_callback)
                    # Add source metadata to each tweet
                    for tweet_data in tweets.values():
                        tweet_data["scraped_from"] = {"type": "query", "value": q}
                    results.update(tweets)
                except (RateLimitError, CaptchaError) as e:
                    # Bot detection! Fall back to Browserbase
                    notify(f"🤖 Bot detection for query [{q}]: {e}")
                    notify(f"🔄 Falling back to Browserbase for query [{q}]...")

                    try:
                        tweets = await fetch_search_browserbase(username or "proudlurker", q, write_callback=write_callback)
                        for tweet_data in tweets.values():
                            tweet_data["scraped_from"] = {"type": "query", "value": q}
                        results.update(tweets)
                        notify(f"✅ Successfully scraped query [{q}] via Browserbase fallback")
                    except Exception as fallback_error:
                        notify(f"❌ Browserbase fallback also failed for query [{q}]: {fallback_error}")
                except Exception as e:
                    notify(f"⚠️ error searching [{q}]: {e}")

            # Mark as complete
            if username:
                scraping_status[username] = {"type": "generating", "value": "", "phase": "generating"}

            notify(f"✅ [gather_trending] Completed for {username}: {len(results)} tweets scraped (local mode)")
            return results
        finally:
            # Always cleanup browser resources, even if exceptions occur
            if ctx:
                try:
                    await ctx.close()
                except Exception as e:
                    notify(f"⚠️ Error closing browser context: {e}")
            if browser:
                try:
                    await browser.close()
                except Exception as e:
                    notify(f"⚠️ Error closing browser: {e}")


async def read_tweets(username=USERNAME, relevant_accounts=None, queries=None, max_tweets=None):
    from backend.tweets_cache import cleanup_old_tweets, purge_unedited_tweets, write_to_cache
    from backend.user import read_user_settings

    user_settings = read_user_settings(username)

    # Check if user settings exist (required for per-user configuration)
    if not user_settings:
        error(f"No settings found for user {username}. Please configure settings first.", critical=True)

    if relevant_accounts is None:
        # Extract only accounts where validated is True, as a list of handles
        accounts_dict = user_settings.get("relevant_accounts", {})
        relevant_accounts = [handle for handle, validated in accounts_dict.items() if validated]
    if queries is None:
        queries = user_settings.get("queries", [])
    if max_tweets is None:
        max_tweets = user_settings.get("max_tweets_retrieve", MAX_TWEETS_RETRIEVE)

    # Purge unedited tweets before retrieving new ones
    purged_count = await purge_unedited_tweets(username)
    if purged_count > 0:
        notify(f"🗑️ Purged {purged_count} unedited tweets before scraping")

    # Clean up old tweets before retrieving new ones (48 hour threshold)
    await cleanup_old_tweets(username, hours=48)

    # Define progressive write callback for incremental updates
    async def progressive_write(tweets_batch, target_username):
        """Write tweets incrementally as they're discovered"""
        await write_to_cache(tweets_batch, "Progressive tweet scraping", username=target_username)

    sorted_items = []
    # Check if we should use Browserbase for all scraping
    use_browserbase = should_use_browserbase_for_scraping()
    if use_browserbase:
        notify("🌐 Environment configured to use Browserbase for all scraping")
    else:
        notify("💻 Using local scraping with Browserbase fallback on bot detection")

    # Gather tweets with progressive writing enabled
    trending = await gather_trending(relevant_accounts, queries, username=username, write_callback=progressive_write, use_browserbase=use_browserbase)
    # sort by score desc
    sorted_items = sorted(trending.values(), key=lambda x: x["score"], reverse=True)
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
    Background task that handles both scraping and reply generation.
    This allows the endpoint to return immediately while work continues in background.
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

        # Generate replies
        notify(f"💬 [Background] Generating replies for {username}...")
        from backend.generate_replies import generate_replies
        result = await generate_replies(username=username, overwrite=False)
        reply_count = sum(1 for t in result if t.get('generated_replies'))
        notify(f"✅ [Background] Generated {reply_count} replies for {username}")

    except Exception as e:
        error(f"Error in background scraping/generation for {username}: {e}", status_code=500, function_name="_scrape_and_generate_background", username=username, critical=False)
        # Ensure status gets reset to idle even on error
        if username in scraping_status:
            asyncio.create_task(update_status_to_reflect_finished_scraping(username))


@router.post("/{username}/tweets")
async def read_tweets_endpoint(username: str, background_tasks: BackgroundTasks, payload: ReadTweetsRequest | None = None) -> dict:
    """
    Start tweet scraping and reply generation in background. Returns immediately.
    Frontend should poll /read/{username}/status to track progress.
    """
    try:
        notify(f"📋 [API] Received scrape request for {username}")

        # Set initial status to scraping
        scraping_status[username] = {"type": "scraping", "value": "", "phase": "scraping"}

        # Extract payload parameters
        relevant_accounts = payload.usernames if payload else None
        queries = payload.queries if payload else None
        max_tweets = payload.max_tweets if payload else None

        # Schedule scraping and generation in background
        background_tasks.add_task(_scrape_and_generate_background, username, relevant_accounts, queries, max_tweets)

        notify(f"✅ [API] Background scraping scheduled for {username}")

        return {"message": "Scraping started in background. Poll /read/{username}/status to track progress.", "status": "scraping_started", "background_task": "scraping_and_generation_scheduled"}
    except Exception as e:
        notify(f"❌ [API] Error scheduling scrape for {username}: {str(e)}")
        print(str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error starting scrape: {str(e)}") from e


@router.get("/{username}/status")
async def get_scraping_status(username: str) -> dict:
    """Get the current scraping status for a user."""
    status = scraping_status.get(username, {"type": "idle", "value": "", "phase": "idle"})
    return status


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
