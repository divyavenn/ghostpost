"""Cookie import route used by the browser extension."""

from __future__ import annotations

import datetime

from fastapi import APIRouter
from playwright.async_api import async_playwright
from pydantic import BaseModel

from backend.config import SHOW_BROWSER
from backend.utlils.utils import notify, read_user_info
from backend.utlils.supabase_client import store_browser_state

router = APIRouter(prefix="/auth", tags=["auth"])


class CookieData(BaseModel):
    username: str


class CookieImport(BaseModel):
    data: CookieData
    cookies: list[dict]


@router.post("/twitter/import-cookies")
async def import_cookies(payload: CookieImport) -> dict:
    username = payload.data.username
    cookies = payload.cookies

    notify(f"📦 Received {len(cookies)} cookies for @{username} from extension")

    from backend.twitter.bread_accounts import BREAD_ACCOUNTS

    bread_account_handles = [acc[0] for acc in BREAD_ACCOUNTS]
    is_bread_account = username in bread_account_handles

    if not is_bread_account:
        user_info = read_user_info(username)
        if not user_info:
            error_msg = f"User @{username} not found in system"
            notify(f"🚫 {error_msg} - rejecting cookie import")
            return {
                "success": False,
                "error": "user_not_found",
                "message": error_msg,
                "user_message": f"Account Error: @{username} is not registered with GhostPoster. Please sign up first at the GhostPoster website.",
                "username": username,
            }
    else:
        notify(f"🍞 Detected bread account: @{username}")

    if not cookies:
        error_msg = f"No cookies provided for @{username}"
        notify(f"❌ {error_msg}")
        return {
            "success": False,
            "error": "no_cookies",
            "message": error_msg,
            "user_message": f"Extension Error: No cookies were captured for @{username}. Make sure you're logged into Twitter/X.",
            "username": username,
        }

    has_auth_token = any(c.get("name") == "auth_token" for c in cookies)
    if not has_auth_token:
        error_msg = f"Missing auth_token cookie for @{username}"
        notify(f"⚠️  {error_msg}")
        return {
            "success": False,
            "error": "missing_auth_token",
            "message": error_msg,
            "user_message": f"Authentication Error: The auth_token cookie is missing for @{username}. Please log out and log back into Twitter/X in your browser.",
            "username": username,
            "cookies_count": len(cookies),
        }

    sanitized_cookies: list[dict] = []
    for cookie in cookies:
        try:
            sanitized = dict(cookie)
            same_site = sanitized.get("sameSite", "Lax")
            if same_site not in ["Strict", "Lax", "None"]:
                sanitized["sameSite"] = "Lax"
            sanitized_cookies.append(sanitized)
        except Exception as exc:
            notify(f"⚠️  Warning: Could not sanitize cookie {cookie.get('name', 'unknown')}: {exc}")
            continue

    if not sanitized_cookies:
        error_msg = f"All cookies failed sanitization for @{username}"
        notify(f"❌ {error_msg}")
        return {
            "success": False,
            "error": "cookie_sanitization_failed",
            "message": error_msg,
            "user_message": f"Cookie Error: Unable to process cookies for @{username}. Please try logging in again.",
            "username": username,
        }

    try:
        storage_state = {
            "cookies": sanitized_cookies,
            "origins": [{"origin": "https://x.com", "localStorage": []}],
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
    except Exception as exc:
        error_msg = f"Failed to create storage state for @{username}: {exc}"
        notify(f"❌ {error_msg}")
        return {
            "success": False,
            "error": "storage_state_creation_failed",
            "message": error_msg,
            "user_message": f"Server Error: Failed to process cookies for @{username}. Please try again.",
            "username": username,
        }

    try:
        if is_bread_account:
            from backend.utlils.supabase_client import store_bread_account_state

            store_bread_account_state(username, storage_state, site="twitter")
            notify(f"✅ Imported {len(cookies)} cookies for bread account @{username}")
        else:
            store_browser_state(username, storage_state, site="twitter")
            notify(f"✅ Imported {len(cookies)} cookies for @{username}")
    except Exception as exc:
        error_msg = f"Failed to save browser state for @{username}: {exc}"
        notify(f"❌ {error_msg}")
        return {
            "success": False,
            "error": "cache_save_failed",
            "message": error_msg,
            "user_message": f"Server Error: Failed to save cookies for @{username}. Please try again.",
            "username": username,
        }

    verified = False
    verification_error = None
    try:
        notify(f"🔍 Verifying cookies for @{username}...")
        playwright = await async_playwright().start()
        try:
            browser = await playwright.chromium.launch(headless=(not SHOW_BROWSER))
            try:
                context = await browser.new_context(storage_state=storage_state)
                page = await context.new_page()
                try:
                    await page.goto("https://x.com/home", timeout=15000)
                    await page.wait_for_timeout(2000)
                    current_url = page.url
                    if "/login" in current_url or "/flow" in current_url:
                        notify(f"⚠️  Cookies for @{username} appear invalid (redirected to login)")
                        verification_error = "Cookies appear invalid - Twitter redirected to login page"
                    else:
                        notify(f"✅ Cookies for @{username} verified successfully")
                        verified = True
                except Exception as exc:
                    notify(f"⚠️  Could not navigate to Twitter: {exc}")
                    verification_error = f"Navigation failed: {exc}"
            finally:
                await browser.close()
        finally:
            await playwright.stop()
    except Exception as exc:
        error_msg = f"Cookie verification failed for @{username}: {exc}"
        notify(f"❌ {error_msg}")
        verification_error = str(exc)

    return {
        "success": True,
        "message": f"Successfully imported cookies for @{username}",
        "cookies_count": len(cookies),
        "username": username,
        "verified": verified,
        "verification_error": verification_error if not verified else None,
        "user_message": f"Cookies imported for @{username}. "
        + ("Login verified successfully!" if verified else f"Warning: Could not verify login - {verification_error}"),
    }
