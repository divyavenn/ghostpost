"""
Manage posted tweets cache in [handle]_posted_tweets.json files.
Stores full tweet data including performance metrics.
"""
import json
from pathlib import Path
from typing import Any

try:  # Python 3.11+
    from datetime import UTC  # type: ignore[attr-defined]
except ImportError:  # Python <3.11
    UTC = UTC

from backend.utlils.utils import CACHE_DIR, _cache_key, notify


def get_posted_tweets_path(username: str) -> Path:
    """Get the path to the posted tweets cache file for a user."""
    return CACHE_DIR / f"{_cache_key(username)}_posted_tweets.json"


def read_posted_tweets_cache(username: str) -> list[dict[str, Any]]:
    """
    Read posted tweets from cache file.
    Returns list of tweet objects sorted by created_at (newest first).
    """
    from pydantic import ValidationError

    from backend.data.twitter.data_validation import PostedTweet
    from backend.utlils.utils import error

    cache_path = get_posted_tweets_path(username)

    if not cache_path.exists():
        return []

    try:
        with open(cache_path, encoding="utf-8") as f:
            tweets = json.load(f)

        # Ensure it's a list
        if not isinstance(tweets, list):
            error("Invalid posted tweets cache format: expected list", status_code=500, function_name="read_posted_tweets_cache", username=username)
            return []

        # Validate each tweet
        validated_tweets = []
        for idx, tweet in enumerate(tweets):
            try:
                validated = PostedTweet(**tweet)
                validated_tweets.append(validated.model_dump())
            except ValidationError as e:
                tweet_id = tweet.get("id", f"index_{idx}")
                error(f"Invalid posted tweet data for tweet {tweet_id}", status_code=500, exception_text=str(e), function_name="read_posted_tweets_cache", username=username)
                # Include invalid tweet but log the error
                validated_tweets.append(tweet)

        return validated_tweets

    except Exception as e:
        error("Error reading posted tweets cache", status_code=500, exception_text=str(e), function_name="read_posted_tweets_cache", username=username)
        notify(f"❌ Error reading posted tweets cache for {username}: {e}")
        return []


def write_posted_tweets_cache(username: str, tweets: list[dict[str, Any]]) -> None:
    """
    Write posted tweets to cache file.
    Overwrites the entire file.
    """
    from pydantic import ValidationError

    from backend.data.twitter.data_validation import PostedTweet
    from backend.utlils.utils import error

    cache_path = get_posted_tweets_path(username)
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    # Validate each tweet before writing
    validated_tweets = []
    for idx, tweet in enumerate(tweets):
        try:
            validated = PostedTweet(**tweet)
            validated_tweets.append(validated.model_dump())
        except ValidationError as e:
            tweet_id = tweet.get("id", f"index_{idx}")
            error(f"Invalid posted tweet data for tweet {tweet_id}", status_code=500, exception_text=str(e), function_name="write_posted_tweets_cache", username=username)
            # Still include the tweet but log the error
            validated_tweets.append(tweet)

    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(validated_tweets, f, indent=2, ensure_ascii=False)
    except Exception as e:
        error("Error writing posted tweets cache", status_code=500, exception_text=str(e), function_name="write_posted_tweets_cache", username=username)
        notify(f"❌ Error writing posted tweets cache for {username}: {e}")
        raise


def add_posted_tweet(username: str,
                     posted_tweet_id: str,
                     text: str,
                     original_tweet_url: str,
                     responding_to_handle: str,
                     replying_to_pfp: str,
                     response_to_thread: list[str],
                     created_at: str | None = None) -> dict[str, Any]:
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
        created_at: ISO timestamp of when tweet was created (defaults to now)

    Returns:
        The created tweet object
    """
    from datetime import datetime

    if created_at is None:
        created_at = datetime.now(UTC).isoformat()

    # Create tweet object with initial metrics (all 0)
    tweet = {
        "id": posted_tweet_id,
        "text": text,
        "likes": 0,
        "retweets": 0,
        "quotes": 0,
        "replies": 0,
        "created_at": created_at,
        "url": f"https://x.com/{username}/status/{posted_tweet_id}",
        "response_to_thread": response_to_thread,
        "responding_to": responding_to_handle,
        "replying_to_pfp": replying_to_pfp,
        "original_tweet_url": original_tweet_url,
        "last_metrics_update": created_at  # Use creation time as initial value
    }

    # Read existing tweets
    tweets = read_posted_tweets_cache(username)

    # Add new tweet at the beginning (newest first)
    tweets.insert(0, tweet)

    # Write back to cache
    write_posted_tweets_cache(username, tweets)

    notify(f"✅ Added posted tweet {posted_tweet_id} to cache for @{username}")

    return tweet


def update_tweet_metrics(username: str, posted_tweet_id: str, likes: int, retweets: int, quotes: int, replies: int) -> dict[str, Any] | None:
    """
    Update performance metrics for a posted tweet.

    Returns:
        Updated tweet object, or None if not found
    """
    from datetime import datetime

    tweets = read_posted_tweets_cache(username)

    # Find the tweet and update metrics
    for tweet in tweets:
        if tweet.get("id") == posted_tweet_id:
            tweet["likes"] = likes
            tweet["retweets"] = retweets
            tweet["quotes"] = quotes
            tweet["replies"] = replies
            tweet["last_metrics_update"] = datetime.now(UTC).isoformat()

            # Write back to cache
            write_posted_tweets_cache(username, tweets)

            notify(f"✅ Updated metrics for tweet {posted_tweet_id}: {likes}L {retweets}RT {quotes}Q {replies}R")
            return tweet

    notify(f"⚠️ Tweet {posted_tweet_id} not found in cache for @{username}")
    return None


def delete_posted_tweet_from_cache(username: str, posted_tweet_id: str) -> bool:
    """
    Delete a posted tweet from the cache.

    Args:
        username: User's Twitter handle
        posted_tweet_id: Twitter's ID for the posted tweet to delete

    Returns:
        True if tweet was found and deleted, False otherwise
    """
    tweets = read_posted_tweets_cache(username)

    # Find and remove the tweet
    original_count = len(tweets)
    tweets = [t for t in tweets if t.get("id") != posted_tweet_id]

    if len(tweets) < original_count:
        # Tweet was found and removed
        write_posted_tweets_cache(username, tweets)
        notify(f"✅ Deleted posted tweet {posted_tweet_id} from cache for @{username}")
        return True
    else:
        notify(f"⚠️ Tweet {posted_tweet_id} not found in posted tweets cache for @{username}")
        return False
