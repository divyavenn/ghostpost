"""
Test that media is correctly passed when posting tweets.
"""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def tmp_cache_dir(tmp_path):
    """Create a temporary cache directory."""
    cache_dir = tmp_path / "twitter_cache"
    cache_dir.mkdir()
    return cache_dir


@pytest.fixture
def sample_cached_tweet_with_media():
    """Return a sample cached tweet with media attachments."""
    return {
        "id": "123456789",
        "cache_id": "test-cache-id",
        "text": "Original tweet text",
        "thread": ["First message", "Second message"],
        "handle": "original_author",
        "author_profile_pic_url": "https://example.com/pic.jpg",
        "url": "https://x.com/original_author/status/123456789",
        "media": [
            {"type": "photo", "url": "https://pbs.twimg.com/media/abc123.jpg", "alt_text": "Photo 1"},
            {"type": "photo", "url": "https://pbs.twimg.com/media/def456.jpg", "alt_text": "Photo 2"},
        ],
        "generated_replies": [("Reply text", "gpt-4")],
        "likes": 10,
        "retweets": 5,
        "quotes": 2,
        "replies": 3,
        "impressions": 100,
        "followers": 1000,
        "score": 0.5,
        "created_at": "2024-01-01T12:00:00Z",
        "username": "Original Author",
        "scraped_from": {"type": "account", "value": "original_author"},
        "quoted_tweet": None,
        "other_replies": [],
        "edited": False,
    }


def test_media_extracted_from_cache_when_posting(tmp_cache_dir, sample_cached_tweet_with_media):
    """Test that media is correctly extracted from cache and passed to add_posted_tweet."""
    # Create mock cache file
    cache_file = tmp_cache_dir / "test_user_cache.json"
    cache_file.write_text(json.dumps([sample_cached_tweet_with_media]))

    # Track what was passed to add_posted_tweet
    captured_media = None

    def mock_add_posted_tweet(**kwargs):
        nonlocal captured_media
        captured_media = kwargs.get("media")
        return {"id": "new_tweet_id", "text": kwargs.get("text", "")}

    # Mock the dependencies
    with patch("backend.twitter.posting._get_access_token_for_user") as mock_token, \
         patch("backend.twitter.posting.requests.post") as mock_post, \
         patch("backend.data.twitter.edit_cache.get_user_tweet_cache") as mock_cache_path, \
         patch("backend.data.twitter.posted_tweets_cache.add_posted_tweet", mock_add_posted_tweet), \
         patch("backend.twitter.logging.log_tweet_action"), \
         patch("backend.utlils.utils.read_user_info") as mock_read_user, \
         patch("backend.utlils.utils.write_user_info"):

        mock_token.return_value = "mock_access_token"
        mock_post.return_value = MagicMock(
            status_code=201,
            json=lambda: {"data": {"id": "new_posted_tweet_123"}}
        )
        mock_cache_path.return_value = cache_file
        mock_read_user.return_value = {"lifetime_posts": 0}

        # Import and call the post function
        import asyncio
        from backend.twitter.posting import post

        payload = {
            "text": "My reply",
            "reply": {"in_reply_to_tweet_id": "123456789"}
        }

        asyncio.run(post("test_user", payload, cache_id="test-cache-id", reply_index=0))

    # Verify media was captured and passed correctly
    assert captured_media is not None, "media should have been passed to add_posted_tweet"
    assert len(captured_media) == 2, f"Expected 2 media items, got {len(captured_media)}"
    assert captured_media[0]["url"] == "https://pbs.twimg.com/media/abc123.jpg"
    assert captured_media[1]["url"] == "https://pbs.twimg.com/media/def456.jpg"


def test_empty_media_when_tweet_has_no_media(tmp_cache_dir):
    """Test that empty media list is passed when tweet has no media."""
    cached_tweet_no_media = {
        "id": "987654321",
        "cache_id": "no-media-cache-id",
        "text": "Tweet without media",
        "thread": [],
        "handle": "author",
        "author_profile_pic_url": "https://example.com/pic.jpg",
        "url": "https://x.com/author/status/987654321",
        "media": [],  # No media
        "generated_replies": [("Reply text", "gpt-4")],
        "likes": 5,
        "retweets": 2,
        "quotes": 1,
        "replies": 1,
        "impressions": 50,
        "followers": 500,
        "score": 0.3,
        "created_at": "2024-01-02T12:00:00Z",
        "username": "Author",
        "scraped_from": {"type": "account", "value": "author"},
        "quoted_tweet": None,
        "other_replies": [],
        "edited": False,
    }

    cache_file = tmp_cache_dir / "test_user_cache.json"
    cache_file.write_text(json.dumps([cached_tweet_no_media]))

    captured_media = None

    def mock_add_posted_tweet(**kwargs):
        nonlocal captured_media
        captured_media = kwargs.get("media")
        return {"id": "new_tweet_id", "text": kwargs.get("text", "")}

    with patch("backend.twitter.posting._get_access_token_for_user") as mock_token, \
         patch("backend.twitter.posting.requests.post") as mock_post, \
         patch("backend.data.twitter.edit_cache.get_user_tweet_cache") as mock_cache_path, \
         patch("backend.data.twitter.posted_tweets_cache.add_posted_tweet", mock_add_posted_tweet), \
         patch("backend.twitter.logging.log_tweet_action"), \
         patch("backend.utlils.utils.read_user_info") as mock_read_user, \
         patch("backend.utlils.utils.write_user_info"):

        mock_token.return_value = "mock_access_token"
        mock_post.return_value = MagicMock(
            status_code=201,
            json=lambda: {"data": {"id": "new_posted_tweet_456"}}
        )
        mock_cache_path.return_value = cache_file
        mock_read_user.return_value = {"lifetime_posts": 0}

        import asyncio
        from backend.twitter.posting import post

        payload = {
            "text": "My reply",
            "reply": {"in_reply_to_tweet_id": "987654321"}
        }

        asyncio.run(post("test_user", payload, cache_id="no-media-cache-id", reply_index=0))

    assert captured_media is not None, "media should have been passed to add_posted_tweet"
    assert captured_media == [], "media should be an empty list when tweet has no media"


def test_media_defaults_to_empty_when_no_cache_id():
    """Test that media defaults to empty list when no cache_id is provided."""
    captured_media = None

    def mock_add_posted_tweet(**kwargs):
        nonlocal captured_media
        captured_media = kwargs.get("media")
        return {"id": "new_tweet_id", "text": kwargs.get("text", "")}

    with patch("backend.twitter.posting._get_access_token_for_user") as mock_token, \
         patch("backend.twitter.posting.requests.post") as mock_post, \
         patch("backend.data.twitter.posted_tweets_cache.add_posted_tweet", mock_add_posted_tweet), \
         patch("backend.twitter.logging.log_tweet_action"), \
         patch("backend.utlils.utils.read_user_info") as mock_read_user, \
         patch("backend.utlils.utils.write_user_info"):

        mock_token.return_value = "mock_access_token"
        mock_post.return_value = MagicMock(
            status_code=201,
            json=lambda: {"data": {"id": "new_posted_tweet_789"}}
        )
        mock_read_user.return_value = {"lifetime_posts": 0}

        import asyncio
        from backend.twitter.posting import post

        # No cache_id provided
        payload = {"text": "A new tweet"}

        asyncio.run(post("test_user", payload, cache_id=None))

    assert captured_media is not None, "media should have been passed to add_posted_tweet"
    assert captured_media == [], "media should be an empty list when no cache_id is provided"
