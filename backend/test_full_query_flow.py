#!/usr/bin/env python3
"""Test the full query generation and save flow."""

import asyncio
import json

from backend.intent_to_queries import _generate_and_update_queries_background
from backend.utils import read_user_info


async def test_full_flow():
    """Test the complete flow from intent to saved queries."""

    test_username = "divya_venn"
    test_intent = "I want to find early stage startups raising seed funding and looking to hire engineers"

    print(f"🧪 Testing full query generation flow for: {test_username}")
    print(f"📝 Intent: {test_intent}\n")

    print("="*80)
    print("BEFORE - Checking current queries in user_info.json:")
    user_info_before = read_user_info(test_username)
    if user_info_before and "queries" in user_info_before:
        queries_before = user_info_before["queries"]
        print(f"Found {len(queries_before)} existing queries")
        for i, q in enumerate(queries_before[:2], 1):  # Show first 2
            print(f"{i}. Type: {type(q)}, Value: {str(q)[:100]}...")
    else:
        print("No queries found")

    print("\n" + "="*80)
    print("🚀 Running background task to generate and save queries...")
    await _generate_and_update_queries_background(test_username, test_intent)

    print("\n" + "="*80)
    print("AFTER - Checking updated queries in user_info.json:")
    user_info_after = read_user_info(test_username)

    if not user_info_after:
        print("❌ ERROR: User info not found!")
        return

    if "queries" not in user_info_after:
        print("❌ ERROR: No queries field in user_info!")
        return

    queries_after = user_info_after["queries"]
    print(f"✅ Found {len(queries_after)} queries")
    print(f"📊 Type of queries list: {type(queries_after)}")

    print("\n📋 Query details:")
    for i, query_item in enumerate(queries_after, 1):
        print(f"\n{i}. Type: {type(query_item)}")

        if isinstance(query_item, list):
            print(f"   ✅ Stored as list (correct format)")
            if len(query_item) == 2:
                full_query, summary = query_item
                print(f"   📝 Summary: '{summary}'")
                print(f"   🔍 Query: '{full_query[:80]}...'")
            else:
                print(f"   ❌ ERROR: List has {len(query_item)} elements, expected 2")
                print(f"   Value: {query_item}")
        elif isinstance(query_item, str):
            print(f"   ❌ ERROR: Stored as string (old format)")
            print(f"   Value: '{query_item[:80]}...'")
        else:
            print(f"   ❌ ERROR: Unexpected type")
            print(f"   Value: {query_item}")

    print("\n" + "="*80)
    print("📄 Raw JSON (first 3 queries):")
    print(json.dumps({"queries": queries_after[:3]}, indent=2))


if __name__ == "__main__":
    asyncio.run(test_full_flow())
