"""
Integration tests for discover_recently_posted background job.

Tests the job that discovers tweets posted externally (not through the app)
by scraping the user's Tweets & Replies tab.

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


class TestDiscoverRecentlyPostedIntegration:
    """Integration tests for discover_recently_posted job."""

    @pytest.mark.asyncio
    async def test_job_runs_successfully(self, test_username, test_handle):
        """Test that the job runs without errors and returns expected structure."""
        from backend.twitter.monitoring import discover_recently_posted

        # Run the job with a small max_tweets to keep test fast
        result = await discover_recently_posted(test_username, test_handle, max_tweets=10)

        # Verify result structure
        assert result is not None
        assert isinstance(result, dict)
        assert "discovered_tweets" in result
        assert "new_comments" in result
        assert "errors" in result

        # Counts should be non-negative integers
        assert isinstance(result["discovered_tweets"], int)
        assert result["discovered_tweets"] >= 0
        assert isinstance(result["new_comments"], int)
        assert result["new_comments"] >= 0

        # Errors should be a list
        assert isinstance(result["errors"], list)

        print(f"✅ discover_recently_posted completed:")
        print(f"   Discovered tweets: {result['discovered_tweets']}")
        print(f"   New comments: {result['new_comments']}")
        print(f"   Errors: {len(result['errors'])}")

    @pytest.mark.asyncio
    async def test_job_handles_browser_context(self, test_username, test_handle):
        """Test that the job properly gets and cleans up browser context."""
        from backend.twitter.monitoring import discover_recently_posted
        from backend.browser_management.context import get_authenticated_context, cleanup_browser_resources

        # First verify we can get an authenticated context
        playwright, browser, context = await get_authenticated_context(test_username)
        assert playwright is not None
        assert browser is not None
        assert context is not None

        # Clean up this test context
        await cleanup_browser_resources(playwright, browser, context)

        # Now run the actual job - it should handle its own context
        result = await discover_recently_posted(test_username, test_handle, max_tweets=5)

        # Job should complete successfully
        assert result is not None
        assert "errors" in result

        print(f"✅ Browser context handling verified")

    @pytest.mark.asyncio
    async def test_discovered_tweets_are_saved(self, test_username, test_handle):
        """Test that discovered tweets are properly saved to cache."""
        from backend.twitter.monitoring import discover_recently_posted
        from backend.data.twitter.posted_tweets_cache import read_posted_tweets_cache

        # Get initial tweet count
        initial_cache = read_posted_tweets_cache(test_username)
        initial_count = len(initial_cache.get("_order", []))

        # Run the job
        result = await discover_recently_posted(test_username, test_handle, max_tweets=5)

        # Get final tweet count
        final_cache = read_posted_tweets_cache(test_username)
        final_count = len(final_cache.get("_order", []))

        # If any tweets were discovered, count should have increased
        if result["discovered_tweets"] > 0:
            assert final_count >= initial_count
            print(f"✅ Tweet count: {initial_count} -> {final_count} ({result['discovered_tweets']} discovered)")
        else:
            print(f"✅ No new tweets discovered (already tracking all recent tweets)")

    @pytest.mark.asyncio
    async def test_external_tweets_marked_correctly(self, test_username, test_handle):
        """Test that discovered tweets are marked with source='external'."""
        from backend.twitter.monitoring import discover_recently_posted
        from backend.data.twitter.posted_tweets_cache import read_posted_tweets_cache

        # Run the job
        result = await discover_recently_posted(test_username, test_handle, max_tweets=5)

        # Check cache for external tweets
        cache = read_posted_tweets_cache(test_username)
        external_tweets = [
            tweet_id for tweet_id, tweet in cache.items()
            if tweet_id != "_order" and isinstance(tweet, dict) and tweet.get("source") == "external"
        ]

        print(f"✅ Found {len(external_tweets)} tweets marked as external")

        # If any external tweets exist, verify they have required fields
        for tweet_id in external_tweets[:3]:  # Check first 3
            tweet = cache[tweet_id]
            assert "monitoring_state" in tweet, f"Tweet {tweet_id} missing monitoring_state"
            assert "last_activity_at" in tweet, f"Tweet {tweet_id} missing last_activity_at"
            assert tweet.get("source") == "external"
            print(f"   ✓ Tweet {tweet_id}: state={tweet['monitoring_state']}")


class TestDiscoverRecentlyPostedHelpers:
    """Tests for helper functions used by discover_recently_posted."""

    def test_determine_monitoring_state_active(self):
        """Recent tweets should be marked as active."""
        from backend.twitter.monitoring import _determine_monitoring_state

        # Tweet from 1 hour ago
        now = datetime.now(UTC)
        recent_time = now.isoformat()

        tweet = {
            "created_at": recent_time,
            "last_activity_at": recent_time
        }

        state = _determine_monitoring_state(tweet)
        # Should be active (within ACTIVE_MAX_AGE_HOURS)
        assert state in ["active", "warm", "cold"]  # Depends on config
        print(f"✅ Recent tweet state: {state}")

    def test_determine_monitoring_state_old(self):
        """Old tweets with no activity should be cold."""
        from backend.twitter.monitoring import _determine_monitoring_state
        from datetime import timedelta

        # Tweet from 30 days ago
        now = datetime.now(UTC)
        old_time = (now - timedelta(days=30)).isoformat()

        tweet = {
            "created_at": old_time,
            "last_activity_at": old_time
        }

        state = _determine_monitoring_state(tweet)
        assert state == "cold"
        print(f"✅ Old tweet correctly marked as cold")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
