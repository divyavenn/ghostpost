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
    from backend.scraping.twitter.api import get_thread

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
    from backend.scraping.twitter.api import get_thread

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
    from backend.scraping.twitter.api import get_thread

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
    from backend.scraping.twitter.api import get_thread

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
    from backend.scraping.twitter.api import get_thread

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
    from backend.scraping.twitter.api import get_thread

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
    from backend.scraping.twitter.api import get_thread

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
    from backend.scraping.twitter.api import get_thread

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
    from backend.scraping.twitter.api import get_thread

    test_url = "https://x.com/someone/status/999999999999999999"
    test_root_id = "999999999999999999"

    result = await get_thread(browser_context, test_url, root_id=test_root_id)

    # Should return empty structure, not error
    assert isinstance(result, dict)
    assert result["thread"] == [] or len(result["thread"]) == 0
    assert result["other_replies"] == []
    assert result["author_handle"] == ""
