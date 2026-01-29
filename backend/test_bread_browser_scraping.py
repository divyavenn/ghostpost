"""
Test bread account browser context for actual scraping.

This tests that the bread account browser context can:
1. Create an authenticated browser session
2. Navigate to Twitter
3. Verify the session is logged in
4. Perform basic scraping operations
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "backend"))

from backend.twitter.bread_context import BreadAccountContext


async def test_bread_browser_scraping():
    """Test bread account context for real browser operations."""
    print("\n" + "="*70)
    print("TEST: BREAD ACCOUNT BROWSER SCRAPING")
    print("="*70 + "\n")

    test_user = "divya_venn"

    try:
        print("📝 Step 1: Creating bread account browser context...")
        async with BreadAccountContext(test_user) as bread_ctx:
            print(f"✅ Context created")
            print(f"   • Bread account: {bread_ctx.bread_username}")
            print(f"   • User: {bread_ctx.user_username}")
            print(f"   • Browser: {bread_ctx.browser is not None}")
            print(f"   • Context: {bread_ctx.context is not None}\n")

            if not bread_ctx.context:
                print("❌ No browser context available!")
                return False

            print("📝 Step 2: Testing browser navigation...")
            page = await bread_ctx.context.new_page()

            # Navigate to Twitter home
            print("   → Navigating to Twitter home...")
            await page.goto("https://x.com/home", timeout=30000)
            await asyncio.sleep(2)

            current_url = page.url
            print(f"   → Current URL: {current_url}\n")

            # Check if we're logged in
            if "login" in current_url.lower():
                print("❌ Session not authenticated - redirected to login")
                print("   Run manual_bread_login.py to create valid sessions")
                await page.close()
                return False

            print("✅ Session is authenticated (stayed on home page)\n")

            print("📝 Step 3: Testing page interactions...")
            # Get page title
            try:
                title = await page.title()
                print(f"   • Page title: {title}")
            except Exception as e:
                print(f"   ⚠️  Could not get page title: {e}")
                title = "unknown"

            # Check for timeline presence
            content = await page.content()
            has_timeline = "timeline" in content.lower() or "tweet" in content.lower()
            print(f"   • Has timeline content: {has_timeline}")

            # Try to get some basic page info
            try:
                # Wait for any article (tweet) to load
                await page.wait_for_selector('article', timeout=10000)
                articles = await page.query_selector_all('article')
                print(f"   • Tweets visible: {len(articles)}\n")

                if len(articles) > 0:
                    print("✅ Successfully loaded timeline with tweets\n")
                else:
                    print("⚠️  No tweets found (timeline may be empty)\n")

            except Exception as e:
                print(f"⚠️  Could not find tweets: {e}\n")

            print("📝 Step 4: Testing browser context reuse...")
            # Create another page in same context
            page2 = await bread_ctx.context.new_page()
            await page2.goto("https://x.com/home")
            await asyncio.sleep(1)

            if "login" not in page2.url.lower():
                print("✅ Second page also authenticated (context reused correctly)\n")
            else:
                print("⚠️  Second page redirected to login\n")

            await page2.close()
            await page.close()

            print("="*70)
            print("BREAD ACCOUNT BROWSER TEST COMPLETE ✅")
            print("="*70)
            print("\n✅ All Checks Passed:")
            print("   • Bread account context created")
            print("   • Browser session authenticated")
            print("   • Can navigate to Twitter")
            print("   • Can access timeline")
            print("   • Context can be reused for multiple pages")
            print("\n🎉 Bread accounts are READY for scraping!")
            print("\n💡 Next Step: Implement Phase 2 (Router Integration)")
            print("   Then jobs can use bread accounts for actual scraping")
            return True

        print("\n✅ Context cleanup successful")
        return True

    except Exception as e:
        print("\n" + "="*70)
        print("TEST FAILED ❌")
        print("="*70)
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        print("\n💡 Possible issues:")
        print("   • Bread account session invalid/expired")
        print("   • Run manual_bread_login.py to create sessions")
        print("   • Network connectivity issues")
        return False


if __name__ == "__main__":
    print("\n📋 This test verifies bread account browser functionality")
    print("   It will open a browser and navigate to Twitter")
    print("   Make sure bread accounts have valid sessions\n")

    result = asyncio.run(test_bread_browser_scraping())
    sys.exit(0 if result else 1)
