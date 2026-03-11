"""Post a tweet to Twitter/X using CDP.

Opens the Twitter compose page in the user's real Chrome session via CDP,
types the tweet text, optionally attaches an image, and clicks Post.

If a URL is provided separately via --url, it is posted as the second tweet
in a thread (using the thread composer) rather than in the main tweet body.

Always uses true_cdp (the user's live browser) because Twitter's anti-bot
detection blocks headless browsers.
"""

from __future__ import annotations

import asyncio
import sys
from typing import Any

from playwright.async_api import async_playwright

from connect_to_chrome import connect_browser

TWITTER_COMPOSE_URL = "https://x.com/compose/post"


async def post_tweet(
    text: str,
    image: str | None = None,
    url: str | None = None,
) -> dict[str, Any]:

    if not text or not text.strip():
        return {"success": False, "error": "Text cannot be empty"}

    playwright = await async_playwright().start()
    browser, ctx, owns_browser = await connect_browser(playwright)
    page = await ctx.new_page()

    async def cleanup():
        try:
            await page.close()
        except Exception:
            pass
        if owns_browser:
            try:
                await browser.close()
            except Exception:
                pass
        await playwright.stop()

    try:
        # Navigate to Twitter compose
        print("[Twitter] Navigating to compose page...")
        await page.goto(TWITTER_COMPOSE_URL, wait_until="domcontentloaded")
        await asyncio.sleep(3)

        # Verify we're logged in
        for login_text in ["Log in", "Sign in"]:
            sign_in = page.get_by_text(login_text)
            try:
                if await sign_in.first.is_visible(timeout=1000):
                    await cleanup()
                    return {"success": False, "error": "Not logged in to Twitter — launch Chrome with --remote-debugging-port=9222"}
            except Exception:
                pass

        # Step 1: Find the tweet composer
        print("[Twitter] Step 1: Finding tweet composer...")
        editor = None
        for sel in ['[data-testid="tweetTextarea_0"]', '[contenteditable="true"]']:
            try:
                el = page.locator(sel).first
                if await el.is_visible(timeout=3000):
                    editor = el
                    break
            except Exception:
                continue

        if not editor:
            await cleanup()
            return {"success": False, "error": "Could not find tweet composer"}

        await editor.click()
        await asyncio.sleep(0.3)

        # Step 2: Type the text
        print(f"[Twitter] Step 2: Typing text ({len(text)} chars)...")
        await page.keyboard.type(text, delay=20)
        await asyncio.sleep(1.5)

        # Step 3: Attach image if provided
        if image:
            print("[Twitter] Step 3: Attaching image...")
            attached = await _attach_image(page, image)
            if attached:
                print("[Twitter] Image attached")
                await asyncio.sleep(2)
            else:
                print("[Twitter] Warning: could not attach image, posting without it")

        # Step 4: Add URL as second tweet in thread
        if url:
            print("[Twitter] Step 4: Adding URL as thread reply...")
            added = await _add_thread_tweet(page, url)
            if added:
                print("[Twitter] Thread tweet added")
            else:
                print("[Twitter] Warning: could not add thread tweet")

        # Step 5: Click the Post All button
        print("[Twitter] Step 5: Clicking Post button...")
        if not await _click_post_button(page):
            await cleanup()
            return {"success": False, "error": "Could not find Post button"}

        print("[Twitter] Post button clicked, waiting for completion...")
        await asyncio.sleep(3)

        await cleanup()
        print("[Twitter] Tweet posted successfully!")
        return {"success": True, "message": "Tweet posted successfully!"}

    except Exception as exc:
        print(f"[Twitter] Error: {exc}", file=sys.stderr)
        await cleanup()
        return {"success": False, "error": str(exc)}


async def _add_thread_tweet(page, url: str) -> bool:
    """Click the '+' button in the compose modal to add a second tweet, then type the URL."""
    try:
        # Twitter's thread button is a "Add" button or the '+' circle in the composer
        add_btn = page.locator('[data-testid="addButton"]').first
        if not await add_btn.is_visible(timeout=2000):
            return False

        await add_btn.click()
        await asyncio.sleep(1)

        # The new tweet editor appears — find the second textarea
        # After clicking add, there will be tweetTextarea_0 (original) and tweetTextarea_1 (new)
        new_editor = page.locator('[data-testid="tweetTextarea_1"]').first
        if not await new_editor.is_visible(timeout=2000):
            # Fallback: click the last contenteditable
            editors = page.locator('[contenteditable="true"]')
            count = await editors.count()
            if count < 2:
                return False
            new_editor = editors.nth(count - 1)

        await new_editor.click()
        await asyncio.sleep(0.3)

        await page.keyboard.type(url, delay=20)
        await asyncio.sleep(0.5)
        return True
    except Exception as e:
        print(f"[Twitter] Thread add error: {e}", file=sys.stderr)
        return False


async def _attach_image(page, image_url: str) -> bool:
    from scrape_image import attach_image
    return await attach_image(page, image_url, platform="Twitter")


async def _click_post_button(page) -> bool:
    """Click the Post/Post all button."""
    try:
        btn = page.locator('[data-testid="tweetButton"]').first
        if await btn.is_visible(timeout=3000):
            for _ in range(10):
                if await btn.is_enabled():
                    await btn.click()
                    return True
                await asyncio.sleep(0.5)
    except Exception:
        pass

    # Fallback: button with "Post" or "Post all" text
    for label in ["Post all", "Post"]:
        try:
            btn = page.locator(f'button:has-text("{label}")').first
            if await btn.is_visible(timeout=2000):
                for _ in range(10):
                    if await btn.is_enabled():
                        await btn.click()
                        return True
                    await asyncio.sleep(0.5)
        except Exception:
            pass
    return False


def main():
    """CLI interface for posting to Twitter."""
    if len(sys.argv) < 2:
        print("Usage: python -m consumed.twitter_post '<tweet text>' [--image <url>] [--url <link>]", file=sys.stderr)
        sys.exit(1)

    args = sys.argv[1:]
    image_url = None
    link_url = None

    if "--image" in args:
        idx = args.index("--image")
        if idx + 1 < len(args):
            image_url = args[idx + 1]
            args = args[:idx] + args[idx + 2:]

    if "--url" in args:
        idx = args.index("--url")
        if idx + 1 < len(args):
            link_url = args[idx + 1]
            args = args[:idx] + args[idx + 2:]

    content = " ".join(args)
    result = asyncio.run(post_tweet(content, image=image_url, url=link_url))

    if result.get("success"):
        print(result.get("message", "Success"))
    else:
        error = result.get("error", "Unknown error")
        print(f"Error: {error}", file=sys.stderr)
        if "Not logged in" in error:
            sys.exit(2)
        sys.exit(1)


if __name__ == "__main__":
    main()
