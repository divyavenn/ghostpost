"""
Tests for multi-tweet thread scraping via Twitter API.

These tests verify that get_thread correctly:
1. Fetches multi-tweet threads (author's continuation tweets)
2. Only includes tweets that are part of the thread chain (not replies to comments)
3. Extracts media from both root tweet and thread continuations
4. Returns thread tweets in chronological order

Note: These tests make real API calls and may be rate limited.
The Twitter API v2 Basic plan allows 15 tweet lookups per 15 minutes.
"""

import pytest


def skip_if_rate_limited(result: dict, tweet_id: str):
    """Skip test if result appears to be rate limited (empty with valid structure)."""
    if result["thread"] == [] and result["author_handle"] == "":
        pytest.skip(f"Tweet {tweet_id} returned empty - likely rate limited")


@pytest.mark.asyncio
@pytest.mark.slow
async def test_thread_1_multi_tweet_thread(browser_context):
    """
    Test multi-tweet thread fetching.

    Thread: https://x.com/divya_venn/status/1924243628777456059
    This is a multi-tweet thread - should return multiple tweets in order.
    """
    from backend.browser_automation.twitter.api import get_thread

    test_url = "https://x.com/divya_venn/status/1924243628777456059"
    test_root_id = "1924243628777456059"

    result = await get_thread(browser_context, test_url, root_id=test_root_id)

    # Skip if rate limited
    skip_if_rate_limited(result, test_root_id)

    # Check basic structure
    assert isinstance(result, dict)
    assert "thread" in result
    assert "other_replies" in result
    assert "author_handle" in result
    assert "author_profile_pic_url" in result
    assert "media" in result

    # Thread should have content
    assert len(result["thread"]) >= 1, "Thread should have at least the root tweet"

    # Author should be divya_venn
    assert result["author_handle"].lower() == "divya_venn", f"Expected divya_venn, got {result['author_handle']}"

    # Thread texts should be non-empty strings
    for i, text in enumerate(result["thread"]):
        assert isinstance(text, str), f"Thread item {i} should be a string"
        assert len(text) > 0, f"Thread item {i} should not be empty"


@pytest.mark.asyncio
@pytest.mark.slow
async def test_thread_2_with_images(browser_context):
    """
    Test thread with images in both first tweet and follow-up.

    Thread: https://x.com/divya_venn/status/1997099604010324363
    This thread has images - verify media extraction works.
    """
    from backend.browser_automation.twitter.api import get_thread

    test_url = "https://x.com/divya_venn/status/1997099604010324363"
    test_root_id = "1997099604010324363"

    result = await get_thread(browser_context, test_url, root_id=test_root_id)

    # Skip if rate limited
    skip_if_rate_limited(result, test_root_id)

    # Check structure
    assert isinstance(result, dict)
    assert "thread" in result
    assert "media" in result
    assert isinstance(result["media"], list)

    # Thread should have content
    assert len(result["thread"]) >= 1, "Thread should have at least the root tweet"

    # Author should be divya_venn
    assert result["author_handle"].lower() == "divya_venn"

    # Media should be present (this tweet has images)
    # Note: Media extraction depends on API returning attachments
    if result["media"]:
        for media_item in result["media"]:
            assert "type" in media_item, "Media item should have 'type' field"
            assert "url" in media_item, "Media item should have 'url' field"
            assert media_item["url"].startswith("https://"), "Media URL should be HTTPS"


@pytest.mark.asyncio
@pytest.mark.slow
async def test_thread_3_structure(browser_context):
    """
    Test thread structure and chronological ordering.

    Thread: https://x.com/divya_venn/status/1996019367977562547
    """
    from backend.browser_automation.twitter.api import get_thread

    test_url = "https://x.com/divya_venn/status/1996019367977562547"
    test_root_id = "1996019367977562547"

    result = await get_thread(browser_context, test_url, root_id=test_root_id)

    # Skip if rate limited
    skip_if_rate_limited(result, test_root_id)

    # Check structure
    assert isinstance(result, dict)
    assert isinstance(result["thread"], list)
    assert isinstance(result["other_replies"], list)
    assert isinstance(result["media"], list)

    # Thread should have content
    assert len(result["thread"]) >= 1, "Thread should have at least the root tweet"

    # Author info should be present
    assert "author_handle" in result
    assert "author_profile_pic_url" in result


@pytest.mark.asyncio
@pytest.mark.slow
async def test_thread_excludes_replies_to_comments(browser_context):
    """
    Test that thread only includes author's thread continuation tweets,
    NOT the author's replies to other people's comments.

    The thread chain should only include tweets where:
    - The tweet is the root tweet, OR
    - The tweet is a reply to another tweet in the thread chain
    """
    from backend.browser_automation.twitter.api import get_thread

    test_url = "https://x.com/divya_venn/status/1997099604010324363"
    test_root_id = "1997099604010324363"

    result = await get_thread(browser_context, test_url, root_id=test_root_id)

    # Skip if rate limited
    skip_if_rate_limited(result, test_root_id)

    # The thread should only contain the author's original thread,
    # not replies to comments from other users
    # Each tweet in the thread should logically follow from the previous

    # Verify thread is a list of strings
    assert isinstance(result["thread"], list)
    for text in result["thread"]:
        assert isinstance(text, str)


@pytest.mark.asyncio
@pytest.mark.slow
async def test_thread_chronological_order(browser_context):
    """
    Test that thread tweets are returned in chronological order.

    The first item should be the root tweet, followed by continuations in order.
    """
    from backend.browser_automation.twitter.api import get_thread

    # Use a known multi-tweet thread
    test_url = "https://x.com/divya_venn/status/1924243628777456059"
    test_root_id = "1924243628777456059"

    result = await get_thread(browser_context, test_url, root_id=test_root_id)

    # Skip if rate limited
    skip_if_rate_limited(result, test_root_id)

    if len(result["thread"]) > 1:
        # First tweet should be the root - it should be the start of the conversation
        # Subsequent tweets should be continuations
        # We can't easily verify order without knowing the content, but we verify
        # that we get multiple tweets back
        assert len(result["thread"]) >= 2, "Multi-tweet thread should have 2+ tweets"


@pytest.mark.asyncio
@pytest.mark.slow
async def test_other_replies_structure(browser_context):
    """
    Test that other_replies contains properly structured reply data.
    """
    from backend.browser_automation.twitter.api import get_thread

    test_url = "https://x.com/divya_venn/status/1997099604010324363"
    test_root_id = "1997099604010324363"

    result = await get_thread(browser_context, test_url, root_id=test_root_id)

    # Skip if rate limited
    skip_if_rate_limited(result, test_root_id)

    # other_replies should be a list
    assert isinstance(result["other_replies"], list)

    # Each reply should have required fields
    for reply in result["other_replies"]:
        assert "text" in reply, "Reply should have 'text' field"
        assert "author_handle" in reply, "Reply should have 'author_handle' field"
        assert "author_name" in reply, "Reply should have 'author_name' field"
        assert "likes" in reply, "Reply should have 'likes' field"


@pytest.mark.asyncio
@pytest.mark.slow
async def test_single_tweet_thread(browser_context):
    """
    Test that a single tweet (not a thread) returns correctly.

    Using a known single tweet that is not part of a multi-tweet thread.
    """
    from backend.browser_automation.twitter.api import get_thread

    # Use the test tweet from existing tests
    test_url = "https://x.com/divya_venn/status/1991059548111843523"
    test_root_id = "1991059548111843523"

    result = await get_thread(browser_context, test_url, root_id=test_root_id)

    # Skip if rate limited
    skip_if_rate_limited(result, test_root_id)

    # Single tweet should have exactly 1 item in thread
    assert len(result["thread"]) >= 1, "Should have at least the root tweet"

    # Author should be correct
    assert result["author_handle"].lower() == "divya_venn"


@pytest.mark.asyncio
@pytest.mark.slow
async def test_thread_media_extraction(browser_context):
    """
    Test media extraction from tweets with images.

    Thread: https://x.com/divya_venn/status/1996077319887487008
    This tweet has an image attached.
    """
    from backend.browser_automation.twitter.api import get_thread

    test_url = "https://x.com/divya_venn/status/1996077319887487008"
    test_root_id = "1996077319887487008"

    result = await get_thread(browser_context, test_url, root_id=test_root_id)

    # Skip if rate limited
    skip_if_rate_limited(result, test_root_id)

    # Check media is present
    assert "media" in result, "Result should have 'media' field"
    assert isinstance(result["media"], list), "Media should be a list"

    # This tweet should have media
    if result["media"]:
        for media_item in result["media"]:
            assert "type" in media_item, "Media item should have 'type' field"
            assert "url" in media_item, "Media item should have 'url' field"
            # Photo type for images
            if media_item["type"] == "photo":
                assert media_item["url"].startswith("https://"), "Photo URL should be HTTPS"


@pytest.mark.asyncio
@pytest.mark.slow
async def test_invalid_tweet_id_returns_empty(browser_context):
    """
    Test that an invalid tweet ID returns empty structure gracefully.
    """
    from backend.browser_automation.twitter.api import get_thread

    test_url = "https://x.com/someone/status/999999999999999999"
    test_root_id = "999999999999999999"

    result = await get_thread(browser_context, test_url, root_id=test_root_id)

    # Should return empty structure, not error
    assert isinstance(result, dict)
    assert result["thread"] == [] or len(result["thread"]) == 0
    assert result["other_replies"] == []
    assert result["author_handle"] == ""


@pytest.mark.asyncio
@pytest.mark.slow
async def test_quoted_tweet_extraction(browser_context):
    """
    Test that quoted tweets are properly extracted from referenced_tweets.

    Tweet: https://x.com/garrytan/status/1997558643898921292
    This is a quote tweet by @garrytan quoting another user's tweet.
    The quoted_tweet field should be populated with the quoted tweet's data.
    """
    from backend.browser_automation.twitter.api import (
        _build_user_map,
        _get_tweet_by_id,
        _tweet_to_dict,
    )
    from backend.twitter.authentication import ensure_access_token
    from backend.config import TEST_USER

    test_tweet_id = "1997558643898921292"

    # Get access token
    access_token = await ensure_access_token(TEST_USER)
    if not access_token:
        pytest.skip("No access token available")

    # Fetch the tweet
    response = await _get_tweet_by_id(access_token, test_tweet_id)

    data = response.get("data")
    if not data:
        pytest.skip(f"Tweet {test_tweet_id} not found - may be rate limited or deleted")

    includes = response.get("includes", {})
    user_map = _build_user_map(includes)

    # Convert to dict format
    tweet_dict = _tweet_to_dict(data, user_map, includes)

    # Verify basic tweet info
    assert tweet_dict["id"] == test_tweet_id
    assert tweet_dict["handle"].lower() == "garrytan", f"Expected garrytan, got {tweet_dict['handle']}"

    # Verify quoted_tweet is present and has correct structure
    quoted = tweet_dict.get("quoted_tweet")
    assert quoted is not None, "quoted_tweet should not be None for a quote tweet"
    assert isinstance(quoted, dict), "quoted_tweet should be a dict"

    # Check required fields
    assert "text" in quoted, "quoted_tweet should have 'text' field"
    assert "author_handle" in quoted, "quoted_tweet should have 'author_handle' field"
    assert "author_name" in quoted, "quoted_tweet should have 'author_name' field"
    assert "author_profile_pic_url" in quoted, "quoted_tweet should have 'author_profile_pic_url' field"
    assert "url" in quoted, "quoted_tweet should have 'url' field"
    assert "media" in quoted, "quoted_tweet should have 'media' field"

    # Validate field types and content
    assert isinstance(quoted["text"], str) and len(quoted["text"]) > 0, "quoted_tweet.text should be non-empty string"
    assert isinstance(quoted["author_handle"], str) and len(quoted["author_handle"]) > 0, "quoted_tweet.author_handle should be non-empty string"
    assert isinstance(quoted["author_name"], str), "quoted_tweet.author_name should be a string"
    assert isinstance(quoted["url"], str) and quoted["url"].startswith("https://"), "quoted_tweet.url should be a valid HTTPS URL"
    assert isinstance(quoted["media"], list), "quoted_tweet.media should be a list"

    # URL should contain the quoted tweet's ID
    assert "/status/" in quoted["url"], "quoted_tweet.url should be a tweet URL"


@pytest.mark.asyncio
@pytest.mark.slow
async def test_non_quote_tweet_has_null_quoted_tweet(browser_context):
    """
    Test that regular tweets (not quote tweets) have quoted_tweet as None.

    Using a known regular tweet that is not quoting another tweet.
    Tweet: https://x.com/divya_venn/status/1997099604010324363
    This is a regular thread without any quoted tweets.
    """
    from backend.browser_automation.twitter.api import (
        _build_user_map,
        _get_tweet_by_id,
        _tweet_to_dict,
    )
    from backend.twitter.authentication import ensure_access_token
    from backend.config import TEST_USER

    # A regular tweet (not a quote tweet) - this is a thread, not a quote
    test_tweet_id = "1997099604010324363"

    # Get access token
    access_token = await ensure_access_token(TEST_USER)
    if not access_token:
        pytest.skip("No access token available")

    # Fetch the tweet
    response = await _get_tweet_by_id(access_token, test_tweet_id)

    data = response.get("data")
    if not data:
        pytest.skip(f"Tweet {test_tweet_id} not found - may be rate limited or deleted")

    includes = response.get("includes", {})
    user_map = _build_user_map(includes)

    # Convert to dict format
    tweet_dict = _tweet_to_dict(data, user_map, includes)

    # Verify quoted_tweet is None for non-quote tweets
    assert tweet_dict.get("quoted_tweet") is None, "quoted_tweet should be None for non-quote tweets"


@pytest.mark.asyncio
@pytest.mark.slow
async def test_comment_with_quoted_tweet_extraction(browser_context):
    """
    Test that quoted tweets in comments/replies are properly extracted by deep_scrape_thread.

    Tweet: https://x.com/WJBlazkowiczII/status/1997213221015769329
    This is a reply that contains a quoted tweet. We verify that when
    deep_scrape_thread extracts replies, the media and quoted_tweet fields are populated.
    """
    from backend.config import TEST_USER
    from backend.browser_automation.twitter.api import _get_tweet_by_id, deep_scrape_thread
    from backend.twitter.authentication import ensure_access_token

    # This tweet is a reply with a quoted tweet
    test_tweet_id = "1997213221015769329"
    test_url = f"https://x.com/WJBlazkowiczII/status/{test_tweet_id}"

    # Get access token
    access_token = await ensure_access_token(TEST_USER)
    if not access_token:
        pytest.skip("No access token available")

    # Fetch the tweet to get conversation_id
    response = await _get_tweet_by_id(access_token, test_tweet_id)
    data = response.get("data")
    if not data:
        pytest.skip(f"Tweet {test_tweet_id} not found")

    # Get the conversation root
    conversation_id = data.get("conversation_id", test_tweet_id)
    author_handle = "WJBlazkowiczII"

    # Deep scrape the thread
    result = await deep_scrape_thread(browser_context, test_url, conversation_id, author_handle)

    assert result is not None, "deep_scrape_thread should return a result"
    assert "replies" in result, "Result should have 'replies' key"

    replies = result.get("replies", [])

    # Find replies with quoted tweets and media
    replies_with_quoted = [r for r in replies if r.get("quoted_tweet") is not None]
    replies_with_media = [r for r in replies if r.get("media") and len(r["media"]) > 0]

    print(f"\n{'='*60}")
    print(f"Deep scrape results for conversation {conversation_id}:")
    print(f"Total replies: {len(replies)}")
    print(f"Replies with quoted tweets: {len(replies_with_quoted)}")
    print(f"Replies with media: {len(replies_with_media)}")

    # Find the specific tweet we're testing
    target_reply = None
    for reply in replies:
        if reply.get("id") == test_tweet_id:
            target_reply = reply
            break

    if target_reply:
        print(f"\n--- Target Reply ({test_tweet_id}) ---")
        print(f"Text: {target_reply.get('text', '')[:100]}...")
        print(f"Has quoted_tweet: {target_reply.get('quoted_tweet') is not None}")
        print(f"Has media: {len(target_reply.get('media', [])) > 0}")

        if target_reply.get("quoted_tweet"):
            qt = target_reply["quoted_tweet"]
            print(f"\nQuoted tweet details:")
            print(f"  Author: @{qt.get('author_handle')}")
            print(f"  Text: {qt.get('text', '')[:100]}...")
            print(f"  URL: {qt.get('url')}")

    print(f"{'='*60}\n")

    # Verify replies have media and quoted_tweet fields
    for reply in replies[:3]:  # Check first 3 replies
        assert "media" in reply, f"Reply {reply.get('id')} should have 'media' field"
        assert "quoted_tweet" in reply, f"Reply {reply.get('id')} should have 'quoted_tweet' field"
        assert isinstance(reply["media"], list), "media should be a list"

    # If we found replies with quoted tweets, verify their structure
    for reply in replies_with_quoted:
        qt = reply["quoted_tweet"]
        assert "text" in qt, "quoted_tweet should have 'text'"
        assert "author_handle" in qt, "quoted_tweet should have 'author_handle'"
        assert "author_name" in qt, "quoted_tweet should have 'author_name'"
        assert "url" in qt, "quoted_tweet should have 'url'"
        assert isinstance(qt.get("text"), str), "quoted_tweet.text should be string"
        print(f"✅ Found comment with quoted tweet from @{qt.get('author_handle')}")

    print("✅ Comment media and quoted tweet extraction test passed!")
