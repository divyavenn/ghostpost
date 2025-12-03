"""
Shared browser context utilities for authenticated scraping.

Provides functions to create and cleanup Playwright browser contexts
using saved authentication state.
"""
from playwright.async_api import Browser, BrowserContext, Playwright, async_playwright

from backend.config import SHOW_BROWSER
from backend.utlils.utils import error, notify


async def get_authenticated_context(username: str) -> tuple[Playwright, Browser, BrowserContext]:
    """
    Get an authenticated browser context for scraping.

    Uses saved browser state (cookies) to create an authenticated session.

    Args:
        username: User's cache key for looking up saved browser state

    Returns:
        Tuple of (playwright, browser, context)

    Raises:
        ValueError: If no saved browser state found for user
    """
    from backend.utlils.utils import read_browser_state

    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=(not SHOW_BROWSER))

    # Get authenticated context from saved cookies
    # read_browser_state returns (browser, context) tuple or None
    result = await read_browser_state(browser, username)
    if not result:
        await browser.close()
        await playwright.stop()
        error(
            "No authorization found; user needs to log in.",
            status_code=401,
            function_name="get_authenticated_context",
            username=username,
            critical=True
        )
        raise ValueError("No authorization found")

    # Unpack the tuple - read_browser_state returns (browser, context)
    _, context = result
    return playwright, browser, context


async def cleanup_browser_resources(
    playwright: Playwright | None,
    browser: Browser | None,
    context: BrowserContext | None
) -> None:
    """
    Clean up browser resources safely.

    Closes context, browser, and stops playwright in order.
    Catches and logs any errors during cleanup.

    Args:
        playwright: Playwright instance to stop
        browser: Browser instance to close
        context: BrowserContext instance to close
    """
    try:
        if context:
            await context.close()
        if browser:
            await browser.close()
        if playwright:
            await playwright.stop()
    except Exception as e:
        notify(f"Error cleaning up browser: {e}")


async def cleanup_browser_session(browser_session: dict) -> None:
    """
    Clean up a browser session dict (works for both local and Browserbase).

    Handles the dict-based session format used by OAuth login flow.
    Also stops Browserbase sessions if applicable.

    Args:
        browser_session: Dict containing playwright, browser, context, and optionally
                        browserbase_session_id and browserbase_client
    """
    try:
        # Close Playwright connection
        await cleanup_browser_resources(
            browser_session.get("playwright"),
            browser_session.get("browser"),
            browser_session.get("context")
        )

        # Stop Browserbase session if it exists
        if "browserbase_session_id" in browser_session and "browserbase_client" in browser_session:
            bb_session_id = browser_session["browserbase_session_id"]
            bb_client = browser_session["browserbase_client"]
            try:
                notify(f"Stopping Browserbase session: {bb_session_id}")
                bb_client.sessions.complete(bb_session_id, status="completed")
                notify(f"Browserbase session {bb_session_id} stopped")
            except Exception as e:
                error(f"Warning: Error stopping Browserbase session: {e}")

    except Exception as e:
        notify(f"Error cleaning up browser session: {e}")
