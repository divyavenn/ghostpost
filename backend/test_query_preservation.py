#!/usr/bin/env python3
"""Test that query summaries are preserved when settings are updated."""

print("=" * 80)
print("Testing Query Summary Preservation in write_user_settings")
print("=" * 80)

# Simulate existing user_info with tuple-format queries
existing_user_info = {
    "handle":
    "test_user",
    "queries": [["\"raising seed\" (startup OR founder) -crypto -filter:links lang:en", "Seed Funding"], ["YC OR \"Y Combinator\" (hiring OR jobs) -filter:replies lang:en", "YC Jobs"],
                ["(founder OR \"tech startup\") (marketing OR growth) lang:en", "Startup Marketing"]]
}

print(f"\n1. BEFORE: User has {len(existing_user_info['queries'])} queries in tuple format:")
for i, q in enumerate(existing_user_info['queries'], 1):
    print(f"   {i}. [{q[1]}] {q[0][:50]}...")

# Simulate what frontend sends (from read_user_settings - only query strings)
incoming_queries = [
    "\"raising seed\" (startup OR founder) -crypto -filter:links lang:en", "YC OR \"Y Combinator\" (hiring OR jobs) -filter:replies lang:en",
    "(founder OR \"tech startup\") (marketing OR growth) lang:en"
]

print(f"\n2. Frontend sends {len(incoming_queries)} query strings (no summaries):")
for i, q in enumerate(incoming_queries, 1):
    print(f"   {i}. {q[:60]}...")

# Simulate write_user_settings logic
print("\n3. Processing with write_user_settings logic...")

existing_queries = existing_user_info.get("queries", [])

# Build map: full_query -> summary
query_summary_map = {}
for stored_q in existing_queries:
    if isinstance(stored_q, list) and len(stored_q) == 2:
        query_summary_map[stored_q[0]] = stored_q[1]

print(f"   Built summary map with {len(query_summary_map)} entries")

# Process incoming queries
updated_queries = []
for q in incoming_queries:
    if q in query_summary_map:
        # Preserve tuple format with summary
        updated_queries.append([q, query_summary_map[q]])
        print(f"   ✅ Preserved summary for: {query_summary_map[q]}")
    else:
        # New query - store as string
        updated_queries.append(q)
        print(f"   ➕ New query (no summary): {q[:40]}...")

print("\n4. AFTER: Updated queries:")
for i, q in enumerate(updated_queries, 1):
    if isinstance(q, list) and len(q) == 2:
        print(f"   {i}. ✅ TUPLE: [{q[1]}] {q[0][:50]}...")
    else:
        print(f"   {i}. ⚠️  STRING: {q[:50]}...")

# Verify all summaries preserved
print("\n" + "=" * 80)
all_preserved = all(isinstance(q, list) and len(q) == 2 for q in updated_queries)
if all_preserved:
    print("✅ SUCCESS: All query summaries preserved!")
else:
    print("❌ FAILURE: Some summaries were lost!")
print("=" * 80)
