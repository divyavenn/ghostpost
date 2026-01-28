"""
Manage comments cache in [handle]_comments.json files.
Stores comments (replies from others) on user's tweets.

Storage format: Map with _order array for pagination
{
    "_order": ["id3", "id2", "id1"],  // newest first
    "id1": { comment data },
    "id2": { comment data },
    ...
}
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Any

try:  # Python 3.11+
    from datetime import UTC
except ImportError:
    from datetime import timezone
    UTC = timezone.utc

from backend.utlils.utils import CACHE_DIR, _cache_key, notify


def get_comments_path(username: str) -> Path:
    """Get the path to the comments cache file for a user."""
    return CACHE_DIR / f"{_cache_key(username)}_comments.json"


def read_comments_cache(username: str) -> dict[str, Any]:
    """
    Read comments from cache file.
    Returns map with _order array for pagination.
    """
    from pydantic import ValidationError

    from backend.data.twitter.data_validation import CommentRecord
    from backend.utlils.utils import error

    cache_path = get_comments_path(username)

    if not cache_path.exists():
        return {"_order": []}

    try:
        with open(cache_path, encoding="utf-8") as f:
            data = json.load(f)

        # Ensure it's a map with _order
        if not isinstance(data, dict):
            error("Invalid comments cache format", status_code=500, function_name="read_comments_cache", username=username)
            return {"_order": []}

        if "_order" not in data:
            data["_order"] = [k for k in data.keys()]

        # Validate each comment (skip _order)
        for comment_id, comment in list(data.items()):
            if comment_id == "_order":
                continue

            try:
                validated = CommentRecord(**comment)
                data[comment_id] = validated.model_dump()
            except ValidationError as e:
                error(f"Invalid comment data for comment {comment_id}", status_code=500, exception_text=str(e), function_name="read_comments_cache", username=username)
                # Keep invalid comment but log the error

        return data

    except Exception as e:
        error("Error reading comments cache", status_code=500, exception_text=str(e), function_name="read_comments_cache", username=username)
        notify(f"❌ Error reading comments cache for {username}: {e}")
        return {"_order": []}


def write_comments_cache(username: str, comments_map: dict[str, Any]) -> None:
    """
    Write comments to cache file.
    Overwrites the entire file.
    """
    from pydantic import ValidationError

    from backend.data.twitter.data_validation import CommentRecord
    from backend.utlils.utils import error

    cache_path = get_comments_path(username)
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    # Ensure _order exists
    if "_order" not in comments_map:
        comments_map["_order"] = [k for k in comments_map.keys() if k != "_order"]

    # Validate each comment before writing (skip _order)
    for comment_id, comment in list(comments_map.items()):
        if comment_id == "_order":
            continue

        try:
            validated = CommentRecord(**comment)
            comments_map[comment_id] = validated.model_dump()
        except ValidationError as e:
            error(f"Invalid comment data for comment {comment_id}", status_code=500, exception_text=str(e), function_name="write_comments_cache", username=username)
            # Still include the comment but log the error

    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(comments_map, f, indent=2, ensure_ascii=False)
    except Exception as e:
        error("Error writing comments cache", status_code=500, exception_text=str(e), function_name="write_comments_cache", username=username)
        notify(f"❌ Error writing comments cache for {username}: {e}")
        raise


def get_comments_list(
    username: str,
    limit: int | None = None,
    offset: int = 0,
    status_filter: str | None = None
) -> list[dict[str, Any]]:
    """
    Get comments as a list for pagination.
    Returns comments in order (newest first).

    Args:
        username: User's Twitter handle
        limit: Maximum number of comments to return
        offset: Number of comments to skip
        status_filter: Optional filter by status ("pending", "replied", "skipped")
    """
    comments_map = read_comments_cache(username)
    order = comments_map.get("_order", [])

    # Get all comments in order
    comments = [comments_map[cid] for cid in order if cid in comments_map and cid != "_order"]

    # Apply status filter if provided
    if status_filter:
        comments = [c for c in comments if c.get("status") == status_filter]

    # Apply pagination
    if limit is not None:
        return comments[offset:offset + limit]
    return comments[offset:]


def get_comment(username: str, comment_id: str) -> dict[str, Any] | None:
    """Get a single comment by ID."""
    comments_map = read_comments_cache(username)
    return comments_map.get(comment_id)


def add_comment(
    username: str,
    comment_id: str,
    text: str,
    handle: str,
    commenter_username: str,
    in_reply_to_id: str,
    parent_chain: list[str],
    created_at: str,
    url: str,
    author_profile_pic_url: str = "",
    followers: int = 0,
    likes: int = 0,
    retweets: int = 0,
    quotes: int = 0,
    replies: int = 0,
    impressions: int = 0,
    thread: list[str] | None = None,
    other_replies: list[dict] | None = None,
    media: list[dict] | None = None,
    quoted_tweet: dict | None = None,
    engagement_type: str = "reply"  # "reply" or "quote_tweet"
) -> dict[str, Any]:
    """
    Add a new comment to the cache.

    Returns:
        The created comment object
    """
    comments_map = read_comments_cache(username)

    # Check if already exists
    if comment_id in comments_map:
        # Update metrics only
        update_comment_metrics(
            username, comment_id,
            likes=likes, retweets=retweets, quotes=quotes, replies=replies, impressions=impressions
        )
        return comments_map[comment_id]

    comment = {
        "id": comment_id,
        "text": text,
        "handle": handle,
        "username": commenter_username,
        "author_profile_pic_url": author_profile_pic_url,
        "followers": followers,
        "likes": likes,
        "retweets": retweets,
        "quotes": quotes,
        "replies": replies,
        "impressions": impressions,
        "created_at": created_at,
        "url": url,
        "last_metrics_update": datetime.now(UTC).isoformat(),
        "parent_chain": parent_chain,
        "in_reply_to_status_id": in_reply_to_id,
        "status": "pending",
        "generated_replies": [],
        "edited": False,
        "source": "external",
        "monitoring_state": "active",
        "last_activity_at": created_at,
        "last_deep_scrape": None,
        "last_shallow_scrape": None,
        "last_reply_count": replies,
        "last_like_count": likes,
        "last_quote_count": quotes,
        "last_retweet_count": retweets,
        "resurrected_via": "none",
        "last_scraped_reply_ids": [],
        "thread": thread or [],
        "other_replies": other_replies or [],
        "media": media or [],
        "quoted_tweet": quoted_tweet,
        "engagement_type": engagement_type  # "reply" or "quote_tweet"
    }

    # Add to map
    comments_map[comment_id] = comment

    # Update order (prepend for newest-first)
    order = comments_map.get("_order", [])
    comments_map["_order"] = [comment_id] + [oid for oid in order if oid != comment_id]

    write_comments_cache(username, comments_map)

    notify(f"💬 Added comment {comment_id} from @{handle} to cache for @{username}")

    return comment


def update_comment_metrics(
    username: str,
    comment_id: str,
    likes: int | None = None,
    retweets: int | None = None,
    quotes: int | None = None,
    replies: int | None = None,
    impressions: int | None = None
) -> dict[str, Any] | None:
    """
    Update metrics for a comment.

    Returns:
        Updated comment object, or None if not found
    """
    comments_map = read_comments_cache(username)

    if comment_id not in comments_map or comment_id == "_order":
        return None

    comment = comments_map[comment_id]

    if likes is not None:
        comment["likes"] = likes
    if retweets is not None:
        comment["retweets"] = retweets
    if quotes is not None:
        comment["quotes"] = quotes
    if replies is not None:
        comment["replies"] = replies
    if impressions is not None:
        comment["impressions"] = impressions

    comment["last_metrics_update"] = datetime.now(UTC).isoformat()

    write_comments_cache(username, comments_map)
    return comment


def update_comment_status(username: str, comment_id: str, status: str) -> bool:
    """
    Update the status of a comment.

    Args:
        username: User's Twitter handle
        comment_id: Comment ID to update
        status: New status ("pending", "replied", "skipped")

    Returns:
        True if updated, False if not found
    """
    comments_map = read_comments_cache(username)

    if comment_id not in comments_map or comment_id == "_order":
        notify(f"⚠️ Comment {comment_id} not found in cache for @{username}")
        return False

    comments_map[comment_id]["status"] = status
    write_comments_cache(username, comments_map)

    notify(f"✅ Updated comment {comment_id} status to {status}")
    return True


def update_comment_generated_replies(
    username: str,
    comment_id: str,
    generated_replies: list[tuple[str, str]]
) -> bool:
    """
    Update the generated replies for a comment.

    Args:
        username: User's Twitter handle
        comment_id: Comment ID to update
        generated_replies: List of (reply_text, model_name) tuples

    Returns:
        True if updated, False if not found
    """
    comments_map = read_comments_cache(username)

    if comment_id not in comments_map or comment_id == "_order":
        return False

    comments_map[comment_id]["generated_replies"] = generated_replies
    write_comments_cache(username, comments_map)
    return True


def delete_comment(username: str, comment_id: str) -> bool:
    """
    Delete a comment from the cache.

    Returns:
        True if deleted, False if not found
    """
    comments_map = read_comments_cache(username)

    if comment_id not in comments_map or comment_id == "_order":
        notify(f"⚠️ Comment {comment_id} not found in cache for @{username}")
        return False

    # Remove from map
    del comments_map[comment_id]

    # Remove from order
    order = comments_map.get("_order", [])
    comments_map["_order"] = [oid for oid in order if oid != comment_id]

    write_comments_cache(username, comments_map)
    notify(f"✅ Deleted comment {comment_id} from cache for @{username}")
    return True


def get_pending_comments_count(username: str) -> int:
    """Get count of pending comments."""
    comments_map = read_comments_cache(username)
    return sum(
        1 for cid, c in comments_map.items()
        if cid != "_order" and isinstance(c, dict) and c.get("status") == "pending"
    )


def get_user_replied_comment_ids(username: str) -> set[str]:
    """
    Get the set of comment IDs that the user has already replied to.

    Checks posted_tweets cache for any tweets that are replies to comments.

    Returns:
        Set of comment IDs that the user has responded to
    """
    from backend.data.twitter.posted_tweets_cache import read_posted_tweets_cache

    posted_tweets = read_posted_tweets_cache(username)
    replied_to_ids = set()

    for tweet_id, tweet in posted_tweets.items():
        if tweet_id == "_order" or not isinstance(tweet, dict):
            continue

        # Check in_reply_to_status_id (direct reply parent)
        in_reply_to = tweet.get("in_reply_to_status_id")
        if in_reply_to:
            replied_to_ids.add(in_reply_to)

        # Also check parent_chain for nested replies
        parent_chain = tweet.get("parent_chain", [])
        for parent_id in parent_chain:
            replied_to_ids.add(parent_id)

    return replied_to_ids


def get_thread_context(
    tweet_id: str,
    username: str,
    posted_tweets: dict[str, Any] | None = None,
    comments: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    """
    Get full thread context for a tweet/comment.
    Returns ordered list from root -> current tweet.

    Args:
        tweet_id: The tweet/comment ID to get context for
        username: User's Twitter handle
        posted_tweets: Optional pre-loaded posted tweets cache (for performance)
        comments: Optional pre-loaded comments cache (for performance)
    """
    from backend.data.twitter.posted_tweets_cache import read_posted_tweets_cache

    # Load caches only if not provided (for backward compatibility)
    if posted_tweets is None:
        posted_tweets = read_posted_tweets_cache(username)
    if comments is None:
        comments = read_comments_cache(username)
    user_tweet_ids = set(k for k in posted_tweets.keys() if k != "_order")

    tweet = posted_tweets.get(tweet_id) or comments.get(tweet_id)
    if not tweet:
        return []

    chain = []
    for ancestor_id in tweet.get("parent_chain", []):
        ancestor = posted_tweets.get(ancestor_id) or comments.get(ancestor_id)
        if ancestor and isinstance(ancestor, dict):
            # Get media - check both 'media' (tweet's own) and 'parent_media' (parent's media)
            # For thread context display, we show the tweet's own media
            ancestor_media = ancestor.get("media", [])
            chain.append({
                "id": ancestor_id,
                "text": ancestor.get("text", ""),
                "handle": ancestor.get("handle", ancestor.get("responding_to", "")),
                "username": ancestor.get("username", ""),
                "author_profile_pic_url": ancestor.get("author_profile_pic_url", ancestor.get("replying_to_pfp", "")),
                "is_user": ancestor_id in user_tweet_ids,
                "followers": ancestor.get("followers", 0),
                "media": ancestor_media if ancestor_media else []
            })
        else:
            # Ancestor was deleted or not tracked
            chain.append({
                "id": ancestor_id,
                "text": "<tweet deleted>",
                "handle": "",
                "username": "",
                "author_profile_pic_url": "",
                "is_user": False,
                "deleted": True,
                "media": []
            })

    # Add current tweet
    # Get media for current tweet
    current_media = tweet.get("media", [])
    chain.append({
        "id": tweet_id,
        "text": tweet.get("text", ""),
        "handle": tweet.get("handle", tweet.get("responding_to", "")),
        "username": tweet.get("username", ""),
        "author_profile_pic_url": tweet.get("author_profile_pic_url", tweet.get("replying_to_pfp", "")),
        "is_user": tweet_id in user_tweet_ids,
        "followers": tweet.get("followers", 0),
        "media": current_media if current_media else []
    })

    return chain


def process_scraped_replies(
    username: str,
    scraped_replies: list[dict[str, Any]],
    user_handle: str
) -> list[str]:
    """
    Process scraped replies and add new comments to cache.

    Only adds comments that the user has NOT already replied to.
    Also removes any existing cached comments that user has replied to externally.

    Args:
        username: User's Twitter handle (for cache)
        scraped_replies: List of reply dicts from scraping
        user_handle: User's Twitter handle (for filtering out user's own tweets)

    Returns:
        List of new comment IDs that were added
    """
    from backend.data.twitter.posted_tweets_cache import read_posted_tweets_cache

    posted_tweets = read_posted_tweets_cache(username)
    comments_map = read_comments_cache(username)
    user_tweet_ids = set(k for k in posted_tweets.keys() if k != "_order")

    # Get IDs of comments the user has already replied to
    user_replied_ids = get_user_replied_comment_ids(username)

    # First pass: Check if any scraped replies are FROM the user
    # If so, their parent comment should be removed from cache
    user_reply_parent_ids = set()
    for reply in scraped_replies:
        reply_handle = reply.get("handle", "")
        if reply_handle.lower() == user_handle.lower():
            # This is a user's reply - mark its parent for removal
            parent_id = reply.get("in_reply_to_status_id")
            if parent_id:
                user_reply_parent_ids.add(parent_id)

    # Remove cached comments that user has replied to (externally or from scraped data)
    all_replied_ids = user_replied_ids | user_reply_parent_ids
    removed_count = 0
    for comment_id in list(comments_map.keys()):
        if comment_id == "_order":
            continue
        if comment_id in all_replied_ids:
            delete_comment(username, comment_id)
            removed_count += 1
            # Refresh comments_map after deletion
            comments_map = read_comments_cache(username)

    if removed_count > 0:
        notify(f"🧹 Removed {removed_count} already-replied comments from cache for @{username}")

    new_comment_ids = []

    for reply in scraped_replies:
        reply_id = reply.get("id")
        reply_handle = reply.get("handle", "")

        if not reply_id:
            continue

        # Skip user's own tweets
        if reply_handle.lower() == user_handle.lower():
            continue

        # Skip if user has already replied to this comment
        if reply_id in all_replied_ids:
            continue

        # Skip if already in comments (just update metrics)
        if reply_id in comments_map:
            update_comment_metrics(
                username, reply_id,
                likes=reply.get("likes", 0),
                retweets=reply.get("retweets", 0),
                quotes=reply.get("quotes", 0),
                replies=reply.get("replies", 0),
                impressions=reply.get("impressions", 0)
            )
            continue

        in_reply_to_id = reply.get("in_reply_to_status_id")
        if not in_reply_to_id:
            continue

        # Build parent_chain
        parent = posted_tweets.get(in_reply_to_id) or comments_map.get(in_reply_to_id)
        if parent and isinstance(parent, dict):
            parent_chain = parent.get("parent_chain", []) + [in_reply_to_id]
        else:
            parent_chain = [in_reply_to_id]

        # Only track if root is user's tweet
        root_id = parent_chain[0] if parent_chain else in_reply_to_id
        if root_id not in user_tweet_ids:
            continue

        # Add comment
        add_comment(
            username=username,
            comment_id=reply_id,
            text=reply.get("text", ""),
            handle=reply_handle,
            commenter_username=reply.get("username", reply_handle),
            in_reply_to_id=in_reply_to_id,
            parent_chain=parent_chain,
            created_at=reply.get("created_at", datetime.now(UTC).isoformat()),
            url=reply.get("url", f"https://x.com/{reply_handle}/status/{reply_id}"),
            author_profile_pic_url=reply.get("author_profile_pic_url", ""),
            followers=reply.get("followers", 0),
            likes=reply.get("likes", 0),
            retweets=reply.get("retweets", 0),
            quotes=reply.get("quotes", 0),
            replies=reply.get("replies", 0),
            impressions=reply.get("impressions", 0),
            thread=reply.get("thread"),
            other_replies=reply.get("other_replies"),
            media=reply.get("media"),
            quoted_tweet=reply.get("quoted_tweet")
        )

        new_comment_ids.append(reply_id)

        # Also add to comments_map for subsequent lookups in this loop
        comments_map = read_comments_cache(username)

    if new_comment_ids:
        notify(f"💬 Found {len(new_comment_ids)} new comments for @{username}")

    return new_comment_ids


def process_scraped_quote_tweets(
    username: str,
    scraped_quote_tweets: list[dict[str, Any]],
    user_handle: str,
    quoted_tweet_id: str
) -> list[str]:
    """
    Process scraped quote tweets and add new ones to cache as engagement opportunities.

    Quote tweets are stored similarly to comments but with engagement_type="quote_tweet".
    The quoted_tweet_id links back to the user's original tweet.

    Args:
        username: User's Twitter handle (for cache)
        scraped_quote_tweets: List of quote tweet dicts from scraping
        user_handle: User's Twitter handle (for filtering out user's own tweets)
        quoted_tweet_id: The ID of the user's tweet that was quoted

    Returns:
        List of new quote tweet IDs that were added
    """
    from backend.data.twitter.posted_tweets_cache import read_posted_tweets_cache

    posted_tweets = read_posted_tweets_cache(username)
    comments_map = read_comments_cache(username)
    user_tweet_ids = set(k for k in posted_tweets.keys() if k != "_order")

    # Verify the quoted tweet belongs to the user
    if quoted_tweet_id not in user_tweet_ids:
        return []

    # Get IDs of comments the user has already replied to
    user_replied_ids = get_user_replied_comment_ids(username)

    new_qt_ids = []

    for qt in scraped_quote_tweets:
        qt_id = qt.get("id")
        qt_handle = qt.get("handle", "")

        if not qt_id:
            continue

        # Skip user's own quote tweets
        if qt_handle.lower() == user_handle.lower():
            continue

        # Skip if user has already replied to this QT
        if qt_id in user_replied_ids:
            continue

        # Skip if already in comments (just update metrics)
        if qt_id in comments_map:
            update_comment_metrics(
                username, qt_id,
                likes=qt.get("likes", 0),
                retweets=qt.get("retweets", 0),
                quotes=qt.get("quotes", 0),
                replies=qt.get("replies", 0),
                impressions=qt.get("impressions", 0)
            )
            continue

        # For QTs, the "parent" is the quoted tweet, not in_reply_to
        # parent_chain is just [quoted_tweet_id] since QT directly references user's tweet
        parent_chain = [quoted_tweet_id]

        # Add as a comment with engagement_type marker
        add_comment(
            username=username,
            comment_id=qt_id,
            text=qt.get("text", ""),
            handle=qt_handle,
            commenter_username=qt.get("username", qt_handle),
            in_reply_to_id=quoted_tweet_id,  # QT is in response to this tweet
            parent_chain=parent_chain,
            created_at=qt.get("created_at", datetime.now(UTC).isoformat()),
            url=qt.get("url", f"https://x.com/{qt_handle}/status/{qt_id}"),
            author_profile_pic_url=qt.get("author_profile_pic_url", ""),
            followers=qt.get("followers", 0),
            likes=qt.get("likes", 0),
            retweets=qt.get("retweets", 0),
            quotes=qt.get("quotes", 0),
            replies=qt.get("replies", 0),
            impressions=qt.get("impressions", 0),
            thread=None,  # QTs don't have thread context in same way
            other_replies=None,
            media=qt.get("media"),
            quoted_tweet=None,  # The QT itself is the quote, not quoting another
            engagement_type="quote_tweet"  # Mark this as a quote tweet
        )

        new_qt_ids.append(qt_id)

        # Refresh comments_map for subsequent lookups
        comments_map = read_comments_cache(username)

    if new_qt_ids:
        notify(f"💬 Found {len(new_qt_ids)} new quote tweets for @{username}")

    return new_qt_ids
