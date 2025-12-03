"""
Tests for build_prompt function in generate_replies.py.

Tests that the prompt is correctly built with:
- Thread content
- Quoted tweets
- Other replies
- Media/images
"""
import pytest

from backend.data.twitter.data_validation import MediaItem, OtherReply, QuotedTweet, ScrapedTweet, Source
from backend.twitter.generate_replies import build_prompt


def make_sample_tweet(**kwargs) -> dict:
    """Create a sample tweet dict with sensible defaults."""
    defaults = {
        "id": "1234567890",
        "text": "This is the main tweet text",
        "thread": ["This is the thread content"],
        "cache_id": "test_cache_123",
        "created_at": "2024-01-15T12:00:00Z",
        "url": "https://x.com/testuser/status/1234567890",
        "username": "Test User",
        "handle": "testuser",
        "author_profile_pic_url": "https://example.com/pic.jpg",
        "likes": 100,
        "retweets": 10,
        "quotes": 5,
        "replies": 20,
        "impressions": 1000,
        "followers": 500,
        "score": 0.5,
        "media": [],
        "quoted_tweet": None,
        "other_replies": [],
        "generated_replies": [],
        "edited": False,
    }
    defaults.update(kwargs)
    return defaults


class TestBuildPromptBasic:
    """Tests for basic prompt building without extra context."""

    def test_simple_tweet_thread(self):
        """Simple tweet with thread content should produce valid prompt."""
        tweet = make_sample_tweet(
            thread=["First message", "Second message", "Third message"]
        )

        result = build_prompt(tweet)
        assert result is not None

        text_prompt, image_urls, has_quoted, tweet_id = result

        assert tweet_id == "1234567890"
        assert has_quoted is False
        assert len(image_urls) == 0
        assert "['First message', 'Second message', 'Third message']" in text_prompt
        # Should NOT have response header since no quoted tweet
        assert "[Test User's RESPONSE]" not in text_prompt

    def test_empty_thread_returns_none(self):
        """Tweet with empty thread should return None."""
        tweet = make_sample_tweet(thread=[])
        result = build_prompt(tweet)
        assert result is None

    def test_missing_thread_returns_none(self):
        """Tweet with no thread key should fail validation."""
        tweet = make_sample_tweet()
        del tweet["thread"]
        result = build_prompt(tweet)
        assert result is None


class TestBuildPromptQuotedTweet:
    """Tests for prompt building with quoted tweets."""

    def test_quoted_tweet_appears_in_prompt(self):
        """Quoted tweet content should appear in prompt."""
        tweet = make_sample_tweet(
            thread=["My response to the quote"],
            quoted_tweet={
                "text": "This is the original quoted tweet",
                "author_handle": "originalauthor",
                "author_name": "Original Author",
                "media": []
            }
        )

        result = build_prompt(tweet)
        assert result is not None

        text_prompt, image_urls, has_quoted, tweet_id = result

        assert has_quoted is True
        # Check quoted tweet header
        assert "[QUOTED TWEET by @originalauthor (Original Author)]" in text_prompt
        # Check quoted tweet text
        assert "This is the original quoted tweet" in text_prompt
        # Check response header
        assert "[Test User's RESPONSE]" in text_prompt
        # Check separator
        assert "---" in text_prompt

    def test_quoted_tweet_with_images(self):
        """Quoted tweet images should be included."""
        tweet = make_sample_tweet(
            thread=["My response"],
            quoted_tweet={
                "text": "Check out this image",
                "author_handle": "photouser",
                "author_name": "Photo User",
                "media": [
                    {"type": "photo", "url": "https://example.com/qt_image.jpg", "alt_text": "A beautiful sunset"}
                ]
            }
        )

        result = build_prompt(tweet)
        assert result is not None

        text_prompt, image_urls, has_quoted, tweet_id = result

        assert has_quoted is True
        assert len(image_urls) == 1
        assert "https://example.com/qt_image.jpg" in image_urls
        assert "[This quoted tweet contains 1 image(s)]" in text_prompt
        assert "A beautiful sunset" in text_prompt  # Alt text

    def test_quoted_tweet_without_text_not_included(self):
        """Quoted tweet with empty text should not be included."""
        tweet = make_sample_tweet(
            thread=["My tweet"],
            quoted_tweet={
                "text": "",  # Empty text
                "author_handle": "someone",
                "author_name": "Someone",
                "media": []
            }
        )

        result = build_prompt(tweet)
        assert result is not None

        text_prompt, image_urls, has_quoted, tweet_id = result

        assert has_quoted is False
        assert "[QUOTED TWEET" not in text_prompt


class TestBuildPromptOtherReplies:
    """Tests for prompt building with other users' replies."""

    def test_other_replies_appear_in_prompt(self):
        """Other replies should appear in prompt."""
        tweet = make_sample_tweet(
            thread=["The original tweet"],
            other_replies=[
                {
                    "text": "Great point!",
                    "author_handle": "replier1",
                    "author_name": "Replier One",
                    "likes": 50
                },
                {
                    "text": "I disagree because...",
                    "author_handle": "replier2",
                    "author_name": "Replier Two",
                    "likes": 25
                }
            ]
        )

        result = build_prompt(tweet)
        assert result is not None

        text_prompt, image_urls, has_quoted, tweet_id = result

        assert "[TOP REPLIES FROM OTHERS]" in text_prompt
        assert "@replier1 (Replier One) - 50 likes:" in text_prompt
        assert "Great point!" in text_prompt
        assert "@replier2 (Replier Two) - 25 likes:" in text_prompt
        assert "I disagree because..." in text_prompt

    def test_only_top_5_replies_included(self):
        """Should only include top 5 replies."""
        replies = [
            {
                "text": f"Reply number {i}",
                "author_handle": f"user{i}",
                "author_name": f"User {i}",
                "likes": 10 - i
            }
            for i in range(10)
        ]

        tweet = make_sample_tweet(
            thread=["The original tweet"],
            other_replies=replies
        )

        result = build_prompt(tweet)
        assert result is not None

        text_prompt, _, _, _ = result

        # First 5 should be included
        for i in range(5):
            assert f"Reply number {i}" in text_prompt

        # 6-9 should NOT be included
        for i in range(5, 10):
            assert f"Reply number {i}" not in text_prompt


class TestBuildPromptMedia:
    """Tests for prompt building with media attachments."""

    def test_main_tweet_images(self):
        """Main tweet images should be included."""
        tweet = make_sample_tweet(
            thread=["Check out this photo"],
            media=[
                {"type": "photo", "url": "https://example.com/image1.jpg", "alt_text": ""},
                {"type": "photo", "url": "https://example.com/image2.jpg", "alt_text": "Second image"}
            ]
        )

        result = build_prompt(tweet)
        assert result is not None

        text_prompt, image_urls, has_quoted, tweet_id = result

        assert len(image_urls) == 2
        assert "https://example.com/image1.jpg" in image_urls
        assert "https://example.com/image2.jpg" in image_urls
        assert "Second image" in text_prompt  # Alt text

    def test_video_not_included_in_images(self):
        """Video media should not be included in image_urls."""
        tweet = make_sample_tweet(
            thread=["Check out this video"],
            media=[
                {"type": "video", "url": "https://example.com/video.mp4", "alt_text": ""},
                {"type": "photo", "url": "https://example.com/thumbnail.jpg", "alt_text": ""}
            ]
        )

        result = build_prompt(tweet)
        assert result is not None

        text_prompt, image_urls, has_quoted, tweet_id = result

        assert len(image_urls) == 1
        assert "https://example.com/thumbnail.jpg" in image_urls
        assert "https://example.com/video.mp4" not in image_urls

    def test_quoted_and_main_images_combined(self):
        """Both quoted tweet and main tweet images should be included, QT first."""
        tweet = make_sample_tweet(
            thread=["My response with image"],
            quoted_tweet={
                "text": "Original with image",
                "author_handle": "quoter",
                "author_name": "Quoter",
                "media": [
                    {"type": "photo", "url": "https://example.com/qt_photo.jpg", "alt_text": "QT alt"}
                ]
            },
            media=[
                {"type": "photo", "url": "https://example.com/main_photo.jpg", "alt_text": "Main alt"}
            ]
        )

        result = build_prompt(tweet)
        assert result is not None

        text_prompt, image_urls, has_quoted, tweet_id = result

        assert has_quoted is True
        assert len(image_urls) == 2
        # QT images should come first
        assert image_urls[0] == "https://example.com/qt_photo.jpg"
        assert image_urls[1] == "https://example.com/main_photo.jpg"
        # Both alt texts
        assert "QT alt" in text_prompt
        assert "Main alt" in text_prompt


class TestBuildPromptCompleteExample:
    """Test complete examples with all elements."""

    def test_complete_tweet_all_elements(self):
        """Tweet with quoted tweet, replies, and images should build correctly."""
        tweet = make_sample_tweet(
            id="9876543210",
            thread=["This is my thoughtful response to the thread"],
            username="Divya",
            handle="divya_venn",
            quoted_tweet={
                "text": "Hot take: AI will change everything",
                "author_handle": "techguru",
                "author_name": "Tech Guru",
                "media": [
                    {"type": "photo", "url": "https://example.com/ai_diagram.png", "alt_text": "AI architecture diagram"}
                ]
            },
            media=[
                {"type": "photo", "url": "https://example.com/my_chart.png", "alt_text": "My analysis chart"}
            ],
            other_replies=[
                {
                    "text": "This is so true! The implications are massive.",
                    "author_handle": "agreeguy",
                    "author_name": "Agree Guy",
                    "likes": 150
                },
                {
                    "text": "I'm skeptical. We've heard this before.",
                    "author_handle": "skeptic",
                    "author_name": "Skeptical Sam",
                    "likes": 75
                }
            ]
        )

        result = build_prompt(tweet)
        assert result is not None

        text_prompt, image_urls, has_quoted, tweet_id = result

        # Verify all components
        assert tweet_id == "9876543210"
        assert has_quoted is True
        assert len(image_urls) == 2

        # Quoted tweet section
        assert "[QUOTED TWEET by @techguru (Tech Guru)]" in text_prompt
        assert "Hot take: AI will change everything" in text_prompt
        assert "[This quoted tweet contains 1 image(s)]" in text_prompt

        # Response section
        assert "[Divya's RESPONSE]" in text_prompt
        assert "This is my thoughtful response to the thread" in text_prompt

        # Alt texts
        assert "AI architecture diagram" in text_prompt
        assert "My analysis chart" in text_prompt

        # Other replies
        assert "[TOP REPLIES FROM OTHERS]" in text_prompt
        assert "@agreeguy (Agree Guy) - 150 likes:" in text_prompt
        assert "This is so true!" in text_prompt
        assert "@skeptic (Skeptical Sam) - 75 likes:" in text_prompt
        assert "I'm skeptical" in text_prompt


class TestBuildPromptWithPydanticModel:
    """Test that build_prompt works with ScrapedTweet model directly."""

    def test_accepts_scraped_tweet_model(self):
        """build_prompt should accept ScrapedTweet model directly."""
        tweet = ScrapedTweet(
            id="model_tweet_123",
            text="Main text",
            thread=["Thread content here"],
            cache_id="cache_123",
            created_at="2024-01-15T12:00:00Z",
            url="https://x.com/user/status/123",
            username="Model User",
            handle="modeluser",
            author_profile_pic_url="https://example.com/pic.jpg",
            likes=50,
            retweets=5,
            quotes=2,
            replies=10,
            followers=100,
            score=0.5,
            quoted_tweet=QuotedTweet(
                text="Quoted content",
                author_handle="quoteduser",
                author_name="Quoted User",
                media=[]
            ),
            other_replies=[
                OtherReply(
                    text="Nice reply!",
                    author_handle="replier",
                    author_name="Replier",
                    likes=20
                )
            ]
        )

        result = build_prompt(tweet)
        assert result is not None

        text_prompt, image_urls, has_quoted, tweet_id = result

        assert tweet_id == "model_tweet_123"
        assert has_quoted is True
        assert "[QUOTED TWEET by @quoteduser (Quoted User)]" in text_prompt
        assert "Quoted content" in text_prompt
        assert "[Model User's RESPONSE]" in text_prompt
        assert "Thread content here" in text_prompt
        assert "[TOP REPLIES FROM OTHERS]" in text_prompt
        assert "@replier (Replier) - 20 likes:" in text_prompt
        assert "Nice reply!" in text_prompt


class TestBuildPromptValidation:
    """Test validation error handling."""

    def test_invalid_tweet_missing_required_fields(self):
        """Tweet missing required fields should return None."""
        # Missing 'id' and other required fields
        invalid_tweet = {
            "thread": ["Some content"],
            # Missing: id, text, cache_id, created_at, url, username, handle, etc.
        }
        result = build_prompt(invalid_tweet)
        assert result is None

    def test_invalid_media_type_still_works(self):
        """Invalid media type should still allow prompt to build (filter it out)."""
        tweet = make_sample_tweet(
            thread=["Tweet with weird media"],
            media=[
                {"type": "unknown_type", "url": "https://example.com/mystery", "alt_text": ""},
                {"type": "photo", "url": "https://example.com/valid.jpg", "alt_text": ""}
            ]
        )

        result = build_prompt(tweet)
        assert result is not None

        text_prompt, image_urls, has_quoted, tweet_id = result

        # Only photo should be in image_urls
        assert len(image_urls) == 1
        assert "https://example.com/valid.jpg" in image_urls


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
