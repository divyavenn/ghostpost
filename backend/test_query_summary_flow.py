#!/usr/bin/env python3
"""Test that query summaries flow through the scraping status correctly."""

import asyncio
import json

from backend.backend.scraping.twitter.timeline import read_tweets, scraping_status

from backend.utils import read_user_info


async def test_summary_in_status():
    """Test that summaries appear in scraping_status during scraping."""

    test_username = "divya_venn"

    print(f"🧪 Testing query summary flow for: {test_username}\n")

    # First, verify user has queries with summaries
    print("=" * 80)
    print("1. Checking user_info.json for query summaries...")
    user_info = read_user_info(test_username)

    if not user_info:
        print("❌ ERROR: User info not found!")
        return

    stored_queries = user_info.get("queries", [])
    print(f"✅ Found {len(stored_queries)} queries")

    has_summaries = False
    for i, q in enumerate(stored_queries[:3], 1):
        if isinstance(q, list) and len(q) == 2:
            print(f"{i}. Query: '{q[0][:60]}...'")
            print(f"   Summary: '{q[1]}'")
            has_summaries = True
        else:
            print(f"{i}. Legacy format: '{str(q)[:60]}...'")

    if not has_summaries:
        print("\n❌ No queries with summaries found. Run test_full_query_flow.py first.")
        return

    print("\n" + "=" * 80)
    print("2. Testing scraping status updates...")
    print("   (This will actually scrape, so it may take a while)\n")

    # Clear any existing status
    if test_username in scraping_status:
        del scraping_status[test_username]

    # Start scraping (this will update scraping_status)
    print("🔍 Starting scraping...")

    # We'll limit to 1 tweet to make it faster
    try:
        # This will trigger the scraping and update scraping_status
        tweets = await read_tweets(username=test_username, max_tweets=1)
        print(f"\n✅ Scraping completed. Found {len(tweets)} tweets")
    except Exception as e:
        print(f"❌ Error during scraping: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 80)
    print("3. Checking final scraping_status...")

    if test_username in scraping_status:
        status = scraping_status[test_username]
        print(f"✅ Status found: {json.dumps(status, indent=2)}")

        if status.get("type") == "query" and "summary" in status:
            print("\n✅ SUCCESS: Summary field found in status!")
            print(f"   Summary: '{status['summary']}'")
            print(f"   Full query: '{status['value']}'")
        else:
            print("\n⚠️ Status doesn't have summary field or is not a query type")
    else:
        print(f"⚠️ No scraping status found for {test_username}")

    print("\n" + "=" * 80)
    print("Test complete!")


if __name__ == "__main__":
    asyncio.run(test_summary_in_status())
