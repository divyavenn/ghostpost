"""
Manage posted tweets cache in [handle]_posted_tweets.json files.
Stores full tweet data including performance metrics.

Storage format: Map with _order array for pagination
{
    "_order": ["id3", "id2", "id1"],  // newest first
    "id1": { tweet data },
    "id2": { tweet data },
    ...
}
"""
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal

try:  # Python 3.11+
    from datetime import UTC
except ImportError:
    from datetime import timezone
    UTC = timezone.utc

from backend.config import HARDCUTOFF_COLD_DAYS
from backend.utlils.utils import CACHE_DIR, _cache_key, notify

# Post types for classification
PostType = Literal["original", "reply", "comment_reply"]


def calculate_engagement_score(likes: int, retweets: int, quotes: int, replies: int) -> int:
    """
    Calculate engagement score from metrics.
    Formula: likes + 2*retweets + 3*quotes + replies
    """
    return likes + 2 * retweets + 3 * quotes + replies


def get_posted_tweets_path(username: str) -> Path:
    """Get the path to the posted tweets cache file for a user."""
    return CACHE_DIR / f"{_cache_key(username)}_posted_tweets.json"


def _is_older_than_days(created_at: str, days: int) -> bool:
    """Check if a tweet is older than the specified number of days."""
    try:
        # Try ISO format first
        if "T" in created_at:
            dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        else:
            # Twitter format: "Sun Nov 30 14:26:48 +0000 2025"
            dt = datetime.strptime(created_at, "%a %b %d %H:%M:%S %z %Y")

        now = datetime.now(UTC)
        return (now - dt) > timedelta(days=days)
    except Exception:
        return False


def _migrate_if_needed(data: Any, username: str) -> dict[str, Any]:
    """
    Migrate from array format to map format if needed.
    Also adds default values for new fields.
    """
    from backend.utlils.utils import error

    # Already a map
    if isinstance(data, dict) and "_order" in data:
        return data

    # Convert from array
    if isinstance(data, list):
        new_data: dict[str, Any] = {"_order": []}

        # Sort by created_at descending for order
        try:
            data.sort(key=lambda t: t.get("created_at", ""), reverse=True)
        except Exception:
            pass

        for tweet in data:
            if not isinstance(tweet, dict):
                continue

            tweet_id = tweet.get("id")
            if not tweet_id:
                continue

            # Add default values for new fields
            tweet.setdefault("parent_chain", [])
            tweet.setdefault("source", "app_posted")
            tweet.setdefault("monitoring_state",
                             "cold" if _is_older_than_days(tweet.get("created_at", ""), HARDCUTOFF_COLD_DAYS) else "active")
            tweet.setdefault("last_activity_at", tweet.get("created_at"))
            tweet.setdefault("last_deep_scrape", None)
            tweet.setdefault("last_shallow_scrape", None)
            tweet.setdefault("last_reply_count", tweet.get("replies", 0))
            tweet.setdefault("last_like_count", tweet.get("likes", 0))
            tweet.setdefault("last_quote_count", tweet.get("quotes", 0))
            tweet.setdefault("last_retweet_count", tweet.get("retweets", 0))
            tweet.setdefault("resurrected_via", "none")
            tweet.setdefault("last_scraped_reply_ids", [])

            new_data[tweet_id] = tweet
            new_data["_order"].append(tweet_id)

        notify(f"📦 Migrated posted_tweets for @{username} from array to map format ({len(new_data) - 1} tweets)")
        return new_data

    # Invalid format
    error("Invalid posted tweets cache format", status_code=500, function_name="_migrate_if_needed", username=username)
    return {"_order": []}


def read_posted_tweets_cache(username: str) -> dict[str, Any]:
    """
    Read posted tweets from cache file.
    Returns map with _order array for pagination.
    """
    from pydantic import ValidationError

    from backend.data.twitter.data_validation import PostedTweet
    from backend.utlils.utils import error

    cache_path = get_posted_tweets_path(username)

    if not cache_path.exists():
        return {"_order": []}

    try:
        with open(cache_path, encoding="utf-8") as f:
            data = json.load(f)

        # Migrate if needed
        tweets_map = _migrate_if_needed(data, username)

        # Validate each tweet (skip _order)
        for tweet_id, tweet in list(tweets_map.items()):
            if tweet_id == "_order":
                continue

            try:
                validated = PostedTweet(**tweet)
                tweets_map[tweet_id] = validated.model_dump()
            except ValidationError as e:
                error(f"Invalid posted tweet data for tweet {tweet_id}", status_code=500, exception_text=str(e), function_name="read_posted_tweets_cache", username=username)
                # Keep invalid tweet but log the error

        return tweets_map

    except Exception as e:
        error("Error reading posted tweets cache", status_code=500, exception_text=str(e), function_name="read_posted_tweets_cache", username=username)
        notify(f"❌ Error reading posted tweets cache for {username}: {e}")
        return {"_order": []}


def write_posted_tweets_cache(username: str, tweets_map: dict[str, Any]) -> None:
    """
    Write posted tweets to cache file.
    Overwrites the entire file.
    """
    from pydantic import ValidationError

    from backend.data.twitter.data_validation import PostedTweet
    from backend.utlils.utils import error

    cache_path = get_posted_tweets_path(username)
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    # Ensure _order exists and is deduplicated
    if "_order" not in tweets_map:
        tweets_map["_order"] = [k for k in tweets_map.keys() if k != "_order"]
    else:
        # Deduplicate _order while preserving order, and ensure all IDs exist in map
        seen = set()
        valid_order = []
        for oid in tweets_map["_order"]:
            if oid not in seen and oid in tweets_map:
                seen.add(oid)
                valid_order.append(oid)
        tweets_map["_order"] = valid_order

    # Validate each tweet before writing (skip _order)
    for tweet_id, tweet in list(tweets_map.items()):
        if tweet_id == "_order":
            continue

        try:
            validated = PostedTweet(**tweet)
            tweets_map[tweet_id] = validated.model_dump()
        except ValidationError as e:
            error(f"Invalid posted tweet data for tweet {tweet_id}", status_code=500, exception_text=str(e), function_name="write_posted_tweets_cache", username=username)
            # Still include the tweet but log the error

    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(tweets_map, f, indent=2, ensure_ascii=False)
    except Exception as e:
        error("Error writing posted tweets cache", status_code=500, exception_text=str(e), function_name="write_posted_tweets_cache", username=username)
        notify(f"❌ Error writing posted tweets cache for {username}: {e}")
        raise


def get_posted_tweets_list(username: str, limit: int | None = None, offset: int = 0) -> list[dict[str, Any]]:
    """
    Get posted tweets as a list for pagination.
    Returns tweets sorted by created_at (newest first).
    """
    tweets_map = read_posted_tweets_cache(username)

    # Get all tweets (excluding _order key)
    tweets = [t for tid, t in tweets_map.items() if tid != "_order" and isinstance(t, dict)]

    # Sort by created_at descending (newest first)
    tweets.sort(key=lambda t: t.get("created_at") or "", reverse=True)

    # Apply pagination
    if limit is not None:
        return tweets[offset:offset + limit]
    else:
        return tweets[offset:]


def get_posted_tweet(username: str, tweet_id: str) -> dict[str, Any] | None:
    """Get a single posted tweet by ID."""
    tweets_map = read_posted_tweets_cache(username)
    return tweets_map.get(tweet_id)


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

    Args:
        username: User's Twitter handle
        posted_tweet_id: Twitter's ID for the posted tweet
        text: The response text that was posted
        original_tweet_url: URL of the original tweet being replied to
        responding_to_handle: Handle of the user being replied to
        replying_to_pfp: Profile picture URL of the original author
        response_to_thread: List of strings representing the original thread
        in_reply_to_id: The tweet ID this is replying to (for parent_chain)
        created_at: ISO timestamp of when tweet was created (defaults to now)
        parent_media: Media from the parent tweet being replied to (not the reply itself)
        post_type: Type of post - "original", "reply", or "comment_reply"

    Returns:
        The created tweet object
    """
    from backend.data.twitter.comments_cache import read_comments_cache

    if created_at is None:
        created_at = datetime.now(UTC).isoformat()

    if response_to_thread is None:
        response_to_thread = []

    if parent_media is None:
        parent_media = []

    # Reply's own media (empty for now - we don't support attaching media to replies yet)
    media: list[dict] = []

    # Read existing caches
    tweets_map = read_posted_tweets_cache(username)
    comments_map = read_comments_cache(username)

    # Build parent_chain
    parent_chain: list[str] = []
    if in_reply_to_id:
        parent = tweets_map.get(in_reply_to_id) or comments_map.get(in_reply_to_id)
        if parent and isinstance(parent, dict):
            parent_chain = parent.get("parent_chain", []) + [in_reply_to_id]
        else:
            # Replying to external tweet we don't track
            parent_chain = [in_reply_to_id]

    # Create tweet object
    tweet = {
        "id": posted_tweet_id,
        "text": text,
        "likes": 0,
        "retweets": 0,
        "quotes": 0,
        "replies": 0,
        "impressions": 0,
        "created_at": created_at,
        "url": f"https://x.com/{username}/status/{posted_tweet_id}",
        "last_metrics_update": created_at,
        "media": media,  # Reply's own media (empty for now)
        "parent_media": parent_media,  # Media from the parent tweet being replied to
        "parent_chain": parent_chain,
        "response_to_thread": response_to_thread,
        "responding_to": responding_to_handle,
        "replying_to_pfp": replying_to_pfp,
        "original_tweet_url": original_tweet_url,
        "source": "app_posted",
        "monitoring_state": "active",
        "last_activity_at": created_at,
        "last_deep_scrape": None,
        "last_shallow_scrape": None,
        "last_reply_count": 0,
        "last_like_count": 0,
        "last_quote_count": 0,
        "last_retweet_count": 0,
        "resurrected_via": "none",
        "last_scraped_reply_ids": [],
        "post_type": post_type,
        "score": 0,  # Will be updated when metrics are fetched
    }

    # Add to map
    tweets_map[posted_tweet_id] = tweet

    # Update order (prepend for newest-first)
    order = tweets_map.get("_order", [])
    tweets_map["_order"] = [posted_tweet_id] + [oid for oid in order if oid != posted_tweet_id]

    # Write back to cache
    write_posted_tweets_cache(username, tweets_map)

    notify(f"✅ Added posted tweet {posted_tweet_id} to cache for @{username}")

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

    Returns:
        Updated tweet object, or None if not found
    """
    tweets_map = read_posted_tweets_cache(username)

    if posted_tweet_id not in tweets_map or posted_tweet_id == "_order":
        notify(f"⚠️ Tweet {posted_tweet_id} not found in cache for @{username}")
        return None

    tweet = tweets_map[posted_tweet_id]
    tweet["likes"] = likes
    tweet["retweets"] = retweets
    tweet["quotes"] = quotes
    tweet["replies"] = replies
    tweet["impressions"] = impressions
    tweet["last_metrics_update"] = datetime.now(UTC).isoformat()

    # Update engagement score
    tweet["score"] = calculate_engagement_score(likes, retweets, quotes, replies)

    write_posted_tweets_cache(username, tweets_map)

    notify(f"✅ Updated metrics for tweet {posted_tweet_id}: {likes}L {retweets}RT {quotes}Q {replies}R (score: {tweet['score']})")
    return tweet


def update_tweet_media(
    username: str,
    posted_tweet_id: str,
    media: list[dict]
) -> dict[str, Any] | None:
    """
    Update media for a posted tweet.

    Args:
        username: User's cache key
        posted_tweet_id: Tweet ID to update
        media: List of media items [{type: "photo", url: "...", alt_text: "..."}]

    Returns:
        Updated tweet object, or None if not found
    """
    tweets_map = read_posted_tweets_cache(username)

    if posted_tweet_id not in tweets_map or posted_tweet_id == "_order":
        return None

    tweet = tweets_map[posted_tweet_id]
    tweet["media"] = media

    write_posted_tweets_cache(username, tweets_map)

    notify(f"✅ Updated media for tweet {posted_tweet_id}: {len(media)} items")
    return tweet


def delete_posted_tweet_from_cache(username: str, posted_tweet_id: str) -> bool:
    """
    Delete a posted tweet from the cache.

    Args:
        username: User's Twitter handle
        posted_tweet_id: Twitter's ID for the posted tweet to delete

    Returns:
        True if tweet was found and deleted, False otherwise
    """
    tweets_map = read_posted_tweets_cache(username)

    if posted_tweet_id not in tweets_map or posted_tweet_id == "_order":
        notify(f"⚠️ Tweet {posted_tweet_id} not found in posted tweets cache for @{username}")
        return False

    # Remove from map
    del tweets_map[posted_tweet_id]

    # Remove from order
    order = tweets_map.get("_order", [])
    tweets_map["_order"] = [oid for oid in order if oid != posted_tweet_id]

    write_posted_tweets_cache(username, tweets_map)
    notify(f"✅ Deleted posted tweet {posted_tweet_id} from cache for @{username}")
    return True


def get_user_tweet_ids(username: str) -> set[str]:
    """Get set of all tweet IDs authored by the user."""
    tweets_map = read_posted_tweets_cache(username)
    return set(k for k in tweets_map.keys() if k != "_order")


def get_tweets_by_monitoring_state(username: str, states: list[str]) -> list[dict[str, Any]]:
    """Get tweets filtered by monitoring state, sorted by last_activity_at descending."""
    tweets_map = read_posted_tweets_cache(username)

    tweets = [
        t for tid, t in tweets_map.items()
        if tid != "_order" and isinstance(t, dict) and t.get("monitoring_state") in states
    ]

    # Sort by last_activity_at descending
    tweets.sort(key=lambda t: t.get("last_activity_at") or "", reverse=True)

    return tweets


def update_monitoring_state(username: str, tweet_id: str, new_state: str, resurrected_via: str | None = None) -> bool:
    """Update the monitoring state of a tweet."""
    tweets_map = read_posted_tweets_cache(username)

    if tweet_id not in tweets_map or tweet_id == "_order":
        return False

    tweets_map[tweet_id]["monitoring_state"] = new_state
    tweets_map[tweet_id]["last_activity_at"] = datetime.now(UTC).isoformat()

    if resurrected_via:
        tweets_map[tweet_id]["resurrected_via"] = resurrected_via

    write_posted_tweets_cache(username, tweets_map)
    return True


def get_top_posts_by_type(
    username: str,
    post_type: PostType | None = None,
    limit: int = 10
) -> list[dict[str, Any]]:
    """
    Get top-performing posts sorted by engagement score.

    Args:
        username: User's handle
        post_type: Filter by type ("original", "reply", "comment_reply"), or None for all
        limit: Maximum number of posts to return

    Returns:
        List of posted tweets sorted by score descending
    """
    tweets_map = read_posted_tweets_cache(username)

    # Filter by post_type if specified
    tweets = []
    for tid, tweet in tweets_map.items():
        if tid == "_order" or not isinstance(tweet, dict):
            continue
        if post_type is None or tweet.get("post_type") == post_type:
            tweets.append(tweet)

    # Sort by score descending
    tweets.sort(key=lambda t: t.get("score", 0), reverse=True)

    return tweets[:limit]


def get_replies_to_account(
    username: str,
    target_account: str,
    limit: int = 10,
    post_type: PostType = "reply"
) -> list[dict[str, Any]]:
    """
    Get replies to a specific account, sorted by engagement score.

    Args:
        username: User's handle (whose posted tweets cache to read)
        target_account: The handle of the account being replied to (without @)
        limit: Maximum number of replies to return
        post_type: Filter by post type ("reply" or "comment_reply")

    Returns:
        List of replies to that account, sorted by score descending
    """
    tweets_map = read_posted_tweets_cache(username)

    # Normalize target account (remove @ if present)
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

    # Sort by score descending
    replies.sort(key=lambda t: t.get("score", 0), reverse=True)

    return replies[:limit]


def get_top_posts_for_llm_context(username: str, limit_per_type: int = 10) -> dict[str, list[dict[str, Any]]]:
    """
    Get top-performing posts of each type for LLM context.

    Args:
        username: User's handle
        limit_per_type: Maximum number of posts per type

    Returns:
        Dict with keys "original", "reply", "comment_reply", each containing a list of posts
    """
    return {
        "original": get_top_posts_by_type(username, "original", limit_per_type),
        "reply": get_top_posts_by_type(username, "reply", limit_per_type),
        "comment_reply": get_top_posts_by_type(username, "comment_reply", limit_per_type),
    }


def build_examples_from_posts(posts: list[dict[str, Any]], post_type: PostType) -> list[str]:
    """
    Build example strings from posts for LLM prompts.

    Args:
        posts: List of posted tweets
        post_type: Type of posts for formatting

    Returns:
        List of formatted example strings
    """
    examples = []

    for post in posts:
        text = post.get("text", "")
        score = post.get("score", 0)
        likes = post.get("likes", 0)
        retweets = post.get("retweets", 0)

        if post_type == "reply":
            # Format: original thread -> your reply
            original = post.get("response_to_thread", [])
            responding_to = post.get("responding_to", "")
            if original and text:
                original_text = " | ".join(original)[:500]
                example = f"[ORIGINAL @{responding_to}]: {original_text}\n[YOUR REPLY ({likes}L, {retweets}RT)]: {text}"
                examples.append(example)

        elif post_type == "comment_reply":
            # For comment replies, we need to reconstruct the context
            # The parent_chain should help, but we store the text directly
            if text:
                responding_to = post.get("responding_to", "someone")
                example = f"[YOUR COMMENT REPLY ({likes}L, {retweets}RT)]: {text}"
                examples.append(example)

        elif post_type == "original":
            # Original posts - just the text
            if text:
                example = f"[YOUR POST ({likes}L, {retweets}RT)]: {text}"
                examples.append(example)

    return examples
