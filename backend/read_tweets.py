import asyncio
import json
import re
from pathlib import Path
from playwright.async_api import async_playwright
from headless_fetch import collect_from_page
from utils import notify, cookie_still_valid, error 

# -------- Config --------
STATE_FILE = Path("storage_state.json")
USERNAME = "proudlurker"
PASSWORD = r"JXJ-pfd3bdv*myu0whb"
see_browser = True  # set to True to see the browser in action (for debugging)
QUERIES   = [
    "multimodal ai -filter:links -filter:replies -is:retweet lang:en",
]
USERNAMES = ["divya_venn"]
MAX_TWEETS_RETRIEVE = 30  # per user or query
CACHE_FILE = "trending_cache.json"



# headless login, legacy code, currently use oAuth instead

async def log_in(username: str, password: str, browser=None):
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
    await page.wait_for_url("https://x.com/home", timeout=30_000)

    await ctx.storage_state(path=STATE_FILE)
    notify("✅ Logged in; storage_state.json written")
    return browser, ctx

async def get_home(browser=None):
    if browser is None:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=(not see_browser))
    if STATE_FILE.exists() and cookie_still_valid(STATE_FILE):
        ctx = await browser.new_context(storage_state=STATE_FILE)
        notify("✅ auth_token looks fresh — using existing session")
        return browser, ctx
    else:
        if STATE_FILE.exists():
            STATE_FILE.unlink(missing_ok=True)
        notify("🔐 Relogging (no/expired cookie)")
        return await log_in(USERNAME, PASSWORD, browser)

# -------- Core collectors --------
GRAPHQL_TWEET_RE = re.compile(r"/i/api/graphql/[^/]+/(UserTweets|SearchTimeline|SearchTimelineV2|HomeTimeline|HomeLatestTimeline)")


async def fetch_user_tweets(ctx, handle: str, **kwargs):
    url = f"https://x.com/{handle}"
    return await collect_from_page(ctx, url, handle=handle, **kwargs)

async def fetch_search(ctx, query: str, **kwargs):
    from urllib.parse import quote_plus
    q = quote_plus(query)  # encodes spaces, quotes, parens, etc.
    url = f"https://x.com/search?q={q}&src=typed_query"
    return await collect_from_page(ctx, url, handle=None, **kwargs)

# -------- Orchestration --------
async def gather_trending(usernames, queries, max_scrolls=3):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=(not see_browser))
        browser, ctx = await get_home(browser=browser)

        results = {}

        # user timelines
        for u in usernames:
            try:
                tweets = await fetch_user_tweets(ctx, u, max_scrolls=max_scrolls)
                results.update(tweets)
            except Exception as e:
                notify(f"⚠️ error fetching @{u}: {e}")

        # topic searches
        for q in queries:
            try:
                tweets = await fetch_search(ctx, q, max_scrolls=max_scrolls)
                results.update(tweets)
            except Exception as e:
                notify(f"⚠️ error searching [{q}]: {e}")

            await ctx.close()
            await browser.close()
        return results


async def write_to_cache(tweets, description):
    with open(CACHE_FILE, "w") as f:
            json.dump(tweets, f, indent=2, ensure_ascii=False)
    notify(f"💾{description} and wrote to cache")

async def read_from_cache():
    notify("💾 Reading tweets from cache")
    try:
        with open(CACHE_FILE, 'r') as f:
            tweets = json.load(f)
        return tweets
    except Exception as e:
        error(f"Error reading JSON file: {e}")
        return []
    
async def read_tweets():
    sorted_items = []
    # write results to cache file
    trending = await gather_trending(USERNAMES, QUERIES, max_scrolls=3)
    # sort by score desc
    sorted_items = sorted(trending.values(), key=lambda x: x["score"], reverse=True)
    if MAX_TWEETS_RETRIEVE:
        sorted_items = sorted_items[:MAX_TWEETS_RETRIEVE]  # top 50
        write_to_cache(sorted_items, "Scraped relevant tweets")  
    
if __name__ == "__main__":
    async def main():
        import os
        sorted_items = []
        
        # # check if cached results exist
        cache_file = "trending_cache.json"
        # if os.path.exists(cache_file):
        #     with open(cache_file) as f:
        #         sorted_items = json.load(f)
        #     notify("📂 Using cached trending results")
        # else:
        if True:
            # write results to cache file
            trending = await gather_trending(USERNAMES, QUERIES, max_scrolls=3)
            # sort by score desc
            sorted_items = sorted(trending.values(), key=lambda x: x["score"], reverse=True)
            if MAX_TWEETS_RETRIEVE:
                sorted_items = sorted_items[:MAX_TWEETS_RETRIEVE]  # top 50
            with open(cache_file, "w") as f:
                json.dump(sorted_items, f, indent=2, ensure_ascii=False)
            notify("💾 Wrote trending results to cache")


    asyncio.run(main())
    