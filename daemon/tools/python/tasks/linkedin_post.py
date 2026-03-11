"""Post to LinkedIn using CDP.

Opens the LinkedIn feed in the user's real Chrome session via CDP,
clicks "Start a post", types the text, optionally attaches an image,
and clicks Post.

Always uses true_cdp (the user's live browser) because LinkedIn's anti-bot
detection blocks headless browsers.
"""

from __future__ import annotations

import asyncio
import sys
from typing import Any

from playwright.async_api import async_playwright

from connect_to_chrome import connect_browser

LINKEDIN_FEED_URL = "https://www.linkedin.com/feed/"


async def post_to_linkedin(text: str, image: str | None = None) -> dict[str, Any]:
    """Post to LinkedIn.

    Parameters
    ----------
    text : str
        The text content of the post.
    image : str | None
        Optional image URL to attach.

    Returns
    -------
    dict with ``success`` (bool), and ``message`` or ``error`` (str).
    """
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
        # Navigate to LinkedIn feed
        print("[LinkedIn] Navigating to feed...")
        await page.goto(LINKEDIN_FEED_URL, wait_until="domcontentloaded")
        await asyncio.sleep(3)

        # Verify we're logged in
        for login_text in ["Sign in", "Join now"]:
            sign_in = page.get_by_text(login_text)
            try:
                if await sign_in.first.is_visible(timeout=1000):
                    await cleanup()
                    return {"success": False, "error": "Not logged in to LinkedIn — launch Chrome with --remote-debugging-port=9222"}
            except Exception:
                pass

        # Step 1: Click "Start a post" to open composer modal
        print("[LinkedIn] Step 1: Opening composer...")
        if not await _click_start_post(page):
            await cleanup()
            return {"success": False, "error": "Could not find 'Start a post' trigger"}
        print("[LinkedIn] Composer opened")
        await asyncio.sleep(2)

        # Step 2: Find and click the editor in the modal
        print("[LinkedIn] Step 2: Clicking editor...")
        editor_clicked = False
        for attempt in range(1, 4):
            editor_clicked = await _click_editor(page)
            if editor_clicked:
                break
            print(f"[LinkedIn] Editor not found, retry {attempt}/3...")
            await asyncio.sleep(1)

        if not editor_clicked:
            await cleanup()
            return {"success": False, "error": "Could not find post editor"}
        await asyncio.sleep(0.3)

        # Step 3: Type the text
        print(f"[LinkedIn] Step 3: Typing text ({len(text)} chars)...")
        await page.keyboard.type(text, delay=20)
        await asyncio.sleep(1.5)

        # Step 4: Attach image if provided
        if image:
            print("[LinkedIn] Step 4: Attaching image...")
            attached = await _attach_image(page, image)
            if attached:
                print("[LinkedIn] Image attached")
                await asyncio.sleep(2)
            else:
                print("[LinkedIn] Warning: could not attach image, posting without it")

        # Step 5: Click the Post button
        print("[LinkedIn] Step 5: Clicking Post button...")
        if not await _click_post_button(page):
            await cleanup()
            return {"success": False, "error": "Could not find Post button"}

        print("[LinkedIn] Post button clicked, waiting for completion...")
        await asyncio.sleep(3)

        await cleanup()
        print("[LinkedIn] Posted to LinkedIn successfully!")
        return {"success": True, "message": "Posted to LinkedIn successfully!"}

    except Exception as exc:
        print(f"[LinkedIn] Error: {exc}", file=sys.stderr)
        await cleanup()
        return {"success": False, "error": str(exc)}


async def _click_start_post(page) -> bool:
    """Click the 'Start a post' trigger button on the LinkedIn feed."""
    # Target the button element specifically — get_by_text can match non-button elements
    try:
        btn = page.locator('button:has-text("Start a post")').first
        if await btn.is_visible(timeout=3000):
            await btn.click()
            return True
    except Exception:
        pass

    # Fallback: click the share box area
    for sel in ['.share-box-feed-entry__trigger']:
        try:
            el = page.locator(sel).first
            if await el.is_visible(timeout=2000):
                await el.click()
                return True
        except Exception:
            continue
    return False


async def _click_editor(page) -> bool:
    """Click the contenteditable editor in the LinkedIn post modal."""
    selectors = [
        '[contenteditable="true"]',
        '.ql-editor',
        '[role="textbox"]',
    ]
    for sel in selectors:
        try:
            el = page.locator(sel).first
            if await el.is_visible(timeout=2000):
                await el.click()
                return True
        except Exception:
            continue
    return False


async def _attach_image(page, image_url: str) -> bool:
    from scrape_image import attach_image
    return await attach_image(page, image_url, platform="LinkedIn")


async def _click_post_button(page) -> bool:
    """Click the Post button in the LinkedIn composer modal."""
    # LinkedIn's post button is typically a submit button in the modal
    for sel in ['button.share-actions__primary-action', 'button:has-text("Post")']:
        try:
            btn = page.locator(sel).first
            if await btn.is_visible(timeout=3000):
                for _ in range(10):
                    if await btn.is_enabled():
                        await btn.click()
                        return True
                    await asyncio.sleep(0.5)
        except Exception:
            continue
    return False


def main():
    """CLI interface for posting to LinkedIn."""
    if len(sys.argv) < 2:
        print("Usage: python -m consumed.linkedin_post '<post text>' [--image <url>]", file=sys.stderr)
        sys.exit(1)

    args = sys.argv[1:]
    image_url = None
    if "--image" in args:
        idx = args.index("--image")
        if idx + 1 < len(args):
            image_url = args[idx + 1]
            args = args[:idx] + args[idx + 2:]

    content = " ".join(args)
    result = asyncio.run(post_to_linkedin(content, image=image_url))

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
