"""
Test script for bread account login ONLY.

Tests:
1. Login succeeds
2. Browser state is saved to bread_storage_state.json
3. Session can be restored from saved state
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "backend"))

from backend.browser_automation.twitter.timeline import log_in_bread_account
from backend.twitter.bread_accounts import BREAD_ACCOUNTS
from backend.utlils.utils import BREAD_STATE_FILE, read_bread_browser_state
from playwright.async_api import async_playwright


async def test_login_only():
    """Test bread account login and state persistence."""
    print("\n" + "="*70)
    print("TESTING BREAD ACCOUNT LOGIN ONLY")
    print("="*70 + "\n")

    if not BREAD_ACCOUNTS:
        print("❌ No bread accounts configured!")
        return False

    # Use first account for testing
    test_username = BREAD_ACCOUNTS[0][0]
    test_password = BREAD_ACCOUNTS[0][1]

    print(f"📝 Test Account: {test_username}")
    print(f"📁 Storage File: {BREAD_STATE_FILE}\n")

    # Step 1: Check initial state
    print("Step 1: Checking initial browser state...")
    initial_state_exists = BREAD_STATE_FILE.exists()
    if initial_state_exists:
        with open(BREAD_STATE_FILE, 'r') as f:
            initial_data = json.load(f)
            initial_timestamp = initial_data.get(test_username, {}).get('timestamp', 'none')
            print(f"   ✓ Existing state found")
            print(f"   ✓ Initial timestamp: {initial_timestamp}")
    else:
        print(f"   ✓ No existing state (fresh login)")
        initial_timestamp = None

    # Step 2: Perform login
    print(f"\nStep 2: Logging in {test_username}...")
    print(f"   ⚠️  Browser will open - if Twitter asks for verification, please complete it manually")
    print(f"   ⚠️  You have 60 seconds to complete any verification steps\n")
    try:
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(
            headless=False,
            slow_mo=500  # Slow down actions by 500ms to make them visible
        )

        browser_result, context_result = await log_in_bread_account(
            test_username,
            test_password,
            browser
        )

        print(f"   ✅ Login successful!")
        print(f"   ✓ Browser: {browser_result}")
        print(f"   ✓ Context: {context_result}")

        # Step 3: Verify state was saved
        print(f"\nStep 3: Verifying browser state was saved...")
        if not BREAD_STATE_FILE.exists():
            print(f"   ❌ State file not created!")
            await context_result.close()
            await browser.close()
            await playwright.stop()
            return False

        with open(BREAD_STATE_FILE, 'r') as f:
            saved_data = json.load(f)

        if test_username not in saved_data:
            print(f"   ❌ {test_username} not in state file!")
            await context_result.close()
            await browser.close()
            await playwright.stop()
            return False

        account_state = saved_data[test_username]
        new_timestamp = account_state.get('timestamp', 'none')

        print(f"   ✅ State file exists and updated")
        print(f"   ✓ New timestamp: {new_timestamp}")

        # Verify timestamp changed
        if initial_timestamp and new_timestamp == initial_timestamp:
            print(f"   ⚠️  Warning: Timestamp did not change!")
        else:
            print(f"   ✅ Timestamp updated (state is fresh)")

        # Verify cookies exist
        cookies = account_state.get('cookies', [])
        auth_cookie = None
        for cookie in cookies:
            if cookie.get('name') == 'auth_token':
                auth_cookie = cookie
                break

        if auth_cookie:
            print(f"   ✅ auth_token cookie found")
            expiry = auth_cookie.get('expires') or auth_cookie.get('expirationDate', 0)
            print(f"   ✓ Cookie expiry: {expiry}")
        else:
            print(f"   ❌ auth_token cookie not found!")
            await context_result.close()
            await browser.close()
            await playwright.stop()
            return False

        # Step 4: Test session restoration
        print(f"\nStep 4: Testing session restoration...")

        # Close current browser
        await context_result.close()
        await browser.close()

        # Create new browser and try to restore
        browser2 = await playwright.chromium.launch(headless=False)
        restore_result = await read_bread_browser_state(browser2, test_username)

        if restore_result:
            _, restored_context = restore_result
            print(f"   ✅ Session restored successfully!")
            print(f"   ✓ Restored context: {restored_context}")

            # Verify restored context works
            page = await restored_context.new_page()
            await page.goto("https://x.com/home")
            await asyncio.sleep(2)

            current_url = page.url
            print(f"   ✓ Navigated to: {current_url}")

            if "login" in current_url.lower():
                print(f"   ❌ Restored session redirected to login (invalid session)")
                await page.close()
                await restored_context.close()
                await browser2.close()
                await playwright.stop()
                return False
            else:
                print(f"   ✅ Restored session is valid (stayed logged in)")

            await page.close()
            await restored_context.close()
        else:
            print(f"   ❌ Session restoration failed!")
            await browser2.close()
            await playwright.stop()
            return False

        # Cleanup
        await browser2.close()
        await playwright.stop()

        # Final summary
        print("\n" + "="*70)
        print("BREAD ACCOUNT LOGIN TEST COMPLETE ✅")
        print("="*70)
        print("\n✅ All Checks Passed:")
        print("   • Login succeeded")
        print("   • Browser state saved to file")
        print("   • Timestamp updated")
        print("   • auth_token cookie present")
        print("   • Session restoration works")
        print("   • Restored session is valid")
        print("\n✨ Bread account is ready for production use!")
        return True

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        print("\n" + "="*70)
        print("BREAD ACCOUNT LOGIN TEST FAILED ❌")
        print("="*70)
        return False


if __name__ == "__main__":
    result = asyncio.run(test_login_only())
    sys.exit(0 if result else 1)
