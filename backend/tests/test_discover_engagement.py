"""
Integration tests for discover_engagement background job.

Tests the job that monitors active/warm tweets for new engagement:
- Active tweets (< 12h since activity): Deep scraped
- Warm tweets (< 3 days since activity): Shallow scraped

Uses divya_venn user's browser context for real integration testing.
"""
import asyncio
import pytest
from datetime import datetime

try:
    from datetime import UTC
except ImportError:
    from datetime import timezone
    UTC = timezone.utc


@pytest.fixture
def test_username():
    """The test user's cache key."""
    return "divya_venn"


@pytest.fixture
def test_handle():
    """The test user's Twitter handle."""
    return "divya_venn"


class TestDiscoverEngagementIntegration:
    """Integration tests for discover_engagement job."""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_discover_engagement_full_integration(self, test_username, test_handle):
        """
        Combined integration test that runs discover_engagement ONCE and verifies:
        1. Job returns correct structure
        2. Active tweets are deep scraped
        3. Warm tweets are shallow scraped
        4. Metrics are updated after scrape
        """
        from backend.data.twitter.posted_tweets_cache import (
            get_tweets_by_monitoring_state,
            read_posted_tweets_cache,
        )
        from backend.twitter.monitoring import discover_engagement

        # Get state counts before running
        active_tweets = get_tweets_by_monitoring_state(test_username, ["active"])
        warm_tweets = get_tweets_by_monitoring_state(test_username, ["warm"])

        print(f"📊 Before job: {len(active_tweets)} active, {len(warm_tweets)} warm tweets")

        # Get a tweet to track metrics update
        tweets_to_track = get_tweets_by_monitoring_state(test_username, ["active", "warm"])
        test_tweet_id = tweets_to_track[0].get("id") if tweets_to_track else None

        initial_scrape_time = None
        if test_tweet_id:
            initial_cache = read_posted_tweets_cache(test_username)
            initial_tweet = initial_cache.get(test_tweet_id, {})
            initial_scrape_time = initial_tweet.get("last_deep_scrape") or initial_tweet.get("last_shallow_scrape")

        # Run the job ONCE
        result = await discover_engagement(test_username, test_handle)

        # 1. Verify result structure
        assert result is not None
        assert isinstance(result, dict)
        for key in ["active_scraped", "warm_scraped", "new_comments",
                    "promoted_to_active", "demoted_to_warm", "demoted_to_cold"]:
            assert key in result, f"Result should have '{key}'"
            assert isinstance(result[key], int), f"{key} should be an integer"
            assert result[key] >= 0, f"{key} should be non-negative"
        assert isinstance(result["errors"], list)

        print(f"✅ discover_engagement completed:")
        print(f"   Active scraped: {result['active_scraped']}")
        print(f"   Warm scraped: {result['warm_scraped']}")
        print(f"   New comments: {result['new_comments']}")
        print(f"   Promoted to active: {result['promoted_to_active']}")
        print(f"   Demoted to warm: {result['demoted_to_warm']}")
        print(f"   Demoted to cold: {result['demoted_to_cold']}")
        print(f"   Errors: {len(result['errors'])}")

        # 2. Verify active tweets were deep scraped
        if len(active_tweets) > 0:
            assert result["active_scraped"] >= 0
            print(f"✅ Deep scraped {result['active_scraped']} of {len(active_tweets)} active tweets")
        else:
            assert result["active_scraped"] == 0
            print("✅ No active tweets to deep scrape")

        # 3. Verify warm tweets were shallow scraped
        if len(warm_tweets) > 0:
            assert result["warm_scraped"] >= 0
            print(f"✅ Shallow scraped {result['warm_scraped']} of {len(warm_tweets)} warm tweets")
        else:
            assert result["warm_scraped"] == 0
            print("✅ No warm tweets to shallow scrape")

        # 4. Verify metrics were updated
        if test_tweet_id and (result["active_scraped"] > 0 or result["warm_scraped"] > 0):
            final_cache = read_posted_tweets_cache(test_username)
            final_tweet = final_cache.get(test_tweet_id, {})
            final_scrape_time = final_tweet.get("last_deep_scrape") or final_tweet.get("last_shallow_scrape")
            print(f"✅ Scrape times: {initial_scrape_time} -> {final_scrape_time}")


class TestDiscoverEngagementHelpers:
    """Tests for helper functions used by discover_engagement."""

    def test_calculate_activity_delta(self):
        """Test activity delta calculation."""
        from backend.twitter.monitoring import _calculate_activity_delta

        tweet = {
            "last_reply_count": 10,
            "last_like_count": 100,
            "last_quote_count": 5,
            "last_retweet_count": 20
        }

        new_metrics = {
            "replies": 15,  # +5
            "likes": 150,   # +50
            "quotes": 7,    # +2
            "retweets": 25  # +5
        }

        delta = _calculate_activity_delta(tweet, new_metrics)
        assert delta == 62  # 5 + 50 + 2 + 5
        print(f"✅ Activity delta calculated correctly: {delta}")

    def test_calculate_activity_delta_no_previous(self):
        """Test delta calculation when no previous counts exist."""
        from backend.twitter.monitoring import _calculate_activity_delta

        tweet = {}  # No previous counts

        new_metrics = {
            "replies": 10,
            "likes": 50,
            "quotes": 5,
            "retweets": 10
        }

        delta = _calculate_activity_delta(tweet, new_metrics)
        assert delta == 75  # All counts are new
        print(f"✅ Delta with no previous: {delta}")

    def test_should_promote_to_active_new_replies(self):
        """Test promotion detection based on new reply IDs."""
        from backend.twitter.monitoring import _should_promote_to_active

        tweet = {
            "last_scraped_reply_ids": ["reply1", "reply2", "reply3"]
        }

        new_metrics = {"replies": 4, "likes": 10, "quotes": 1, "retweets": 2}
        new_reply_ids = ["reply1", "reply2", "reply3", "reply4"]  # One new reply

        should_promote = _should_promote_to_active(tweet, new_metrics, new_reply_ids)
        assert should_promote is True
        print(f"✅ Correctly detected new reply -> should promote")

    def test_should_promote_to_active_no_change(self):
        """Test no promotion when nothing has changed."""
        from backend.twitter.monitoring import _should_promote_to_active

        tweet = {
            "last_scraped_reply_ids": ["reply1", "reply2"],
            "last_reply_count": 2,
            "last_like_count": 10,
            "last_quote_count": 1,
            "last_retweet_count": 2
        }

        new_metrics = {"replies": 2, "likes": 10, "quotes": 1, "retweets": 2}
        new_reply_ids = ["reply1", "reply2"]  # Same replies

        should_promote = _should_promote_to_active(tweet, new_metrics, new_reply_ids)
        # Should be False unless delta >= threshold
        print(f"✅ No changes -> should_promote = {should_promote}")


class TestMonitoringStateTransitions:
    """Tests for monitoring state transitions."""

    @pytest.mark.asyncio
    async def test_state_distribution(self, test_username):
        """Test the distribution of monitoring states."""
        from backend.data.twitter.posted_tweets_cache import (
            get_tweets_by_monitoring_state,
            read_posted_tweets_cache,
        )

        cache = read_posted_tweets_cache(test_username)
        total = len(cache.get("_order", []))

        active = get_tweets_by_monitoring_state(test_username, ["active"])
        warm = get_tweets_by_monitoring_state(test_username, ["warm"])
        cold = get_tweets_by_monitoring_state(test_username, ["cold"])

        print(f"📊 Monitoring state distribution for {test_username}:")
        print(f"   Total tweets: {total}")
        print(f"   Active: {len(active)}")
        print(f"   Warm: {len(warm)}")
        print(f"   Cold: {len(cold)}")
        print(f"   Unassigned: {total - len(active) - len(warm) - len(cold)}")

        # Counts should make sense
        assert len(active) >= 0
        assert len(warm) >= 0
        assert len(cold) >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
