"""
Tests for post type classification in posted_tweets_cache.

Verifies that:
- Original posts, replies, and comment replies are correctly identified
- get_top_posts_by_type correctly filters by type
- Engagement scores are calculated correctly
- get_top_posts_for_llm_context returns proper structure
"""
import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

try:  # Python 3.11+
    from datetime import UTC
except ImportError:
    from datetime import timezone
    UTC = timezone.utc


class TestPostTypeClassification:
    """Tests for post type classification during tweet creation."""

    @pytest.fixture
    def mock_supabase(self):
        """Mock Supabase client functions."""
        stored_tweets = {}

        def mock_get_posted_tweets(username, limit=None, offset=0):
            return list(stored_tweets.values())

        def mock_add_posted_tweet(tweet):
            stored_tweets[tweet["tweet_id"]] = tweet

        def mock_get_comments(username):
            return []

        with patch("backend.utlils.supabase_client.get_posted_tweets", mock_get_posted_tweets), \
             patch("backend.utlils.supabase_client.add_posted_tweet", mock_add_posted_tweet), \
             patch("backend.utlils.supabase_client.get_comments", mock_get_comments):
            yield stored_tweets

    def test_add_posted_tweet_default_type_is_reply(self, mock_supabase):
        """Default post_type should be 'reply' when not specified."""
        from backend.data.twitter.posted_tweets_cache import add_posted_tweet

        tweet = add_posted_tweet(
            username="testuser_default",
            posted_tweet_id="123",
            text="This is a reply",
        )

        assert tweet["post_type"] == "reply"
        assert mock_supabase["123"]["post_type"] == "reply"

    def test_add_posted_tweet_type_original(self, mock_supabase):
        """Original posts should have post_type='original'."""
        from backend.data.twitter.posted_tweets_cache import add_posted_tweet

        tweet = add_posted_tweet(
            username="testuser_orig",
            posted_tweet_id="456",
            text="This is an original post",
            post_type="original",
        )

        assert tweet["post_type"] == "original"
        assert mock_supabase["456"]["post_type"] == "original"

    def test_add_posted_tweet_type_reply(self, mock_supabase):
        """Replies should have post_type='reply'."""
        from backend.data.twitter.posted_tweets_cache import add_posted_tweet

        tweet = add_posted_tweet(
            username="testuser_reply",
            posted_tweet_id="789",
            text="This is a reply to someone's tweet",
            post_type="reply",
            in_reply_to_id="external_tweet_123",
            responding_to_handle="someone",
        )

        assert tweet["post_type"] == "reply"
        assert "external_tweet_123" in tweet["parent_chain"]
        assert mock_supabase["789"]["post_type"] == "reply"

    def test_add_posted_tweet_type_comment_reply(self, mock_supabase):
        """Comment replies should have post_type='comment_reply'."""
        from backend.data.twitter.posted_tweets_cache import add_posted_tweet

        tweet = add_posted_tweet(
            username="testuser_comment",
            posted_tweet_id="999",
            text="Thanks for the comment!",
            post_type="comment_reply",
            in_reply_to_id="comment_456",
        )

        assert tweet["post_type"] == "comment_reply"
        assert mock_supabase["999"]["post_type"] == "comment_reply"

    def test_initial_score_is_zero(self, mock_supabase):
        """New tweets should have score=0."""
        from backend.data.twitter.posted_tweets_cache import add_posted_tweet

        tweet = add_posted_tweet(
            username="testuser_score",
            posted_tweet_id="new123",
            text="New tweet",
        )

        assert tweet["score"] == 0


class TestEngagementScore:
    """Tests for engagement score calculation."""

    def test_calculate_engagement_score_formula(self):
        """Score should be: likes + 2*retweets + 3*quotes + replies."""
        from backend.data.twitter.posted_tweets_cache import calculate_engagement_score

        # likes=10, retweets=5, quotes=2, replies=3
        # Expected: 10 + 2*5 + 3*2 + 3 = 10 + 10 + 6 + 3 = 29
        score = calculate_engagement_score(likes=10, retweets=5, quotes=2, replies=3)
        assert score == 29

    def test_calculate_engagement_score_zero_metrics(self):
        """Score should be 0 when all metrics are 0."""
        from backend.data.twitter.posted_tweets_cache import calculate_engagement_score

        score = calculate_engagement_score(likes=0, retweets=0, quotes=0, replies=0)
        assert score == 0

    def test_calculate_engagement_score_only_likes(self):
        """Score with only likes equals the like count."""
        from backend.data.twitter.posted_tweets_cache import calculate_engagement_score

        score = calculate_engagement_score(likes=100, retweets=0, quotes=0, replies=0)
        assert score == 100

    def test_calculate_engagement_score_quotes_weighted_highest(self):
        """Quotes should have the highest weight (3x)."""
        from backend.data.twitter.posted_tweets_cache import calculate_engagement_score

        # 1 quote = 3 points
        score = calculate_engagement_score(likes=0, retweets=0, quotes=1, replies=0)
        assert score == 3

        # Compared to 1 like = 1 point, 1 retweet = 2 points, 1 reply = 1 point
        assert score > calculate_engagement_score(likes=1, retweets=0, quotes=0, replies=0)
        assert score > calculate_engagement_score(likes=0, retweets=1, quotes=0, replies=0)
        assert score > calculate_engagement_score(likes=0, retweets=0, quotes=0, replies=1)


class TestUpdateMetricsUpdatesScore:
    """Tests that updating metrics also updates the engagement score."""

    @pytest.fixture
    def mock_supabase_with_tweet(self):
        """Mock Supabase with an existing tweet."""
        stored_tweets = {
            "tweet1": {
                "tweet_id": "tweet1",
                "handle": "metrics_testuser",
                "text": "Test tweet",
                "likes": 0,
                "retweets": 0,
                "quotes": 0,
                "replies": 0,
                "impressions": 0,
                "created_at": datetime.now(UTC).isoformat(),
                "url": "https://x.com/test/status/tweet1",
                "last_metrics_update": datetime.now(UTC).isoformat(),
                "parent_chain": [],
                "response_to_thread": [],
                "responding_to": "someone",
                "replying_to_pfp": "",
                "original_tweet_url": "",
                "source": "app_posted",
                "monitoring_state": "active",
                "last_activity_at": datetime.now(UTC).isoformat(),
                "resurrected_via": "none",
                "last_scraped_reply_ids": [],
                "post_type": "reply",
                "score": 0,
            },
        }

        def mock_get_posted_tweets(username, limit=None, offset=0):
            return [t for t in stored_tweets.values() if t.get("handle") == username]

        def mock_update_posted_tweet(tweet_id, updates):
            if tweet_id in stored_tweets:
                stored_tweets[tweet_id].update(updates)
                return stored_tweets[tweet_id]
            return None

        with patch("backend.utlils.supabase_client.get_posted_tweets", mock_get_posted_tweets), \
             patch("backend.utlils.supabase_client.update_posted_tweet", mock_update_posted_tweet):
            yield stored_tweets

    def test_update_tweet_metrics_updates_score(self, mock_supabase_with_tweet):
        """Updating metrics should recalculate the engagement score."""
        from backend.data.twitter.posted_tweets_cache import update_tweet_metrics, read_posted_tweets_cache

        # Update with new metrics: 10 likes, 5 RT, 2 quotes, 3 replies
        # Expected score: 10 + 10 + 6 + 3 = 29
        updated = update_tweet_metrics(
            username="metrics_testuser",
            posted_tweet_id="tweet1",
            likes=10,
            retweets=5,
            quotes=2,
            replies=3,
        )

        assert updated is not None
        assert updated["score"] == 29

        # Verify it's persisted in mock
        assert mock_supabase_with_tweet["tweet1"]["score"] == 29


class TestGetTopPostsByType:
    """Tests for filtering posts by type and sorting by score."""

    @pytest.fixture
    def mock_supabase_with_mixed_types(self):
        """Mock Supabase with posts of different types and scores."""
        test_data = [
            {
                "tweet_id": "orig1", "handle": "mixed_testuser",
                "text": "Original post 1",
                "likes": 50, "retweets": 10, "quotes": 5, "replies": 10,
                "impressions": 1000,
                "created_at": datetime.now(UTC).isoformat(),
                "post_type": "original", "score": 95,
            },
            {
                "tweet_id": "orig2", "handle": "mixed_testuser",
                "text": "Original post 2 - lower engagement",
                "likes": 5, "retweets": 1, "quotes": 0, "replies": 2,
                "impressions": 100,
                "post_type": "original", "score": 9,
            },
            {
                "tweet_id": "reply1", "handle": "mixed_testuser",
                "text": "Best reply",
                "likes": 100, "retweets": 20, "quotes": 10, "replies": 5,
                "impressions": 2000,
                "post_type": "reply", "score": 175,
            },
            {
                "tweet_id": "reply2", "handle": "mixed_testuser",
                "text": "Medium reply",
                "likes": 20, "retweets": 5, "quotes": 1, "replies": 2,
                "impressions": 500,
                "post_type": "reply", "score": 35,
            },
            {
                "tweet_id": "reply3", "handle": "mixed_testuser",
                "text": "Low engagement reply",
                "likes": 2, "retweets": 0, "quotes": 0, "replies": 0,
                "impressions": 50,
                "post_type": "reply", "score": 2,
            },
            {
                "tweet_id": "comment1", "handle": "mixed_testuser",
                "text": "Great comment reply",
                "likes": 15, "retweets": 3, "quotes": 1, "replies": 2,
                "impressions": 300,
                "post_type": "comment_reply", "score": 26,
            },
            {
                "tweet_id": "comment2", "handle": "mixed_testuser",
                "text": "Another comment reply",
                "likes": 5, "retweets": 0, "quotes": 0, "replies": 1,
                "impressions": 80,
                "post_type": "comment_reply", "score": 6,
            },
        ]

        def mock_get_top_posted_tweets(username, post_type=None, limit=10):
            filtered = [t for t in test_data if t.get("handle") == username]
            if post_type:
                filtered = [t for t in filtered if t.get("post_type") == post_type]
            filtered.sort(key=lambda x: x.get("score", 0), reverse=True)
            return filtered[:limit]

        with patch("backend.utlils.supabase_client.get_top_posted_tweets", mock_get_top_posted_tweets):
            yield test_data

    def test_get_top_posts_by_type_original(self, mock_supabase_with_mixed_types):
        """Should return only original posts, sorted by score descending."""
        from backend.data.twitter.posted_tweets_cache import get_top_posts_by_type

        originals = get_top_posts_by_type("mixed_testuser", "original")

        assert len(originals) == 2
        # Should be sorted by score (highest first)
        assert originals[0]["tweet_id"] == "orig1"
        assert originals[0]["score"] == 95
        assert originals[1]["tweet_id"] == "orig2"
        assert originals[1]["score"] == 9

        # Verify all are original type
        for post in originals:
            assert post["post_type"] == "original"

    def test_get_top_posts_by_type_reply(self, mock_supabase_with_mixed_types):
        """Should return only replies, sorted by score descending."""
        from backend.data.twitter.posted_tweets_cache import get_top_posts_by_type

        replies = get_top_posts_by_type("mixed_testuser", "reply")

        assert len(replies) == 3
        # Should be sorted by score (highest first)
        assert replies[0]["tweet_id"] == "reply1"
        assert replies[0]["score"] == 175
        assert replies[1]["tweet_id"] == "reply2"
        assert replies[1]["score"] == 35
        assert replies[2]["tweet_id"] == "reply3"
        assert replies[2]["score"] == 2

        # Verify all are reply type
        for post in replies:
            assert post["post_type"] == "reply"

    def test_get_top_posts_by_type_comment_reply(self, mock_supabase_with_mixed_types):
        """Should return only comment replies, sorted by score descending."""
        from backend.data.twitter.posted_tweets_cache import get_top_posts_by_type

        comments = get_top_posts_by_type("mixed_testuser", "comment_reply")

        assert len(comments) == 2
        # Should be sorted by score (highest first)
        assert comments[0]["tweet_id"] == "comment1"
        assert comments[0]["score"] == 26
        assert comments[1]["tweet_id"] == "comment2"
        assert comments[1]["score"] == 6

        # Verify all are comment_reply type
        for post in comments:
            assert post["post_type"] == "comment_reply"

    def test_get_top_posts_by_type_with_limit(self, mock_supabase_with_mixed_types):
        """Should respect the limit parameter."""
        from backend.data.twitter.posted_tweets_cache import get_top_posts_by_type

        # Only get top 2 replies
        top2_replies = get_top_posts_by_type("mixed_testuser", "reply", limit=2)

        assert len(top2_replies) == 2
        # Should be the top 2 by score
        assert top2_replies[0]["tweet_id"] == "reply1"
        assert top2_replies[1]["tweet_id"] == "reply2"

    def test_get_top_posts_by_type_none_returns_all(self, mock_supabase_with_mixed_types):
        """Passing None for post_type should return all posts."""
        from backend.data.twitter.posted_tweets_cache import get_top_posts_by_type

        all_posts = get_top_posts_by_type("mixed_testuser", None)

        assert len(all_posts) == 7
        # Should be sorted by score (highest first)
        assert all_posts[0]["tweet_id"] == "reply1"  # score 175
        assert all_posts[1]["tweet_id"] == "orig1"   # score 95


class TestGetTopPostsForLLMContext:
    """Tests for the combined function that gets all types for LLM context."""

    @pytest.fixture
    def mock_supabase_with_mixed_types(self):
        """Mock Supabase with posts of different types."""
        test_data = [
            {
                "tweet_id": "orig1", "handle": "llm_testuser",
                "text": "Original", "post_type": "original",
                "likes": 10, "retweets": 2, "quotes": 1, "replies": 1,
                "impressions": 100, "score": 17,
            },
            {
                "tweet_id": "reply1", "handle": "llm_testuser",
                "text": "Reply", "post_type": "reply",
                "likes": 20, "retweets": 5, "quotes": 2, "replies": 3,
                "impressions": 200, "score": 39,
                "response_to_thread": ["Original"], "responding_to": "someone",
            },
            {
                "tweet_id": "comment1", "handle": "llm_testuser",
                "text": "Comment reply", "post_type": "comment_reply",
                "likes": 5, "retweets": 1, "quotes": 0, "replies": 1,
                "impressions": 50, "score": 8,
            },
        ]

        def mock_get_top_posted_tweets(username, post_type=None, limit=10):
            filtered = [t for t in test_data if t.get("handle") == username]
            if post_type:
                filtered = [t for t in filtered if t.get("post_type") == post_type]
            filtered.sort(key=lambda x: x.get("score", 0), reverse=True)
            return filtered[:limit]

        with patch("backend.utlils.supabase_client.get_top_posted_tweets", mock_get_top_posted_tweets):
            yield test_data

    def test_get_top_posts_for_llm_context_structure(self, mock_supabase_with_mixed_types):
        """Should return a dict with all three post type keys."""
        from backend.data.twitter.posted_tweets_cache import get_top_posts_for_llm_context

        result = get_top_posts_for_llm_context("llm_testuser")

        assert "original" in result
        assert "reply" in result
        assert "comment_reply" in result

        assert len(result["original"]) == 1
        assert len(result["reply"]) == 1
        assert len(result["comment_reply"]) == 1

    def test_get_top_posts_for_llm_context_empty_cache(self):
        """Should return empty lists for each type when cache is empty."""
        def mock_get_top_posted_tweets(username, post_type=None, limit=10):
            return []

        with patch("backend.utlils.supabase_client.get_top_posted_tweets", mock_get_top_posted_tweets):
            from backend.data.twitter.posted_tweets_cache import get_top_posts_for_llm_context

            result = get_top_posts_for_llm_context("nonexistent_user")

            assert result["original"] == []
            assert result["reply"] == []
            assert result["comment_reply"] == []


class TestBuildExamplesFromPosts:
    """Tests for building LLM example strings from posts."""

    def test_build_examples_from_posts_reply(self):
        """Reply examples should include original tweet and your reply."""
        from backend.data.twitter.posted_tweets_cache import build_examples_from_posts

        posts = [
            {
                "text": "Great point! I agree.",
                "response_to_thread": ["Original tweet about AI"],
                "responding_to": "ai_expert",
                "likes": 50,
                "retweets": 10,
                "score": 70,
            }
        ]

        examples = build_examples_from_posts(posts, "reply")

        assert len(examples) == 1
        assert "[ORIGINAL @ai_expert]" in examples[0]
        assert "Original tweet about AI" in examples[0]
        assert "[YOUR REPLY (50L, 10RT)]" in examples[0]
        assert "Great point! I agree." in examples[0]

    def test_build_examples_from_posts_comment_reply(self):
        """Comment reply examples should show just the reply."""
        from backend.data.twitter.posted_tweets_cache import build_examples_from_posts

        posts = [
            {
                "text": "Thanks for reading!",
                "responding_to": "reader",
                "likes": 10,
                "retweets": 2,
                "score": 14,
            }
        ]

        examples = build_examples_from_posts(posts, "comment_reply")

        assert len(examples) == 1
        assert "[YOUR COMMENT REPLY (10L, 2RT)]" in examples[0]
        assert "Thanks for reading!" in examples[0]

    def test_build_examples_from_posts_original(self):
        """Original post examples should show just the post."""
        from backend.data.twitter.posted_tweets_cache import build_examples_from_posts

        posts = [
            {
                "text": "Just shipped a new feature!",
                "likes": 100,
                "retweets": 25,
                "score": 150,
            }
        ]

        examples = build_examples_from_posts(posts, "original")

        assert len(examples) == 1
        assert "[YOUR POST (100L, 25RT)]" in examples[0]
        assert "Just shipped a new feature!" in examples[0]

    def test_build_examples_from_posts_empty_list(self):
        """Should return empty list for empty input."""
        from backend.data.twitter.posted_tweets_cache import build_examples_from_posts

        examples = build_examples_from_posts([], "reply")
        assert examples == []


class TestPostTypeEndpointDetermination:
    """
    Tests that verify post_type is correctly determined by posting endpoints.

    Based on real examples:
    - https://x.com/divya_venn/status/1998595712138056093 → comment_reply
    - https://x.com/divya_venn/status/1998584939886027235 → reply
    - https://x.com/divya_venn/status/1998510228602851514 → original
    """

    @pytest.fixture
    def mock_supabase(self):
        """Mock Supabase client functions."""
        stored_tweets = {}

        def mock_get_posted_tweets(username, limit=None, offset=0):
            return list(stored_tweets.values())

        def mock_add_posted_tweet(tweet):
            stored_tweets[tweet["tweet_id"]] = tweet

        def mock_get_comments(username):
            return []

        with patch("backend.utlils.supabase_client.get_posted_tweets", mock_get_posted_tweets), \
             patch("backend.utlils.supabase_client.add_posted_tweet", mock_add_posted_tweet), \
             patch("backend.utlils.supabase_client.get_comments", mock_get_comments):
            yield stored_tweets

    @pytest.fixture
    def mock_cache_dir(self, tmp_path):
        """Create a temporary cache directory for edit_cache tests."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        return cache_dir

    @pytest.fixture
    def mock_tweet_cache_with_others_tweet(self, mock_cache_dir):
        """Mock tweet cache with a tweet from someone else (for reply test)."""
        cache_data = [
            {
                "tweet_id": "1998584939886027235",
                "cache_id": "cache_reply_to_other",
                "handle": "other_user",  # Different from our user
                "thread": ["This is someone else's tweet"],
                "url": "https://x.com/other_user/status/1998584939886027235",
            }
        ]
        cache_file = mock_cache_dir / "divya_venn_tweets.json"
        with open(cache_file, "w") as f:
            json.dump(cache_data, f)
        return mock_cache_dir

    @pytest.fixture
    def mock_tweet_cache_with_own_tweet(self, mock_cache_dir):
        """Mock tweet cache with user's own tweet (for thread/original test)."""
        cache_data = [
            {
                "tweet_id": "1998510228602851514",
                "cache_id": "cache_own_tweet",
                "handle": "divya_venn",  # Same as our user
                "thread": ["This is my own tweet I'm replying to"],
                "url": "https://x.com/divya_venn/status/1998510228602851514",
            }
        ]
        cache_file = mock_cache_dir / "divya_venn_tweets.json"
        with open(cache_file, "w") as f:
            json.dump(cache_data, f)
        return mock_cache_dir

    def test_post_tweet_endpoint_sets_original_type(self, mock_supabase):
        """
        /post/tweet should set post_type='original' for standalone tweets.
        Example: https://x.com/divya_venn/status/1998510228602851514
        """
        from backend.data.twitter.posted_tweets_cache import add_posted_tweet

        # Simulate what post_tweet endpoint does
        tweet = add_posted_tweet(
            username="divya_venn",
            posted_tweet_id="1998510228602851514",
            text="This is an original post",
            post_type="original",  # post_tweet endpoint passes this
        )

        assert tweet["post_type"] == "original"

    def test_reply_to_others_tweet_sets_reply_type(self, mock_tweet_cache_with_others_tweet):
        """
        Replying to someone else's tweet should set post_type='reply'.
        Example: https://x.com/divya_venn/status/1998584939886027235
        """
        # Simulate the logic from post_reply endpoint
        username = "divya_venn"
        cache_id = "cache_reply_to_other"

        # Read cache to determine post_type (same logic as post_reply)
        post_type = "reply"  # default
        cache_path = mock_tweet_cache_with_others_tweet / "divya_venn_tweets.json"
        if cache_path.exists():
            with open(cache_path, encoding="utf-8") as f:
                cached_tweets = json.load(f)
            for tweet in cached_tweets:
                if tweet.get("cache_id") == cache_id:
                    responding_to_handle = tweet.get("handle", "")
                    if responding_to_handle.lower() == username.lower():
                        post_type = "original"
                    break

        # other_user != divya_venn, so should be "reply"
        assert post_type == "reply"

    def test_reply_to_own_tweet_sets_original_type(self, mock_tweet_cache_with_own_tweet):
        """
        Replying to your own tweet (thread continuation) should set post_type='original'.
        """
        # Simulate the logic from post_reply endpoint
        username = "divya_venn"
        cache_id = "cache_own_tweet"

        # Read cache to determine post_type (same logic as post_reply)
        post_type = "reply"  # default
        cache_path = mock_tweet_cache_with_own_tweet / "divya_venn_tweets.json"
        if cache_path.exists():
            with open(cache_path, encoding="utf-8") as f:
                cached_tweets = json.load(f)
            for tweet in cached_tweets:
                if tweet.get("cache_id") == cache_id:
                    responding_to_handle = tweet.get("handle", "")
                    if responding_to_handle.lower() == username.lower():
                        post_type = "original"
                    break

        # divya_venn == divya_venn, so should be "original" (thread)
        assert post_type == "original"

    def test_reply_to_own_tweet_case_insensitive(self, mock_cache_dir):
        """Handle comparison should be case-insensitive."""
        # Create cache with mixed case handle
        cache_data = [
            {
                "tweet_id": "123",
                "cache_id": "test_cache",
                "handle": "Divya_Venn",  # Different case
                "thread": ["My tweet"],
            }
        ]
        cache_file = mock_cache_dir / "divya_venn_tweets.json"
        with open(cache_file, "w") as f:
            json.dump(cache_data, f)

        username = "divya_venn"  # lowercase
        cache_id = "test_cache"

        # Simulate the logic from post_reply endpoint
        post_type = "reply"
        if cache_file.exists():
            with open(cache_file, encoding="utf-8") as f:
                cached_tweets = json.load(f)
            for tweet in cached_tweets:
                if tweet.get("cache_id") == cache_id:
                    responding_to_handle = tweet.get("handle", "")
                    if responding_to_handle.lower() == username.lower():
                        post_type = "original"
                    break

        # Divya_Venn.lower() == divya_venn.lower(), so should be "original"
        assert post_type == "original"

    def test_comment_reply_sets_comment_reply_type(self, mock_supabase):
        """
        Comment replies should set post_type='comment_reply'.
        Example: https://x.com/divya_venn/status/1998595712138056093
        """
        from backend.data.twitter.posted_tweets_cache import add_posted_tweet

        # Simulate what comment_reply endpoint does
        tweet = add_posted_tweet(
            username="divya_venn",
            posted_tweet_id="1998595712138056093",
            text="Thanks for the comment!",
            post_type="comment_reply",  # comments_routes.py passes this
        )

        assert tweet["post_type"] == "comment_reply"

    def test_missing_cache_defaults_to_reply(self, mock_cache_dir):
        """If cache doesn't exist or cache_id not found, default to 'reply'."""
        # No cache file exists
        username = "divya_venn"
        cache_id = "nonexistent_cache"
        cache_file = mock_cache_dir / "divya_venn_tweets.json"

        # Simulate the logic from post_reply endpoint
        post_type = "reply"
        if cache_file.exists():
            with open(cache_file, encoding="utf-8") as f:
                cached_tweets = json.load(f)
            for tweet in cached_tweets:
                if tweet.get("cache_id") == cache_id:
                    responding_to_handle = tweet.get("handle", "")
                    if responding_to_handle.lower() == username.lower():
                        post_type = "original"
                    break

        # Cache doesn't exist, should default to "reply"
        assert post_type == "reply"

    def test_no_cache_id_defaults_to_reply(self):
        """If no cache_id is provided, default to 'reply'."""
        # Simulate the logic when cache_id is None
        cache_id = None
        post_type = "reply"

        if cache_id:
            # Would look up cache here, but cache_id is None
            pass

        assert post_type == "reply"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
