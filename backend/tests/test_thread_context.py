"""
Tests for get_thread_context function.
Verifies that thread context is built correctly with parent chain and media.
"""

import pytest
from unittest.mock import patch


# Test data: A comment with multiple parents in the chain
TEST_COMMENT = {
    "tweet_id": "1998770703634767906",
    "text": "@EyeDual @divya_venn Ok, yeah a lot of their songs were basically solo but they agreed to still credit each other. But, I was pretty sure many of them were still a team effort",
    "handle": "Rorywrite",
    "username": "Rory",
    "author_profile_pic_url": "https://pbs.twimg.com/profile_images/1786849157220556800/wkcszw6d_400x400.jpg",
    "followers": 1371,
    "likes": 0,
    "retweets": 0,
    "quotes": 0,
    "replies": 0,
    "impressions": 25,
    "created_at": "2025-12-10T15:04:05+00:00",
    "url": "https://x.com/Rorywrite/status/1998770703634767906",
    "parent_chain": [
        "1998510228602851514",  # Original post by user (divya_venn)
        "1998530617500451256",  # First reply (EyeDual)
        "1998582940796952629"   # Second reply (divya_venn replying to EyeDual)
    ],
    "in_reply_to_status_id": "1998582940796952629",
    "status": "pending",
    "generated_replies": [
        [
            "totally, the best collaborations are almost always someone running with their spark and then looping in the other person to elevate it.",
            "divya-upgraded-g"
        ]
    ],
    "edited": False,
    "media": []
}

# User's original post (first in parent_chain)
TEST_POSTED_TWEET_ORIGINAL = {
    "tweet_id": "1998510228602851514",
    "text": "Hot take: The Beatles weren't really a band, they were four solo artists who happened to share a name",
    "handle": "divya_venn",
    "username": "divya",
    "author_profile_pic_url": "https://example.com/divya.jpg",
    "responding_to": "divya_venn",
    "replying_to_pfp": "https://example.com/divya.jpg",
    "media": [
        {"type": "photo", "url": "https://example.com/beatles.jpg", "alt_text": "Beatles album cover"}
    ]
}

# User's reply to EyeDual (third in parent_chain)
TEST_POSTED_TWEET_REPLY = {
    "tweet_id": "1998582940796952629",
    "text": "@EyeDual That's fair! I was being hyperbolic but you're right they did collaborate",
    "handle": "divya_venn",
    "username": "divya",
    "author_profile_pic_url": "https://example.com/divya.jpg",
    "responding_to": "EyeDual",
    "replying_to_pfp": "https://example.com/eyedual.jpg",
    "media": []  # No media on this reply
}

# Intermediate comment from EyeDual (second in parent_chain)
TEST_INTERMEDIATE_COMMENT = {
    "tweet_id": "1998530617500451256",
    "text": "@divya_venn I disagree - they clearly wrote songs together and collaborated on arrangements",
    "handle": "EyeDual",
    "username": "Eye Dual",
    "author_profile_pic_url": "https://example.com/eyedual.jpg",
    "media": [
        {"type": "photo", "url": "https://example.com/lennon_mccartney.jpg", "alt_text": "Lennon and McCartney writing"}
    ]
}


def test_get_thread_context_with_multiple_parents():
    """
    Test that get_thread_context returns the full parent chain with media.

    Parent chain: original_post -> eyedual_reply -> divya_reply -> rory_comment

    Expected thread_context should include all 4 tweets in order:
    1. Original post (user's)
    2. EyeDual's reply
    3. Divya's reply to EyeDual
    4. Rory's comment (the current tweet)
    """
    from backend.data.twitter.comments_cache import get_thread_context

    # Mock posted_tweets cache (user's tweets)
    mock_posted_tweets = {
        "_order": ["1998582940796952629", "1998510228602851514"],
        "1998510228602851514": TEST_POSTED_TWEET_ORIGINAL,
        "1998582940796952629": TEST_POSTED_TWEET_REPLY,
    }

    # Mock comments cache (includes intermediate comments and the target comment)
    mock_comments = {
        "_order": ["1998770703634767906", "1998530617500451256"],
        "1998530617500451256": TEST_INTERMEDIATE_COMMENT,
        "1998770703634767906": TEST_COMMENT,
    }

    with patch("backend.data.twitter.comments_cache.read_comments_cache", return_value=mock_comments):
        with patch("backend.data.twitter.posted_tweets_cache.read_posted_tweets_cache", return_value=mock_posted_tweets):
            thread_context = get_thread_context("1998770703634767906", "divya_venn")

    # Should have 4 items: original post, eyedual reply, divya reply, rory comment
    assert len(thread_context) == 4, f"Expected 4 items in thread context, got {len(thread_context)}"

    # Verify order: root -> current
    assert thread_context[0]["tweet_id"] == "1998510228602851514", "First should be original post"
    assert thread_context[1]["tweet_id"] == "1998530617500451256", "Second should be EyeDual's reply"
    assert thread_context[2]["tweet_id"] == "1998582940796952629", "Third should be divya's reply"
    assert thread_context[3]["tweet_id"] == "1998770703634767906", "Fourth should be Rory's comment"

    # Verify media is included
    assert thread_context[0]["media"] == TEST_POSTED_TWEET_ORIGINAL["media"], "Original post should have media"
    assert thread_context[1]["media"] == TEST_INTERMEDIATE_COMMENT["media"], "EyeDual's reply should have media"
    assert thread_context[2]["media"] == [], "Divya's reply should have empty media"
    assert thread_context[3]["media"] == [], "Rory's comment should have empty media"

    # Verify is_user flags
    assert thread_context[0]["is_user"] == True, "Original post is by user"
    assert thread_context[1]["is_user"] == False, "EyeDual's reply is not by user"
    assert thread_context[2]["is_user"] == True, "Divya's reply is by user"
    assert thread_context[3]["is_user"] == False, "Rory's comment is not by user"


def test_get_thread_context_handles_deleted_ancestor():
    """
    Test that get_thread_context handles missing/deleted tweets in parent chain.
    """
    from backend.data.twitter.comments_cache import get_thread_context

    # Mock posted_tweets cache - missing the intermediate tweet
    mock_posted_tweets = {
        "_order": ["1998510228602851514"],
        "1998510228602851514": TEST_POSTED_TWEET_ORIGINAL,
        # Missing: 1998582940796952629 (divya's reply)
    }

    # Mock comments cache - missing EyeDual's comment
    mock_comments = {
        "_order": ["1998770703634767906"],
        # Missing: 1998530617500451256 (EyeDual's reply)
        "1998770703634767906": TEST_COMMENT,
    }

    with patch("backend.data.twitter.comments_cache.read_comments_cache", return_value=mock_comments):
        with patch("backend.data.twitter.posted_tweets_cache.read_posted_tweets_cache", return_value=mock_posted_tweets):
            thread_context = get_thread_context("1998770703634767906", "divya_venn")

    # Should still have 4 items, but 2 marked as deleted
    assert len(thread_context) == 4

    # First item should be found (original post) - no "deleted" key
    assert thread_context[0].get("deleted") is not True
    assert thread_context[0]["text"] == TEST_POSTED_TWEET_ORIGINAL["text"]

    # Second item (EyeDual's reply) should be marked deleted
    assert thread_context[1].get("deleted") == True
    assert thread_context[1]["text"] == "<tweet deleted>"
    assert thread_context[1]["media"] == []

    # Third item (divya's reply) should be marked deleted
    assert thread_context[2].get("deleted") == True
    assert thread_context[2]["text"] == "<tweet deleted>"

    # Fourth item (current comment) should be found - no "deleted" key
    assert thread_context[3].get("deleted") is not True
    assert thread_context[3]["text"] == TEST_COMMENT["text"]


def test_frontend_filtering_logic():
    """
    Test the frontend filtering logic that excludes:
    1. The original post (shown in PostSection)
    2. The current comment (shown below thread context)

    This simulates what the React component does with filteredThreadContext.
    """
    from backend.data.twitter.comments_cache import get_thread_context

    mock_posted_tweets = {
        "_order": ["1998582940796952629", "1998510228602851514"],
        "1998510228602851514": TEST_POSTED_TWEET_ORIGINAL,
        "1998582940796952629": TEST_POSTED_TWEET_REPLY,
    }

    mock_comments = {
        "_order": ["1998770703634767906", "1998530617500451256"],
        "1998530617500451256": TEST_INTERMEDIATE_COMMENT,
        "1998770703634767906": TEST_COMMENT,
    }

    with patch("backend.data.twitter.comments_cache.read_comments_cache", return_value=mock_comments):
        with patch("backend.data.twitter.posted_tweets_cache.read_posted_tweets_cache", return_value=mock_posted_tweets):
            thread_context = get_thread_context("1998770703634767906", "divya_venn")

    # Simulate frontend filtering (from CommentDisplay.tsx)
    original_post_id = "1998510228602851514"
    current_comment_id = "1998770703634767906"

    filtered_thread_context = [
        ctx for ctx in thread_context
        if ctx["tweet_id"] != original_post_id and ctx["tweet_id"] != current_comment_id
    ]

    # Should have 2 items: EyeDual's reply and divya's reply
    assert len(filtered_thread_context) == 2, f"Expected 2 items after filtering, got {len(filtered_thread_context)}"

    # Verify the filtered items are the intermediate replies
    assert filtered_thread_context[0]["tweet_id"] == "1998530617500451256", "First should be EyeDual's reply"
    assert filtered_thread_context[0]["handle"] == "EyeDual"
    assert filtered_thread_context[0]["media"] == TEST_INTERMEDIATE_COMMENT["media"]

    assert filtered_thread_context[1]["tweet_id"] == "1998582940796952629", "Second should be divya's reply"
    assert filtered_thread_context[1]["handle"] == "divya_venn"
    assert filtered_thread_context[1]["is_user"] == True


def test_comment_prompt_format():
    """
    Test that build_comment_prompt produces the expected format:

    You are @divya_venn. This is a discussion under something you posted...

    Original post:
    Controversial opinion: tabs are better than spaces.

    ---

    first_person (25k followers):

    @divya_venn you're absolutely right about this! What's your take on the counterargument though?

    ---

    second_person (25k followers):

    @first_person @divya_venn ...
    """
    from backend.twitter.comment_replies import build_comment_prompt

    # Thread context: original post -> first_person's reply
    thread_context = [
        {
            "tweet_id": "original_post_id",
            "text": "Controversial opinion: tabs are better than spaces.",
            "handle": "divya_venn",
            "username": "divya",
            "is_user": True,
            "media": [],
            "followers": 5000
        },
        {
            "tweet_id": "first_reply_id",
            "text": "@divya_venn you're absolutely right about this! What's your take on the counterargument though?",
            "handle": "first_person",
            "username": "First Person",
            "is_user": False,
            "media": [],
            "followers": 25000
        },
        {
            "tweet_id": "comment_id",
            "text": "@first_person @divya_venn here's my take on the counterargument...",
            "handle": "second_person",
            "username": "Second Person",
            "is_user": False,
            "media": [],
            "followers": 25000
        }
    ]

    # The comment we're replying to (same as last in thread_context)
    comment = {
        "tweet_id": "comment_id",
        "text": "@first_person @divya_venn here's my take on the counterargument...",
        "handle": "second_person",
        "username": "Second Person",
        "followers": 25000,
        "media": [],
        "quoted_tweet": None,
        "other_replies": []
    }

    prompt, images = build_comment_prompt(comment, thread_context, user_handle="divya_venn")

    print(prompt)
    
    # Verify the prompt structure
    assert "You are @divya_venn" in prompt
    assert "This is a discussion under something you posted" in prompt

    # Verify original post format
    assert "Original post:" in prompt
    assert "Controversial opinion: tabs are better than spaces." in prompt

    # Verify first_person's reply format (with follower count)
    assert "first_person (25k followers):" in prompt
    assert "@divya_venn you're absolutely right" in prompt

    # Verify second_person's comment format
    assert "second_person (25k followers):" in prompt
    assert "@first_person @divya_venn here's my take" in prompt

    # Verify dividers
    assert "---" in prompt

    # Verify ending
    assert "Write your reply to this comment:" in prompt


def test_comment_prompt_with_rory_example():
    """
    Test with the actual Rory comment example from the codebase.
    """
    from backend.twitter.comment_replies import build_comment_prompt

    # Thread context based on real data
    thread_context = [
        {
            "tweet_id": "1998510228602851514",
            "text": "Hot take: The Beatles weren't really a band, they were four solo artists who happened to share a name",
            "handle": "divya_venn",
            "username": "divya",
            "is_user": True,
            "media": [{"type": "photo", "url": "https://example.com/beatles.jpg"}],
            "followers": 5000
        },
        {
            "tweet_id": "1998530617500451256",
            "text": "@divya_venn I disagree - they clearly wrote songs together and collaborated on arrangements",
            "handle": "EyeDual",
            "username": "Eye Dual",
            "is_user": False,
            "media": [],
            "followers": 2500
        },
        {
            "tweet_id": "1998582940796952629",
            "text": "@EyeDual That's fair! I was being hyperbolic but you're right they did collaborate",
            "handle": "divya_venn",
            "username": "divya",
            "is_user": True,
            "media": [],
            "followers": 5000
        },
        {
            "tweet_id": "1998770703634767906",
            "text": "@EyeDual @divya_venn Ok, yeah a lot of their songs were basically solo but they agreed to still credit each other. But, I was pretty sure many of them were still a team effort",
            "handle": "Rorywrite",
            "username": "Rory",
            "is_user": False,
            "media": [],
            "followers": 1371
        }
    ]

    comment = {
        "tweet_id": "1998770703634767906",
        "text": "@EyeDual @divya_venn Ok, yeah a lot of their songs were basically solo but they agreed to still credit each other. But, I was pretty sure many of them were still a team effort",
        "handle": "Rorywrite",
        "username": "Rory",
        "followers": 1371,
        "media": [],
        "quoted_tweet": None,
        "other_replies": []
    }

    prompt, images = build_comment_prompt(comment, thread_context, user_handle="divya_venn")

    # Verify structure
    assert "You are @divya_venn" in prompt

    # Original post
    assert "Original post:" in prompt
    assert "Hot take: The Beatles" in prompt

    # EyeDual's reply
    assert "EyeDual (2.5k followers):" in prompt
    assert "@divya_venn I disagree" in prompt

    # divya's reply to EyeDual - should NOT have "Original post:" label
    assert "divya_venn" in prompt
    assert "@EyeDual That's fair!" in prompt

    # Rory's comment
    assert "Rorywrite (1.4k followers):" in prompt or "Rorywrite (1371 followers):" in prompt
    assert "@EyeDual @divya_venn Ok, yeah" in prompt

    # Should have image from original post
    assert len(images) == 1
    assert images[0] == "https://example.com/beatles.jpg"


def test_direct_reply_has_no_intermediate_context():
    """
    Test that a direct reply to the original post has no intermediate context after filtering.
    """
    from backend.data.twitter.comments_cache import get_thread_context

    # A comment that replies directly to the original post (no intermediate tweets)
    direct_reply_comment = {
        **TEST_COMMENT,
        "tweet_id": "direct_reply_id",
        "parent_chain": ["1998510228602851514"],  # Only the original post
        "in_reply_to_status_id": "1998510228602851514",
    }

    mock_posted_tweets = {
        "_order": ["1998510228602851514"],
        "1998510228602851514": TEST_POSTED_TWEET_ORIGINAL,
    }

    mock_comments = {
        "_order": ["direct_reply_id"],
        "direct_reply_id": direct_reply_comment,
    }

    with patch("backend.data.twitter.comments_cache.read_comments_cache", return_value=mock_comments):
        with patch("backend.data.twitter.posted_tweets_cache.read_posted_tweets_cache", return_value=mock_posted_tweets):
            thread_context = get_thread_context("direct_reply_id", "divya_venn")

    # Should have 2 items: original post and the direct reply
    assert len(thread_context) == 2

    # Simulate frontend filtering
    original_post_id = "1998510228602851514"
    current_comment_id = "direct_reply_id"

    filtered_thread_context = [
        ctx for ctx in thread_context
        if ctx["tweet_id"] != original_post_id and ctx["tweet_id"] != current_comment_id
    ]

    # Should be empty - no intermediate context to show
    assert len(filtered_thread_context) == 0, "Direct reply should have no intermediate context"
