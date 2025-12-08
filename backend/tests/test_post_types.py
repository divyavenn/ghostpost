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
from unittest.mock import patch

import pytest

try:  # Python 3.11+
    from datetime import UTC
except ImportError:
    from datetime import timezone
    UTC = timezone.utc


def patch_cache_path(cache_dir):
    """Helper to patch get_posted_tweets_path to use a temp directory."""
    def patched_path(username):
        return cache_dir / f"{username}_posted_tweets.json"
    return patched_path


class TestPostTypeClassification:
    """Tests for post type classification during tweet creation."""

    @pytest.fixture
    def mock_cache_dir(self, tmp_path):
        """Create a temporary cache directory."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        return cache_dir

    def test_add_posted_tweet_default_type_is_reply(self, mock_cache_dir):
        """Default post_type should be 'reply' when not specified."""
        with patch("backend.data.twitter.posted_tweets_cache.get_posted_tweets_path", patch_cache_path(mock_cache_dir)):
            from backend.data.twitter.posted_tweets_cache import add_posted_tweet, read_posted_tweets_cache

            tweet = add_posted_tweet(
                username="testuser_default",
                posted_tweet_id="123",
                text="This is a reply",
            )

            assert tweet["post_type"] == "reply"

            # Verify it's persisted correctly
            tweets_map = read_posted_tweets_cache("testuser_default")
            assert tweets_map["123"]["post_type"] == "reply"

    def test_add_posted_tweet_type_original(self, mock_cache_dir):
        """Original posts should have post_type='original'."""
        with patch("backend.data.twitter.posted_tweets_cache.get_posted_tweets_path", patch_cache_path(mock_cache_dir)):
            from backend.data.twitter.posted_tweets_cache import add_posted_tweet, read_posted_tweets_cache

            tweet = add_posted_tweet(
                username="testuser_orig",
                posted_tweet_id="456",
                text="This is an original post",
                post_type="original",
            )

            assert tweet["post_type"] == "original"

            # Verify it's persisted correctly
            tweets_map = read_posted_tweets_cache("testuser_orig")
            assert tweets_map["456"]["post_type"] == "original"

    def test_add_posted_tweet_type_reply(self, mock_cache_dir):
        """Replies should have post_type='reply'."""
        with patch("backend.data.twitter.posted_tweets_cache.get_posted_tweets_path", patch_cache_path(mock_cache_dir)):
            from backend.data.twitter.posted_tweets_cache import add_posted_tweet, read_posted_tweets_cache

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

            # Verify it's persisted correctly
            tweets_map = read_posted_tweets_cache("testuser_reply")
            assert tweets_map["789"]["post_type"] == "reply"

    def test_add_posted_tweet_type_comment_reply(self, mock_cache_dir):
        """Comment replies should have post_type='comment_reply'."""
        with patch("backend.data.twitter.posted_tweets_cache.get_posted_tweets_path", patch_cache_path(mock_cache_dir)):
            from backend.data.twitter.posted_tweets_cache import add_posted_tweet, read_posted_tweets_cache

            tweet = add_posted_tweet(
                username="testuser_comment",
                posted_tweet_id="999",
                text="Thanks for the comment!",
                post_type="comment_reply",
                in_reply_to_id="comment_456",
            )

            assert tweet["post_type"] == "comment_reply"

            # Verify it's persisted correctly
            tweets_map = read_posted_tweets_cache("testuser_comment")
            assert tweets_map["999"]["post_type"] == "comment_reply"

    def test_initial_score_is_zero(self, mock_cache_dir):
        """New tweets should have score=0."""
        with patch("backend.data.twitter.posted_tweets_cache.get_posted_tweets_path", patch_cache_path(mock_cache_dir)):
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
    def mock_cache_with_tweet(self, tmp_path):
        """Create a cache with an existing tweet."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        test_data = {
            "_order": ["tweet1"],
            "tweet1": {
                "id": "tweet1",
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
                "last_deep_scrape": None,
                "last_shallow_scrape": None,
                "last_reply_count": 0,
                "last_like_count": 0,
                "last_quote_count": 0,
                "last_retweet_count": 0,
                "resurrected_via": "none",
                "last_scraped_reply_ids": [],
                "post_type": "reply",
                "score": 0,
            },
        }

        test_file = cache_dir / "metrics_testuser_posted_tweets.json"
        with open(test_file, "w") as f:
            json.dump(test_data, f)

        return cache_dir

    def test_update_tweet_metrics_updates_score(self, mock_cache_with_tweet):
        """Updating metrics should recalculate the engagement score."""
        with patch("backend.data.twitter.posted_tweets_cache.get_posted_tweets_path", patch_cache_path(mock_cache_with_tweet)):
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

            # Verify it's persisted
            tweets_map = read_posted_tweets_cache("metrics_testuser")
            assert tweets_map["tweet1"]["score"] == 29


class TestGetTopPostsByType:
    """Tests for filtering posts by type and sorting by score."""

    @pytest.fixture
    def mock_cache_with_mixed_types(self, tmp_path):
        """Create a cache with posts of different types and scores."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        test_data = {
            "_order": ["orig1", "orig2", "reply1", "reply2", "reply3", "comment1", "comment2"],
            "orig1": {
                "id": "orig1",
                "text": "Original post 1",
                "likes": 50, "retweets": 10, "quotes": 5, "replies": 10,
                "impressions": 1000,
                "created_at": datetime.now(UTC).isoformat(),
                "url": "https://x.com/test/status/orig1",
                "last_metrics_update": datetime.now(UTC).isoformat(),
                "parent_chain": [], "response_to_thread": [],
                "responding_to": "", "replying_to_pfp": "", "original_tweet_url": "",
                "source": "app_posted", "monitoring_state": "active",
                "last_activity_at": datetime.now(UTC).isoformat(),
                "last_deep_scrape": None, "last_shallow_scrape": None,
                "last_reply_count": 10, "last_like_count": 50,
                "last_quote_count": 5, "last_retweet_count": 10,
                "resurrected_via": "none", "last_scraped_reply_ids": [],
                "post_type": "original",
                "score": 95,  # 50 + 20 + 15 + 10
            },
            "orig2": {
                "id": "orig2",
                "text": "Original post 2 - lower engagement",
                "likes": 5, "retweets": 1, "quotes": 0, "replies": 2,
                "impressions": 100,
                "created_at": datetime.now(UTC).isoformat(),
                "url": "https://x.com/test/status/orig2",
                "last_metrics_update": datetime.now(UTC).isoformat(),
                "parent_chain": [], "response_to_thread": [],
                "responding_to": "", "replying_to_pfp": "", "original_tweet_url": "",
                "source": "app_posted", "monitoring_state": "active",
                "last_activity_at": datetime.now(UTC).isoformat(),
                "last_deep_scrape": None, "last_shallow_scrape": None,
                "last_reply_count": 2, "last_like_count": 5,
                "last_quote_count": 0, "last_retweet_count": 1,
                "resurrected_via": "none", "last_scraped_reply_ids": [],
                "post_type": "original",
                "score": 9,  # 5 + 2 + 0 + 2
            },
            "reply1": {
                "id": "reply1",
                "text": "Best reply",
                "likes": 100, "retweets": 20, "quotes": 10, "replies": 5,
                "impressions": 2000,
                "created_at": datetime.now(UTC).isoformat(),
                "url": "https://x.com/test/status/reply1",
                "last_metrics_update": datetime.now(UTC).isoformat(),
                "parent_chain": ["ext1"], "response_to_thread": ["Original tweet text"],
                "responding_to": "famous_person", "replying_to_pfp": "", "original_tweet_url": "https://x.com/famous/status/ext1",
                "source": "app_posted", "monitoring_state": "active",
                "last_activity_at": datetime.now(UTC).isoformat(),
                "last_deep_scrape": None, "last_shallow_scrape": None,
                "last_reply_count": 5, "last_like_count": 100,
                "last_quote_count": 10, "last_retweet_count": 20,
                "resurrected_via": "none", "last_scraped_reply_ids": [],
                "post_type": "reply",
                "score": 175,  # 100 + 40 + 30 + 5
            },
            "reply2": {
                "id": "reply2",
                "text": "Medium reply",
                "likes": 20, "retweets": 5, "quotes": 1, "replies": 2,
                "impressions": 500,
                "created_at": datetime.now(UTC).isoformat(),
                "url": "https://x.com/test/status/reply2",
                "last_metrics_update": datetime.now(UTC).isoformat(),
                "parent_chain": ["ext2"], "response_to_thread": ["Another tweet"],
                "responding_to": "another_person", "replying_to_pfp": "", "original_tweet_url": "",
                "source": "app_posted", "monitoring_state": "active",
                "last_activity_at": datetime.now(UTC).isoformat(),
                "last_deep_scrape": None, "last_shallow_scrape": None,
                "last_reply_count": 2, "last_like_count": 20,
                "last_quote_count": 1, "last_retweet_count": 5,
                "resurrected_via": "none", "last_scraped_reply_ids": [],
                "post_type": "reply",
                "score": 35,  # 20 + 10 + 3 + 2
            },
            "reply3": {
                "id": "reply3",
                "text": "Low engagement reply",
                "likes": 2, "retweets": 0, "quotes": 0, "replies": 0,
                "impressions": 50,
                "created_at": datetime.now(UTC).isoformat(),
                "url": "https://x.com/test/status/reply3",
                "last_metrics_update": datetime.now(UTC).isoformat(),
                "parent_chain": ["ext3"], "response_to_thread": ["Third tweet"],
                "responding_to": "third_person", "replying_to_pfp": "", "original_tweet_url": "",
                "source": "app_posted", "monitoring_state": "active",
                "last_activity_at": datetime.now(UTC).isoformat(),
                "last_deep_scrape": None, "last_shallow_scrape": None,
                "last_reply_count": 0, "last_like_count": 2,
                "last_quote_count": 0, "last_retweet_count": 0,
                "resurrected_via": "none", "last_scraped_reply_ids": [],
                "post_type": "reply",
                "score": 2,
            },
            "comment1": {
                "id": "comment1",
                "text": "Great comment reply",
                "likes": 15, "retweets": 3, "quotes": 1, "replies": 2,
                "impressions": 300,
                "created_at": datetime.now(UTC).isoformat(),
                "url": "https://x.com/test/status/comment1",
                "last_metrics_update": datetime.now(UTC).isoformat(),
                "parent_chain": ["my_tweet", "commenter_reply"],
                "response_to_thread": [], "responding_to": "commenter",
                "replying_to_pfp": "", "original_tweet_url": "",
                "source": "app_posted", "monitoring_state": "active",
                "last_activity_at": datetime.now(UTC).isoformat(),
                "last_deep_scrape": None, "last_shallow_scrape": None,
                "last_reply_count": 2, "last_like_count": 15,
                "last_quote_count": 1, "last_retweet_count": 3,
                "resurrected_via": "none", "last_scraped_reply_ids": [],
                "post_type": "comment_reply",
                "score": 26,  # 15 + 6 + 3 + 2
            },
            "comment2": {
                "id": "comment2",
                "text": "Another comment reply",
                "likes": 5, "retweets": 0, "quotes": 0, "replies": 1,
                "impressions": 80,
                "created_at": datetime.now(UTC).isoformat(),
                "url": "https://x.com/test/status/comment2",
                "last_metrics_update": datetime.now(UTC).isoformat(),
                "parent_chain": ["my_tweet2", "commenter2_reply"],
                "response_to_thread": [], "responding_to": "commenter2",
                "replying_to_pfp": "", "original_tweet_url": "",
                "source": "app_posted", "monitoring_state": "active",
                "last_activity_at": datetime.now(UTC).isoformat(),
                "last_deep_scrape": None, "last_shallow_scrape": None,
                "last_reply_count": 1, "last_like_count": 5,
                "last_quote_count": 0, "last_retweet_count": 0,
                "resurrected_via": "none", "last_scraped_reply_ids": [],
                "post_type": "comment_reply",
                "score": 6,  # 5 + 0 + 0 + 1
            },
        }

        test_file = cache_dir / "mixed_testuser_posted_tweets.json"
        with open(test_file, "w") as f:
            json.dump(test_data, f)

        return cache_dir

    def test_get_top_posts_by_type_original(self, mock_cache_with_mixed_types):
        """Should return only original posts, sorted by score descending."""
        with patch("backend.data.twitter.posted_tweets_cache.get_posted_tweets_path", patch_cache_path(mock_cache_with_mixed_types)):
            from backend.data.twitter.posted_tweets_cache import get_top_posts_by_type

            originals = get_top_posts_by_type("mixed_testuser", "original")

            assert len(originals) == 2
            # Should be sorted by score (highest first)
            assert originals[0]["id"] == "orig1"
            assert originals[0]["score"] == 95
            assert originals[1]["id"] == "orig2"
            assert originals[1]["score"] == 9

            # Verify all are original type
            for post in originals:
                assert post["post_type"] == "original"

    def test_get_top_posts_by_type_reply(self, mock_cache_with_mixed_types):
        """Should return only replies, sorted by score descending."""
        with patch("backend.data.twitter.posted_tweets_cache.get_posted_tweets_path", patch_cache_path(mock_cache_with_mixed_types)):
            from backend.data.twitter.posted_tweets_cache import get_top_posts_by_type

            replies = get_top_posts_by_type("mixed_testuser", "reply")

            assert len(replies) == 3
            # Should be sorted by score (highest first)
            assert replies[0]["id"] == "reply1"
            assert replies[0]["score"] == 175
            assert replies[1]["id"] == "reply2"
            assert replies[1]["score"] == 35
            assert replies[2]["id"] == "reply3"
            assert replies[2]["score"] == 2

            # Verify all are reply type
            for post in replies:
                assert post["post_type"] == "reply"

    def test_get_top_posts_by_type_comment_reply(self, mock_cache_with_mixed_types):
        """Should return only comment replies, sorted by score descending."""
        with patch("backend.data.twitter.posted_tweets_cache.get_posted_tweets_path", patch_cache_path(mock_cache_with_mixed_types)):
            from backend.data.twitter.posted_tweets_cache import get_top_posts_by_type

            comments = get_top_posts_by_type("mixed_testuser", "comment_reply")

            assert len(comments) == 2
            # Should be sorted by score (highest first)
            assert comments[0]["id"] == "comment1"
            assert comments[0]["score"] == 26
            assert comments[1]["id"] == "comment2"
            assert comments[1]["score"] == 6

            # Verify all are comment_reply type
            for post in comments:
                assert post["post_type"] == "comment_reply"

    def test_get_top_posts_by_type_with_limit(self, mock_cache_with_mixed_types):
        """Should respect the limit parameter."""
        with patch("backend.data.twitter.posted_tweets_cache.get_posted_tweets_path", patch_cache_path(mock_cache_with_mixed_types)):
            from backend.data.twitter.posted_tweets_cache import get_top_posts_by_type

            # Only get top 2 replies
            top2_replies = get_top_posts_by_type("mixed_testuser", "reply", limit=2)

            assert len(top2_replies) == 2
            # Should be the top 2 by score
            assert top2_replies[0]["id"] == "reply1"
            assert top2_replies[1]["id"] == "reply2"

    def test_get_top_posts_by_type_none_returns_all(self, mock_cache_with_mixed_types):
        """Passing None for post_type should return all posts."""
        with patch("backend.data.twitter.posted_tweets_cache.get_posted_tweets_path", patch_cache_path(mock_cache_with_mixed_types)):
            from backend.data.twitter.posted_tweets_cache import get_top_posts_by_type

            all_posts = get_top_posts_by_type("mixed_testuser", None)

            assert len(all_posts) == 7
            # Should be sorted by score (highest first)
            assert all_posts[0]["id"] == "reply1"  # score 175
            assert all_posts[1]["id"] == "orig1"   # score 95


class TestGetTopPostsForLLMContext:
    """Tests for the combined function that gets all types for LLM context."""

    @pytest.fixture
    def mock_cache_with_mixed_types(self, tmp_path):
        """Create a cache with posts of different types."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        test_data = {
            "_order": ["orig1", "reply1", "comment1"],
            "orig1": {
                "id": "orig1", "text": "Original", "post_type": "original",
                "likes": 10, "retweets": 2, "quotes": 1, "replies": 1,
                "impressions": 100, "score": 17,
                "created_at": datetime.now(UTC).isoformat(),
                "url": "https://x.com/test/status/orig1",
                "last_metrics_update": datetime.now(UTC).isoformat(),
                "parent_chain": [], "response_to_thread": [],
                "responding_to": "", "replying_to_pfp": "", "original_tweet_url": "",
                "source": "app_posted", "monitoring_state": "active",
                "last_activity_at": datetime.now(UTC).isoformat(),
                "last_deep_scrape": None, "last_shallow_scrape": None,
                "last_reply_count": 1, "last_like_count": 10,
                "last_quote_count": 1, "last_retweet_count": 2,
                "resurrected_via": "none", "last_scraped_reply_ids": [],
            },
            "reply1": {
                "id": "reply1", "text": "Reply", "post_type": "reply",
                "likes": 20, "retweets": 5, "quotes": 2, "replies": 3,
                "impressions": 200, "score": 39,
                "created_at": datetime.now(UTC).isoformat(),
                "url": "https://x.com/test/status/reply1",
                "last_metrics_update": datetime.now(UTC).isoformat(),
                "parent_chain": ["ext1"], "response_to_thread": ["Original"],
                "responding_to": "someone", "replying_to_pfp": "", "original_tweet_url": "",
                "source": "app_posted", "monitoring_state": "active",
                "last_activity_at": datetime.now(UTC).isoformat(),
                "last_deep_scrape": None, "last_shallow_scrape": None,
                "last_reply_count": 3, "last_like_count": 20,
                "last_quote_count": 2, "last_retweet_count": 5,
                "resurrected_via": "none", "last_scraped_reply_ids": [],
            },
            "comment1": {
                "id": "comment1", "text": "Comment reply", "post_type": "comment_reply",
                "likes": 5, "retweets": 1, "quotes": 0, "replies": 1,
                "impressions": 50, "score": 8,
                "created_at": datetime.now(UTC).isoformat(),
                "url": "https://x.com/test/status/comment1",
                "last_metrics_update": datetime.now(UTC).isoformat(),
                "parent_chain": ["my_tweet", "their_comment"],
                "response_to_thread": [], "responding_to": "commenter",
                "replying_to_pfp": "", "original_tweet_url": "",
                "source": "app_posted", "monitoring_state": "active",
                "last_activity_at": datetime.now(UTC).isoformat(),
                "last_deep_scrape": None, "last_shallow_scrape": None,
                "last_reply_count": 1, "last_like_count": 5,
                "last_quote_count": 0, "last_retweet_count": 1,
                "resurrected_via": "none", "last_scraped_reply_ids": [],
            },
        }

        test_file = cache_dir / "llm_testuser_posted_tweets.json"
        with open(test_file, "w") as f:
            json.dump(test_data, f)

        return cache_dir

    def test_get_top_posts_for_llm_context_structure(self, mock_cache_with_mixed_types):
        """Should return a dict with all three post type keys."""
        with patch("backend.data.twitter.posted_tweets_cache.get_posted_tweets_path", patch_cache_path(mock_cache_with_mixed_types)):
            from backend.data.twitter.posted_tweets_cache import get_top_posts_for_llm_context

            result = get_top_posts_for_llm_context("llm_testuser")

            assert "original" in result
            assert "reply" in result
            assert "comment_reply" in result

            assert len(result["original"]) == 1
            assert len(result["reply"]) == 1
            assert len(result["comment_reply"]) == 1

    def test_get_top_posts_for_llm_context_empty_cache(self, tmp_path):
        """Should return empty lists for each type when cache is empty."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        with patch("backend.data.twitter.posted_tweets_cache.get_posted_tweets_path", patch_cache_path(cache_dir)):
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
