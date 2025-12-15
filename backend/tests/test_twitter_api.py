"""
Test Twitter API v2 scraping functionality.

Tests:
1. Account scraping via `from:handle` query
2. Query search with operator conversion
3. Home timeline fetch

Run with: uv run pytest tests/test_twitter_api.py -v
"""

import pytest


@pytest.fixture
def username():
    """Test user for authentication."""
    return "divya_venn"


@pytest.fixture
def test_account():
    """Account to test scraping."""
    return "paulg"


@pytest.mark.asyncio
async def test_account_scraping(username, test_account):
    """Test scraping tweets from a specific account using from:handle query."""
    from backend.browser_automation.twitter.api import fetch_search
    from backend.twitter.authentication import ensure_access_token

    # Ensure we have auth
    access_token = await ensure_access_token(username)
    assert access_token, "No access token available"

    # Scrape account
    account_query = f"from:{test_account}"
    tweets, _stats = await fetch_search(
        query=account_query,
        username=username
    )

    # Test passes if we got any tweets
    assert len(tweets) > 0, f"No tweets found for @{test_account}"
    print(f"\n[PASS] Found {len(tweets)} tweets from @{test_account}")

    # Verify tweet structure
    first_tweet = next(iter(tweets.values()))
    assert "id" in first_tweet
    assert "text" in first_tweet
    assert "handle" in first_tweet
    print(f"  Sample: @{first_tweet['handle']}: {first_tweet['text'][:80]}...")


@pytest.mark.asyncio
async def test_query_search_with_web_operators(username):
    """Test query search with web-style operators (should be auto-converted)."""
    from backend.browser_automation.twitter.api import fetch_search
    from backend.twitter.authentication import ensure_access_token

    # Ensure we have auth
    access_token = await ensure_access_token(username)
    assert access_token, "No access token available"

    # Query with web-style operators (should be converted to API style)
    query = "AI agents -filter:replies -filter:links lang:en"
    tweets, _stats = await fetch_search(
        query=query,
        username=username
    )

    # Test passes if we got any tweets
    assert len(tweets) > 0, f"No tweets found for query: {query}"
    print(f"\n[PASS] Found {len(tweets)} tweets for query")

    # Verify tweet structure
    first_tweet = next(iter(tweets.values()))
    assert "id" in first_tweet
    assert "text" in first_tweet
    print(f"  Sample: @{first_tweet.get('handle', 'unknown')}: {first_tweet['text'][:80]}...")


@pytest.mark.asyncio
async def test_query_search_with_api_operators(username):
    """Test query search with API-style operators directly."""
    from backend.browser_automation.twitter.api import fetch_search
    from backend.twitter.authentication import ensure_access_token

    # Ensure we have auth
    access_token = await ensure_access_token(username)
    assert access_token, "No access token available"

    # Query with API-style operators
    query = "startup funding -is:reply -has:links lang:en"
    tweets, _stats = await fetch_search(
        query=query,
        username=username
    )

    # Test passes if we got any tweets
    assert len(tweets) > 0, f"No tweets found for query: {query}"
    print(f"\n[PASS] Found {len(tweets)} tweets for API-style query")


@pytest.mark.asyncio
async def test_home_timeline(username):
    """Test fetching home timeline via API."""
    from backend.browser_automation.twitter.api import fetch_home_timeline_with_intent_filter
    from backend.twitter.authentication import ensure_access_token

    # Ensure we have auth
    access_token = await ensure_access_token(username)
    assert access_token, "No access token available"

    # Fetch home timeline with intent filter
    tweets, _stats = await fetch_home_timeline_with_intent_filter(
        username=username,
        max_tweets=20
    )

    # Test passes if we got any tweets (even 0 is fine if intent filter is strict)
    # The key test is that the API call succeeds without error
    print(f"\n[PASS] Home timeline API call succeeded - found {len(tweets)} tweets matching intent")

    if tweets:
        # Verify tweet structure
        first_tweet = next(iter(tweets.values()))
        assert "id" in first_tweet
        assert "text" in first_tweet
        print(f"  Sample: @{first_tweet.get('handle', 'unknown')}: {first_tweet['text'][:80]}...")


@pytest.mark.asyncio
async def test_operator_conversion():
    """Test that web-style operators are correctly converted to API-style."""
    from backend.browser_automation.twitter.api import _convert_web_query_to_api

    # Test conversions
    test_cases = [
        ("AI -filter:replies", "AI -is:reply"),
        ("tech -filter:links", "tech -has:links"),
        ("news -filter:retweets", "news -is:retweet"),
        ("test filter:links", "test has:links"),
        # Combined
        ("AI -filter:replies -filter:links lang:en", "AI -is:reply -has:links lang:en"),
        # Already API-style (should pass through unchanged)
        ("AI -is:reply -has:links", "AI -is:reply -has:links"),
    ]

    for web_query, expected_api_query in test_cases:
        result = _convert_web_query_to_api(web_query)
        assert result == expected_api_query, f"Conversion failed: {web_query} -> {result}, expected {expected_api_query}"
        print(f"  [OK] '{web_query}' -> '{result}'")

    print(f"\n[PASS] All {len(test_cases)} operator conversions correct")


@pytest.mark.asyncio
async def test_scrape_stats_are_logged_to_file(username):
    """Test that scrape stats are written to the log file correctly.

    This test:
    1. Runs a scrape for a single query
    2. Reads the last line of the log file
    3. Verifies all scrape stats info is present
    """
    import json
    from backend.browser_automation.twitter.api import fetch_search, ScrapeStats
    from backend.twitter.logging import get_user_log_path
    from backend.twitter.authentication import ensure_access_token

    # Ensure we have auth
    access_token = await ensure_access_token(username)
    assert access_token, "No access token available"

    # Run a scrape - this should log stats to file
    test_query = "from:paulg"
    tweets, stats = await fetch_search(
        query=test_query,
        username=username
    )

    # Verify we got stats back
    assert isinstance(stats, ScrapeStats), "Should return ScrapeStats"
    assert stats.source_type == "account", f"Expected source_type='account', got '{stats.source_type}'"
    assert stats.source_value == "paulg", f"Expected source_value='paulg', got '{stats.source_value}'"

    # Read the log file and get the last scrape_stats entry
    log_path = get_user_log_path(username)
    assert log_path.exists(), f"Log file should exist at {log_path}"

    # Find the last scrape_stats entry in the log file
    last_scrape_stats = None
    with open(log_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entry = json.loads(line)
                    if entry.get("action") == "scrape_stats":
                        last_scrape_stats = entry
                except json.JSONDecodeError:
                    continue

    assert last_scrape_stats is not None, "Should have a scrape_stats entry in log file"

    # Verify all required fields are present
    assert "timestamp" in last_scrape_stats, "Log should have timestamp"
    assert "action" in last_scrape_stats, "Log should have action"
    assert last_scrape_stats["action"] == "scrape_stats", "Action should be 'scrape_stats'"
    assert "source_type" in last_scrape_stats, "Log should have source_type"
    assert "source_value" in last_scrape_stats, "Log should have source_value"
    assert "fetched" in last_scrape_stats, "Log should have fetched count"
    assert "passed" in last_scrape_stats, "Log should have passed count"
    assert "filtered" in last_scrape_stats, "Log should have filtered dict"
    assert "total_filtered" in last_scrape_stats, "Log should have total_filtered"

    # Verify the filtered breakdown
    filtered = last_scrape_stats["filtered"]
    assert "old" in filtered, "filtered should have 'old'"
    assert "impressions" in filtered, "filtered should have 'impressions'"
    assert "no_thread" in filtered, "filtered should have 'no_thread'"
    assert "intent" in filtered, "filtered should have 'intent'"
    assert "seen" in filtered, "filtered should have 'seen'"
    assert "replies" in filtered, "filtered should have 'replies'"
    assert "retweets" in filtered, "filtered should have 'retweets'"

    # Verify the counts match what stats returned
    assert last_scrape_stats["source_type"] == stats.source_type
    assert last_scrape_stats["source_value"] == stats.source_value
    assert last_scrape_stats["fetched"] == stats.fetched
    assert last_scrape_stats["passed"] == stats.passed

    print(f"\n[PASS] Scrape stats logged correctly:")
    print(f"  source_type: {last_scrape_stats['source_type']}")
    print(f"  source_value: {last_scrape_stats['source_value']}")
    print(f"  fetched: {last_scrape_stats['fetched']}")
    print(f"  passed: {last_scrape_stats['passed']}")
    print(f"  total_filtered: {last_scrape_stats['total_filtered']}")
