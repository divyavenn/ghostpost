"""Scrape og:image from URLs and copy images to the macOS clipboard."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import tempfile

import httpx
from bs4 import BeautifulSoup


def scrape_image_url(url: str) -> str | None:
    """Return the og:image or twitter:image URL from a web page, or None."""
    try:
        resp = httpx.get(
            url,
            follow_redirects=True,
            timeout=30.0,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"},
        )
        resp.raise_for_status()
    except Exception:
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    for attr in ("og:image", "twitter:image"):
        tag = soup.find("meta", property=attr) or soup.find("meta", attrs={"name": attr})
        if tag and tag.get("content"):
            return tag["content"]

    return None


def copy_image_to_clipboard(file_path: str) -> bool:
    """Copy an image file to the macOS clipboard using AppKit via osascript.

    Supports PNG, JPEG, WebP, GIF — anything NSImage can read.
    Returns True on success, False on failure.
    """
    script = f'''
use framework "AppKit"
set img to current application's NSImage's alloc()'s initWithContentsOfFile:"{file_path}"
if img is missing value then
    error "Could not load image"
end if
set pb to current application's NSPasteboard's generalPasteboard()
pb's clearContents()
pb's writeObjects:{{img}}
'''
    try:
        subprocess.run(
            ["osascript", "-e", script],
            check=True,
            capture_output=True,
            timeout=10,
        )
        return True
    except Exception:
        return False


def download_and_copy_to_clipboard(image_url: str) -> tuple[bool, str | None]:
    """Download an image URL to a temp file and copy it to the clipboard.

    Returns (success, tmp_path). Caller is responsible for cleaning up tmp_path.
    """
    try:
        resp = httpx.get(
            image_url,
            follow_redirects=True,
            timeout=30.0,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        resp.raise_for_status()
    except Exception:
        return False, None

    ct = resp.headers.get("content-type", "")
    ext = ".jpg"
    if "png" in ct:
        ext = ".png"
    elif "webp" in ct:
        ext = ".webp"
    elif "gif" in ct:
        ext = ".gif"

    tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
    tmp.write(resp.content)
    tmp.close()

    ok = copy_image_to_clipboard(tmp.name)
    return ok, tmp.name


async def attach_image(page, image_url: str, platform: str = "") -> bool:
    """Download image, copy to clipboard, and paste into a Playwright page.

    Shared by all posting modules (Substack, Twitter, LinkedIn).
    """
    tmp_path = None
    try:
        ok, tmp_path = download_and_copy_to_clipboard(image_url)
        if not ok:
            return False

        editor = page.locator('[contenteditable="true"]').first
        await editor.click()
        await page.keyboard.press("Meta+v")
        await asyncio.sleep(2)
        return True
    except Exception as e:
        label = f"[{platform}] " if platform else ""
        print(f"{label}Image attach error: {e}", file=sys.stderr)
        return False
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
