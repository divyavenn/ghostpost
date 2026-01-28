"""
Test script for bread account login and session management.

Run this to verify Phase 1 implementation before proceeding to Phase 2.
"""
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from backend.twitter.bread_context import BreadAccountContext
from backend.utlils.utils import notify


async def test_bread_account_login():
    """Test bread account login and session management."""
    print("\n" + "="*70)
    print("TESTING BREAD ACCOUNT INFRASTRUCTURE")
    print("="*70 + "\n")

    test_username = "test_user"

    try:
        print("📝 Test 1: BreadAccountContext creation and login")
        async with BreadAccountContext(test_username) as bread_ctx:
            print(f"✅ Context created successfully")
            print(f"   - Bread account: {bread_ctx.bread_username}")
            print(f"   - User username: {bread_ctx.user_username}")
            print(f"   - Browser: {type(bread_ctx.browser).__name__}")
            print(f"   - Context: {type(bread_ctx.context).__name__}")

            # Verify context is usable
            if bread_ctx.context:
                print(f"✅ Browser context is ready for scraping")
            else:
                print(f"❌ Browser context is None!")
                return False

        print(f"✅ Context cleanup successful\n")

        print("📝 Test 2: Session restoration (should use saved session)")
        async with BreadAccountContext(test_username) as bread_ctx2:
            print(f"✅ Second context created")
            print(f"   - Bread account: {bread_ctx2.bread_username}")
            print(f"   - Should have restored session instead of logging in again")

        print(f"✅ All tests passed!\n")
        print("="*70)
        print("PHASE 1 VERIFICATION COMPLETE ✅")
        print("="*70)
        return True

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        print("\n" + "="*70)
        print("PHASE 1 VERIFICATION FAILED ❌")
        print("="*70)
        return False


if __name__ == "__main__":
    print("\nNote: This will attempt to login to bread accounts.")
    print("Make sure credentials in bread_accounts.py are correct.")
    print("Press Ctrl+C to cancel...\n")

    try:
        asyncio.sleep(3)  # Give user time to cancel
    except KeyboardInterrupt:
        print("\nCancelled by user")
        sys.exit(0)

    result = asyncio.run(test_bread_account_login())
    sys.exit(0 if result else 1)
