"""
Test tweet discovery for divya_venn using their queries and home timeline.

Run with: uv run python tests/test_divya_discovery.py
"""

import asyncio
import sys

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)

print("[DEBUG] Script starting...", flush=True)


async def test_divya_venn_discovery():
    """Test discovering tweets using divya_venn's settings."""
    print("[DEBUG] Starting async function", flush=True)

    from backend.browser_automation.twitter.api import (
        fetch_home_timeline_with_intent_filter,
        fetch_search,
    )
    print("[DEBUG] API imports done", flush=True)

    from backend.twitter.authentication import ensure_access_token
    from backend.utlils.utils import read_user_info
    from playwright.async_api import async_playwright
    from backend.utlils.utils import read_browser_state
    print("[DEBUG] All imports done", flush=True)

    username = "divya_venn"

    # Get user info
    user_info = read_user_info(username)
    if not user_info:
        print(f"[ERROR] User {username} not found", flush=True)
        return

    print(f"\n{'='*60}", flush=True)
    print(f"Testing Tweet Discovery for @{username}", flush=True)
    print(f"{'='*60}", flush=True)
    print(f"Intent: {user_info.get('intent', 'N/A')[:100]}...", flush=True)
    print(f"Number of queries: {len(user_info.get('queries', []))}", flush=True)
    print(f"Max tweets to retrieve: {user_info.get('max_tweets_retrieve', 30)}", flush=True)

    # Check OAuth token
    print("[DEBUG] Checking OAuth token...", flush=True)
    try:
        access_token = await ensure_access_token(username)
        print(f"\n[OK] OAuth token available", flush=True)
    except Exception as e:
        print(f"\n[ERROR] OAuth token not available: {e}", flush=True)
        return

    # Test 1: Home Timeline with Intent Filter
    print(f"\n{'='*60}", flush=True)
    print("TEST 1: Home Timeline with Intent Filter", flush=True)
    print(f"{'='*60}", flush=True)

    try:
        print("[DEBUG] Calling fetch_home_timeline_with_intent_filter...", flush=True)
        home_tweets = await fetch_home_timeline_with_intent_filter(
            username=username,
            generate_replies_inline=False  # Don't generate replies, just discover
        )

        print(f"\n[RESULT] Found {len(home_tweets)} tweets from home timeline", flush=True)

        if home_tweets:
            print("\nSample tweets from home timeline:", flush=True)
            for i, (tweet_id, tweet) in enumerate(list(home_tweets.items())[:3]):
                print(f"\n  {i+1}. @{tweet.get('handle', 'unknown')} ({tweet.get('followers', 0)} followers)", flush=True)
                print(f"     Score: {tweet.get('score', 0)} | Likes: {tweet.get('likes', 0)}", flush=True)
                text = tweet.get('text', '')[:150].replace('\n', ' ')
                print(f"     Text: {text}...", flush=True)
    except Exception as e:
        print(f"[ERROR] Home timeline fetch failed: {e}", flush=True)
        import traceback
        traceback.print_exc()

    # Test 2: Search Queries
    print(f"\n{'='*60}", flush=True)
    print("TEST 2: Search with User's Queries", flush=True)
    print(f"{'='*60}", flush=True)

    queries = user_info.get('queries', [])
    if not queries:
        print("[SKIP] No queries configured", flush=True)
        return

    # Set up browser context for search
    print("[DEBUG] Launching Playwright browser...", flush=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        print("[DEBUG] Browser launched", flush=True)

        try:
            result = await read_browser_state(browser, username)
            if result:
                _, ctx = result
            else:
                ctx = await browser.new_context()
        except Exception:
            ctx = await browser.new_context()

        try:
            # Test first 2 queries
            for i, query_item in enumerate(queries[:2]):
                # Handle both [query, summary] and plain query string
                if isinstance(query_item, list):
                    query, summary = query_item[0], query_item[1]
                else:
                    query, summary = query_item, "Query"

                print(f"\n  Query {i+1}: {summary}", flush=True)
                print(f"  Full query: {query[:80]}...", flush=True)

                try:
                    search_results = await fetch_search(
                        ctx,
                        query=query,
                        username=username
                    )

                    print(f"  [RESULT] Found {len(search_results)} tweets", flush=True)

                    if search_results:
                        # Show first result
                        first_id, first_tweet = next(iter(search_results.items()))
                        print(f"    Sample: @{first_tweet.get('handle', 'unknown')} - {first_tweet.get('text', '')[:80]}...", flush=True)
                except Exception as e:
                    print(f"  [ERROR] Search failed: {e}", flush=True)

        finally:
            await ctx.close()
            await browser.close()

    print(f"\n{'='*60}", flush=True)
    print("Discovery Test Complete", flush=True)
    print(f"{'='*60}", flush=True)


if __name__ == "__main__":
    asyncio.run(test_divya_venn_discovery())
