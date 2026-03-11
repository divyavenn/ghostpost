"""Post a note to Substack deterministically using CDP.

Opens the Substack notes page in a background browser window via the user's
real Chrome session, clicks the composer, types the note text, and clicks Post.

Always uses true_cdp (the user's live browser) because Substack's anti-bot
detection blocks headless browsers even with valid session cookies.
"""

from __future__ import annotations

import asyncio
import sys
from typing import Any

from playwright.async_api import async_playwright

from connect_to_chrome import connect_browser

SUBSTACK_NOTES_URL = "https://substack.com/notes"


async def post_note(text: str, image: str | None = None) -> dict[str, Any]:
    """Post a note to Substack.

    Parameters
    ----------
    text : str
        The text content of the note.
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
        # Navigate to Substack notes
        print("[Substack] Navigating to notes page...")
        await page.goto(SUBSTACK_NOTES_URL, wait_until="domcontentloaded")
        await asyncio.sleep(2)

        # Verify we're logged in (Substack shows "Sign in" when not authenticated)
        sign_in = page.get_by_text("Sign in")
        try:
            if await sign_in.first.is_visible(timeout=1000):
                await cleanup()
                return {"success": False, "error": "Not logged in to Substack — launch Chrome with --remote-debugging-port=9222"}
        except Exception:
            pass

        # Step 1: Click the composer trigger
        print("[Substack] Step 1: Opening composer...")
        if not await _click_composer(page):
            await cleanup()
            return {"success": False, "error": "Could not find composer trigger"}
        print("[Substack] Composer opened")
        await asyncio.sleep(2)

        # Step 2: Click the input area (retry for slow-loading modal)
        print("[Substack] Step 2: Clicking input area...")
        input_clicked = False
        for attempt in range(1, 4):
            input_clicked = await _click_note_input(page)
            if input_clicked:
                break
            print(f"[Substack] Input not found, retry {attempt}/3...")
            await asyncio.sleep(1)

        if not input_clicked:
            await cleanup()
            return {"success": False, "error": "Could not find note input"}
        await asyncio.sleep(0.3)

        # Step 2.5: Clear any existing content
        print("[Substack] Clearing any existing content...")
        await page.evaluate("""
            (() => {
                const el = document.querySelector('[contenteditable="true"]');
                if (el) { el.innerHTML = ''; el.focus(); }
            })()
        """)
        await asyncio.sleep(0.2)

        # Step 3: Type the text
        print(f"[Substack] Step 3: Typing text ({len(text)} chars)...")
        await page.keyboard.type(text, delay=20)
        await asyncio.sleep(1.5)

        # Step 3.5: Attach image if provided
        if image:
            print(f"[Substack] Step 3.5: Attaching image...")
            attached = await _attach_image(page, image)
            if attached:
                print("[Substack] Image attached")
                await asyncio.sleep(2)
            else:
                print("[Substack] Warning: could not attach image, posting without it")

        # Step 4: Click the Post button
        print("[Substack] Step 4: Clicking Post button...")
        if not await _click_post_button(page):
            await cleanup()
            return {"success": False, "error": "Could not find Post button"}

        print("[Substack] Post button clicked, waiting for completion...")
        await asyncio.sleep(3)

        await cleanup()
        print("[Substack] Note posted successfully!")
        return {"success": True, "message": "Note posted successfully!"}

    except Exception as exc:
        print(f"[Substack] Error: {exc}", file=sys.stderr)
        await cleanup()
        return {"success": False, "error": str(exc)}


async def _click_composer(page) -> bool:
    """Click the inline 'What's on your mind?' trigger to open the note editor."""
    # The Substack notes page has an inline trigger div (not a button)
    trigger = page.get_by_text("What's on your mind?")
    try:
        if await trigger.first.is_visible(timeout=3000):
            await trigger.first.click()
            return True
    except Exception:
        pass
    return False


async def _click_note_input(page) -> bool:
    """Click the contenteditable editor that appears after opening the composer."""
    selectors = [
        '[contenteditable="true"]',
        '.tiptap.ProseMirror',
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
    return await attach_image(page, image_url, platform="Substack")


async def _click_post_button(page) -> bool:
    """Click the Post button (becomes enabled after typing text)."""
    try:
        btn = page.locator('button:has-text("Post")').first
        if await btn.is_visible(timeout=2000):
            # Wait for button to become enabled (it starts disabled until text is typed)
            for _ in range(10):
                if await btn.is_enabled():
                    await btn.click()
                    return True
                await asyncio.sleep(0.5)
    except Exception:
        pass
    return False


def post_to_substack_notes(content: str, **kwargs) -> dict:
    """Sync wrapper for backward compatibility with existing callers."""
    return asyncio.run(post_note(content))


def main():
    """CLI interface for posting to Substack Notes."""
    if len(sys.argv) < 2:
        print("Usage: python -m consumed.substack_notes '<note text>' [--image <url>]", file=sys.stderr)
        sys.exit(1)

    args = sys.argv[1:]
    image_url = None
    if "--image" in args:
        idx = args.index("--image")
        if idx + 1 < len(args):
            image_url = args[idx + 1]
            args = args[:idx] + args[idx + 2:]

    content = " ".join(args)
    result = asyncio.run(post_note(content, image=image_url))

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
