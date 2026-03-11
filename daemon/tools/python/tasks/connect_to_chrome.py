"""True CDP browser connection — scrapes in the user's real Chrome session.

Opens pages in the user's actual browser via CDP for full TOS compliance
(indistinguishable from normal browsing). New pages open as background tabs
and close automatically when scraping finishes.
"""

from __future__ import annotations

import asyncio
import sys
from typing import Any, Mapping

CDP_URL = "http://127.0.0.1:9222"


async def connect_browser(playwright, cookies=None):
    """Connect to Chrome via CDP and scrape in the user's real browser.

    Uses the user's live browser context. New pages are created via
    Target.createTarget as background tabs (no new window, no focus steal).

    Falls back to a standalone headless browser when CDP is unavailable.

    Returns
    -------
    tuple[Browser, BrowserContext, bool]
        ``(browser, context, owns_browser)`` — *owns_browser* is ``False``
        when connected via CDP, ``True`` when a fallback was launched.
    """
    try:
        browser = await playwright.chromium.connect_over_cdp(CDP_URL)
        ctx = browser.contexts[0] if browser.contexts else await browser.new_context()

        # Patch new_page to create a background tab via CDP
        _original_new_page = ctx.new_page

        async def _new_page_background(**kwargs):
            page_future = asyncio.get_event_loop().create_future()

            def on_page(page):
                if not page_future.done():
                    page_future.set_result(page)

            ctx.on("page", on_page)

            try:
                anchor = ctx.pages[0] if ctx.pages else None
                if anchor is None:
                    try:
                        ctx.remove_listener("page", on_page)
                    except Exception:
                        pass
                    return await _original_new_page(**kwargs)

                cdp_session = await ctx.new_cdp_session(anchor)

                await cdp_session.send(
                    "Target.createTarget",
                    {
                        "url": "about:blank",
                        "background": True,
                    },
                )

                await cdp_session.detach()

                page = await asyncio.wait_for(page_future, timeout=5.0)
            except Exception:
                try:
                    ctx.remove_listener("page", on_page)
                except Exception:
                    pass
                return await _original_new_page(**kwargs)
            finally:
                try:
                    ctx.remove_listener("page", on_page)
                except Exception:
                    pass

            return page

        ctx.new_page = _new_page_background
        return browser, ctx, False

    except Exception as exc:
        print(
            f"[true_cdp] CDP connection failed ({exc}), falling back to headless",
            file=sys.stderr,
        )
        browser = await playwright.chromium.launch(headless=True)
        if cookies:
            ctx = await browser.new_context(storage_state=cookies)
        else:
            ctx = await browser.new_context()
        return browser, ctx, True
