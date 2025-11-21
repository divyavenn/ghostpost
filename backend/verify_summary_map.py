#!/usr/bin/env python3
"""Verify query_summary_map is built correctly from user_info."""

from backend.utils import read_user_info

test_username = "divya_venn"

print(f"🧪 Verifying query_summary_map construction for: {test_username}\n")

# Simulate the code from read_tweets.py
user_info = read_user_info(test_username)

if not user_info:
    print("❌ User info not found!")
    exit(1)

stored_queries = user_info.get("queries", [])
print(f"✅ Found {len(stored_queries)} stored queries in user_info\n")

# Build query_summary_map (same logic as read_tweets.py)
query_summary_map = {}
queries = []

for q in stored_queries:
    if isinstance(q, list) and len(q) == 2:
        # New format: [query, summary]
        queries.append(q[0])
        query_summary_map[q[0]] = q[1]
    elif isinstance(q, str):
        # Legacy format: just query string
        queries.append(q)
        query_summary_map[q] = q  # Use query itself as summary for legacy

print("=" * 80)
print("Query Summary Map:")
print("=" * 80)

for i, query in enumerate(queries, 1):
    summary = query_summary_map.get(query, "NOT FOUND")
    print(f"\n{i}. Full Query:")
    print(f"   {query[:100]}...")
    print(f"   Summary: '{summary}'")
    if summary == query[:len(summary)]:
        print("   ⚠️  Summary is just the start of the query (legacy format)")
    elif summary == "NOT FOUND":
        print("   ❌ ERROR: No summary found!")
    else:
        print("   ✅ Has distinct summary!")

print("\n" + "=" * 80)
print(f"Total queries: {len(queries)}")
print(f"Total summaries in map: {len(query_summary_map)}")
print(f"Match: {'✅' if len(queries) == len(query_summary_map) else '❌'}")
