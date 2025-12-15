"""
Simple API scraping test - verify query formats work.

Tests:
1. Account scraping via `from:handle` query
2. Query search

Run with: uv run python tests/test_api_scraping_simple.py
"""

import asyncio
import sys

sys.stdout.reconfigure(line_buffering=True)

print("[DEBUG] Script starting...", flush=True)


async def test_api_scraping():
    """Test API scraping with different query types."""
    print("[DEBUG] Starting async function", flush=True)

    from backend.browser_automation.twitter.api import fetch_search
    from backend.twitter.authentication import ensure_access_token
    print("[DEBUG] Imports done", flush=True)

    username = "divya_venn"  # User for authentication

    # Test account to scrape
    test_account = "paulg"  # Paul Graham - active poster

    # Test query - using web-style operators (should be auto-converted)
    test_query = "AI agents -filter:replies -filter:links lang:en"

    # Check OAuth token
    print("[DEBUG] Checking OAuth token...", flush=True)
    try:
        access_token = await ensure_access_token(username)
        print(f"[OK] OAuth token available", flush=True)
    except Exception as e:
        print(f"[ERROR] OAuth token not available: {e}", flush=True)
        return

    results = {
        "account": {"success": False, "count": 0, "error": None},
        "query": {"success": False, "count": 0, "error": None},
    }

    # =================================================================
    # TEST 1: Account scraping via from:handle query
    # =================================================================
    print(f"\n{'='*60}", flush=True)
    print(f"TEST 1: Account Scraping (@{test_account})", flush=True)
    print(f"{'='*60}", flush=True)

    account_query = f"from:{test_account} -filter:replies"
    print(f"Query: {account_query}", flush=True)

    try:
        tweets, _stats = await fetch_search(
            query=account_query,
            username=username
        )
        results["account"]["success"] = True
        results["account"]["count"] = len(tweets)
        print(f"[OK] Found {len(tweets)} tweets from @{test_account}", flush=True)

        if tweets:
            # Show first 3 tweets
            for i, (tweet_id, tweet) in enumerate(list(tweets.items())[:3]):
                print(f"\n  Tweet {i+1}:", flush=True)
                print(f"    ID: {tweet_id}", flush=True)
                print(f"    Author: @{tweet.get('handle', 'unknown')}", flush=True)
                print(f"    Text: {tweet.get('text', '')[:100]}...", flush=True)
                print(f"    Likes: {tweet.get('likes', 0)}", flush=True)
    except Exception as e:
        results["account"]["error"] = str(e)
        print(f"[ERROR] Account scraping failed: {e}", flush=True)
        import traceback
        traceback.print_exc()

    # =================================================================
    # TEST 2: Query search
    # =================================================================
    print(f"\n{'='*60}", flush=True)
    print(f"TEST 2: Query Search", flush=True)
    print(f"{'='*60}", flush=True)

    print(f"Query: {test_query}", flush=True)

    try:
        tweets, _stats = await fetch_search(
            query=test_query,
            username=username
        )
        results["query"]["success"] = True
        results["query"]["count"] = len(tweets)
        print(f"[OK] Found {len(tweets)} tweets for query", flush=True)

        if tweets:
            # Show first 3 tweets
            for i, (tweet_id, tweet) in enumerate(list(tweets.items())[:3]):
                print(f"\n  Tweet {i+1}:", flush=True)
                print(f"    ID: {tweet_id}", flush=True)
                print(f"    Author: @{tweet.get('handle', 'unknown')}", flush=True)
                print(f"    Text: {tweet.get('text', '')[:100]}...", flush=True)
                print(f"    Likes: {tweet.get('likes', 0)}", flush=True)
    except Exception as e:
        results["query"]["error"] = str(e)
        print(f"[ERROR] Query search failed: {e}", flush=True)
        import traceback
        traceback.print_exc()

    # =================================================================
    # Summary
    # =================================================================
    print(f"\n{'='*60}", flush=True)
    print("SUMMARY", flush=True)
    print(f"{'='*60}", flush=True)

    for test_name, result in results.items():
        status = "PASS" if result["success"] else "FAIL"
        count = result["count"]
        error = result.get("error", "")
        error_str = f" - {error}" if error else ""
        print(f"  {test_name}: [{status}] {count} tweets{error_str}", flush=True)

    all_passed = all(r["success"] for r in results.values())
    print(f"\nOverall: {'ALL TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}", flush=True)


if __name__ == "__main__":
    asyncio.run(test_api_scraping())
