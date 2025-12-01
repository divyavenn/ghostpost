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
    from backend.scraping.twitter.full_threads import get_thread

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
    from backend.scraping.twitter.full_threads import get_thread

    test_url = "https://x.com/divya_venn/status/1991059548111843523"

    result = await get_thread(browser_context, test_url)

    # Check structure
    assert isinstance(result, dict)
    assert "thread" in result
    assert "other_replies" in result
    assert isinstance(result["thread"], list)
    assert isinstance(result["other_replies"], list)
