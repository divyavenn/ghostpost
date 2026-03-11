"""Playwright helpers for exporting Twitter threads.

This module complements :mod:`scrapers.tweet` by offering an async helper that
spins up a Playwright browser using caller-provided authentication state. The
Chrome extension (or any API client) can pass the cookies / storage state it
already captured so no persistent browser context has to be reused between
requests.
"""

from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path
from typing import Any, Mapping

from playwright.async_api import async_playwright

# True = use user's real Chrome session (TOS-safe, tabs minimized)
# False = extract cookies from Chrome, scrape in separate headless browser
USE_REAL_BROWSER = False

TASKS_DIR = Path(__file__).resolve().parents[1] / "python" / "tasks"
if str(TASKS_DIR) not in sys.path:
    sys.path.append(str(TASKS_DIR))

if USE_REAL_BROWSER:
    from connect_to_chrome import connect_browser
else:
    from connect_headless import connect_browser


TWEET_DETAIL_RE = re.compile(r"/i/api/graphql/[^/]+/TweetDetail")

def cookie_still_valid(state: dict[str, Any]) -> bool:
    import time
    if not isinstance(state, dict):
        return False
    for c in state.get("cookies", []):
        if c.get("name") == 'auth_token':
            return c.get("expires", 0) == 0 or c["expires"] > time.time() + 60
    return False


async def get_browser(cookies: Mapping[str, Any]):
    """Connect to the user's running Chrome via CDP, or fall back to launching a fresh instance."""
    playwright = await async_playwright().start()
    session = cookies 
    browser, ctx, owns_browser = await connect_browser(playwright, cookies=session)
    return playwright, browser, ctx, owns_browser


async def get_thread(tweet_url: str, root_id: str | None = None, cookies: Mapping[str, Any] | None = None) -> list[str]:
    playwright, browser, ctx, owns_browser = await get_browser(cookies=cookies)
    page = await ctx.new_page()

    results: list[str] = []
    root_author_id: str | None = None

    def extract_text(node: Mapping[str, Any]) -> str:
        legacy = node.get("legacy") or {}
        note_text = (
            (node.get("note_tweet") or {})
            
            .get("note_tweet_results", {})
            .get("result", {})
            .get("text")
        )
        if note_text:
            return note_text

        txt = legacy.get("full_text") or legacy.get("text")
        return txt or ""

    async def on_response(resp):
        nonlocal root_author_id
        if not (TWEET_DETAIL_RE.search(resp.url) and resp.ok):
            return
        try:
            data = await resp.json()
        except Exception:
            return

        # Collect instructions from both containers
        instructions = []
        tc_v2 = (data.get("data") or {}).get("threaded_conversation_with_injections_v2") or {}
        instructions.extend(tc_v2.get("instructions", []) or [])
        tc_v1 = (data.get("data") or {}).get("threaded_conversation_with_injections") or {}
        instructions.extend(tc_v1.get("instructions", []) or [])

        for inst in instructions:
            for entry in inst.get("entries", []) or []:
                content = entry.get("content") or {}

                # Candidate shapes containing tweets
                candidates = []
                ic = content.get("itemContent") or {}
                if ic:
                    candidates.append(ic)
                ic2 = (content.get("item") or {}).get("itemContent") or {}
                if ic2:
                    candidates.append(ic2)
                for it in (content.get("items") or content.get("moduleItems") or []):
                    cand = (it.get("item") or {}).get("itemContent") or it.get("itemContent") or {}
                    if cand:
                        candidates.append(cand)

                for cand in candidates:
                    raw = (cand.get("tweet_results") or {}).get("result")
                    if not isinstance(raw, dict):
                        continue
                    node = raw.get("tweet") or raw
                    legacy = node.get("legacy") or {}
                    if not legacy:
                        continue

                    tid = legacy.get("id_str") or str(node.get("rest_id") or "")
                    uid = legacy.get("user_id_str")
                    if not tid or not uid:
                        continue

                    # Resolve root author from the focal tweet if possible
                    if root_author_id is None:
                        if root_id and tid == str(root_id):
                            root_author_id = uid
                        elif not root_id:
                            # No explicit root tweet id provided; infer from first seen item
                            root_author_id = uid

                    # Keep only tweets by the root author that reply **only** to the root author
                    if root_author_id:
                        allow = False
                        # Always allow the focal/root tweet if provided
                        if root_id and tid == str(root_id):
                            allow = True
                        else:
                            reply_to_uid = legacy.get("in_reply_to_user_id_str")
                            mentions = (legacy.get("entities") or {}).get("user_mentions") or []
                            mention_ids = [m.get("id_str") for m in mentions if isinstance(m, dict) and m.get("id_str")]
                            # Only the root author may be mentioned (or none mentioned)
                            only_author_mentioned = (len(mention_ids) == 0) or (len(mention_ids) == 1 and mention_ids[0] == root_author_id)
                            if (uid == root_author_id and reply_to_uid == root_author_id and only_author_mentioned):
                                allow = True
                        if allow:
                            text = extract_text(node)
                            if text:
                                results.append(text)

    page.on("response", lambda r: asyncio.create_task(on_response(r)))

    try:
        await page.goto(tweet_url, wait_until="domcontentloaded")
        # Wait for at least one TweetDetail to arrive
        try:
            await page.wait_for_event(
                "response",
                predicate=lambda r: TWEET_DETAIL_RE.search(r.url),
                timeout=30_000,
            )
        except Exception:
            pass
        # Nudge to load more thread items
        for _ in range(4):
            try:
                await page.mouse.wheel(0, 2200)
            except Exception:
                pass
            await asyncio.sleep(0.2)
    finally:
        await page.close()
        if owns_browser:
            await browser.close()
        await playwright.stop()

    return results
