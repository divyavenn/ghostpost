"""
Manage comments cache in Supabase.
Stores comments (replies from others) on user's tweets.
"""
from datetime import datetime
from typing import Any

try:  # Python 3.11+
    from datetime import UTC
except ImportError:
    from datetime import timezone
    UTC = timezone.utc

from backend.utlils.utils import notify


def _convert_to_map_format(comments: list[dict[str, Any]]) -> dict[str, Any]:
    """Convert a list of comments to map format with _order."""
    comments_map: dict[str, Any] = {"_order": []}
    for comment in comments:
        comment_id = comment.get("tweet_id")
        if comment_id:
            comments_map[comment_id] = comment
            comments_map["_order"].append(comment_id)
    return comments_map


def read_comments_cache(username: str) -> dict[str, Any]:
    """
    Read comments from Supabase.
    Returns map with _order array for pagination.
    """
    from backend.utlils.supabase_client import get_comments

    comments = get_comments(username)
    return _convert_to_map_format(comments or [])


def get_comments_list(
    username: str,
    limit: int | None = None,
    offset: int = 0,
    status_filter: str | None = None
) -> list[dict[str, Any]]:
    """
    Get comments as a list for pagination.
    Returns comments in order (newest first).
    """
    from backend.utlils.supabase_client import get_comments

    return get_comments(username, limit, offset, status_filter)


def get_comment(username: str, comment_id: str) -> dict[str, Any] | None:
    """Get a single comment by ID."""
    from backend.utlils.supabase_client import get_comment as sb_get_comment

    return sb_get_comment(username, comment_id)


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
    engagement_type: str = "reply"
) -> dict[str, Any]:
    """
    Add a new comment to the cache.
    """
    from backend.utlils.supabase_client import add_comment as sb_add_comment, get_comment as sb_get_comment

    # Check if already exists - update metrics only
    existing = sb_get_comment(username, comment_id)
    if existing:
        update_comment_metrics(
            username, comment_id,
            likes=likes, retweets=retweets, quotes=quotes, replies=replies, impressions=impressions
        )
        return existing

    comment = {
        "tweet_id": comment_id,
        "handle": username,
        "text": text,
        "commenter_handle": handle,
        "commenter_username": commenter_username,
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
        "resurrected_via": "none",
        "last_scraped_reply_ids": [],
        "thread": thread or [],
        "other_replies": other_replies or [],
        "media": media or [],
        "quoted_tweet": quoted_tweet,
        "engagement_type": engagement_type
    }

    sb_add_comment(comment)
    notify(f"💬 Added comment {comment_id} from @{handle} for @{username}")
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
    """
    from backend.utlils.supabase_client import update_comment as sb_update_comment

    updates = {"last_metrics_update": datetime.now(UTC).isoformat()}
    if likes is not None:
        updates["likes"] = likes
    if retweets is not None:
        updates["retweets"] = retweets
    if quotes is not None:
        updates["quotes"] = quotes
    if replies is not None:
        updates["replies"] = replies
    if impressions is not None:
        updates["impressions"] = impressions
    return sb_update_comment(comment_id, updates)


def update_comment_status(username: str, comment_id: str, status: str) -> bool:
    """
    Update the status of a comment.
    """
    from backend.utlils.supabase_client import update_comment as sb_update_comment

    result = sb_update_comment(comment_id, {"status": status})
    if result:
        notify(f"✅ Updated comment {comment_id} status to {status}")
    return result is not None


def update_comment_generated_replies(
    username: str,
    comment_id: str,
    generated_replies: list[tuple[str, str]]
) -> bool:
    """
    Update the generated replies for a comment.
    """
    from backend.utlils.supabase_client import update_comment as sb_update_comment

    result = sb_update_comment(comment_id, {"generated_replies": generated_replies})
    return result is not None


def delete_comment(username: str, comment_id: str) -> bool:
    """
    Delete a comment from the cache.
    """
    from backend.utlils.supabase_client import delete_comment as sb_delete_comment

    result = sb_delete_comment(comment_id)
    if result:
        notify(f"✅ Deleted comment {comment_id} for @{username}")
    return result


def get_pending_comments_count(username: str) -> int:
    """Get count of pending comments."""
    from backend.utlils.supabase_client import get_pending_comments_count as sb_get_count

    return sb_get_count(username)


def get_user_replied_comment_ids(username: str) -> set[str]:
    """
    Get the set of comment IDs that the user has already replied to.
    """
    from backend.data.twitter.posted_tweets_cache import read_posted_tweets_cache

    posted_tweets = read_posted_tweets_cache(username)
    replied_to_ids = set()

    for tweet_id, tweet in posted_tweets.items():
        if tweet_id == "_order" or not isinstance(tweet, dict):
            continue

        in_reply_to = tweet.get("in_reply_to_status_id")
        if in_reply_to:
            replied_to_ids.add(in_reply_to)

        parent_chain = tweet.get("parent_chain", [])
        for parent_id in parent_chain:
            replied_to_ids.add(parent_id)

    return replied_to_ids


def get_thread_context(tweet_id: str, username: str) -> list[dict[str, Any]]:
    """
    Get full thread context for a tweet/comment.
    Returns ordered list from root -> current tweet.
    """
    from backend.data.twitter.posted_tweets_cache import read_posted_tweets_cache

    posted_tweets = read_posted_tweets_cache(username)
    comments = read_comments_cache(username)
    user_tweet_ids = set(k for k in posted_tweets.keys() if k != "_order")

    tweet = posted_tweets.get(tweet_id) or comments.get(tweet_id)
    if not tweet:
        return []

    chain = []
    for ancestor_id in tweet.get("parent_chain", []):
        ancestor = posted_tweets.get(ancestor_id) or comments.get(ancestor_id)
        if ancestor and isinstance(ancestor, dict):
            ancestor_media = ancestor.get("media", [])
            chain.append({
                "tweet_id": ancestor_id,
                "text": ancestor.get("text", ""),
                "handle": ancestor.get("handle", ancestor.get("responding_to", "")),
                "username": ancestor.get("username", ""),
                "author_profile_pic_url": ancestor.get("author_profile_pic_url", ancestor.get("replying_to_pfp", "")),
                "is_user": ancestor_id in user_tweet_ids,
                "followers": ancestor.get("followers", 0),
                "media": ancestor_media if ancestor_media else []
            })
        else:
            chain.append({
                "tweet_id": ancestor_id,
                "text": "<tweet deleted>",
                "handle": "",
                "username": "",
                "author_profile_pic_url": "",
                "is_user": False,
                "deleted": True,
                "media": []
            })

    current_media = tweet.get("media", [])
    chain.append({
        "tweet_id": tweet_id,
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
    """
    from backend.data.twitter.posted_tweets_cache import read_posted_tweets_cache

    posted_tweets = read_posted_tweets_cache(username)
    comments_map = read_comments_cache(username)
    user_tweet_ids = set(k for k in posted_tweets.keys() if k != "_order")

    user_replied_ids = get_user_replied_comment_ids(username)

    # First pass: Check if any scraped replies are FROM the user
    user_reply_parent_ids = set()
    for reply in scraped_replies:
        reply_handle = reply.get("handle", "")
        if reply_handle.lower() == user_handle.lower():
            parent_id = reply.get("in_reply_to_status_id")
            if parent_id:
                user_reply_parent_ids.add(parent_id)

    # Remove cached comments that user has replied to
    all_replied_ids = user_replied_ids | user_reply_parent_ids
    removed_count = 0
    for comment_id in list(comments_map.keys()):
        if comment_id == "_order":
            continue
        if comment_id in all_replied_ids:
            delete_comment(username, comment_id)
            removed_count += 1
            comments_map = read_comments_cache(username)

    if removed_count > 0:
        notify(f"🧹 Removed {removed_count} already-replied comments from cache for @{username}")

    new_comment_ids = []

    for reply in scraped_replies:
        reply_id = reply.get("id")
        reply_handle = reply.get("handle", "")

        if not reply_id:
            continue

        if reply_handle.lower() == user_handle.lower():
            continue

        if reply_id in all_replied_ids:
            continue

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

        parent = posted_tweets.get(in_reply_to_id) or comments_map.get(in_reply_to_id)
        if parent and isinstance(parent, dict):
            parent_chain = parent.get("parent_chain", []) + [in_reply_to_id]
        else:
            parent_chain = [in_reply_to_id]

        root_id = parent_chain[0] if parent_chain else in_reply_to_id
        if root_id not in user_tweet_ids:
            continue

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
    Process scraped quote tweets and add new ones to cache.
    """
    from backend.data.twitter.posted_tweets_cache import read_posted_tweets_cache

    posted_tweets = read_posted_tweets_cache(username)
    comments_map = read_comments_cache(username)
    user_tweet_ids = set(k for k in posted_tweets.keys() if k != "_order")

    if quoted_tweet_id not in user_tweet_ids:
        return []

    user_replied_ids = get_user_replied_comment_ids(username)

    new_qt_ids = []

    for qt in scraped_quote_tweets:
        qt_id = qt.get("id")
        qt_handle = qt.get("handle", "")

        if not qt_id:
            continue

        if qt_handle.lower() == user_handle.lower():
            continue

        if qt_id in user_replied_ids:
            continue

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

        parent_chain = [quoted_tweet_id]

        add_comment(
            username=username,
            comment_id=qt_id,
            text=qt.get("text", ""),
            handle=qt_handle,
            commenter_username=qt.get("username", qt_handle),
            in_reply_to_id=quoted_tweet_id,
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
            thread=None,
            other_replies=None,
            media=qt.get("media"),
            quoted_tweet=None,
            engagement_type="quote_tweet"
        )

        new_qt_ids.append(qt_id)
        comments_map = read_comments_cache(username)

    if new_qt_ids:
        notify(f"💬 Found {len(new_qt_ids)} new quote tweets for @{username}")

    return new_qt_ids
