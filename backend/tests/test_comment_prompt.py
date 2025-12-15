"""
Test for build_comment_prompt to visualize what's passed to the LLM.

Run with: pytest tests/test_comment_prompt.py -v -s
"""

import pytest


def test_build_comment_prompt_output():
    """
    Print out what build_comment_prompt generates for the LLM.
    This helps debug and visualize the prompt structure.
    """
    from backend.twitter.comment_replies import build_comment_prompt

    # Sample comment (someone replying to the user's tweet)
    sample_comment = {
        "id": "1234567890",
        "text": "@divya_venn this is such a great point! I've been thinking about this too.",
        "handle": "commenter_handle",
        "username": "Friendly Commenter",
        "author_profile_pic_url": "https://example.com/pic.jpg",
        "followers": 5000,
        "likes": 15,
        "retweets": 2,
        "quotes": 0,
        "replies": 1,
        "created_at": "2025-01-15T10:30:00+00:00",
        "url": "https://x.com/commenter_handle/status/1234567890",
        "media": [],
        "quoted_tweet": None,
        "other_replies": [
            {
                "author_handle": "another_user",
                "author_name": "Another User",
                "text": "Agreed! This is important.",
                "likes": 5
            }
        ]
    }

    # Sample thread context (user's original tweet + any intermediate replies)
    sample_thread_context = [
        {
            "id": "1111111111",
            "text": "Hot take: the best way to learn is to build in public. Share your progress, get feedback, iterate.",
            "handle": "divya_venn",
            "username": "Divya",
            "author_profile_pic_url": "https://example.com/divya.jpg",
            "is_user": True,
            "media": []
        },
        {
            "id": "2222222222",
            "text": "Adding to this - vulnerability is key. Don't just show wins, show struggles too.",
            "handle": "divya_venn",
            "username": "Divya",
            "author_profile_pic_url": "https://example.com/divya.jpg",
            "is_user": True,
            "media": []
        },
        # The comment itself (will be excluded from context but shown separately)
        sample_comment
    ]

    # Build the prompt with user's handle
    text_prompt, image_urls = build_comment_prompt(
        comment=sample_comment,
        thread_context=sample_thread_context,
        user_handle="divya_venn"
    )

    print("\n" + "=" * 80)
    print("WHAT GETS PASSED TO THE LLM FOR COMMENT REPLY")
    print("=" * 80)
    print("\n--- TEXT PROMPT ---\n")
    print(text_prompt)
    print("\n--- IMAGE URLS ---\n")
    print(image_urls if image_urls else "(none)")
    print("\n" + "=" * 80)

    # Basic assertions
    assert "[YOUR HANDLE: @divya_venn]" in text_prompt, "Should include user's handle"
    assert "[CONVERSATION CONTEXT]" in text_prompt, "Should have conversation context section"
    assert "[COMMENT from @commenter_handle" in text_prompt, "Should show commenter"
    assert "this is such a great point" in text_prompt, "Should include comment text"


def test_build_comment_prompt_with_quoted_tweet():
    """
    Test prompt when the comment includes a quoted tweet.
    """
    from backend.twitter.comment_replies import build_comment_prompt

    sample_comment = {
        "id": "9999999999",
        "text": "This reminds me of what @elonmusk said",
        "handle": "quoter",
        "username": "Quote Tweeter",
        "followers": 1000,
        "likes": 3,
        "retweets": 0,
        "quotes": 0,
        "replies": 0,
        "created_at": "2025-01-15T12:00:00+00:00",
        "url": "https://x.com/quoter/status/9999999999",
        "media": [],
        "quoted_tweet": {
            "text": "The future is bright for AI",
            "author_handle": "elonmusk",
            "author_name": "Elon Musk",
            "media": []
        },
        "other_replies": []
    }

    sample_thread_context = [
        {
            "id": "0000000000",
            "text": "What do you think about the future of AI?",
            "handle": "divya_venn",
            "username": "Divya",
            "is_user": True,
            "media": []
        },
        sample_comment
    ]

    text_prompt, image_urls = build_comment_prompt(
        comment=sample_comment,
        thread_context=sample_thread_context,
        user_handle="divya_venn"
    )

    print("\n" + "=" * 80)
    print("PROMPT WITH QUOTED TWEET")
    print("=" * 80)
    print("\n--- TEXT PROMPT ---\n")
    print(text_prompt)
    print("\n" + "=" * 80)

    assert "[Comment quotes @elonmusk" in text_prompt, "Should show quoted tweet"


def test_build_comment_prompt_direct_mention():
    """
    Test that the prompt helps LLM understand when user is addressed directly.
    """
    from backend.twitter.comment_replies import build_comment_prompt

    # Comment that directly mentions the user
    sample_comment = {
        "id": "5555555555",
        "text": "@divya_venn you're absolutely right about this! What's your take on the counterargument though?",
        "handle": "curious_person",
        "username": "Curious Person",
        "followers": 2500,
        "likes": 8,
        "retweets": 0,
        "quotes": 0,
        "replies": 0,
        "created_at": "2025-01-15T14:00:00+00:00",
        "url": "https://x.com/curious_person/status/5555555555",
        "media": [],
        "quoted_tweet": None,
        "other_replies": []
    }

    sample_thread_context = [
        {
            "id": "4444444444",
            "text": "Controversial opinion: tabs are better than spaces.",
            "handle": "divya_venn",
            "username": "Divya",
            "is_user": True,
            "media": []
        },
        sample_comment
    ]

    text_prompt, _ = build_comment_prompt(
        comment=sample_comment,
        thread_context=sample_thread_context,
        user_handle="divya_venn"
    )

    print("\n" + "=" * 80)
    print("PROMPT WITH DIRECT USER MENTION")
    print("=" * 80)
    print("\n--- TEXT PROMPT ---\n")
    print(text_prompt)
    print("\n" + "=" * 80)

    # Verify the prompt explains the user's handle
    assert "When someone mentions @divya_venn, they are addressing YOU directly" in text_prompt
    assert "[YOU (@divya_venn)]" in text_prompt, "Should show user's handle with YOU label"


if __name__ == "__main__":
    # Run tests directly for quick debugging
    test_build_comment_prompt_output()
    test_build_comment_prompt_with_quoted_tweet()
    test_build_comment_prompt_direct_mention()
