"""
Tests for posted_tweets_cache migration and functionality.

Tests that the map-based storage format with _order array works correctly,
including migration from the old array format.
"""
import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

# Import migration function
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from migrations.c113a0d_posted_tweets_to_map import migrate_file, is_older_than_days

try:  # Python 3.11+
    from datetime import UTC
except ImportError:
    from datetime import timezone
    UTC = timezone.utc


class TestMigration:
    """Tests for the migration script."""

    def test_is_older_than_days_recent(self):
        """Recent tweets should not be older than 7 days."""
        recent = datetime.now(UTC).isoformat()
        assert is_older_than_days(recent, 7) is False

    def test_is_older_than_days_old(self):
        """Old tweets should be older than 7 days."""
        old = (datetime.now(UTC) - timedelta(days=10)).isoformat()
        assert is_older_than_days(old, 7) is True

    def test_migrate_array_to_map(self):
        """Migration should convert array format to map with _order."""
        # Create temp file with old array format
        old_data = [
            {
                "id": "123",
                "text": "Test tweet 1",
                "likes": 5,
                "retweets": 2,
                "quotes": 0,
                "replies": 1,
                "impressions": 100,
                "created_at": datetime.now(UTC).isoformat(),
            },
            {
                "id": "456",
                "text": "Test tweet 2",
                "likes": 10,
                "retweets": 3,
                "quotes": 1,
                "replies": 2,
                "impressions": 200,
                "created_at": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
            },
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(old_data, f)
            temp_path = Path(f.name)

        try:
            result = migrate_file(temp_path)

            assert result["migrated"] is True
            assert result["tweets_count"] == 2
            assert result["error"] is None

            # Verify the new format
            with open(temp_path) as f:
                new_data = json.load(f)

            assert "_order" in new_data
            assert "123" in new_data
            assert "456" in new_data
            assert len(new_data["_order"]) == 2

            # Verify new fields were added
            tweet = new_data["123"]
            assert "parent_chain" in tweet
            assert "source" in tweet
            assert "monitoring_state" in tweet
            assert "last_activity_at" in tweet
            assert "last_deep_scrape" in tweet
            assert "last_shallow_scrape" in tweet
            assert "last_reply_count" in tweet
            assert "resurrected_via" in tweet
            assert "last_scraped_reply_ids" in tweet
        finally:
            temp_path.unlink(missing_ok=True)
            temp_path.with_suffix(".json.bak").unlink(missing_ok=True)

    def test_migrate_already_migrated(self):
        """Migration should skip files already in map format."""
        map_data = {
            "_order": ["123"],
            "123": {"id": "123", "text": "Test"},
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(map_data, f)
            temp_path = Path(f.name)

        try:
            result = migrate_file(temp_path)

            assert result["already_migrated"] is True
            assert result["tweets_count"] == 1
        finally:
            temp_path.unlink(missing_ok=True)

    def test_migrate_dry_run(self):
        """Dry run should not modify files."""
        old_data = [{"id": "123", "text": "Test", "created_at": datetime.now(UTC).isoformat()}]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(old_data, f)
            temp_path = Path(f.name)

        try:
            result = migrate_file(temp_path, dry_run=True)

            assert result["migrated"] is True
            assert result["tweets_count"] == 1

            # Verify file was NOT modified
            with open(temp_path) as f:
                data = json.load(f)
            assert isinstance(data, list)
        finally:
            temp_path.unlink(missing_ok=True)

    def test_migrate_creates_backup(self):
        """Migration should create a .bak backup file."""
        old_data = [{"id": "123", "text": "Test", "created_at": datetime.now(UTC).isoformat()}]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(old_data, f)
            temp_path = Path(f.name)

        try:
            result = migrate_file(temp_path)

            assert result["migrated"] is True

            # Verify backup exists
            backup_path = temp_path.with_suffix(".json.bak")
            assert backup_path.exists()

            # Verify backup has old format
            with open(backup_path) as f:
                backup_data = json.load(f)
            assert isinstance(backup_data, list)
        finally:
            temp_path.unlink(missing_ok=True)
            temp_path.with_suffix(".json.bak").unlink(missing_ok=True)


class TestPostedTweetsCache:
    """Tests for posted_tweets_cache functions."""

    @pytest.fixture
    def mock_cache_dir(self, tmp_path):
        """Create a temporary cache directory with test data."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        # Create test data in new map format
        test_data = {
            "_order": ["tweet1", "tweet2", "tweet3"],
            "tweet1": {
                "id": "tweet1",
                "text": "First tweet",
                "likes": 10,
                "retweets": 2,
                "quotes": 0,
                "replies": 1,
                "impressions": 100,
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
                "last_reply_count": 1,
                "last_like_count": 10,
                "last_quote_count": 0,
                "last_retweet_count": 2,
                "resurrected_via": "none",
                "last_scraped_reply_ids": [],
            },
            "tweet2": {
                "id": "tweet2",
                "text": "Second tweet",
                "likes": 5,
                "retweets": 0,
                "quotes": 0,
                "replies": 0,
                "impressions": 50,
                "created_at": (datetime.now(UTC) - timedelta(days=2)).isoformat(),
                "url": "https://x.com/test/status/tweet2",
                "last_metrics_update": datetime.now(UTC).isoformat(),
                "parent_chain": [],
                "response_to_thread": [],
                "responding_to": "another",
                "replying_to_pfp": "",
                "original_tweet_url": "",
                "source": "app_posted",
                "monitoring_state": "warm",
                "last_activity_at": (datetime.now(UTC) - timedelta(days=2)).isoformat(),
                "last_deep_scrape": None,
                "last_shallow_scrape": None,
                "last_reply_count": 0,
                "last_like_count": 5,
                "last_quote_count": 0,
                "last_retweet_count": 0,
                "resurrected_via": "none",
                "last_scraped_reply_ids": [],
            },
            "tweet3": {
                "id": "tweet3",
                "text": "Third tweet",
                "likes": 20,
                "retweets": 5,
                "quotes": 1,
                "replies": 3,
                "impressions": 500,
                "created_at": (datetime.now(UTC) - timedelta(days=10)).isoformat(),
                "url": "https://x.com/test/status/tweet3",
                "last_metrics_update": datetime.now(UTC).isoformat(),
                "parent_chain": [],
                "response_to_thread": [],
                "responding_to": "third",
                "replying_to_pfp": "",
                "original_tweet_url": "",
                "source": "app_posted",
                "monitoring_state": "cold",
                "last_activity_at": (datetime.now(UTC) - timedelta(days=10)).isoformat(),
                "last_deep_scrape": None,
                "last_shallow_scrape": None,
                "last_reply_count": 3,
                "last_like_count": 20,
                "last_quote_count": 1,
                "last_retweet_count": 5,
                "resurrected_via": "none",
                "last_scraped_reply_ids": [],
            },
        }

        test_file = cache_dir / "testuser_posted_tweets.json"
        with open(test_file, "w") as f:
            json.dump(test_data, f)

        return cache_dir

    def test_read_posted_tweets_cache(self, mock_cache_dir):
        """Test reading the posted tweets cache."""
        with patch("backend.utlils.utils.CACHE_DIR", mock_cache_dir):
            from backend.data.twitter.posted_tweets_cache import read_posted_tweets_cache

            tweets_map = read_posted_tweets_cache("testuser")

            assert "_order" in tweets_map
            assert len(tweets_map["_order"]) == 3
            assert "tweet1" in tweets_map
            assert "tweet2" in tweets_map
            assert "tweet3" in tweets_map

    def test_get_posted_tweets_list_pagination(self, mock_cache_dir):
        """Test pagination with get_posted_tweets_list."""
        with patch("backend.utlils.utils.CACHE_DIR", mock_cache_dir):
            from backend.data.twitter.posted_tweets_cache import get_posted_tweets_list

            # Get first 2
            page1 = get_posted_tweets_list("testuser", limit=2, offset=0)
            assert len(page1) == 2
            assert page1[0]["id"] == "tweet1"
            assert page1[1]["id"] == "tweet2"

            # Get next 2 (only 1 remaining)
            page2 = get_posted_tweets_list("testuser", limit=2, offset=2)
            assert len(page2) == 1
            assert page2[0]["id"] == "tweet3"

    def test_get_tweets_by_monitoring_state(self, mock_cache_dir):
        """Test filtering by monitoring state."""
        with patch("backend.utlils.utils.CACHE_DIR", mock_cache_dir):
            from backend.data.twitter.posted_tweets_cache import get_tweets_by_monitoring_state

            active = get_tweets_by_monitoring_state("testuser", ["active"])
            assert len(active) == 1
            assert active[0]["id"] == "tweet1"

            warm = get_tweets_by_monitoring_state("testuser", ["warm"])
            assert len(warm) == 1
            assert warm[0]["id"] == "tweet2"

            cold = get_tweets_by_monitoring_state("testuser", ["cold"])
            assert len(cold) == 1
            assert cold[0]["id"] == "tweet3"

            # Multiple states
            active_warm = get_tweets_by_monitoring_state("testuser", ["active", "warm"])
            assert len(active_warm) == 2

    def test_get_user_tweet_ids(self, mock_cache_dir):
        """Test getting all tweet IDs."""
        with patch("backend.utlils.utils.CACHE_DIR", mock_cache_dir):
            from backend.data.twitter.posted_tweets_cache import get_user_tweet_ids

            ids = get_user_tweet_ids("testuser")
            assert ids == {"tweet1", "tweet2", "tweet3"}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
