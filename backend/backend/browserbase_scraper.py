"""Browserbase-based scraping fallback for improved bot detection evasion."""

from playwright.async_api import async_playwright
from browserbase import Browserbase

from backend.config import BROWSERBASE_API_KEY, BROWSERBASE_PROJECT_ID

try:
    from backend.headless_fetch import collect_from_page
    from backend.utils import error, notify, read_browser_state, store_browser_state
except ImportError:
    from headless_fetch import collect_from_page
    from utils import error, notify, read_browser_state, store_browser_state


async def get_browserbase_session(username: str):
    """
    Create a Browserbase session and connect Playwright to it.
    Loads browser state for the given username if available.

    Args:
        username: Twitter username to load browser state for

    Returns:
        tuple: (playwright, browser, context, browserbase_client, session_id)

    Raises:
        ValueError: If Browserbase credentials are missing
    """
    from backend.utils import error
    if not BROWSERBASE_API_KEY:
        error("BROWSERBASE_API_KEY environment variable not set", status_code=500, function_name="scrape_with_browserbase", username=username)
        raise ValueError("BROWSERBASE_API_KEY environment variable not set")

    if not BROWSERBASE_PROJECT_ID:
        error("BROWSERBASE_PROJECT_ID environment variable not set", status_code=500, function_name="scrape_with_browserbase", username=username)
        raise ValueError("BROWSERBASE_PROJECT_ID environment variable not set")

    notify(f"🌐 Creating Browserbase session for {username}...")
    browserbase = Browserbase(api_key=BROWSERBASE_API_KEY)

    # Create session
    session = browserbase.sessions.create(project_id=BROWSERBASE_PROJECT_ID)
    session_id = session.id

    notify(f"✅ Browserbase session created: {session_id}")

    # Connect Playwright to Browserbase
    playwright = await async_playwright().start()
    browser = await playwright.chromium.connect_over_cdp(session.connect_url)
    context = browser.contexts[0]  # Browserbase provides a default context

    # Try to load saved browser state
    try:
        # Load cookies and localStorage from saved state
        state = await read_browser_state(None, username)  # Returns the state dict
        if state and "cookies" in state:
            await context.add_cookies(state["cookies"])
            notify(f"✅ Loaded browser state for {username}")
        else:
            notify(f"⚠️ No saved browser state found for {username}")
    except Exception as e:
        notify(f"⚠️ Could not load browser state: {e}")

    return playwright, browser, context, browserbase, session_id


async def cleanup_browserbase_session(playwright, browser, context, browserbase_client, session_id):
    """
    Clean up Browserbase session and Playwright connections.

    Args:
        playwright: Playwright instance
        browser: Browser instance
        context: Browser context
        browserbase_client: Browserbase client
        session_id: Browserbase session ID
    """
    try:
        if context:
            await context.close()
        if browser:
            await browser.close()
        if playwright:
            await playwright.stop()

        # Complete Browserbase session
        if browserbase_client and session_id:
            try:
                notify(f"🛑 Stopping Browserbase session: {session_id}")
                browserbase_client.sessions.complete(session_id, status="completed")
                notify(f"✅ Browserbase session {session_id} stopped")
            except Exception as e:
                notify(f"Warning: Error stopping Browserbase session: {e}")
    except Exception as e:
        error(f"Error cleaning up Browserbase session: {e}")


async def fetch_user_tweets_browserbase(username: str, handle: str, write_callback=None, **kwargs):
    """
    Fetch user tweets using Browserbase cloud browser.

    Args:
        username: User's Twitter handle (for loading browser state)
        handle: Twitter handle to scrape
        write_callback: Optional callback for progressive writing
        **kwargs: Additional arguments passed to collect_from_page

    Returns:
        dict: Scraped tweets

    Raises:
        Exception: If scraping fails
    """
    playwright = None
    browser = None
    context = None
    browserbase = None
    session_id = None

    try:
        playwright, browser, context, browserbase, session_id = await get_browserbase_session(username)

        url = f"https://x.com/{handle}"
        notify(f"🔍 [Browserbase] Scraping tweets from @{handle}")

        tweets = await collect_from_page(context, url, handle=handle, username=username, write_callback=write_callback, **kwargs)

        notify(f"✅ [Browserbase] Successfully scraped {len(tweets)} tweets from @{handle}")
        return tweets

    finally:
        await cleanup_browserbase_session(playwright, browser, context, browserbase, session_id)


async def fetch_search_browserbase(username: str, query: str, write_callback=None, **kwargs):
    """
    Fetch search results using Browserbase cloud browser.

    Args:
        username: User's Twitter handle (for loading browser state)
        query: Search query
        write_callback: Optional callback for progressive writing
        **kwargs: Additional arguments passed to collect_from_page

    Returns:
        dict: Scraped tweets

    Raises:
        Exception: If scraping fails
    """
    from urllib.parse import quote_plus

    playwright = None
    browser = None
    context = None
    browserbase = None
    session_id = None

    try:
        playwright, browser, context, browserbase, session_id = await get_browserbase_session(username)

        q = quote_plus(query)
        url = f"https://x.com/search?q={q}&src=typed_query"
        notify(f"🔍 [Browserbase] Scraping query: {query}")

        tweets = await collect_from_page(context, url, handle=None, username=username, write_callback=write_callback, **kwargs)

        notify(f"✅ [Browserbase] Successfully scraped {len(tweets)} tweets for query: {query}")
        return tweets

    finally:
        await cleanup_browserbase_session(playwright, browser, context, browserbase, session_id)
