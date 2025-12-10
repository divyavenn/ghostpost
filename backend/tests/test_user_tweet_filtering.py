"""
Test that scrape_user_recent_tweets correctly filters out tweets from other users.

This test verifies that:
1. Only tweets authored by the target user are captured
2. Tweets that the user replied to (from other users) are not captured
3. The target_user_id filtering works correctly
"""
import pytest


@pytest.fixture
def test_username():
    """The test user's cache key."""
    return "divya_venn"


@pytest.fixture
def test_handle():
    """The test user's Twitter handle."""
    return "divya_venn"


class TestUserTweetFiltering:
    """Test that tweet filtering correctly identifies user's own tweets."""

    @pytest.mark.asyncio
    async def test_only_captures_user_tweets(self, browser_context, test_handle):
        """
        Verify that scrape_user_recent_tweets only captures tweets authored by the target user.

        This test scrapes the user's profile and verifies:
        1. All captured tweets have the user's handle
        2. Tweets from users the target replied to are NOT captured
        """
        from backend.browser_automation.twitter.api import scrape_user_recent_tweets

        # Scrape recent tweets
        tweets = await scrape_user_recent_tweets(browser_context, test_handle, max_tweets=20)

        assert len(tweets) > 0, "Should have found at least some tweets"

        # Verify ALL captured tweets are from the target user
        for tweet in tweets:
            tweet_handle = tweet.get("handle", "").lower()
            # The handle should match the target user
            assert tweet_handle == test_handle.lower(), \
                f"Tweet {tweet['id']} has handle @{tweet_handle}, expected @{test_handle}. " \
                f"Text: {tweet.get('text', '')[:100]}"

            # For debugging
            print(f"✓ Tweet {tweet['id']}: @{tweet_handle} - {tweet.get('text', '')[:50]}...")

        print(f"\n✅ All {len(tweets)} captured tweets are from @{test_handle}")

    @pytest.mark.asyncio
    async def test_replies_have_in_reply_to_set(self, browser_context, test_handle):
        """
        Verify that replies have in_reply_to_status_id set correctly.

        When a tweet is a reply, it should have in_reply_to_status_id pointing
        to the parent tweet (which is NOT captured, just referenced).
        """
        from backend.browser_automation.twitter.api import scrape_user_recent_tweets

        tweets = await scrape_user_recent_tweets(browser_context, test_handle, max_tweets=20)

        replies = [t for t in tweets if t.get("in_reply_to_status_id")]
        original_tweets = [t for t in tweets if not t.get("in_reply_to_status_id")]

        print(f"📊 Found {len(replies)} replies and {len(original_tweets)} original tweets")

        # Verify replies have proper in_reply_to_status_id
        for reply in replies[:5]:  # Check first 5 replies
            in_reply_to = reply.get("in_reply_to_status_id")
            assert in_reply_to, f"Reply {reply['id']} missing in_reply_to_status_id"
            assert in_reply_to != reply["id"], "in_reply_to_status_id should not equal tweet id"
            print(f"  Reply {reply['id']} -> in_reply_to: {in_reply_to}")

        print(f"✅ Reply structure verified")

    @pytest.mark.asyncio
    async def test_does_not_capture_parent_tweets(self, browser_context, test_handle):
        """
        Verify that parent tweets (tweets user replied to) are NOT captured.

        When viewing the "with_replies" tab, Twitter shows both:
        - The user's replies
        - The tweets the user replied to (from OTHER users)

        We should ONLY capture the user's tweets, not the parent tweets.
        """
        from backend.browser_automation.twitter.api import scrape_user_recent_tweets

        tweets = await scrape_user_recent_tweets(browser_context, test_handle, max_tweets=30)

        # Get all in_reply_to IDs (these are parent tweet IDs)
        parent_ids = {t.get("in_reply_to_status_id") for t in tweets if t.get("in_reply_to_status_id")}
        captured_ids = {t.get("id") for t in tweets}

        # Parent tweet IDs should NOT be in captured tweets
        # (unless the user replied to their own tweet)
        wrongly_captured = parent_ids & captured_ids

        # Filter out self-replies (user replying to their own tweets)
        for tweet in tweets:
            if tweet["id"] in wrongly_captured:
                # This might be a self-reply (user replying to their own tweet) - that's OK
                if tweet.get("handle", "").lower() == test_handle.lower():
                    wrongly_captured.discard(tweet["id"])

        assert len(wrongly_captured) == 0, \
            f"Parent tweets from other users were incorrectly captured: {wrongly_captured}"

        print(f"✅ No parent tweets from other users were captured")
        print(f"   Parent IDs referenced: {len(parent_ids)}")
        print(f"   Tweets captured: {len(captured_ids)}")


class TestSpecificReplyContext:
    """
    Test with a specific known tweet to verify reply context is captured correctly.

    Original tweet: https://x.com/animalologist/status/1995502685651718290
    - Author: @animalologist (taco belle)
    - Text: "why r people bookmarking this 🥺🥹"

    Reply: https://x.com/divya_venn/status/1995697049984270837
    - Author: @divya_venn
    - Text: "Because it's beautiful and relatable"
    """

    ORIGINAL_TWEET_ID = "1995502685651718290"
    ORIGINAL_AUTHOR = "animalologist"
    REPLY_TWEET_ID = "1995697049984270837"
    REPLY_AUTHOR = "divya_venn"

    @pytest.mark.asyncio
    async def test_reply_captured_with_correct_in_reply_to(self, browser_context, test_handle):
        """
        Verify that divya_venn's reply is captured with correct in_reply_to_status_id
        pointing to the @animalologist tweet.
        """
        from backend.browser_automation.twitter.api import scrape_user_recent_tweets

        tweets = await scrape_user_recent_tweets(browser_context, test_handle, max_tweets=50)

        # Find the specific reply
        reply = next((t for t in tweets if t.get("id") == self.REPLY_TWEET_ID), None)

        assert reply is not None, f"Reply {self.REPLY_TWEET_ID} should be captured"
        assert reply.get("handle", "").lower() == self.REPLY_AUTHOR.lower(), \
            f"Reply should be from @{self.REPLY_AUTHOR}"
        assert "beautiful and relatable" in reply.get("text", "").lower(), \
            f"Reply text should contain 'beautiful and relatable'"

        # Verify in_reply_to points to the original tweet
        assert reply.get("in_reply_to_status_id") == self.ORIGINAL_TWEET_ID, \
            f"in_reply_to_status_id should be {self.ORIGINAL_TWEET_ID}, got {reply.get('in_reply_to_status_id')}"

        print(f"✅ Reply {self.REPLY_TWEET_ID} correctly points to original {self.ORIGINAL_TWEET_ID}")

    @pytest.mark.asyncio
    async def test_original_tweet_not_captured_as_user_tweet(self, browser_context, test_handle):
        """
        Verify that the original @animalologist tweet is NOT captured as divya_venn's tweet.
        """
        from backend.browser_automation.twitter.api import scrape_user_recent_tweets

        tweets = await scrape_user_recent_tweets(browser_context, test_handle, max_tweets=50)

        # The original tweet should NOT be in the captured tweets
        original = next((t for t in tweets if t.get("id") == self.ORIGINAL_TWEET_ID), None)

        assert original is None, \
            f"Original tweet {self.ORIGINAL_TWEET_ID} from @{self.ORIGINAL_AUTHOR} should NOT be captured as @{test_handle}'s tweet"

        print(f"✅ Original tweet {self.ORIGINAL_TWEET_ID} correctly NOT captured")

    @pytest.mark.asyncio
    async def test_original_tweet_context_fetched_for_reply(self, browser_context):
        """
        Verify that when processing a reply, we can fetch the original tweet's context
        (text, author handle, profile pic) using get_thread.
        """
        from backend.browser_automation.twitter.api import get_thread

        original_url = f"https://x.com/i/status/{self.ORIGINAL_TWEET_ID}"

        thread_result = await get_thread(browser_context, original_url, root_id=self.ORIGINAL_TWEET_ID)

        assert thread_result is not None, "Should be able to fetch original tweet context"

        # Verify author info
        author_handle = thread_result.get("author_handle", "").lower()
        assert author_handle == self.ORIGINAL_AUTHOR.lower(), \
            f"Author should be @{self.ORIGINAL_AUTHOR}, got @{author_handle}"

        # Verify thread text contains the original tweet
        thread_texts = thread_result.get("thread", [])
        assert len(thread_texts) > 0, "Thread should have at least one message"

        # The original tweet text should be in the thread
        full_thread_text = " ".join(thread_texts).lower()
        assert "bookmarking" in full_thread_text or "why r people" in full_thread_text, \
            f"Thread should contain original tweet text, got: {thread_texts}"

        # Verify profile pic URL is present
        assert thread_result.get("author_profile_pic_url"), "Should have author profile pic URL"

        print(f"✅ Original tweet context fetched successfully:")
        print(f"   Author: @{thread_result.get('author_handle')}")
        print(f"   Thread: {thread_texts[:1]}...")  # First message
        print(f"   Profile pic: {thread_result.get('author_profile_pic_url', '')[:50]}...")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
