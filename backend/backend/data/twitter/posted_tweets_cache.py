"""
Manage posted tweets cache in Supabase.
Stores full tweet data including performance metrics.
"""
from datetime import datetime
from typing import Any, Literal

try:  # Python 3.11+
    from datetime import UTC
except ImportError:
    from datetime import timezone
    UTC = timezone.utc

from backend.utlils.utils import notify

# Post types for classification
PostType = Literal["original", "reply", "comment_reply"]


def calculate_engagement_score(likes: int, retweets: int, quotes: int, replies: int) -> int:
    """
    Calculate engagement score from metrics.
    Formula: likes + 2*retweets + 3*quotes + replies
    """
    return likes + 2 * retweets + 3 * quotes + replies


def _convert_to_map_format(tweets: list[dict[str, Any]]) -> dict[str, Any]:
    """Convert a list of tweets to map format with _order."""
    tweets_map: dict[str, Any] = {"_order": []}
    for tweet in tweets:
        tweet_id = tweet.get("tweet_id")
        if tweet_id:
            tweets_map[tweet_id] = tweet
            tweets_map["_order"].append(tweet_id)
    return tweets_map


def read_posted_tweets_cache(username: str) -> dict[str, Any]:
    """
    Read posted tweets from Supabase.
    Returns map with _order array for pagination.
    """
    from backend.utlils.supabase_client import get_posted_tweets

    tweets = get_posted_tweets(username)
    return _convert_to_map_format(tweets or [])


def get_posted_tweets_list(username: str, limit: int | None = None, offset: int = 0) -> list[dict[str, Any]]:
    """
    Get posted tweets as a list for pagination.
    Returns tweets sorted by created_at (newest first).
    """
    from backend.utlils.supabase_client import get_posted_tweets

    return get_posted_tweets(username, limit, offset)


def get_posted_tweet(username: str, tweet_id: str) -> dict[str, Any] | None:
    """Get a single posted tweet by ID."""
    from backend.utlils.supabase_client import get_posted_tweet as sb_get_tweet

    return sb_get_tweet(username, tweet_id)


def add_posted_tweet(
    username: str,
    posted_tweet_id: str,
    text: str,
    original_tweet_url: str = "",
    responding_to_handle: str = "",
    replying_to_pfp: str = "",
    response_to_thread: list[str] | None = None,
    in_reply_to_id: str | None = None,
    created_at: str | None = None,
    parent_media: list[dict] | None = None,
    post_type: PostType = "reply"
) -> dict[str, Any]:
    """
    Add a new posted tweet to the cache.
    """
    from backend.data.twitter.comments_cache import read_comments_cache
    from backend.utlils.supabase_client import add_posted_tweet as sb_add_tweet

    if created_at is None:
        created_at = datetime.now(UTC).isoformat()

    if response_to_thread is None:
        response_to_thread = []

    if parent_media is None:
        parent_media = []

    # Reply's own media (empty for now)
    media: list[dict] = []

    # Read existing caches for parent chain
    tweets_map = read_posted_tweets_cache(username)
    comments_map = read_comments_cache(username)

    # Build parent_chain
    parent_chain: list[str] = []
    if in_reply_to_id:
        parent = tweets_map.get(in_reply_to_id) or comments_map.get(in_reply_to_id)
        if parent and isinstance(parent, dict):
            parent_chain = parent.get("parent_chain", []) + [in_reply_to_id]
        else:
            parent_chain = [in_reply_to_id]

    # Create tweet object
    tweet = {
        "tweet_id": posted_tweet_id,
        "handle": username,
        "text": text,
        "likes": 0,
        "retweets": 0,
        "quotes": 0,
        "replies": 0,
        "impressions": 0,
        "created_at": created_at,
        "url": f"https://x.com/{username}/status/{posted_tweet_id}",
        "last_metrics_update": created_at,
        "media": media,
        "parent_media": parent_media,
        "parent_chain": parent_chain,
        "response_to_thread": response_to_thread,
        "responding_to": responding_to_handle,
        "replying_to_pfp": replying_to_pfp,
        "original_tweet_url": original_tweet_url,
        "source": "app_posted",
        "monitoring_state": "active",
        "last_activity_at": created_at,
        "resurrected_via": "none",
        "last_scraped_reply_ids": [],
        "post_type": post_type,
        "score": 0,
    }

    sb_add_tweet(tweet)
    notify(f"✅ Added posted tweet {posted_tweet_id} for @{username}")
    return tweet


def update_tweet_metrics(
    username: str,
    posted_tweet_id: str,
    likes: int,
    retweets: int,
    quotes: int,
    replies: int,
    impressions: int = 0
) -> dict[str, Any] | None:
    """
    Update performance metrics for a posted tweet.
    """
    from backend.utlils.supabase_client import update_posted_tweet as sb_update_tweet

    score = calculate_engagement_score(likes, retweets, quotes, replies)
    updates = {
        "likes": likes,
        "retweets": retweets,
        "quotes": quotes,
        "replies": replies,
        "impressions": impressions,
        "score": score,
        "last_metrics_update": datetime.now(UTC).isoformat()
    }
    result = sb_update_tweet(posted_tweet_id, updates)
    if result:
        notify(f"✅ Updated metrics for tweet {posted_tweet_id}: {likes}L {retweets}RT {quotes}Q {replies}R (score: {score})")
    return result


def update_tweet_media(
    username: str,
    posted_tweet_id: str,
    media: list[dict]
) -> dict[str, Any] | None:
    """
    Update media for a posted tweet.
    """
    from backend.utlils.supabase_client import update_posted_tweet as sb_update_tweet

    result = sb_update_tweet(posted_tweet_id, {"media": media})
    if result:
        notify(f"✅ Updated media for tweet {posted_tweet_id}: {len(media)} items")
    return result


def delete_posted_tweet_from_cache(username: str, posted_tweet_id: str) -> bool:
    """
    Delete a posted tweet from the cache.
    """
    from backend.utlils.supabase_client import delete_posted_tweet as sb_delete_tweet

    result = sb_delete_tweet(posted_tweet_id)
    if result:
        notify(f"✅ Deleted posted tweet {posted_tweet_id} for @{username}")
    return result


def get_user_tweet_ids(username: str) -> set[str]:
    """Get set of all tweet IDs authored by the user."""
    from backend.utlils.supabase_client import get_user_posted_tweet_ids

    return get_user_posted_tweet_ids(username)


def get_tweets_by_monitoring_state(username: str, states: list[str]) -> list[dict[str, Any]]:
    """Get tweets filtered by monitoring state, sorted by last_activity_at descending."""
    from backend.utlils.supabase_client import get_posted_tweets_by_state

    return get_posted_tweets_by_state(username, states)


def update_monitoring_state(username: str, tweet_id: str, new_state: str, resurrected_via: str | None = None) -> bool:
    """Update the monitoring state of a tweet."""
    from backend.utlils.supabase_client import update_posted_tweet as sb_update_tweet

    updates = {
        "monitoring_state": new_state,
        "last_activity_at": datetime.now(UTC).isoformat()
    }
    if resurrected_via:
        updates["resurrected_via"] = resurrected_via
    result = sb_update_tweet(tweet_id, updates)
    return result is not None


def get_top_posts_by_type(
    username: str,
    post_type: PostType | None = None,
    limit: int = 10
) -> list[dict[str, Any]]:
    """
    Get top-performing posts sorted by engagement score.
    """
    from backend.utlils.supabase_client import get_top_posted_tweets

    return get_top_posted_tweets(username, post_type, limit)


def get_replies_to_account(
    username: str,
    target_account: str,
    limit: int = 10,
    post_type: PostType = "reply"
) -> list[dict[str, Any]]:
    """
    Get replies to a specific account, sorted by engagement score.
    """
    tweets_map = read_posted_tweets_cache(username)

    target_normalized = target_account.lstrip("@").lower()

    replies = []
    for tid, tweet in tweets_map.items():
        if tid == "_order" or not isinstance(tweet, dict):
            continue
        if tweet.get("post_type") != post_type:
            continue

        responding_to = tweet.get("responding_to", "")
        if responding_to and responding_to.lower() == target_normalized:
            replies.append(tweet)

    replies.sort(key=lambda t: t.get("score", 0), reverse=True)
    return replies[:limit]


def get_top_posts_for_llm_context(username: str, limit_per_type: int = 10) -> dict[str, list[dict[str, Any]]]:
    """
    Get top-performing posts of each type for LLM context.
    """
    return {
        "original": get_top_posts_by_type(username, "original", limit_per_type),
        "reply": get_top_posts_by_type(username, "reply", limit_per_type),
        "comment_reply": get_top_posts_by_type(username, "comment_reply", limit_per_type),
    }


def build_examples_from_posts(posts: list[dict[str, Any]], post_type: PostType) -> list[str]:
    """
    Build example strings from posts for LLM prompts.
    """
    examples = []

    for post in posts:
        text = post.get("text", "")
        score = post.get("score", 0)
        likes = post.get("likes", 0)
        retweets = post.get("retweets", 0)

        if post_type == "reply":
            original = post.get("response_to_thread", [])
            responding_to = post.get("responding_to", "")
            if original and text:
                original_text = " | ".join(original)[:500]
                example = f"[ORIGINAL @{responding_to}]: {original_text}\n[YOUR REPLY ({likes}L, {retweets}RT)]: {text}"
                examples.append(example)

        elif post_type == "comment_reply":
            if text:
                responding_to = post.get("responding_to", "someone")
                example = f"[YOUR COMMENT REPLY ({likes}L, {retweets}RT)]: {text}"
                examples.append(example)

        elif post_type == "original":
            if text:
                example = f"[YOUR POST ({likes}L, {retweets}RT)]: {text}"
                examples.append(example)

    return examples
