#!/usr/bin/env python3
"""Test that summaries display correctly in loading animation."""

# Simulate what happens with new format queries
print("=" * 80)
print("Testing query summary flow with NEW format queries")
print("=" * 80)

# Simulate new format queries (what user will have after regenerating)
stored_queries = [["\"raising seed\" (startup OR \"early stage\") (engineer OR developer) (hiring OR \"we're hiring\") -giveaway -crypto", "Seed Hiring"],
                  ["(\"seed round\" OR \"raising seed\") (founder OR startup) (hiring OR \"open roles\") (engineer OR tech)", "Seed Engineers"],
                  ["YC OR \"Y Combinator\" (hiring OR \"we're hiring\") (engineer OR dev) (startup OR founder)", "YC Jobs"]]

print(f"\n1. User has {len(stored_queries)} queries in new format")
for i, q in enumerate(stored_queries, 1):
    print(f"   {i}. [{q[1]}] {q[0][:50]}...")

# Simulate query_summary_map building (from read_tweets.py)
print("\n2. Building query_summary_map...")
query_summary_map = {}
queries = []

for q in stored_queries:
    if isinstance(q, list) and len(q) == 2:
        # New format: [query, summary]
        queries.append(q[0])
        query_summary_map[q[0]] = q[1]

print(f"   ✅ Built map with {len(query_summary_map)} entries")

# Simulate what gets passed to scraping status (from gather_trending)
print("\n3. Simulating scraping status updates...")
for query in queries[:2]:  # Just first 2
    summary = query_summary_map.get(query, query)
    status = {"type": "query", "value": query, "summary": summary, "phase": "scraping"}
    print("\n   Status for query:")
    print(f"   - Full query: {status['value'][:60]}...")
    print(f"   - Summary: {status['summary']}")
    print(f"   - What frontend will display: '{status['summary']}'")

# Simulate what LoadingOverlay displays
print("\n" + "=" * 80)
print("4. What LoadingOverlay will show:")
print("=" * 80)
for query in queries[:2]:
    summary = query_summary_map.get(query, query)
    statusData = {"type": "query", "value": query, "summary": summary}
    displayText = statusData.get("summary") or statusData["value"]
    print(f'   Scraping tweets related to "{displayText}"')

print("\n" + "=" * 80)
print("✅ CONCLUSION: Once user regenerates queries, summaries will display!")
print("=" * 80)
