"""
Manual Login Helper for Bread Accounts

Opens a browser where you can manually log in to bread accounts.
Once logged in, the session is saved to Supabase.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "backend"))

from backend.twitter.bread_accounts import BREAD_ACCOUNTS
from backend.utlils.utils import store_browser_state, cookie_still_valid
from backend.utlils.supabase_client import get_browser_state
from playwright.async_api import async_playwright


async def manual_login_helper():
    """Helper to manually log in bread accounts and save sessions."""

    print("\n" + "="*70)
    print("MANUAL BREAD ACCOUNT LOGIN HELPER")
    print("="*70 + "\n")

    if not BREAD_ACCOUNTS:
        print("❌ No bread accounts configured!")
        return False

    # Check which accounts need login
    print("🔍 Checking bread account sessions in Supabase...\n")
    accounts_to_login = []
    accounts_valid = []

    for i, (username, _) in enumerate(BREAD_ACCOUNTS):
        # Get browser state from Supabase
        state = get_browser_state(username, site="twitter")

        if state:
            # Check if session is valid
            if cookie_still_valid(state):
                timestamp = state.get('timestamp', 'unknown')
                print(f"   ✅ {username}: Valid session (saved {timestamp})")
                accounts_valid.append(username)
            else:
                print(f"   ❌ {username}: Session expired - needs login")
                accounts_to_login.append(i)
        else:
            print(f"   ❌ {username}: No session found - needs login")
            accounts_to_login.append(i)

    if not accounts_to_login:
        print(f"\n✅ All bread accounts have valid sessions!")
        print(f"📁 Sessions stored in: Supabase (browser_states table)")
        return True

    print(f"\n📋 Need to log in {len(accounts_to_login)} account(s)")
    print(f"{'='*70}\n")
    input("Press ENTER to start logging in accounts...")

    playwright = await async_playwright().start()

    for idx in accounts_to_login:
        username = BREAD_ACCOUNTS[idx][0]
        password = BREAD_ACCOUNTS[idx][1]

        print(f"\n{'='*70}")
        print(f"LOGGING IN: {username}")
        print(f"{'='*70}\n")
        print(f"📝 Instructions:")
        print(f"   1. A browser will open to Twitter login page")
        print(f"   2. Manually log in to {username}")
        print(f"   3. Complete any verification steps (phone, email, CAPTCHA)")
        print(f"   4. Once you see the home timeline, press ENTER here")
        print(f"   5. The session will be saved automatically\n")
        print(f"💡 Credentials (for reference):")
        print(f"   Username: {username}")
        print(f"   Password: {password}\n")

        input("Press ENTER to open browser...")

        # Launch with stealth args to avoid bot detection
        browser = await playwright.chromium.launch(
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',  # Hide automation
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process',
            ]
        )

        # Create context with realistic user agent and permissions
        ctx = await browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            locale='en-US',
            timezone_id='America/New_York',
        )

        # Hide webdriver property
        await ctx.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        page = await ctx.new_page()

        # Navigate to login page
        await page.goto("https://x.com/i/flow/login?lang=en")

        print("\n🌐 Browser opened. Complete the login manually...")
        print("   When you see the home timeline, press ENTER here.\n")

        # Wait for user to complete login
        input("Press ENTER after you've logged in and see the home timeline...")

        # Check if logged in
        current_url = page.url
        print(f"\n📍 Current URL: {current_url}")

        if "home" in current_url.lower():
            print(f"✅ Detected home page - saving session...")

            # Save session to Supabase (account_type="bread" for burner accounts)
            await store_browser_state(username, ctx, account_type="bread")

            # Verify saved
            saved_state = get_browser_state(username, site="twitter")
            if saved_state:
                timestamp = saved_state.get('timestamp', 'unknown')
                cookies_count = len(saved_state.get('cookies', []))
                print(f"✅ Session saved successfully!")
                print(f"   • Timestamp: {timestamp}")
                print(f"   • Cookies saved: {cookies_count}")
                print(f"   • Stored in: Supabase (browser_states table)")
            else:
                print(f"⚠️  Warning: Failed to save session to Supabase!")

        else:
            print(f"⚠️  Warning: Not on home page. Login may not be complete.")
            print(f"   Current URL: {current_url}")
            print(f"   Session may not be valid.")

        await page.close()
        await ctx.close()
        await browser.close()

        if idx < len(accounts_to_login) - 1:
            print(f"\n{'='*70}")
            print("Moving to next account...")
            print(f"{'='*70}")
            await asyncio.sleep(2)

    await playwright.stop()

    print("\n" + "="*70)
    print("MANUAL LOGIN COMPLETE")
    print("="*70)

    if accounts_valid:
        print(f"\n✅ Accounts with valid sessions (skipped):")
        for username in accounts_valid:
            print(f"   • {username}")

    print(f"\n✅ Newly logged in accounts: {len(accounts_to_login)}")
    print(f"✅ Total accounts ready: {len(accounts_valid) + len(accounts_to_login)}/{len(BREAD_ACCOUNTS)}")
    print(f"\n📁 All sessions stored in: Supabase (browser_states table)")
    print("\n🚀 You can now run automated jobs with these bread accounts!")
    return True


if __name__ == "__main__":
    try:
        result = asyncio.run(manual_login_helper())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n\n❌ Cancelled by user")
        sys.exit(1)
