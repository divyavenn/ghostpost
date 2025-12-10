"""
Test that verifies the LLM can actually see and understand images in tweets.

This test fetches a tweet with an image and asks the LLM to describe it,
rather than generate a reply. This confirms images are being sent correctly.
"""

import pytest


@pytest.mark.asyncio
@pytest.mark.slow
async def test_llm_can_describe_tweet_image(browser_context):
    """
    Test that the LLM receives and understands images from tweets.

    Tweet: https://x.com/WholesomeMeme/status/1997297551792345490
    This tweet has an image. We ask the LLM to describe what it sees
    to verify the image is being processed correctly.
    """
    from backend.config import OBELISK_KEY, TEST_USER
    from backend.browser_automation.twitter.api import (
        _build_user_map,
        _get_tweet_by_id,
        _tweet_to_dict,
        get_thread,
    )
    from backend.twitter.authentication import ensure_access_token
    from backend.twitter.rate_limiter import LLM_OBELISK, call_api

    test_tweet_id = "1997297551792345490"
    test_url = f"https://x.com/WholesomeMeme/status/{test_tweet_id}"

    # Skip if no API key
    if not OBELISK_KEY:
        pytest.skip("OBELISK_KEY not configured")

    # Get access token
    access_token = await ensure_access_token(TEST_USER)
    if not access_token:
        pytest.skip("No access token available")

    # Fetch the tweet
    response = await _get_tweet_by_id(access_token, test_tweet_id)

    data = response.get("data")
    if not data:
        pytest.skip(f"Tweet {test_tweet_id} not found - may be rate limited or deleted")

    includes = response.get("includes", {})
    user_map = _build_user_map(includes)

    # Convert to dict format
    tweet_dict = _tweet_to_dict(data, user_map, includes)

    # Get thread data (which includes media)
    thread_data = await get_thread(browser_context, test_url, root_id=test_tweet_id)
    tweet_dict["thread"] = thread_data.get("thread", [])
    tweet_dict["other_replies"] = thread_data.get("other_replies", [])
    if thread_data.get("media"):
        tweet_dict["media"] = thread_data["media"]

    # Extract image URLs
    image_urls = [m["url"] for m in tweet_dict.get("media", []) if m.get("type") == "photo"]

    print(f"\n{'='*60}")
    print(f"Tweet ID: {test_tweet_id}")
    print(f"Tweet text: {tweet_dict.get('text', '')[:200]}...")
    print(f"Images found: {len(image_urls)}")
    for i, url in enumerate(image_urls):
        print(f"  Image {i+1}: {url[:80]}...")
    print(f"{'='*60}\n")

    # If no images, the test can't verify image understanding
    if not image_urls:
        pytest.skip("Tweet has no images - cannot test image understanding")

    # Build a custom prompt that asks for description instead of reply
    description_prompt = f"""Please describe what you see in this tweet.

Tweet text: {tweet_dict.get('text', '')}

The tweet contains {len(image_urls)} image(s). Please describe:
1. What is shown in the image(s)?
2. What is the mood or tone of the image?
3. How does the image relate to the tweet text?

Be specific about visual details you can see."""

    # Build multimodal message content
    user_content = [{"type": "text", "text": description_prompt}]
    for img_url in image_urls:
        user_content.append({"type": "image_url", "image_url": {"url": img_url}})

    # Make LLM call
    url = "https://obelisk.dread.technology/api/chat/completions"
    headers = {"Authorization": f"Bearer {OBELISK_KEY}", "Content-Type": "application/json"}

    # Use a vision-capable model
    model = "chatgpt-4o"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant that describes images accurately."},
            {"role": "user", "content": user_content}
        ]
    }

    print(f"Sending request to LLM with {len(image_urls)} image(s)...")
    print(f"Model: {model}")

    response = await call_api(
        method="POST",
        url=url,
        bucket=LLM_OBELISK,
        headers=headers,
        json_data=payload,
        username=TEST_USER
    )

    assert response.success, f"LLM API call failed: {response.error_message}"

    # Extract the description
    result = response.data
    description = result.get("choices", [{}])[0].get("message", {}).get("content", "")

    print(f"\n{'='*60}")
    print("LLM DESCRIPTION OF TWEET:")
    print(f"{'='*60}")
    print(description)
    print(f"{'='*60}\n")

    # Verify we got a meaningful description
    assert description, "LLM returned empty description"
    assert len(description) > 50, "Description seems too short to be meaningful"

    # The description should mention visual elements if the LLM actually saw the image
    # We can't predict exact content, but it shouldn't be a generic "I cannot see images" response
    cannot_see_phrases = [
        "cannot see",
        "can't see",
        "unable to see",
        "no image",
        "don't have access",
        "cannot view",
        "can't view"
    ]

    description_lower = description.lower()
    for phrase in cannot_see_phrases:
        assert phrase not in description_lower, f"LLM says it cannot see images: found '{phrase}'"

    print("✅ LLM successfully described the image content!")


@pytest.mark.asyncio
@pytest.mark.slow
async def test_build_prompt_includes_images(browser_context):
    """
    Test that build_prompt correctly extracts and includes image URLs.
    """
    from backend.config import TEST_USER
    from backend.data.twitter.data_validation import MediaItem, ScrapedTweet
    from backend.twitter.generate_replies import build_prompt

    # Create a mock tweet with images
    mock_tweet = ScrapedTweet(
        id="123456789",
        text="Check out this cool photo!",
        thread=["Check out this cool photo!"],
        cache_id="test-cache-id",
        created_at="2024-01-01T12:00:00Z",
        url="https://x.com/test/status/123456789",
        username="Test User",
        handle="testuser",
        author_profile_pic_url="https://example.com/pic.jpg",
        likes=100,
        retweets=50,
        quotes=10,
        replies=20,
        followers=1000,
        score=200,
        media=[
            MediaItem(type="photo", url="https://pbs.twimg.com/media/test1.jpg", alt_text="A beautiful sunset"),
            MediaItem(type="photo", url="https://pbs.twimg.com/media/test2.jpg", alt_text="Mountains"),
            MediaItem(type="video", url="https://video.twimg.com/test.mp4", alt_text=""),  # Should be filtered out
        ]
    )

    result = build_prompt(mock_tweet)

    assert result is not None, "build_prompt returned None"

    text_prompt, image_urls, has_quoted, tweet_id = result

    # Should have 2 images (photos only, not video)
    assert len(image_urls) == 2, f"Expected 2 images, got {len(image_urls)}"
    assert "https://pbs.twimg.com/media/test1.jpg" in image_urls
    assert "https://pbs.twimg.com/media/test2.jpg" in image_urls
    assert "https://video.twimg.com/test.mp4" not in image_urls

    # Alt text should be included in prompt
    assert "A beautiful sunset" in text_prompt, "Alt text should be in prompt"
    assert "Mountains" in text_prompt, "Alt text should be in prompt"

    print(f"\n✅ build_prompt correctly extracted {len(image_urls)} images")
    print(f"Image URLs: {image_urls}")
    print(f"Text prompt includes alt text: Yes")
