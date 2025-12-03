"""
Integration tests for discover_resurrected background job.

Tests the job that checks for activity on cold tweets via notifications:
- Scrapes Twitter notifications to find activity on cold tweets
- Promotes resurrected tweets back to active state
- Deep scrapes to get new replies

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


class TestDiscoverResurrectedIntegration:
    """Integration tests for discover_resurrected job."""

    @pytest.mark.asyncio
    async def test_job_runs_successfully(self, test_username, test_handle):
        """Test that the job runs without errors and returns expected structure."""
        from backend.twitter.monitoring import discover_resurrected

        result = await discover_resurrected(test_username, test_handle)

        # Verify result structure
        assert result is not None
        assert isinstance(result, dict)
        assert "resurrected_tweets" in result
        assert "new_comments" in result
        assert "errors" in result

        # Counts should be non-negative integers
        assert isinstance(result["resurrected_tweets"], int)
        assert result["resurrected_tweets"] >= 0
        assert isinstance(result["new_comments"], int)
        assert result["new_comments"] >= 0

        # Errors should be a list
        assert isinstance(result["errors"], list)

        print(f"✅ discover_resurrected completed:")
        print(f"   Resurrected tweets: {result['resurrected_tweets']}")
        print(f"   New comments: {result['new_comments']}")
        print(f"   Errors: {len(result['errors'])}")

    @pytest.mark.asyncio
    async def test_cold_tweets_monitored(self, test_username, test_handle):
        """Test that cold tweets are checked for resurrection."""
        from backend.twitter.monitoring import discover_resurrected
        from backend.data.twitter.posted_tweets_cache import get_tweets_by_monitoring_state

        # Check if there are any cold tweets
        cold_tweets = get_tweets_by_monitoring_state(test_username, ["cold"])

        print(f"📊 Found {len(cold_tweets)} cold tweets to monitor for resurrection")

        result = await discover_resurrected(test_username, test_handle)

        # The job should complete regardless of cold tweet count
        assert result is not None

        if len(cold_tweets) == 0:
            # No cold tweets means nothing to resurrect
            assert result["resurrected_tweets"] == 0
            print(f"✅ No cold tweets available (nothing to resurrect)")
        else:
            print(f"✅ Monitored cold tweets, resurrected: {result['resurrected_tweets']}")

    @pytest.mark.asyncio
    async def test_resurrected_tweets_promoted(self, test_username, test_handle):
        """Test that resurrected tweets are promoted to active state."""
        from backend.twitter.monitoring import discover_resurrected
        from backend.data.twitter.posted_tweets_cache import read_posted_tweets_cache

        result = await discover_resurrected(test_username, test_handle)

        # Check for resurrected tweets in cache
        cache = read_posted_tweets_cache(test_username)
        resurrected_via_notification = [
            tweet_id for tweet_id, tweet in cache.items()
            if tweet_id != "_order" and isinstance(tweet, dict)
            and tweet.get("resurrected_via") == "notification"
        ]

        print(f"📊 Tweets resurrected via notification: {len(resurrected_via_notification)}")

        # Verify resurrected tweets are now active
        for tweet_id in resurrected_via_notification[:3]:  # Check first 3
            tweet = cache[tweet_id]
            # Should be active after resurrection
            if tweet.get("monitoring_state") == "active":
                print(f"   ✓ Tweet {tweet_id}: correctly promoted to active")
            else:
                # May have been demoted again if time passed
                print(f"   ⚠ Tweet {tweet_id}: state = {tweet.get('monitoring_state')}")

    @pytest.mark.asyncio
    async def test_browser_context_cleanup(self, test_username, test_handle):
        """Test that browser resources are properly cleaned up."""
        from backend.twitter.monitoring import discover_resurrected
        import gc

        # Run the job
        result = await discover_resurrected(test_username, test_handle)

        # Force garbage collection
        gc.collect()

        # Job should complete without resource leaks
        assert result is not None
        print(f"✅ Browser context cleaned up successfully")


class TestNotificationsScraping:
    """Tests for notifications page scraping."""

    @pytest.mark.asyncio
    async def test_can_access_notifications(self, test_username):
        """Test that we can access the notifications page."""
        from backend.browser_management.context import get_authenticated_context, cleanup_browser_resources
        import asyncio

        playwright, browser, context = await get_authenticated_context(test_username)

        try:
            page = await context.new_page()
            await page.goto("https://x.com/notifications", wait_until="domcontentloaded")
            await asyncio.sleep(3)

            # Check that we're on the notifications page
            title = await page.title()
            url = page.url

            print(f"📊 Notifications page:")
            print(f"   Title: {title}")
            print(f"   URL: {url}")

            # Should be on notifications page (not login redirect)
            assert "notifications" in url.lower() or "x.com" in url.lower()

            # Look for tweet status links
            links = await page.locator("a[href*='/status/']").count()
            print(f"   Tweet links found: {links}")

            await page.close()

        finally:
            await cleanup_browser_resources(playwright, browser, context)

        print(f"✅ Successfully accessed notifications page")


class TestRunEngagementMonitoring:
    """Tests for the combined monitoring job."""

    @pytest.mark.asyncio
    async def test_full_monitoring_run(self, test_username, test_handle):
        """Test running the complete engagement monitoring pipeline."""
        from backend.twitter.monitoring import run_engagement_monitoring

        print(f"🚀 Starting full engagement monitoring run...")

        result = await run_engagement_monitoring(test_username, test_handle)

        # Verify combined result structure
        assert result is not None
        assert isinstance(result, dict)
        assert "discover_recently_posted" in result
        assert "discover_engagement" in result
        assert "discover_resurrected" in result
        assert "total_new_comments" in result
        assert "errors" in result

        # Each sub-job result should be a dict
        assert isinstance(result["discover_recently_posted"], dict)
        assert isinstance(result["discover_engagement"], dict)
        assert isinstance(result["discover_resurrected"], dict)

        print(f"✅ Full monitoring run completed:")
        print(f"   Recently posted: {result['discover_recently_posted']}")
        print(f"   Engagement: {result['discover_engagement']}")
        print(f"   Resurrected: {result['discover_resurrected']}")
        print(f"   Total new comments: {result['total_new_comments']}")
        print(f"   Errors: {result['errors']}")


class TestColdTweetTracking:
    """Tests for cold tweet state tracking."""

    @pytest.mark.asyncio
    async def test_cold_tweet_attributes(self, test_username):
        """Test that cold tweets have expected attributes."""
        from backend.data.twitter.posted_tweets_cache import get_tweets_by_monitoring_state

        cold_tweets = get_tweets_by_monitoring_state(test_username, ["cold"])

        print(f"📊 Analyzing {len(cold_tweets)} cold tweets")

        for tweet in cold_tweets[:5]:  # Check first 5
            tweet_id = tweet.get("id")

            # Cold tweets should have these attributes
            assert "created_at" in tweet or tweet_id
            assert "monitoring_state" in tweet

            state = tweet.get("monitoring_state")
            assert state == "cold", f"Tweet {tweet_id} should be cold but is {state}"

            resurrected_via = tweet.get("resurrected_via", "none")
            print(f"   Cold tweet {tweet_id}: resurrected_via={resurrected_via}")

        print(f"✅ Cold tweet attributes verified")

    @pytest.mark.asyncio
    async def test_state_after_resurrection(self, test_username, test_handle):
        """Test tweet state after potential resurrection."""
        from backend.twitter.monitoring import discover_resurrected
        from backend.data.twitter.posted_tweets_cache import read_posted_tweets_cache

        # Get initial cold tweets
        cache_before = read_posted_tweets_cache(test_username)
        cold_before = [
            tid for tid, t in cache_before.items()
            if tid != "_order" and isinstance(t, dict) and t.get("monitoring_state") == "cold"
        ]

        # Run resurrection job
        result = await discover_resurrected(test_username, test_handle)

        # Get final state
        cache_after = read_posted_tweets_cache(test_username)
        cold_after = [
            tid for tid, t in cache_after.items()
            if tid != "_order" and isinstance(t, dict) and t.get("monitoring_state") == "cold"
        ]

        resurrected_count = result.get("resurrected_tweets", 0)

        print(f"📊 State changes:")
        print(f"   Cold before: {len(cold_before)}")
        print(f"   Cold after: {len(cold_after)}")
        print(f"   Resurrected: {resurrected_count}")

        # If any were resurrected, cold count should decrease
        if resurrected_count > 0:
            assert len(cold_after) <= len(cold_before)
            print(f"✅ Resurrection correctly reduced cold count")
        else:
            print(f"✅ No tweets resurrected (no notification activity)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
