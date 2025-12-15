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
    tweets = await fetch_search(
        ctx=None,
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
    tweets = await fetch_search(
        ctx=None,
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
    tweets = await fetch_search(
        ctx=None,
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

    # Fetch home timeline with intent filter (but generate_replies_inline=False to be quick)
    tweets = await fetch_home_timeline_with_intent_filter(
        username=username,
        max_tweets=20,
        generate_replies_inline=False
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
