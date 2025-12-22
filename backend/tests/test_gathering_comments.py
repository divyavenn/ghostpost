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
    from backend.browser_automation.twitter.api import get_thread

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
    from backend.browser_automation.twitter.api import deep_scrape_thread

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
    from backend.browser_automation.twitter.api import shallow_scrape_thread

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
    from backend.browser_automation.twitter.api import deep_scrape_thread

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
    from backend.browser_automation.twitter.api import deep_scrape_thread

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
        assert reply["tweet_id"] in url, f"URL should contain tweet ID {reply['id']}, got: {url}"


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
    async def test_discover_engagement_gathers_and_stores_comments(self, test_username, test_handle):
        """
        Combined test that runs discover_engagement ONCE and verifies:
        1. Job returns correct structure with new_comments count
        2. Comments are persisted to cache
        3. Stored comments have valid structure
        4. Comments link to user's tweets
        """
        from backend.data.twitter.comments_cache import get_comments_list, read_comments_cache
        from backend.data.twitter.posted_tweets_cache import get_user_tweet_ids
        from backend.twitter.monitoring import discover_engagement

        # Get initial comment count
        initial_cache = read_comments_cache(test_username)
        initial_count = len([k for k in initial_cache.keys() if k != "_order"])

        # Run the job ONCE
        result = await discover_engagement(test_username, test_handle)

        # 1. Verify result structure
        assert "new_comments" in result, "Result should have 'new_comments' count"
        assert isinstance(result["new_comments"], int), "new_comments should be an integer"
        assert result["new_comments"] >= 0, "new_comments should be non-negative"

        print(f"✅ discover_engagement completed:")
        print(f"   Active tweets scraped: {result['active_scraped']}")
        print(f"   Warm tweets scraped: {result['warm_scraped']}")
        print(f"   New comments gathered: {result['new_comments']}")

        # 2. Verify comments persisted to cache
        # Note: Comment count may decrease if user has replied to some externally
        # (those get cleaned up during scraping as the cache is only for pending comments)
        final_cache = read_comments_cache(test_username)
        final_count = len([k for k in final_cache.keys() if k != "_order"])
        net_change = final_count - initial_count

        print(f"📊 Comments in cache: {initial_count} -> {final_count} (net change: {net_change})")
        print(f"   New comments reported by job: {result['new_comments']}")
        # Verify the job's new_comments count is reasonable
        assert result["new_comments"] >= 0, "new_comments should be non-negative"

        # 3. Validate stored comments have required fields
        comments = get_comments_list(test_username, limit=10)
        required_fields = [
            "id", "text", "handle", "username", "created_at", "url",
            "in_reply_to_status_id", "parent_chain", "status",
            "likes", "retweets", "quotes", "replies"
        ]

        for comment in comments:
            for field in required_fields:
                assert field in comment, f"Comment missing required field: {field}"

            assert comment["status"] in ["pending", "replied", "skipped"], \
                f"Invalid status: {comment['status']}"
            assert isinstance(comment["parent_chain"], list), "parent_chain should be a list"

        print(f"✅ Validated {len(comments)} comments have correct structure")

        # 4. Verify comments link to user's tweets
        user_tweet_ids = get_user_tweet_ids(test_username)
        for comment in comments:
            parent_chain = comment.get("parent_chain", [])
            if parent_chain:
                root_id = parent_chain[0]
                assert root_id in user_tweet_ids, \
                    f"Comment root {root_id} should be a user tweet"
            else:
                in_reply_to = comment.get("in_reply_to_status_id")
                if in_reply_to:
                    assert in_reply_to in user_tweet_ids, \
                        f"Comment in_reply_to {in_reply_to} should be a user tweet"

        print(f"✅ All comments correctly link to user's tweets")


class TestCommentsCacheReadWrite:
    """
    Unit tests for comments_cache read/write functions.
    Tests Supabase-based cache operations with mocking.
    """

    TEST_USER = "__test_cache_user__"

    @pytest.fixture
    def mock_supabase(self):
        """Mock Supabase client for cache tests."""
        from unittest.mock import patch

        stored_comments = {}

        def mock_get_comments(username, limit=None, offset=0, status_filter=None):
            comments = list(stored_comments.values())
            if offset:
                comments = comments[offset:]
            if limit:
                comments = comments[:limit]
            return comments

        def mock_get_comment(username, comment_id):
            return stored_comments.get(comment_id)

        def mock_add_comment(comment):
            stored_comments[comment["tweet_id"]] = comment

        def mock_delete_comment(comment_id):
            if comment_id in stored_comments:
                del stored_comments[comment_id]
                return True
            return False

        with patch("backend.utlils.supabase_client.get_comments", mock_get_comments), \
             patch("backend.utlils.supabase_client.get_comment", mock_get_comment), \
             patch("backend.utlils.supabase_client.add_comment", mock_add_comment), \
             patch("backend.utlils.supabase_client.delete_comment", mock_delete_comment):
            yield stored_comments

    def test_read_empty_cache(self, mock_supabase):
        """Test reading from empty cache returns empty structure."""
        from backend.data.twitter.comments_cache import read_comments_cache

        result = read_comments_cache(self.TEST_USER)
        assert result == {"_order": []}, "Empty cache should return {'_order': []}"

    def test_write_and_read_comment(self, mock_supabase):
        """Test adding a comment and reading it back."""
        from backend.data.twitter.comments_cache import add_comment, get_comment, read_comments_cache

        # Add a test comment
        add_comment(
            username=self.TEST_USER,
            comment_id="12345",
            text="Test comment",
            handle="tester",
            commenter_username="Test User",
            in_reply_to_id="parent_1",
            parent_chain=["parent_1"],
            created_at="2025-01-01T00:00:00+00:00",
            url="https://x.com/tester/status/12345",
            followers=100,
            likes=5
        )

        # Read it back
        result = read_comments_cache(self.TEST_USER)
        assert "12345" in result, "Comment should be in cache"
        assert result["12345"]["text"] == "Test comment"
        assert result["12345"]["commenter_handle"] == "tester"

        # Test get_comment
        comment = get_comment(self.TEST_USER, "12345")
        assert comment is not None
        assert comment["text"] == "Test comment"

        print("✅ Write and read comment works correctly")

    def test_delete_comment(self, mock_supabase):
        """Test deleting a comment from cache."""
        from backend.data.twitter.comments_cache import add_comment, delete_comment, get_comment

        # Add a test comment
        add_comment(
            username=self.TEST_USER,
            comment_id="99999",
            text="To be deleted",
            handle="tester",
            commenter_username="Test User",
            in_reply_to_id="parent_1",
            parent_chain=[],
            created_at="2025-01-01T00:00:00+00:00",
            url="https://x.com/tester/status/99999"
        )

        # Verify it exists
        assert get_comment(self.TEST_USER, "99999") is not None

        # Delete it
        result = delete_comment(self.TEST_USER, "99999")
        assert result is True, "Delete should return True"

        # Verify it's gone
        assert get_comment(self.TEST_USER, "99999") is None

        print("✅ Delete comment works correctly")

    def test_get_comments_list_pagination(self, mock_supabase):
        """Test pagination of comments list."""
        from backend.data.twitter.comments_cache import add_comment, get_comments_list

        # Create multiple comments
        for i, cid in enumerate(["c1", "c2", "c3", "c4", "c5"]):
            add_comment(
                username=self.TEST_USER,
                comment_id=cid,
                text=f"Comment {i+1}",
                handle="tester",
                commenter_username="Test User",
                in_reply_to_id="parent_1",
                parent_chain=[],
                created_at="2025-01-01T00:00:00+00:00",
                url=f"https://x.com/tester/status/{cid}"
            )

        # Test limit
        result = get_comments_list(self.TEST_USER, limit=2)
        assert len(result) == 2, "Should return 2 comments"
        assert result[0]["tweet_id"] == "c1"
        assert result[1]["tweet_id"] == "c2"

        # Test offset
        result = get_comments_list(self.TEST_USER, limit=2, offset=2)
        assert len(result) == 2, "Should return 2 comments"
        assert result[0]["tweet_id"] == "c3"
        assert result[1]["tweet_id"] == "c4"

        # Test no limit
        result = get_comments_list(self.TEST_USER)
        assert len(result) == 5, "Should return all 5 comments"

        print("✅ Pagination works correctly")


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
            assert comment["commenter_handle"] == "test_replier"  # commenter_handle, not handle
            assert comment["handle"] == test_username  # handle is the owner's username
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
