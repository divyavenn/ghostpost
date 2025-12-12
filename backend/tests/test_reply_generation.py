"""
Tests for reply generation functionality.

Tests the LLM API connection and reply generation pipeline.
"""
import asyncio
import os

import pytest
from dotenv import load_dotenv

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from backend.config import OBELISK_KEY
from backend.twitter.generate_replies import ask_model, build_prompt, generate_replies_for_tweet
from backend.twitter.reply_prompt_builder import PROMPT_VARIANTS, get_prompt_builder


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


class TestObeliskAPIConnection:
    """Tests for the Obelisk LLM API connection."""

    def test_obelisk_key_configured(self):
        """OBELISK_KEY should be set in environment."""
        assert OBELISK_KEY is not None, "OBELISK_KEY environment variable is not set"
        assert len(OBELISK_KEY) > 0, "OBELISK_KEY is empty"
        print(f"✅ OBELISK_KEY is configured (length: {len(OBELISK_KEY)})")

    @pytest.mark.asyncio
    async def test_ask_model_simple_prompt(self):
        """Test that ask_model can successfully call the API."""
        if not OBELISK_KEY:
            pytest.skip("OBELISK_KEY not configured")

        response = await ask_model(
            prompt="Say 'hello' and nothing else.",
            model="chatgpt-4o",  # Use a model that exists on Obelisk
            target_handle="testuser",
            prompt_variant="minimal",
            username="test"
        )

        print(f"API Response: {response}")

        # Check response structure
        if "error" in response:
            pytest.fail(f"API returned error: {response['error']}")

        assert "message" in response, f"Response missing 'message' key: {response}"
        assert response["message"], f"Response message is empty: {response}"
        print(f"✅ API returned message: {response['message'][:100]}...")

    @pytest.mark.asyncio
    async def test_ask_model_with_different_models(self):
        """Test API with different model configurations."""
        if not OBELISK_KEY:
            pytest.skip("OBELISK_KEY not configured")

        models_to_test = [
            "chatgpt-4o",
            # Note: claude-3-5-sonnet-20241022 doesn't exist on Obelisk
        ]

        for model in models_to_test:
            print(f"\n--- Testing model: {model} ---")
            response = await ask_model(
                prompt="Respond with exactly one word: 'working'",
                model=model,
                target_handle="testuser",
                prompt_variant="minimal",
                username="test"
            )

            print(f"Response for {model}: {response}")

            if "error" in response:
                print(f"⚠️ Model {model} returned error: {response['error']}")
                # Don't fail - some models might not be available
                continue

            assert "message" in response, f"Response missing 'message' for {model}"
            print(f"✅ {model} returned: {response['message'][:50]}...")


class TestPromptVariants:
    """Tests for different prompt variants."""

    def test_all_prompt_variants_load(self):
        """All prompt variants should load without error."""
        for variant_name in PROMPT_VARIANTS.keys():
            builder = get_prompt_builder(variant_name)
            prompt = builder("testuser")
            assert prompt, f"Prompt variant '{variant_name}' returned empty"
            assert len(prompt) > 100, f"Prompt variant '{variant_name}' seems too short"
            print(f"✅ Variant '{variant_name}' loaded ({len(prompt)} chars)")

    def test_prompt_variants_include_target_handle(self):
        """Prompt variants should include the target handle."""
        target_handle = "divya_venn"
        for variant_name in PROMPT_VARIANTS.keys():
            builder = get_prompt_builder(variant_name)
            prompt = builder(target_handle)
            assert f"@{target_handle}" in prompt, f"Variant '{variant_name}' doesn't include target handle"
            print(f"✅ Variant '{variant_name}' includes @{target_handle}")


class TestGenerateRepliesForTweet:
    """Tests for the full reply generation pipeline."""

    @pytest.mark.asyncio
    async def test_generate_reply_for_simple_tweet(self):
        """Generate a reply for a simple tweet."""
        if not OBELISK_KEY:
            pytest.skip("OBELISK_KEY not configured")

        tweet = make_sample_tweet(
            thread=["I just discovered the best coffee shop in town. The atmosphere is incredible and the baristas really know their craft."],
            handle="coffeelover",
            username="Coffee Lover"
        )

        replies = await generate_replies_for_tweet(
            tweet=tweet,
            models=["chatgpt-4o"],  # Use a model that exists on Obelisk
            needed_generations=1,
            delay_seconds=0,
            batch=True,  # Don't raise critical errors
            username="test"
        )

        print(f"\n--- Generated replies: ---")
        for i, reply in enumerate(replies):
            print(f"Reply {i+1}: {reply}")

        assert len(replies) > 0, "No replies generated"

        # Check reply structure (should be tuple of reply_text, model, variant)
        reply_text, model, variant = replies[0]
        assert reply_text, "Reply text is empty"
        assert model, "Model name is empty"
        assert variant, "Variant name is empty"
        print(f"✅ Generated reply: {reply_text[:100]}...")
        print(f"   Model: {model}, Variant: {variant}")

    @pytest.mark.asyncio
    async def test_generate_reply_with_quoted_tweet(self):
        """Generate a reply for a tweet with quoted content."""
        if not OBELISK_KEY:
            pytest.skip("OBELISK_KEY not configured")

        tweet = make_sample_tweet(
            thread=["This is exactly what I've been saying!"],
            handle="agreeguy",
            username="Agree Guy",
            quoted_tweet={
                "text": "Hot take: remote work is better for productivity than office work.",
                "author_handle": "remoteworker",
                "author_name": "Remote Worker",
                "media": []
            }
        )

        replies = await generate_replies_for_tweet(
            tweet=tweet,
            models=["chatgpt-4o"],  # Use a model that exists on Obelisk
            needed_generations=1,
            delay_seconds=0,
            batch=True,
            username="test"
        )

        print(f"\n--- Generated replies for quoted tweet: ---")
        for i, reply in enumerate(replies):
            print(f"Reply {i+1}: {reply}")

        assert len(replies) > 0, "No replies generated for quoted tweet"
        reply_text, model, variant = replies[0]
        assert reply_text, "Reply text is empty"
        print(f"✅ Generated reply for quoted tweet: {reply_text[:100]}...")


class TestRawAPICall:
    """Test raw API call to diagnose connection issues."""

    @pytest.mark.asyncio
    async def test_raw_api_call(self):
        """Make a raw API call to Obelisk to check connectivity."""
        import httpx

        if not OBELISK_KEY:
            pytest.skip("OBELISK_KEY not configured")

        url = "https://obelisk.dread.technology/api/chat/completions"
        headers = {
            "Authorization": f"Bearer {OBELISK_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "chatgpt-4o",  # Use a model that exists on Obelisk
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say 'test successful' and nothing else."}
            ]
        }

        print(f"\n--- Raw API call to {url} ---")
        print(f"Headers: Authorization: Bearer {OBELISK_KEY[:10]}...")
        print(f"Payload: {payload}")

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            status = resp.status_code
            response_text = resp.text

            print(f"\nResponse status: {status}")
            print(f"Response body: {response_text[:500]}...")

            assert status == 200, f"API returned status {status}: {response_text}"

            import json
            data = json.loads(response_text)

            assert "choices" in data, f"Response missing 'choices': {data}"
            assert len(data["choices"]) > 0, f"Empty choices array: {data}"

            message = data["choices"][0]["message"]["content"]
            print(f"\n✅ Raw API call successful!")
            print(f"   Message: {message}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
