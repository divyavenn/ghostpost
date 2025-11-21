#!/usr/bin/env python3
"""Test script to verify query generation with summaries."""

import asyncio
import json

from backend.intent_to_queries import generate_queries_from_intent
from backend.utils import read_user_info


async def test_query_generation():
    """Test that queries are generated with summaries and saved correctly."""

    # Test with a sample intent
    test_username = "divya_venn"  # Replace with actual username
    test_intent = "I want to find early stage startups raising seed funding and looking to hire engineers"

    print(f"🧪 Testing query generation for: {test_username}")
    print(f"📝 Intent: {test_intent}\n")

    # Generate queries
    print("🤖 Generating queries...")
    queries = await generate_queries_from_intent(test_intent, test_username)

    print(f"\n✅ Generated {len(queries)} queries:")
    print(f"📊 Type of queries: {type(queries)}")

    for i, query_tuple in enumerate(queries, 1):
        print(f"\n{i}. Type: {type(query_tuple)}")
        if isinstance(query_tuple, tuple) and len(query_tuple) == 2:
            full_query, summary = query_tuple
            print(f"   Summary: '{summary}'")
            print(f"   Query: '{full_query[:80]}...'")
        else:
            print(f"   ❌ ERROR: Not a tuple! Value: {query_tuple}")

    # Now check what's actually stored in user_info.json
    print("\n" + "=" * 80)
    print("📂 Checking user_info.json storage...")

    user_info = read_user_info(test_username)
    if user_info and "queries" in user_info:
        stored_queries = user_info["queries"]
        print(f"\n✅ Found {len(stored_queries)} queries in user_info.json")
        print(f"📊 Type of stored queries: {type(stored_queries)}")

        for i, query_item in enumerate(stored_queries, 1):
            print(f"\n{i}. Type: {type(query_item)}")
            if isinstance(query_item, list) and len(query_item) == 2:
                full_query, summary = query_item
                print(f"   ✅ Summary: '{summary}'")
                print(f"   ✅ Query: '{full_query[:80]}...'")
            elif isinstance(query_item, str):
                print(f"   ❌ ERROR: Stored as string! Value: '{query_item[:80]}...'")
            else:
                print(f"   ❌ ERROR: Unexpected format! Value: {query_item}")
    else:
        print("❌ No queries found in user_info.json")

    # Print raw JSON to verify format
    print("\n" + "=" * 80)
    print("📄 Raw JSON format in user_info.json:")
    if user_info and "queries" in user_info:
        print(json.dumps({"queries": user_info["queries"]}, indent=2))


if __name__ == "__main__":
    asyncio.run(test_query_generation())
