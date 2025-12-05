"""
Tests for full_threads.py - thread and reply scraping.
"""

import pytest


@pytest.mark.asyncio
@pytest.mark.slow
async def test_get_thread_scrapes_thread_and_replies(browser_context):
    """
    Test that get_thread correctly scrapes thread texts and other_replies.

    Tests URL: https://x.com/divya_venn/status/1991059548111843523
    """
    from backend.scraping.twitter.api import get_thread

    test_url = "https://x.com/divya_venn/status/1991059548111843523"
    test_root_id = "1991059548111843523"

    result = await get_thread(browser_context, test_url, root_id=test_root_id)

    # Check thread has content
    assert len(result.get("thread", [])) > 0, "Thread should have at least one tweet"

    # Check other_replies structure
    for reply in result.get("other_replies", []):
        assert "text" in reply, "Reply should have 'text' field"
        assert "author_handle" in reply, "Reply should have 'author_handle' field"
        assert "author_name" in reply, "Reply should have 'author_name' field"
        assert "likes" in reply, "Reply should have 'likes' field"

        # Verify author info is populated (not empty)
        assert reply["author_handle"] != "", f"author_handle should not be empty for reply: {reply['text'][:50]}..."
        assert reply["author_name"] != "", f"author_name should not be empty for reply: {reply['text'][:50]}..."


@pytest.mark.asyncio
@pytest.mark.slow
async def test_get_thread_returns_correct_structure(browser_context):
    """
    Test that get_thread returns the expected dict structure.
    """
    from backend.scraping.twitter.api import get_thread

    test_url = "https://x.com/divya_venn/status/1991059548111843523"

    result = await get_thread(browser_context, test_url)

    # Check structure
    assert isinstance(result, dict)
    assert "thread" in result
    assert "other_replies" in result
    assert isinstance(result["thread"], list)
    assert isinstance(result["other_replies"], list)
    # Check new fields are present
    assert "author_handle" in result
    assert "author_profile_pic_url" in result
    assert "media" in result
    assert isinstance(result["media"], list)


@pytest.mark.asyncio
@pytest.mark.slow
async def test_get_thread_extracts_media(browser_context):
    """
    Test that get_thread correctly extracts media (images) from a tweet.

    Tests URL: https://x.com/divya_venn/status/1996077319887487008
    This tweet has an image attached.
    """
    from backend.scraping.twitter.api import get_thread

    test_url = "https://x.com/divya_venn/status/1996077319887487008"
    test_root_id = "1996077319887487008"

    result = await get_thread(browser_context, test_url, root_id=test_root_id)

    # Check media is present
    assert "media" in result, "Result should have 'media' field"
    assert isinstance(result["media"], list), "Media should be a list"
    assert len(result["media"]) > 0, "Tweet should have at least one media item"

    # Check media structure
    for media_item in result["media"]:
        assert "type" in media_item, "Media item should have 'type' field"
        assert "url" in media_item, "Media item should have 'url' field"
        assert media_item["type"] == "photo", f"Expected photo, got {media_item['type']}"
        assert media_item["url"].startswith("https://"), "Media URL should be HTTPS"

    # Check author info is also returned
    assert "author_handle" in result, "Result should have 'author_handle' field"
    assert result["author_handle"] == "divya_venn", f"Expected divya_venn, got {result['author_handle']}"
    assert "author_profile_pic_url" in result, "Result should have 'author_profile_pic_url' field"


@pytest.mark.asyncio
@pytest.mark.slow
async def test_deep_scrape_thread_extracts_metrics(browser_context):
    """
    Test that deep_scrape_thread correctly extracts metrics and replies.

    Tests URL: https://x.com/divya_venn/status/1996077319887487008
    """
    from backend.scraping.twitter.api import deep_scrape_thread

    test_url = "https://x.com/divya_venn/status/1996077319887487008"
    test_id = "1996077319887487008"

    result = await deep_scrape_thread(browser_context, test_url, test_id, "divya_venn")

    # Check metrics are present
    assert "like_count" in result, "Result should have 'like_count'"
    assert "reply_count" in result, "Result should have 'reply_count'"
    assert "quote_count" in result, "Result should have 'quote_count'"
    assert "retweet_count" in result, "Result should have 'retweet_count'"

    # Metrics should be non-negative integers
    assert isinstance(result["like_count"], int) and result["like_count"] >= 0
    assert isinstance(result["reply_count"], int) and result["reply_count"] >= 0

    # Check replies structure
    assert "replies" in result, "Result should have 'replies'"
    assert isinstance(result["replies"], list)
    assert "all_reply_ids" in result, "Result should have 'all_reply_ids'"
