"""Shared CDP (Chrome DevTools Protocol) connection logic for Playwright.

Connects to the user's live Chrome via CDP to grab fresh session cookies,
then scrapes in a separate headless browser so nothing visible pops up.
"""

from __future__ import annotations

import sys
from typing import Any, Mapping

CDP_URL = "http://127.0.0.1:9222"


async def connect_browser(playwright, cookies=None):
    """Extract cookies from Chrome via CDP, then scrape in headless.

    Connects to the user's running Chrome to grab live cookies, disconnects,
    then launches a headless browser with those cookies. Nothing visible
    opens and focus is never stolen.

    Falls back to a standalone headless browser with explicit cookies
    when CDP is unavailable.

    Returns
    -------
    tuple[Browser, BrowserContext, bool]
        ``(browser, context, owns_browser)`` — *owns_browser* is always
        ``True`` (headless browser that the caller should close).
    """
    live_cookies = None

    # Try to grab fresh cookies from the user's running Chrome
    try:
        cdp_browser = await playwright.chromium.connect_over_cdp(CDP_URL)
        if cdp_browser.contexts:
            live_cookies = await cdp_browser.contexts[0].cookies()
        await cdp_browser.close()
    except Exception as exc:
        print(
            f"[cdp] CDP connection failed ({exc}), using provided cookies",
            file=sys.stderr,
        )

    # Always scrape in a separate headless browser
    browser = await playwright.chromium.launch(headless=True)
    if live_cookies:
        ctx = await browser.new_context()
        await ctx.add_cookies(live_cookies)
    elif cookies:
        ctx = await browser.new_context(storage_state=cookies)
    else:
        ctx = await browser.new_context()
    return browser, ctx, True
