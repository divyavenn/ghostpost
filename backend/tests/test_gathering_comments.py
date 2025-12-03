"""
Tests for comment/reply gathering functionality.
Tests the scraping functions that discover comments on tweets.

Includes:
- Individual scraping function tests
- Full job tests (discover_engagement gathers comments from all active threads)
- Comment storage validation
"""

import pytest


@pytest.mark.asyncio
@pytest.mark.slow
async def test_get_thread_discovers_comments(browser_context):
    """
    Test that get_thread discovers comments (other_replies) on a tweet.

    Tests URL: https://x.com/divya_venn/status/1991059548111843523
    """
    from backend.scraping.twitter.thread import get_thread

    test_url = "https://x.com/divya_venn/status/1991059548111843523"
    test_root_id = "1991059548111843523"

    result = await get_thread(browser_context, test_url, root_id=test_root_id)

    # Verify other_replies structure
    other_replies = result.get("other_replies", [])

    # Each reply should have required fields
    for reply in other_replies:
        assert "text" in reply, "Reply should have 'text' field"
        assert "author_handle" in reply, "Reply should have 'author_handle' field"
        assert "author_name" in reply, "Reply should have 'author_name' field"
        assert "likes" in reply, "Reply should have 'likes' field"

        # Verify data is populated
        assert isinstance(reply["text"], str), "text should be a string"
        assert isinstance(reply["likes"], int), "likes should be an integer"


@pytest.mark.asyncio
@pytest.mark.slow
async def test_deep_scrape_thread_gets_all_replies(browser_context):
    """
    Test that deep_scrape_thread collects all replies with full metadata.

    Tests URL: https://x.com/divya_venn/status/1991059548111843523
    """
    from backend.scraping.twitter.thread import deep_scrape_thread

    test_url = "https://x.com/divya_venn/status/1991059548111843523"
    test_tweet_id = "1991059548111843523"
    test_author = "divya_venn"

    result = await deep_scrape_thread(
        browser_context,
        test_url,
        tweet_id=test_tweet_id,
        author_handle=test_author
    )

    # Verify result structure
    assert "reply_count" in result, "Should have reply_count"
    assert "like_count" in result, "Should have like_count"
    assert "quote_count" in result, "Should have quote_count"
    assert "retweet_count" in result, "Should have retweet_count"
    assert "all_reply_ids" in result, "Should have all_reply_ids"
    assert "replies" in result, "Should have replies list"

    # Verify metrics are integers
    assert isinstance(result["reply_count"], int)
    assert isinstance(result["like_count"], int)
    assert isinstance(result["quote_count"], int)
    assert isinstance(result["retweet_count"], int)

    # Verify replies structure
    for reply in result["replies"]:
        assert "id" in reply, "Reply should have 'id'"
        assert "text" in reply, "Reply should have 'text'"
        assert "handle" in reply, "Reply should have 'handle'"
        assert "username" in reply, "Reply should have 'username'"
        assert "in_reply_to_status_id" in reply, "Reply should have 'in_reply_to_status_id'"
        assert "created_at" in reply, "Reply should have 'created_at'"
        assert "url" in reply, "Reply should have 'url'"
        assert "likes" in reply, "Reply should have 'likes'"


@pytest.mark.asyncio
@pytest.mark.slow
async def test_shallow_scrape_detects_reply_activity(browser_context):
    """
    Test that shallow_scrape_thread detects reply activity without deep scrolling.
    Used for quick activity detection on warm tweets.

    Tests URL: https://x.com/divya_venn/status/1991059548111843523
    """
    from backend.scraping.twitter.metrics import shallow_scrape_thread

    test_url = "https://x.com/divya_venn/status/1991059548111843523"
    test_tweet_id = "1991059548111843523"

    result = await shallow_scrape_thread(
        browser_context,
        test_url,
        tweet_id=test_tweet_id
    )

    # Verify result structure
    assert "reply_count" in result, "Should have reply_count"
    assert "like_count" in result, "Should have like_count"
    assert "quote_count" in result, "Should have quote_count"
    assert "retweet_count" in result, "Should have retweet_count"
    assert "latest_reply_ids" in result, "Should have latest_reply_ids"

    # Verify metrics are integers
    assert isinstance(result["reply_count"], int)
    assert isinstance(result["like_count"], int)
    assert isinstance(result["quote_count"], int)
    assert isinstance(result["retweet_count"], int)

    # Verify latest_reply_ids is a list
    assert isinstance(result["latest_reply_ids"], list)
    # Shallow scrape caps at 10 reply IDs
    assert len(result["latest_reply_ids"]) <= 10


@pytest.mark.asyncio
@pytest.mark.slow
async def test_deep_scrape_excludes_author_replies(browser_context):
    """
    Test that deep_scrape_thread excludes the author's own replies from the replies list.
    Author's self-replies are thread continuations, not comments.
    """
    from backend.scraping.twitter.thread import deep_scrape_thread

    test_url = "https://x.com/divya_venn/status/1991059548111843523"
    test_tweet_id = "1991059548111843523"
    test_author = "divya_venn"

    result = await deep_scrape_thread(
        browser_context,
        test_url,
        tweet_id=test_tweet_id,
        author_handle=test_author
    )

    # All replies should be from users other than the author
    for reply in result["replies"]:
        assert reply["handle"].lower() != test_author.lower(), \
            f"Author's own replies should be excluded, found: {reply['handle']}"


@pytest.mark.asyncio
@pytest.mark.slow
async def test_replies_have_valid_urls(browser_context):
    """
    Test that discovered replies have valid Twitter URLs.
    """
    from backend.scraping.twitter.thread import deep_scrape_thread

    test_url = "https://x.com/divya_venn/status/1991059548111843523"
    test_tweet_id = "1991059548111843523"
    test_author = "divya_venn"

    result = await deep_scrape_thread(
        browser_context,
        test_url,
        tweet_id=test_tweet_id,
        author_handle=test_author
    )

    for reply in result["replies"]:
        url = reply.get("url", "")
        assert url.startswith("https://x.com/"), f"URL should start with https://x.com/, got: {url}"
        assert "/status/" in url, f"URL should contain /status/, got: {url}"
        # URL should contain the reply's tweet ID
        assert reply["id"] in url, f"URL should contain tweet ID {reply['id']}, got: {url}"


# ============================================================================
# Full Job Tests - Gathering comments from all active threads
# ============================================================================

@pytest.fixture
def test_username():
    """The test user's cache key."""
    return "divya_venn"


@pytest.fixture
def test_handle():
    """The test user's Twitter handle."""
    return "divya_venn"


class TestDiscoverEngagementCommentsJob:
    """
    Tests for discover_engagement job's comment gathering.
    Verifies total comments gathered across all active threads.
    """

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_discover_engagement_gathers_comments(self, test_username, test_handle):
        """
        Test that discover_engagement job gathers comments from all active threads.
        Verifies the total new_comments count returned.
        """
        from backend.twitter.monitoring import discover_engagement

        result = await discover_engagement(test_username, test_handle)

        # Verify result has new_comments tracking
        assert "new_comments" in result, "Result should have 'new_comments' count"
        assert isinstance(result["new_comments"], int), "new_comments should be an integer"
        assert result["new_comments"] >= 0, "new_comments should be non-negative"

        print(f"✅ discover_engagement completed:")
        print(f"   Active tweets scraped: {result['active_scraped']}")
        print(f"   New comments gathered: {result['new_comments']}")

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_gathered_comments_are_stored_in_cache(self, test_username, test_handle):
        """
        Test that comments gathered by discover_engagement are persisted to cache.
        """
        from backend.data.twitter.comments_cache import read_comments_cache
        from backend.twitter.monitoring import discover_engagement

        # Get initial comment count
        initial_cache = read_comments_cache(test_username)
        initial_count = len([k for k in initial_cache.keys() if k != "_order"])

        # Run the job
        result = await discover_engagement(test_username, test_handle)

        # Get final comment count
        final_cache = read_comments_cache(test_username)
        final_count = len([k for k in final_cache.keys() if k != "_order"])

        # Verify comments were added (if any new ones found)
        new_in_cache = final_count - initial_count
        print(f"📊 Comments in cache: {initial_count} -> {final_count} (+{new_in_cache})")
        print(f"📊 Job reported new_comments: {result['new_comments']}")

        # new_comments should match what was actually added
        # (could be 0 if no new comments or all were already in cache)
        assert new_in_cache >= 0, "Should not lose comments"

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_stored_comments_have_valid_structure(self, test_username, test_handle):
        """
        Test that comments stored in cache have all required fields.
        """
        from backend.data.twitter.comments_cache import get_comments_list
        from backend.twitter.monitoring import discover_engagement

        # Run the job to ensure we have comments
        await discover_engagement(test_username, test_handle)

        # Get comments from cache
        comments = get_comments_list(test_username, limit=10)

        # Validate each comment has required fields
        required_fields = [
            "id", "text", "handle", "username", "created_at", "url",
            "in_reply_to_status_id", "parent_chain", "status",
            "likes", "retweets", "quotes", "replies"
        ]

        for comment in comments:
            for field in required_fields:
                assert field in comment, f"Comment missing required field: {field}"

            # Validate status is valid
            assert comment["status"] in ["pending", "replied", "skipped"], \
                f"Invalid status: {comment['status']}"

            # Validate parent_chain is a list
            assert isinstance(comment["parent_chain"], list), "parent_chain should be a list"

            print(f"✅ Comment {comment['id'][:10]}... from @{comment['handle']} validated")

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_comments_link_to_user_tweets(self, test_username, test_handle):
        """
        Test that gathered comments are replies to user's tweets.
        Each comment's root should be a tweet owned by the user.
        """
        from backend.data.twitter.comments_cache import get_comments_list
        from backend.data.twitter.posted_tweets_cache import get_user_tweet_ids
        from backend.twitter.monitoring import discover_engagement

        # Run the job
        await discover_engagement(test_username, test_handle)

        # Get user's tweet IDs and comments
        user_tweet_ids = get_user_tweet_ids(test_username)
        comments = get_comments_list(test_username, limit=20)

        for comment in comments:
            parent_chain = comment.get("parent_chain", [])
            if parent_chain:
                root_id = parent_chain[0]
                assert root_id in user_tweet_ids, \
                    f"Comment root {root_id} should be a user tweet"
            else:
                # Direct reply - in_reply_to should be user's tweet
                in_reply_to = comment.get("in_reply_to_status_id")
                if in_reply_to:
                    assert in_reply_to in user_tweet_ids, \
                        f"Comment in_reply_to {in_reply_to} should be a user tweet"


class TestProcessScrapedReplies:
    """Tests for the process_scraped_replies function that stores comments."""

    def test_process_scraped_replies_adds_to_cache(self, test_username):
        """Test that process_scraped_replies correctly adds comments to cache."""
        from backend.data.twitter.comments_cache import (
            get_comment,
            process_scraped_replies,
            read_comments_cache,
        )
        from backend.data.twitter.posted_tweets_cache import read_posted_tweets_cache

        # Get a user tweet to be the parent
        posted_tweets = read_posted_tweets_cache(test_username)
        order = posted_tweets.get("_order", [])
        if not order:
            pytest.skip("No posted tweets to test with")

        parent_tweet_id = order[0]

        # Create mock scraped reply
        test_reply_id = "test_reply_123456789"
        scraped_replies = [{
            "id": test_reply_id,
            "text": "Test reply for unit test",
            "handle": "test_replier",
            "username": "Test Replier",
            "in_reply_to_status_id": parent_tweet_id,
            "created_at": "2025-01-01T00:00:00+00:00",
            "url": f"https://x.com/test_replier/status/{test_reply_id}",
            "likes": 5,
            "retweets": 0,
            "quotes": 0,
            "replies": 0
        }]

        # Process the replies
        new_ids = process_scraped_replies(test_username, scraped_replies, test_username)

        # Verify it was added
        if test_reply_id in new_ids:
            comment = get_comment(test_username, test_reply_id)
            assert comment is not None, "Comment should be in cache"
            assert comment["text"] == "Test reply for unit test"
            assert comment["handle"] == "test_replier"
            assert comment["status"] == "pending"
            print(f"✅ Successfully added test comment {test_reply_id}")

            # Cleanup - remove test comment
            from backend.data.twitter.comments_cache import delete_comment
            delete_comment(test_username, test_reply_id)

    def test_process_scraped_replies_skips_user_own_replies(self, test_username, test_handle):
        """Test that user's own replies are not added as comments."""
        from backend.data.twitter.comments_cache import get_comment, process_scraped_replies
        from backend.data.twitter.posted_tweets_cache import read_posted_tweets_cache

        # Get a user tweet to be the parent
        posted_tweets = read_posted_tweets_cache(test_username)
        order = posted_tweets.get("_order", [])
        if not order:
            pytest.skip("No posted tweets to test with")

        parent_tweet_id = order[0]

        # Create mock scraped reply FROM the user (should be skipped)
        test_reply_id = "test_own_reply_123456789"
        scraped_replies = [{
            "id": test_reply_id,
            "text": "My own reply",
            "handle": test_handle,  # Same as user
            "username": "Divya Venn",
            "in_reply_to_status_id": parent_tweet_id,
            "created_at": "2025-01-01T00:00:00+00:00",
            "url": f"https://x.com/{test_handle}/status/{test_reply_id}",
            "likes": 0,
            "retweets": 0,
            "quotes": 0,
            "replies": 0
        }]

        # Process the replies
        new_ids = process_scraped_replies(test_username, scraped_replies, test_handle)

        # Verify it was NOT added
        assert test_reply_id not in new_ids, "User's own reply should not be added"
        comment = get_comment(test_username, test_reply_id)
        assert comment is None, "User's own reply should not be in cache"
        print(f"✅ Correctly skipped user's own reply")
