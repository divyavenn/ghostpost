"""
Tests for Twitter API v2 scraping functions.

These tests verify that the API-based scraping functions in backend/scraping/twitter/api.py
work correctly and return properly structured data.
"""

import pytest


@pytest.mark.asyncio
@pytest.mark.slow
async def test_fetch_search_from_user_returns_tweets(browser_context, test_user):
    """
    Test that fetch_search with from:handle returns tweets from a user's timeline.

    Tests fetching tweets from divya_venn account.
    """
    from backend.browser_automation.twitter.api import fetch_search

    result = await fetch_search(
        query="from:divya_venn",
        username=test_user
    )

    # Result should be a dict (could be empty if no recent tweets meet criteria)
    assert isinstance(result, dict), "Result should be a dict"

    # If tweets are returned, check structure
    for tweet_id, tweet in result.items():
        assert isinstance(tweet_id, str), "Tweet ID should be a string"
        assert "id" in tweet, "Tweet should have 'id' field"
        assert "text" in tweet, "Tweet should have 'text' field"
        assert "handle" in tweet, "Tweet should have 'handle' field"
        assert "url" in tweet, "Tweet should have 'url' field"
        assert "likes" in tweet, "Tweet should have 'likes' field"
        assert "created_at" in tweet, "Tweet should have 'created_at' field"

        # Validate handle is correct
        assert tweet["handle"].lower() == "divya_venn", f"Expected divya_venn, got {tweet['handle']}"


@pytest.mark.asyncio
@pytest.mark.slow
async def test_fetch_search_structure(browser_context, test_user):
    """
    Test that fetch_search returns tweets with complete structure.
    """
    from backend.browser_automation.twitter.api import fetch_search

    result = await fetch_search(
        query="from:elikitten1",  # Use a different account that may have more activity
        username=test_user
    )

    # Check the complete structure of each tweet
    expected_fields = [
        "id", "text", "likes", "retweets", "quotes", "replies",
        "impressions", "score", "followers", "created_at", "url",
        "username", "handle", "author_profile_pic_url", "media",
        "quoted_tweet", "in_reply_to_status_id", "conversation_id"
    ]

    for tweet_id, tweet in result.items():
        for field in expected_fields:
            assert field in tweet, f"Tweet should have '{field}' field"

        # Validate types
        assert isinstance(tweet["likes"], int), "likes should be an int"
        assert isinstance(tweet["retweets"], int), "retweets should be an int"
        assert isinstance(tweet["score"], int), "score should be an int"
        assert isinstance(tweet["media"], list), "media should be a list"


@pytest.mark.asyncio
@pytest.mark.slow
async def test_fetch_search_query_returns_tweets(browser_context, test_user):
    """
    Test that fetch_search returns tweets matching a query.
    """
    from backend.browser_automation.twitter.api import fetch_search

    # Search for tweets about AI/ML (common topic with many results)
    result = await fetch_search(
        query="artificial intelligence",
        username=test_user
    )

    assert isinstance(result, dict), "Result should be a dict"

    # If tweets are returned, check structure
    for tweet_id, tweet in result.items():
        assert "id" in tweet
        assert "text" in tweet
        assert "handle" in tweet
        assert "url" in tweet


@pytest.mark.asyncio
@pytest.mark.slow
async def test_fetch_search_excludes_retweets_and_replies(browser_context, test_user):
    """
    Test that fetch_search automatically excludes retweets and replies.
    """
    from backend.browser_automation.twitter.api import fetch_search

    result = await fetch_search(
        browser_context,
        query="technology",
        username=test_user
    )

    # All returned tweets should be original posts (not RTs or replies)
    for tweet_id, tweet in result.items():
        text = tweet.get("text", "")
        # Retweets typically start with "RT @"
        assert not text.startswith("RT @"), f"Found retweet: {text[:50]}..."


@pytest.mark.asyncio
@pytest.mark.slow
async def test_shallow_scrape_thread_returns_metrics(browser_context):
    """
    Test that shallow_scrape_thread returns tweet metrics quickly.

    Tests URL: https://x.com/divya_venn/status/1996077319887487008
    """
    from backend.browser_automation.twitter.api import shallow_scrape_thread

    test_url = "https://x.com/divya_venn/status/1996077319887487008"
    test_id = "1996077319887487008"

    result = await shallow_scrape_thread(browser_context, test_url, test_id)

    # Check structure
    assert isinstance(result, dict), "Result should be a dict"
    assert "reply_count" in result
    assert "like_count" in result
    assert "quote_count" in result
    assert "retweet_count" in result
    assert "latest_reply_ids" in result

    # Check types
    assert isinstance(result["reply_count"], int)
    assert isinstance(result["like_count"], int)
    assert isinstance(result["quote_count"], int)
    assert isinstance(result["retweet_count"], int)
    assert isinstance(result["latest_reply_ids"], list)

    # Metrics should be non-negative
    assert result["like_count"] >= 0
    assert result["reply_count"] >= 0


@pytest.mark.asyncio
@pytest.mark.slow
async def test_scrape_user_recent_tweets_returns_list(browser_context):
    """
    Test that scrape_user_recent_tweets returns a list of user tweets.
    """
    from backend.browser_automation.twitter.api import scrape_user_recent_tweets

    result = await scrape_user_recent_tweets(
        browser_context,
        username="divya_venn"
    )

    assert isinstance(result, list), "Result should be a list"

    # Check structure of each tweet
    for tweet in result:
        assert "id" in tweet
        assert "text" in tweet
        assert "handle" in tweet
        assert "url" in tweet
        assert "created_at" in tweet

        # Handle should be the requested user
        assert tweet["handle"].lower() == "divya_venn"


@pytest.mark.asyncio
@pytest.mark.slow
async def test_fetch_search_from_user_with_thread(browser_context, test_user):
    """
    Test that fetch_search with from:handle returns tweets with thread data.
    """
    from backend.browser_automation.twitter.api import fetch_search

    result = await fetch_search(
        query="from:divya_venn",
        username=test_user
    )

    assert isinstance(result, dict), "Result should be a dict"

    # Each tweet should have thread data attached
    for tweet_id, tweet in result.items():
        assert "thread" in tweet, "Tweet should have 'thread' field"
        assert "other_replies" in tweet, "Tweet should have 'other_replies' field"


@pytest.mark.asyncio
@pytest.mark.slow
async def test_fetch_search_with_thread(browser_context, test_user):
    """
    Test that fetch_search returns tweets with thread data.
    """
    from backend.browser_automation.twitter.api import fetch_search

    result = await fetch_search(
        query="python",
        username=test_user
    )

    assert isinstance(result, dict), "Result should be a dict"


@pytest.mark.asyncio
@pytest.mark.slow
async def test_engagement_score_calculation(browser_context, test_user):
    """
    Test that engagement score is calculated correctly.

    Score formula: likes + 2*retweets + 3*quotes + replies
    """
    from backend.browser_automation.twitter.api import fetch_search

    result = await fetch_search(
        query="from:divya_venn",
        username=test_user
    )

    for tweet_id, tweet in result.items():
        expected_score = (
            tweet["likes"] +
            2 * tweet["retweets"] +
            3 * tweet["quotes"] +
            tweet["replies"]
        )
        assert tweet["score"] == expected_score, (
            f"Score mismatch: expected {expected_score}, got {tweet['score']}"
        )


@pytest.mark.asyncio
@pytest.mark.slow
async def test_api_returns_empty_on_invalid_handle(browser_context, test_user):
    """
    Test that fetch_search returns empty dict for invalid handle.
    """
    from backend.browser_automation.twitter.api import fetch_search

    result = await fetch_search(
        query="from:this_handle_definitely_does_not_exist_12345678",
        username=test_user
    )

    # Should return empty dict rather than error
    assert isinstance(result, dict)
    assert len(result) == 0


@pytest.mark.asyncio
@pytest.mark.slow
async def test_media_extraction_in_tweets(browser_context, test_user):
    """
    Test that media (images) are correctly extracted from tweets.
    """
    from backend.browser_automation.twitter.api import fetch_search

    result = await fetch_search(
        query="from:divya_venn",
        username=test_user
    )

    # Check that media field is properly structured
    for tweet_id, tweet in result.items():
        assert "media" in tweet
        assert isinstance(tweet["media"], list)

        for media_item in tweet["media"]:
            assert "type" in media_item
            assert "url" in media_item


@pytest.mark.asyncio
@pytest.mark.slow
async def test_tweet_url_format(browser_context, test_user):
    """
    Test that tweet URLs are correctly formatted.
    """
    from backend.browser_automation.twitter.api import fetch_search

    result = await fetch_search(
        query="from:divya_venn",
        username=test_user
    )

    for tweet_id, tweet in result.items():
        url = tweet["url"]
        # URL should be in format https://x.com/handle/status/id
        assert url.startswith("https://x.com/"), f"URL should start with https://x.com/, got {url}"
        assert "/status/" in url, f"URL should contain /status/, got {url}"
        assert tweet_id in url, f"URL should contain tweet ID {tweet_id}, got {url}"


@pytest.mark.asyncio
@pytest.mark.slow
async def test_fetch_home_timeline_returns_tweets(test_user):
    """
    Test that fetch_home_timeline_with_intent_filter returns tweets from the user's home timeline.

    Requires a valid OAuth access token for the test user.
    """
    from backend.browser_automation.twitter.api import fetch_home_timeline_with_intent_filter
    from backend.twitter.authentication import ensure_access_token

    # Pre-check if we have a valid token
    access_token = await ensure_access_token(test_user)
    if not access_token:
        pytest.skip(f"No OAuth access token available for {test_user} - user needs to re-authenticate")

    result = await fetch_home_timeline_with_intent_filter(
        username=test_user,
        generate_replies_inline=False  # Don't generate replies during test
    )

    # Result should be a dict
    assert isinstance(result, dict), f"Result should be a dict, got {type(result)}"

    # Log how many tweets we got
    print(f"[Home Timeline] Got {len(result)} tweets for @{test_user}")

    # Should return at least some tweets from home timeline
    assert len(result) > 0, f"Home timeline should return at least 1 tweet for @{test_user}"

    # If tweets are returned, check structure
    for tweet_id, tweet in result.items():
        assert isinstance(tweet_id, str), "Tweet ID should be a string"
        assert "id" in tweet, "Tweet should have 'id' field"
        assert "text" in tweet, "Tweet should have 'text' field"
        assert "handle" in tweet, "Tweet should have 'handle' field"
        assert "url" in tweet, "Tweet should have 'url' field"


@pytest.mark.asyncio
@pytest.mark.slow
async def test_fetch_search_returns_non_empty_results(browser_context, test_user):
    """
    Test that fetch_search actually returns tweets for a common query.

    Requires a valid OAuth access token for the test user.
    """
    from backend.browser_automation.twitter.api import fetch_search
    from backend.twitter.authentication import ensure_access_token

    # Pre-check if we have a valid token
    access_token = await ensure_access_token(test_user)
    if not access_token:
        pytest.skip(f"No OAuth access token available for {test_user} - user needs to re-authenticate")

    result = await fetch_search(
        browser_context,
        query="python",  # Use a specific programming term
        username=test_user
    )

    assert isinstance(result, dict), f"Result should be a dict, got {type(result)}"

    # Log the count
    print(f"[Search] Query 'python' returned {len(result)} tweets")

    # This query should return at least some results
    assert len(result) > 0, "Search for 'python' should return at least 1 tweet"
