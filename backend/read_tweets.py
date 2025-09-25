import asyncio
import json
import re
from pathlib import Path
from playwright.async_api import async_playwright
from .headless_fetch import collect_from_page
from .utils import notify, error

# -------- Config --------
USERNAME = "proudlurker"
PASSWORD = r"JXJ-pfd3bdv*myu0whb"
see_browser = True  # set to True to see the browser in action (for debugging)
QUERIES = [
    "multimodal ai -filter:links -filter:replies -is:retweet lang:en",
]
USERNAMES = ["divya_venn"]
MAX_TWEETS_RETRIEVE = 30  # per user or query


# headless login, legacy code, currently use oAuth instead


async def log_in(username: str, password: str, browser=None):
    from utils import store_browser_state

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

    await store_browser_state(username, ctx)
    return browser, ctx


async def get_home(browser=None):
    from utils import read_browser_state

    if browser is None:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=(not see_browser))
    session = await read_browser_state(browser, USERNAME)
    if session:
        return session
    error("No authorization found; user needs to log in.")


# -------- Core collectors --------
GRAPHQL_TWEET_RE = re.compile(
    r"/i/api/graphql/[^/]+/(UserTweets|SearchTimeline|SearchTimelineV2|HomeTimeline|HomeLatestTimeline)"
)


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


async def read_tweets(username=USERNAME):
    from utils import write_to_cache

    sorted_items = []
    # write results to cache file
    trending = await gather_trending(USERNAMES, QUERIES, max_scrolls=3)
    # sort by score desc
    sorted_items = sorted(trending.values(), key=lambda x: x["score"], reverse=True)
    if MAX_TWEETS_RETRIEVE:
        sorted_items = sorted_items[:MAX_TWEETS_RETRIEVE]  # top 50
        await write_to_cache(sorted_items, "Scraped relevant tweets", username=username)


if __name__ == "__main__":

    async def main():
        sorted_items = []

        if True:
            # write results to cache file
            trending = await gather_trending(USERNAMES, QUERIES, max_scrolls=3)
            # sort by score desc
            sorted_items = sorted(
                trending.values(), key=lambda x: x["score"], reverse=True
            )
            if MAX_TWEETS_RETRIEVE:
                sorted_items = sorted_items[:MAX_TWEETS_RETRIEVE]  # top 50
            from utils import write_to_cache

            await write_to_cache(
                sorted_items, "Wrote trending results", username=USERNAME
            )

    asyncio.run(main())
