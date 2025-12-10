"""
Tests for Twitter API v2 scraping functions.

These tests verify that the API-based scraping functions in backend/scraping/twitter/api.py
work correctly and return properly structured data.
"""

import pytest


@pytest.mark.asyncio
@pytest.mark.slow
async def test_fetch_user_tweets_returns_tweets(browser_context, test_user):
    """
    Test that fetch_user_tweets returns tweets from a user's timeline.

    Tests fetching tweets from divya_venn account.
    """
    from backend.browser_automation.twitter.api import fetch_user_tweets

    result = await fetch_user_tweets(
        browser_context,
        handle="divya_venn",
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
async def test_fetch_user_tweets_structure(browser_context, test_user):
    """
    Test that fetch_user_tweets returns tweets with complete structure.
    """
    from backend.browser_automation.twitter.api import fetch_user_tweets

    result = await fetch_user_tweets(
        browser_context,
        handle="elikitten1",  # Use a different account that may have more activity
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
async def test_fetch_search_returns_tweets(browser_context, test_user):
    """
    Test that fetch_search returns tweets matching a query.
    """
    from backend.browser_automation.twitter.api import fetch_search

    # Search for tweets about AI/ML (common topic with many results)
    result = await fetch_search(
        browser_context,
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
        username="divya_venn",
        max_tweets=10
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
async def test_scrape_user_recent_tweets_respects_max_limit(browser_context):
    """
    Test that scrape_user_recent_tweets respects the max_tweets limit.
    """
    from backend.browser_automation.twitter.api import scrape_user_recent_tweets

    max_limit = 5
    result = await scrape_user_recent_tweets(
        browser_context,
        username="divya_venn",
        max_tweets=max_limit
    )

    # Result should not exceed max_tweets (could be less if user has fewer tweets)
    assert len(result) <= max_limit, f"Expected at most {max_limit} tweets, got {len(result)}"


@pytest.mark.asyncio
@pytest.mark.slow
async def test_collect_from_page_user_timeline(browser_context, test_user):
    """
    Test that collect_from_page works for user timeline URLs.
    """
    from backend.browser_automation.twitter.api import collect_from_page

    result = await collect_from_page(
        browser_context,
        url="https://x.com/divya_venn",
        handle="divya_venn",
        username=test_user
    )

    assert isinstance(result, dict), "Result should be a dict"

    # Each tweet should have thread data attached
    for tweet_id, tweet in result.items():
        assert "thread" in tweet, "Tweet should have 'thread' field"
        assert "other_replies" in tweet, "Tweet should have 'other_replies' field"


@pytest.mark.asyncio
@pytest.mark.slow
async def test_collect_from_page_search(browser_context, test_user):
    """
    Test that collect_from_page works for search URLs.
    """
    from backend.browser_automation.twitter.api import collect_from_page

    result = await collect_from_page(
        browser_context,
        url="https://x.com/search?q=python",
        handle=None,
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
    from backend.browser_automation.twitter.api import fetch_user_tweets

    result = await fetch_user_tweets(
        browser_context,
        handle="divya_venn",
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
    Test that fetch_user_tweets returns empty dict for invalid handle.
    """
    from backend.browser_automation.twitter.api import fetch_user_tweets

    result = await fetch_user_tweets(
        browser_context,
        handle="this_handle_definitely_does_not_exist_12345678",
        username=test_user
    )

    # Should return empty dict rather than error
    assert isinstance(result, dict)
    assert len(result) == 0


@pytest.mark.asyncio
@pytest.mark.slow
async def test_media_extraction_in_user_tweets(browser_context, test_user):
    """
    Test that media (images) are correctly extracted from user tweets.
    """
    from backend.browser_automation.twitter.api import fetch_user_tweets

    result = await fetch_user_tweets(
        browser_context,
        handle="divya_venn",
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
    from backend.browser_automation.twitter.api import fetch_user_tweets

    result = await fetch_user_tweets(
        browser_context,
        handle="divya_venn",
        username=test_user
    )

    for tweet_id, tweet in result.items():
        url = tweet["url"]
        # URL should be in format https://x.com/handle/status/id
        assert url.startswith("https://x.com/"), f"URL should start with https://x.com/, got {url}"
        assert "/status/" in url, f"URL should contain /status/, got {url}"
        assert tweet_id in url, f"URL should contain tweet ID {tweet_id}, got {url}"
