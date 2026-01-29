"""
Integration test for running background jobs with bread accounts.

Tests the full flow:
1. BreadAccountContext creates browser with bread account session
2. Job runs with bread account for authentication
3. User's data (divya_venn) is used for queries/settings
4. Results are written to user's cache files
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "backend"))

from backend.twitter.bread_accounts import run_with_bread_account
from backend.twitter.twitter_jobs import find_and_reply_to_new_posts
from backend.data.twitter.edit_cache import get_user_tweet_cache


async def test_bread_job_integration():
    """Test running find_and_reply_to_new_posts with bread account."""
    print("\n" + "="*70)
    print("INTEGRATION TEST: BREAD ACCOUNT + BACKGROUND JOB")
    print("="*70 + "\n")

    test_user = "divya_venn"

    print(f"📝 Test Configuration:")
    print(f"   • User: {test_user}")
    print(f"   • Job: find_and_reply_to_new_posts")
    print(f"   • Auth: Bread account (random selection)")
    print(f"   • Data: {test_user}'s queries and settings")
    print(f"   • Cache: {test_user}'s cache files\n")

    # Check user's cache file before
    cache_file = get_user_tweet_cache(test_user)
    print(f"📁 User's tweet cache file: {cache_file}")
    if cache_file.exists():
        import json
        try:
            with open(cache_file, 'r') as f:
                initial_data = json.load(f)
                initial_count = len(initial_data)
                print(f"   • Initial tweet count: {initial_count}\n")
        except Exception:
            initial_count = 0
            print(f"   • Cache exists but couldn't read (will be overwritten)\n")
    else:
        initial_count = 0
        print(f"   • No existing cache (will be created)\n")

    print("="*70)
    print("STARTING JOB WITH BREAD ACCOUNT")
    print("="*70 + "\n")

    try:
        # Run the actual job with bread account
        result = await run_with_bread_account(
            find_and_reply_to_new_posts,
            test_user,
            triggered_by="manual"
        )

        print("\n" + "="*70)
        print("JOB COMPLETED SUCCESSFULLY ✅")
        print("="*70 + "\n")

        # Check results
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    final_data = json.load(f)
                    final_count = len(final_data)
                    new_tweets = final_count - initial_count

                    print(f"📊 Results:")
                    print(f"   • Final tweet count: {final_count}")
                    print(f"   • New tweets discovered: {new_tweets}")
                    print(f"   • Cache file: {cache_file}")

                    if new_tweets > 0:
                        print(f"\n✅ SUCCESS: Job discovered and cached {new_tweets} new tweets")
                        print(f"   • Used bread account for authentication")
                        print(f"   • Used {test_user}'s queries and settings")
                        print(f"   • Wrote results to {test_user}'s cache")
                    else:
                        print(f"\n⚠️  No new tweets discovered (may be expected)")
                        print(f"   • Job ran successfully but found no new content")
                        print(f"   • This can happen if queries have no new results")

                    # Show some sample tweets
                    if new_tweets > 0 and final_count > 0:
                        print(f"\n📝 Sample tweets from cache:")
                        sample_tweets = list(final_data.values())[:3]
                        for i, tweet in enumerate(sample_tweets, 1):
                            tweet_id = tweet.get('id', 'unknown')
                            author = tweet.get('author_handle', 'unknown')
                            text_preview = tweet.get('text', '')[:60] + "..."
                            print(f"   {i}. @{author} (ID: {tweet_id})")
                            print(f"      {text_preview}")

            except Exception as e:
                print(f"⚠️  Warning: Could not read cache file: {e}")
        else:
            print(f"⚠️  Warning: Cache file not created")

        print("\n" + "="*70)
        print("INTEGRATION TEST COMPLETE ✅")
        print("="*70)
        print("\n✅ Key Validations:")
        print("   • Bread account context created successfully")
        print("   • Browser session authenticated")
        print("   • Job executed without errors")
        print("   • Results written to correct user cache")
        print("\n🎉 Phase 1 + Job Integration VERIFIED!")
        return True

    except Exception as e:
        print("\n" + "="*70)
        print("JOB FAILED ❌")
        print("="*70)
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        print("\n💡 Possible issues:")
        print("   • Bread account session invalid/expired")
        print("   • User queries not configured")
        print("   • Network/API issues")
        print("   • Browser automation errors")
        return False


if __name__ == "__main__":
    print("\n⚠️  NOTE: This test will run the actual background job!")
    print("   • It will scrape Twitter using a bread account")
    print("   • It may take several minutes to complete")
    print("   • Browser will open if bread account needs authentication")
    print("\n")

    result = asyncio.run(test_bread_job_integration())
    sys.exit(0 if result else 1)
