import asyncio
import re

from fastapi import APIRouter, HTTPException, status
from playwright.async_api import async_playwright
from pydantic import BaseModel

from .headless_fetch import collect_from_page
from .utils import error, notify

try:
    from backend.resolve_imports import ensure_standalone_imports
except ModuleNotFoundError:  # Running from inside backend/
    from resolve_imports import ensure_standalone_imports

ensure_standalone_imports(globals())

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
    await page.wait_for_url("https://x.com/home", timeout=30_000)

    await store_browser_state(username, ctx)
    return browser, ctx


async def get_home(browser=None):
    from backend.utils import read_browser_state

    if browser is None:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=(not see_browser))
    session = await read_browser_state(browser, USERNAME)
    if session:
        return session
    error("No authorization found; user needs to log in.")


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


async def read_tweets(username=USERNAME, usernames=None, queries=None, max_scrolls=3, max_tweets=None):
    from backend.tweets_cache import write_to_cache

    if usernames is None:
        usernames = USERNAMES
    if queries is None:
        queries = QUERIES
    if max_tweets is None:
        max_tweets = MAX_TWEETS_RETRIEVE

    sorted_items = []
    # write results to cache file
    trending = await gather_trending(usernames, queries, max_scrolls=max_scrolls)
    # sort by score desc
    sorted_items = sorted(trending.values(), key=lambda x: x["score"], reverse=True)
    if max_tweets:
        sorted_items = sorted_items[:max_tweets]
    await write_to_cache(sorted_items, "Scraped relevant tweets", username=username)
    return sorted_items


# API Router
router = APIRouter(prefix="/read", tags=["read"])


class ReadTweetsRequest(BaseModel):
    usernames: list[str] | None = None
    queries: list[str] | None = None
    max_scrolls: int = 3
    max_tweets: int | None = None


@router.post("/{username}/tweets")
async def read_tweets_endpoint(username: str, payload: ReadTweetsRequest | None = None) -> dict:
    """Scrape tweets from usernames and queries, save to cache."""
    try:
        if payload is None:
            tweets = await read_tweets(username=username)
        else:
            tweets = await read_tweets(
                username=username,
                usernames=payload.usernames,
                queries=payload.queries,
                max_scrolls=payload.max_scrolls,
                max_tweets=payload.max_tweets
            )
        return {
            "message": "Tweets scraped and cached successfully",
            "count": len(tweets),
            "tweets": tweets
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error scraping tweets: {str(e)}"
        )


if __name__ == "__main__":

    async def main():
        sorted_items = []

        if True:
            # write results to cache file
            trending = await gather_trending(USERNAMES, QUERIES, max_scrolls=3)
            # sort by score desc
            sorted_items = sorted(trending.values(), key=lambda x: x["score"], reverse=True)
            if MAX_TWEETS_RETRIEVE:
                sorted_items = sorted_items[:MAX_TWEETS_RETRIEVE]  # top 50

    asyncio.run(main())
