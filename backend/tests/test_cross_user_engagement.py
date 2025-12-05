"""
End-to-end tests for cross-user engagement flow.

Tests the complete posting, commenting, and reply workflow using two test users:
- divya_venn (primary user)
- witkowski_cam (secondary user for comments)

Flow tested:
1. Divya posts "hello world!" -> discover_recently_posted captures it
2. Cam likes and comments on Divya's post -> discover_engagement captures the comment
3. Divya replies to Cam's comment -> comment is removed from cache
4. Cleanup: delete all test posts/comments/replies

These tests use the real Twitter API and browser scraping.
"""

import asyncio
import time
import uuid

import pytest
import requests


# ============================================================================
# Test Configuration
# ============================================================================

TEST_USER_1 = "divya_venn"  # Primary user - posts and replies
TEST_USER_2 = "witkowski_cam"  # Secondary user - comments


# ============================================================================
# Twitter API Helpers
# ============================================================================

async def _get_access_token(username: str) -> str:
    """Get OAuth access token for a user."""
    from backend.twitter.authentication import ensure_access_token
    token = await ensure_access_token(username)
    if not token:
        pytest.skip(f"No access token available for {username}")
    return token


async def twitter_post_tweet(username: str, text: str) -> dict:
    """Post a tweet via Twitter API."""
    access_token = await _get_access_token(username)

    url = "https://api.x.com/2/tweets"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    data = {"text": text}

    response = requests.post(url, headers=headers, json=data, timeout=30)

    if response.status_code not in (200, 201):
        pytest.fail(f"Failed to post tweet: {response.status_code} - {response.text}")

    result = response.json()
    return {
        "tweet_id": result.get("data", {}).get("id"),
        "text": text
    }


async def twitter_reply_to_tweet(username: str, text: str, reply_to_id: str) -> dict:
    """Post a reply to a tweet via Twitter API."""
    access_token = await _get_access_token(username)

    url = "https://api.x.com/2/tweets"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    data = {
        "text": text,
        "reply": {"in_reply_to_tweet_id": reply_to_id}
    }

    response = requests.post(url, headers=headers, json=data, timeout=30)

    if response.status_code not in (200, 201):
        pytest.fail(f"Failed to post reply: {response.status_code} - {response.text}")

    result = response.json()
    return {
        "tweet_id": result.get("data", {}).get("id"),
        "text": text,
        "reply_to_id": reply_to_id
    }


async def twitter_like_tweet(username: str, tweet_id: str) -> bool:
    """Like a tweet via Twitter API."""
    access_token = await _get_access_token(username)

    # First get user ID
    user_url = "https://api.x.com/2/users/me"
    headers = {"Authorization": f"Bearer {access_token}"}
    user_response = requests.get(user_url, headers=headers, timeout=30)

    if user_response.status_code != 200:
        pytest.fail(f"Failed to get user ID: {user_response.status_code}")

    user_id = user_response.json().get("data", {}).get("id")

    # Like the tweet
    like_url = f"https://api.x.com/2/users/{user_id}/likes"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    data = {"tweet_id": tweet_id}

    response = requests.post(like_url, headers=headers, json=data, timeout=30)

    # 200 = success, 400 might mean already liked
    return response.status_code in (200, 400)


async def twitter_delete_tweet(username: str, tweet_id: str) -> bool:
    """Delete a tweet via Twitter API."""
    access_token = await _get_access_token(username)

    url = f"https://api.x.com/2/tweets/{tweet_id}"
    headers = {"Authorization": f"Bearer {access_token}"}

    response = requests.delete(url, headers=headers, timeout=30)

    # 200 = deleted, 404 = already deleted
    return response.status_code in (200, 404)


# ============================================================================
# Cache Helpers
# ============================================================================

def add_tweet_to_posted_cache(username: str, tweet_id: str, text: str) -> None:
    """Add a tweet to the posted_tweets cache."""
    from datetime import datetime
    try:
        from datetime import UTC
    except ImportError:
        from datetime import timezone
        UTC = timezone.utc

    from backend.data.twitter.posted_tweets_cache import (
        read_posted_tweets_cache,
        write_posted_tweets_cache,
    )
    from backend.utlils.utils import read_user_info

    user_info = read_user_info(username)
    handle = user_info.get("handle", username) if user_info else username

    tweets_map = read_posted_tweets_cache(username)

    tweet_data = {
        "id": tweet_id,
        "text": text,
        "likes": 0,
        "retweets": 0,
        "quotes": 0,
        "replies": 0,
        "impressions": 0,
        "created_at": datetime.now(UTC).isoformat(),
        "url": f"https://x.com/{handle}/status/{tweet_id}",
        "last_metrics_update": datetime.now(UTC).isoformat(),
        "media": [],
        "parent_chain": [],
        "response_to_thread": [],
        "responding_to": "",
        "replying_to_pfp": "",
        "original_tweet_url": "",
        "source": "app_posted",
        "monitoring_state": "active",
        "last_activity_at": datetime.now(UTC).isoformat(),
        "last_deep_scrape": None,
        "last_shallow_scrape": None,
        "last_reply_count": 0,
        "last_like_count": 0,
        "last_quote_count": 0,
        "last_retweet_count": 0,
        "resurrected_via": "none",
        "last_scraped_reply_ids": []
    }

    tweets_map[tweet_id] = tweet_data
    order = tweets_map.get("_order", [])
    tweets_map["_order"] = [tweet_id] + [oid for oid in order if oid != tweet_id]

    write_posted_tweets_cache(username, tweets_map)


def add_reply_to_posted_cache(username: str, tweet_id: str, text: str, reply_to_id: str) -> None:
    """Add a reply to the posted_tweets cache with proper parent_chain."""
    from datetime import datetime
    try:
        from datetime import UTC
    except ImportError:
        from datetime import timezone
        UTC = timezone.utc

    from backend.data.twitter.posted_tweets_cache import (
        read_posted_tweets_cache,
        write_posted_tweets_cache,
    )
    from backend.utlils.utils import read_user_info

    user_info = read_user_info(username)
    handle = user_info.get("handle", username) if user_info else username

    tweets_map = read_posted_tweets_cache(username)

    # Build parent_chain from parent if exists
    parent = tweets_map.get(reply_to_id)
    if parent and isinstance(parent, dict):
        parent_chain = parent.get("parent_chain", []) + [reply_to_id]
    else:
        parent_chain = [reply_to_id]

    tweet_data = {
        "id": tweet_id,
        "text": text,
        "likes": 0,
        "retweets": 0,
        "quotes": 0,
        "replies": 0,
        "impressions": 0,
        "created_at": datetime.now(UTC).isoformat(),
        "url": f"https://x.com/{handle}/status/{tweet_id}",
        "last_metrics_update": datetime.now(UTC).isoformat(),
        "media": [],
        "parent_chain": parent_chain,
        "in_reply_to_status_id": reply_to_id,
        "response_to_thread": [],
        "responding_to": "",
        "replying_to_pfp": "",
        "original_tweet_url": "",
        "source": "app_posted",
        "monitoring_state": "active",
        "last_activity_at": datetime.now(UTC).isoformat(),
        "last_deep_scrape": None,
        "last_shallow_scrape": None,
        "last_reply_count": 0,
        "last_like_count": 0,
        "last_quote_count": 0,
        "last_retweet_count": 0,
        "resurrected_via": "none",
        "last_scraped_reply_ids": []
    }

    tweets_map[tweet_id] = tweet_data
    order = tweets_map.get("_order", [])
    tweets_map["_order"] = [tweet_id] + [oid for oid in order if oid != tweet_id]

    write_posted_tweets_cache(username, tweets_map)


def remove_tweet_from_cache(username: str, tweet_id: str) -> None:
    """Remove a tweet from posted_tweets cache."""
    from backend.data.twitter.posted_tweets_cache import delete_posted_tweet_from_cache
    delete_posted_tweet_from_cache(username, tweet_id)


def get_comment_from_cache(username: str, comment_id: str) -> dict | None:
    """Get a comment from the comments cache."""
    from backend.data.twitter.comments_cache import get_comment
    return get_comment(username, comment_id)


def is_tweet_in_cache(username: str, tweet_id: str) -> bool:
    """Check if a tweet is in the posted_tweets cache."""
    from backend.data.twitter.posted_tweets_cache import read_posted_tweets_cache
    tweets_map = read_posted_tweets_cache(username)
    return tweet_id in tweets_map and tweet_id != "_order"


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def test_tweet_id():
    """Generate a unique test identifier."""
    return f"TEST_{uuid.uuid4().hex[:8]}"


@pytest.fixture
async def cleanup_tweets():
    """
    Fixture to track and cleanup tweets after test.
    Returns a dict to store tweet IDs for cleanup.
    """
    tweets_to_delete = {"divya_venn": [], "witkowski_cam": []}

    yield tweets_to_delete

    # Cleanup after test
    for username, tweet_ids in tweets_to_delete.items():
        for tweet_id in tweet_ids:
            try:
                await twitter_delete_tweet(username, tweet_id)
                remove_tweet_from_cache(username, tweet_id)
                print(f"✅ Cleaned up tweet {tweet_id} for @{username}")
            except Exception as e:
                print(f"⚠️ Failed to cleanup tweet {tweet_id}: {e}")

    # Small delay to let deletions propagate
    await asyncio.sleep(2)


# ============================================================================
# Test: Post Discovery
# ============================================================================

class TestPostDiscovery:
    """Tests for discover_recently_posted capturing new posts."""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_posted_tweet_is_discovered(self, test_tweet_id, cleanup_tweets):
        """
        Test that a newly posted tweet is captured by discover_recently_posted.

        Flow:
        1. Divya posts a tweet
        2. Run discover_recently_posted for Divya
        3. Verify the tweet appears in posted_tweets cache
        """
        from backend.twitter.monitoring import discover_recently_posted
        from backend.utlils.utils import read_user_info

        user_info = read_user_info(TEST_USER_1)
        user_handle = user_info.get("handle", TEST_USER_1)

        # 1. Post a test tweet
        test_text = f"hello world! {test_tweet_id}"
        posted = await twitter_post_tweet(TEST_USER_1, test_text)
        tweet_id = posted["tweet_id"]
        cleanup_tweets[TEST_USER_1].append(tweet_id)

        print(f"✅ Posted test tweet: {tweet_id}")

        # Wait for Twitter to index the tweet
        await asyncio.sleep(5)

        # 2. Run discover_recently_posted
        result = await discover_recently_posted(TEST_USER_1, user_handle, max_tweets=20)

        print(f"📊 discover_recently_posted result: {result}")

        # 3. Verify the tweet is in cache
        assert is_tweet_in_cache(TEST_USER_1, tweet_id), \
            f"Posted tweet {tweet_id} should be in cache after discover_recently_posted"

        print(f"✅ Tweet {tweet_id} successfully discovered and cached")


# ============================================================================
# Test: Comment Discovery
# ============================================================================

class TestCommentDiscovery:
    """Tests for discover_engagement capturing comments."""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_comment_is_discovered(self, test_tweet_id, cleanup_tweets):
        """
        Test that a comment on user's post is captured by discover_engagement.

        Flow:
        1. Divya posts a tweet
        2. Cam comments on Divya's tweet
        3. Run discover_engagement for Divya
        4. Verify Cam's comment is in the comments cache
        """
        from backend.data.twitter.comments_cache import get_comment
        from backend.twitter.monitoring import discover_engagement
        from backend.utlils.utils import read_user_info

        user_info = read_user_info(TEST_USER_1)
        user_handle = user_info.get("handle", TEST_USER_1)

        # 1. Divya posts a test tweet
        test_text = f"Testing comments! {test_tweet_id}"
        posted = await twitter_post_tweet(TEST_USER_1, test_text)
        divya_tweet_id = posted["tweet_id"]
        cleanup_tweets[TEST_USER_1].append(divya_tweet_id)

        # Add to cache immediately (simulating app-posted tweet)
        add_tweet_to_posted_cache(TEST_USER_1, divya_tweet_id, test_text)

        print(f"✅ Divya posted: {divya_tweet_id}")

        # Wait for Twitter to index
        await asyncio.sleep(5)

        # 2. Cam comments on Divya's tweet
        comment_text = f"42 {test_tweet_id}"
        comment_result = await twitter_reply_to_tweet(TEST_USER_2, comment_text, divya_tweet_id)
        cam_comment_id = comment_result["tweet_id"]
        cleanup_tweets[TEST_USER_2].append(cam_comment_id)

        print(f"✅ Cam commented: {cam_comment_id}")

        # Wait for Twitter to index the comment
        await asyncio.sleep(5)

        # 3. Run discover_engagement for Divya
        result = await discover_engagement(TEST_USER_1, user_handle)

        print(f"📊 discover_engagement result: {result}")

        # 4. Verify Cam's comment is in cache
        comment = get_comment(TEST_USER_1, cam_comment_id)

        assert comment is not None, \
            f"Cam's comment {cam_comment_id} should be in Divya's comments cache"
        assert comment["text"] == comment_text, \
            f"Comment text should match. Expected: {comment_text}, Got: {comment.get('text')}"
        assert comment["status"] == "pending", \
            "New comment should have 'pending' status"

        print(f"✅ Cam's comment {cam_comment_id} successfully discovered")


# ============================================================================
# Test: Like Discovery (Metrics Update)
# ============================================================================

class TestMetricsDiscovery:
    """Tests for discover_engagement capturing likes and other metrics."""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_like_is_captured(self, test_tweet_id, cleanup_tweets):
        """
        Test that likes on user's post are captured by discover_engagement.

        Flow:
        1. Divya posts a tweet
        2. Cam likes Divya's tweet
        3. Run discover_engagement for Divya
        4. Verify the like count increased
        """
        from backend.data.twitter.posted_tweets_cache import read_posted_tweets_cache
        from backend.twitter.monitoring import discover_engagement
        from backend.utlils.utils import read_user_info

        user_info = read_user_info(TEST_USER_1)
        user_handle = user_info.get("handle", TEST_USER_1)

        # 1. Divya posts a test tweet
        test_text = f"Like this! {test_tweet_id}"
        posted = await twitter_post_tweet(TEST_USER_1, test_text)
        divya_tweet_id = posted["tweet_id"]
        cleanup_tweets[TEST_USER_1].append(divya_tweet_id)

        # Add to cache with 0 likes
        add_tweet_to_posted_cache(TEST_USER_1, divya_tweet_id, test_text)

        print(f"✅ Divya posted: {divya_tweet_id}")

        # Wait for Twitter to index
        await asyncio.sleep(5)

        # 2. Cam likes Divya's tweet
        liked = await twitter_like_tweet(TEST_USER_2, divya_tweet_id)
        assert liked, "Cam should be able to like the tweet"

        print(f"✅ Cam liked: {divya_tweet_id}")

        # Wait for Twitter to update
        await asyncio.sleep(5)

        # 3. Run discover_engagement for Divya
        result = await discover_engagement(TEST_USER_1, user_handle)

        print(f"📊 discover_engagement result: {result}")

        # 4. Verify like count increased
        tweets_map = read_posted_tweets_cache(TEST_USER_1)
        tweet = tweets_map.get(divya_tweet_id)

        assert tweet is not None, "Tweet should be in cache"
        assert tweet.get("likes", 0) >= 1, \
            f"Like count should be at least 1, got: {tweet.get('likes', 0)}"

        print(f"✅ Like count updated: {tweet.get('likes', 0)}")


# ============================================================================
# Test: Reply Removes Comment from Cache
# ============================================================================

class TestReplyRemovesComment:
    """Tests that replying to a comment removes it from cache."""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_reply_removes_comment_from_cache(self, test_tweet_id, cleanup_tweets):
        """
        Test the complete flow: comment is discovered, then removed after user replies.

        Flow:
        1. Divya posts a tweet
        2. Cam comments on Divya's tweet
        3. Run discover_engagement -> Cam's comment is in cache
        4. Divya replies to Cam's comment
        5. Run discover_engagement again -> Cam's comment is removed from cache
        """
        from backend.data.twitter.comments_cache import get_comment, read_comments_cache
        from backend.twitter.monitoring import discover_engagement
        from backend.utlils.utils import read_user_info

        user_info = read_user_info(TEST_USER_1)
        user_handle = user_info.get("handle", TEST_USER_1)

        # 1. Divya posts a test tweet
        test_text = f"Reply flow test! {test_tweet_id}"
        posted = await twitter_post_tweet(TEST_USER_1, test_text)
        divya_tweet_id = posted["tweet_id"]
        cleanup_tweets[TEST_USER_1].append(divya_tweet_id)

        add_tweet_to_posted_cache(TEST_USER_1, divya_tweet_id, test_text)

        print(f"✅ Divya posted: {divya_tweet_id}")
        await asyncio.sleep(5)

        # 2. Cam comments
        comment_text = f"42 {test_tweet_id}"
        comment_result = await twitter_reply_to_tweet(TEST_USER_2, comment_text, divya_tweet_id)
        cam_comment_id = comment_result["tweet_id"]
        cleanup_tweets[TEST_USER_2].append(cam_comment_id)

        print(f"✅ Cam commented: {cam_comment_id}")
        await asyncio.sleep(5)

        # 3. Run discover_engagement -> comment should be in cache
        result1 = await discover_engagement(TEST_USER_1, user_handle)
        print(f"📊 First discover_engagement: {result1}")

        comment = get_comment(TEST_USER_1, cam_comment_id)
        assert comment is not None, \
            f"Cam's comment {cam_comment_id} should be in cache after first discover_engagement"

        print(f"✅ Cam's comment is in cache")

        # 4. Divya replies to Cam's comment
        reply_text = f"i now know the meaning of everything, my existence is obsolete {test_tweet_id}"
        reply_result = await twitter_reply_to_tweet(TEST_USER_1, reply_text, cam_comment_id)
        divya_reply_id = reply_result["tweet_id"]
        cleanup_tweets[TEST_USER_1].append(divya_reply_id)

        # Add Divya's reply to posted_tweets cache
        add_reply_to_posted_cache(TEST_USER_1, divya_reply_id, reply_text, cam_comment_id)

        print(f"✅ Divya replied: {divya_reply_id}")
        await asyncio.sleep(5)

        # 5. Run discover_engagement again -> comment should be REMOVED from cache
        result2 = await discover_engagement(TEST_USER_1, user_handle)
        print(f"📊 Second discover_engagement: {result2}")

        # Verify comment is removed
        comment_after = get_comment(TEST_USER_1, cam_comment_id)

        assert comment_after is None, \
            f"Cam's comment {cam_comment_id} should be REMOVED from cache after Divya replied"

        print(f"✅ Cam's comment correctly removed from cache after Divya replied")


# ============================================================================
# Test: Full End-to-End Flow
# ============================================================================

class TestFullEngagementFlow:
    """Complete end-to-end test of the engagement monitoring flow."""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_complete_engagement_flow(self, test_tweet_id, cleanup_tweets):
        """
        Complete flow test with all interactions.

        Flow:
        1. Divya posts "hello world!"
        2. discover_recently_posted captures the post
        3. Cam likes and comments "42"
        4. discover_engagement captures the like and comment
        5. Divya replies to Cam's comment
        6. discover_engagement removes Cam's comment from cache
        7. Cleanup: delete all test tweets
        """
        from backend.data.twitter.comments_cache import get_comment
        from backend.data.twitter.posted_tweets_cache import read_posted_tweets_cache
        from backend.twitter.monitoring import discover_engagement, discover_recently_posted
        from backend.utlils.utils import read_user_info

        user_info = read_user_info(TEST_USER_1)
        user_handle = user_info.get("handle", TEST_USER_1)

        print("\n" + "=" * 60)
        print("STEP 1: Divya posts 'hello world!'")
        print("=" * 60)

        hello_text = f"hello world! {test_tweet_id}"
        posted = await twitter_post_tweet(TEST_USER_1, hello_text)
        divya_tweet_id = posted["tweet_id"]
        cleanup_tweets[TEST_USER_1].append(divya_tweet_id)

        print(f"✅ Posted: {divya_tweet_id}")
        await asyncio.sleep(5)

        print("\n" + "=" * 60)
        print("STEP 2: discover_recently_posted captures the post")
        print("=" * 60)

        discover_result = await discover_recently_posted(TEST_USER_1, user_handle, max_tweets=20)
        print(f"📊 Result: {discover_result}")

        assert is_tweet_in_cache(TEST_USER_1, divya_tweet_id), \
            "Post should be in cache after discover_recently_posted"
        print(f"✅ Post captured in cache")

        print("\n" + "=" * 60)
        print("STEP 3: Cam likes and comments '42'")
        print("=" * 60)

        # Like
        await twitter_like_tweet(TEST_USER_2, divya_tweet_id)
        print(f"✅ Cam liked the post")

        # Comment
        comment_text = f"42 {test_tweet_id}"
        comment_result = await twitter_reply_to_tweet(TEST_USER_2, comment_text, divya_tweet_id)
        cam_comment_id = comment_result["tweet_id"]
        cleanup_tweets[TEST_USER_2].append(cam_comment_id)

        print(f"✅ Cam commented: {cam_comment_id}")
        await asyncio.sleep(5)

        print("\n" + "=" * 60)
        print("STEP 4: discover_engagement captures the like and comment")
        print("=" * 60)

        engagement_result1 = await discover_engagement(TEST_USER_1, user_handle)
        print(f"📊 Result: {engagement_result1}")

        # Check like count
        tweets_map = read_posted_tweets_cache(TEST_USER_1)
        tweet = tweets_map.get(divya_tweet_id)
        print(f"📊 Like count: {tweet.get('likes', 0)}")

        # Check comment in cache
        comment = get_comment(TEST_USER_1, cam_comment_id)
        assert comment is not None, "Cam's comment should be in cache"
        assert comment["text"] == comment_text, "Comment text should match"
        print(f"✅ Comment captured with text: {comment['text']}")

        print("\n" + "=" * 60)
        print("STEP 5: Divya replies to Cam's comment")
        print("=" * 60)

        reply_text = f"i now know the meaning of everything, my existence is obsolete {test_tweet_id}"
        reply_result = await twitter_reply_to_tweet(TEST_USER_1, reply_text, cam_comment_id)
        divya_reply_id = reply_result["tweet_id"]
        cleanup_tweets[TEST_USER_1].append(divya_reply_id)

        # Add to cache
        add_reply_to_posted_cache(TEST_USER_1, divya_reply_id, reply_text, cam_comment_id)

        print(f"✅ Divya replied: {divya_reply_id}")
        await asyncio.sleep(5)

        print("\n" + "=" * 60)
        print("STEP 6: discover_engagement removes Cam's comment from cache")
        print("=" * 60)

        engagement_result2 = await discover_engagement(TEST_USER_1, user_handle)
        print(f"📊 Result: {engagement_result2}")

        # Comment should be removed
        comment_after = get_comment(TEST_USER_1, cam_comment_id)
        assert comment_after is None, \
            "Cam's comment should be removed from cache after Divya replied"

        print(f"✅ Comment correctly removed from cache")

        print("\n" + "=" * 60)
        print("STEP 7: Cleanup (handled by fixture)")
        print("=" * 60)
        print("✅ Test complete! Cleanup will run automatically.")


# ============================================================================
# Test: Comment from External User Not in Cache After User Reply
# ============================================================================

class TestExternalReplyCleanup:
    """Tests that external replies (made outside the app) also trigger cleanup."""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_external_reply_removes_comment(self, test_tweet_id, cleanup_tweets):
        """
        Test that comments are cleaned up even when user replies externally.

        This simulates a user replying via the Twitter app/website instead of
        through this application.
        """
        from backend.data.twitter.comments_cache import get_comment
        from backend.twitter.monitoring import discover_engagement, discover_recently_posted
        from backend.utlils.utils import read_user_info

        user_info = read_user_info(TEST_USER_1)
        user_handle = user_info.get("handle", TEST_USER_1)

        # 1. Divya posts a tweet
        test_text = f"External reply test! {test_tweet_id}"
        posted = await twitter_post_tweet(TEST_USER_1, test_text)
        divya_tweet_id = posted["tweet_id"]
        cleanup_tweets[TEST_USER_1].append(divya_tweet_id)

        # Add to cache
        add_tweet_to_posted_cache(TEST_USER_1, divya_tweet_id, test_text)

        print(f"✅ Divya posted: {divya_tweet_id}")
        await asyncio.sleep(5)

        # 2. Cam comments
        comment_text = f"External comment {test_tweet_id}"
        comment_result = await twitter_reply_to_tweet(TEST_USER_2, comment_text, divya_tweet_id)
        cam_comment_id = comment_result["tweet_id"]
        cleanup_tweets[TEST_USER_2].append(cam_comment_id)

        print(f"✅ Cam commented: {cam_comment_id}")
        await asyncio.sleep(5)

        # 3. Discover engagement -> comment in cache
        await discover_engagement(TEST_USER_1, user_handle)

        comment = get_comment(TEST_USER_1, cam_comment_id)
        assert comment is not None, "Comment should be in cache"
        print(f"✅ Comment in cache")

        # 4. Divya replies EXTERNALLY (via API, not through app cache)
        reply_text = f"External reply {test_tweet_id}"
        reply_result = await twitter_reply_to_tweet(TEST_USER_1, reply_text, cam_comment_id)
        divya_reply_id = reply_result["tweet_id"]
        cleanup_tweets[TEST_USER_1].append(divya_reply_id)

        # NOTE: We don't add to cache - simulating external reply
        print(f"✅ Divya replied externally: {divya_reply_id}")
        await asyncio.sleep(5)

        # 5. Run discover_recently_posted to pick up the external reply
        await discover_recently_posted(TEST_USER_1, user_handle, max_tweets=20)

        # 6. Run discover_engagement again
        await discover_engagement(TEST_USER_1, user_handle)

        # 7. Comment should be removed (because discover_recently_posted added
        # Divya's reply to posted_tweets, and discover_engagement uses
        # get_user_replied_comment_ids to check)
        comment_after = get_comment(TEST_USER_1, cam_comment_id)

        assert comment_after is None, \
            "Comment should be removed after external reply was discovered"

        print(f"✅ Comment correctly removed after external reply")
