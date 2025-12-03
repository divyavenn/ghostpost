"""
API routes for comment management.

Provides endpoints for:
- Listing comments with pagination
- Getting single comment with thread context
- Updating comment status
- Posting replies to comments
- Running engagement monitoring jobs
"""
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel

from backend.utlils.utils import error, notify, read_user_info


router = APIRouter(prefix="/comments", tags=["comments"])


class UpdateCommentStatusRequest(BaseModel):
    status: str  # "pending", "replied", "skipped"


class PostCommentReplyRequest(BaseModel):
    text: str
    reply_index: int | None = None


@router.get("/{username}")
async def get_comments(
    username: str,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status: str | None = Query(default=None, description="Filter by status: pending, replied, skipped")
) -> dict:
    """
    Get comments list with pagination.

    Returns comments on user's tweets from other users.
    """
    from backend.data.twitter.comments_cache import get_comments_list, read_comments_cache

    comments = get_comments_list(username, limit=limit, offset=offset, status_filter=status)

    # Get total count for pagination
    all_comments = read_comments_cache(username)
    total = len([k for k in all_comments.keys() if k != "_order"])

    # If filtered, count filtered
    if status:
        filtered_count = sum(
            1 for k, c in all_comments.items()
            if k != "_order" and isinstance(c, dict) and c.get("status") == status
        )
    else:
        filtered_count = total

    return {
        "comments": comments,
        "total": filtered_count,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(comments) < filtered_count
    }


@router.get("/{username}/{comment_id}")
async def get_comment(username: str, comment_id: str) -> dict:
    """
    Get a single comment with its thread context.
    """
    from backend.data.twitter.comments_cache import get_comment as get_comment_from_cache
    from backend.data.twitter.comments_cache import get_thread_context

    comment = get_comment_from_cache(username, comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    # Get thread context for display
    thread_context = get_thread_context(comment_id, username)

    return {
        "comment": comment,
        "thread_context": thread_context
    }


@router.patch("/{username}/{comment_id}/status")
async def update_comment_status(
    username: str,
    comment_id: str,
    payload: UpdateCommentStatusRequest
) -> dict:
    """
    Update the status of a comment.

    Valid statuses: pending, replied, skipped
    """
    from backend.data.twitter.comments_cache import update_comment_status as do_update_status

    valid_statuses = ["pending", "replied", "skipped"]
    if payload.status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {valid_statuses}"
        )

    success = do_update_status(username, comment_id, payload.status)
    if not success:
        raise HTTPException(status_code=404, detail="Comment not found")

    return {
        "message": f"Comment status updated to {payload.status}",
        "comment_id": comment_id,
        "new_status": payload.status
    }


@router.post("/{username}/{comment_id}/reply")
async def post_comment_reply(
    username: str,
    comment_id: str,
    payload: PostCommentReplyRequest
) -> dict:
    """
    Post a reply to a comment via Twitter API.

    This will:
    1. Post the reply to Twitter
    2. Add the reply to posted_tweets cache
    3. Update the comment status to "replied"
    """
    from backend.data.twitter.comments_cache import (
        get_comment as get_comment_from_cache,
        update_comment_status,
    )
    from backend.twitter.posting import post

    # Get the comment
    comment = get_comment_from_cache(username, comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    # Build the payload for posting
    post_payload = {
        "text": payload.text,
        "reply": {
            "in_reply_to_tweet_id": comment_id
        }
    }

    try:
        # Post via Twitter API
        result = await post(
            username=username,
            payload=post_payload,
            cache_id=None,  # Comments don't have cache_id
            reply_index=payload.reply_index
        )

        # Update comment status to replied
        update_comment_status(username, comment_id, "replied")

        return {
            "message": "Reply posted successfully",
            "comment_id": comment_id,
            "posted_tweet_id": result.get("posted_tweet_id"),
            "twitter_response": result
        }

    except HTTPException:
        raise
    except Exception as e:
        error(f"Error posting reply to comment {comment_id}: {e}", status_code=500, function_name="post_comment_reply", username=username, critical=True)


@router.delete("/{username}/{comment_id}")
async def skip_comment(username: str, comment_id: str) -> dict:
    """
    Skip a comment (mark as skipped, don't delete).
    """
    from backend.data.twitter.comments_cache import update_comment_status

    success = update_comment_status(username, comment_id, "skipped")
    if not success:
        raise HTTPException(status_code=404, detail="Comment not found")

    return {
        "message": "Comment skipped",
        "comment_id": comment_id
    }


@router.get("/{username}/stats/summary")
async def get_comments_stats(username: str) -> dict:
    """
    Get summary statistics for comments.
    """
    from backend.data.twitter.comments_cache import read_comments_cache

    comments_map = read_comments_cache(username)

    stats = {
        "total": 0,
        "pending": 0,
        "replied": 0,
        "skipped": 0
    }

    for cid, comment in comments_map.items():
        if cid == "_order" or not isinstance(comment, dict):
            continue

        stats["total"] += 1
        status = comment.get("status", "pending")
        if status in stats:
            stats[status] += 1

    return stats


# Engagement monitoring endpoints
@router.post("/{username}/monitor/start")
async def start_engagement_monitoring(
    username: str,
    background_tasks: BackgroundTasks
) -> dict:
    """
    Start background engagement monitoring.

    Runs all three jobs in order:
    1. discover_recently_posted
    2. discover_engagement
    3. discover_resurrected
    """
    from backend.backend.twitter.monitoring import run_engagement_monitoring

    user_info = read_user_info(username)
    if not user_info:
        raise HTTPException(status_code=404, detail="User not found")

    user_handle = user_info.get("handle", username)

    # Run in background
    background_tasks.add_task(run_engagement_monitoring, username, user_handle)

    notify(f"🚀 Started engagement monitoring for @{user_handle}")

    return {
        "message": "Engagement monitoring started in background",
        "username": username,
        "handle": user_handle
    }


@router.post("/{username}/monitor/discover-recent")
async def run_discover_recently_posted(
    username: str,
    background_tasks: BackgroundTasks,
    max_tweets: int = Query(default=50, ge=1, le=200)
) -> dict:
    """
    Run discover_recently_posted job to find external tweets.
    """
    from backend.backend.twitter.monitoring import discover_recently_posted

    user_info = read_user_info(username)
    if not user_info:
        raise HTTPException(status_code=404, detail="User not found")

    user_handle = user_info.get("handle", username)

    # Run in background
    background_tasks.add_task(discover_recently_posted, username, user_handle, max_tweets)

    return {
        "message": "discover_recently_posted started",
        "username": username,
        "handle": user_handle,
        "max_tweets": max_tweets
    }


@router.post("/{username}/monitor/discover-engagement")
async def run_discover_engagement(
    username: str,
    background_tasks: BackgroundTasks
) -> dict:
    """
    Run discover_engagement job to monitor active/warm tweets.
    """
    from backend.backend.twitter.monitoring import discover_engagement

    user_info = read_user_info(username)
    if not user_info:
        raise HTTPException(status_code=404, detail="User not found")

    user_handle = user_info.get("handle", username)

    # Run in background
    background_tasks.add_task(discover_engagement, username, user_handle)

    return {
        "message": "discover_engagement started",
        "username": username,
        "handle": user_handle
    }


@router.post("/{username}/monitor/discover-resurrected")
async def run_discover_resurrected(
    username: str,
    background_tasks: BackgroundTasks
) -> dict:
    """
    Run discover_resurrected job to check notifications for cold tweets.
    """
    from backend.backend.twitter.monitoring import discover_resurrected

    user_info = read_user_info(username)
    if not user_info:
        raise HTTPException(status_code=404, detail="User not found")

    user_handle = user_info.get("handle", username)

    # Run in background
    background_tasks.add_task(discover_resurrected, username, user_handle)

    return {
        "message": "discover_resurrected started",
        "username": username,
        "handle": user_handle
    }


# Posted tweets monitoring state endpoints
@router.get("/{username}/posted-tweets")
async def get_posted_tweets_by_state(
    username: str,
    states: str = Query(default="active,warm", description="Comma-separated monitoring states"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0)
) -> dict:
    """
    Get posted tweets filtered by monitoring state.
    """
    from backend.data.twitter.posted_tweets_cache import get_tweets_by_monitoring_state

    state_list = [s.strip() for s in states.split(",")]
    valid_states = ["active", "warm", "cold"]

    for state in state_list:
        if state not in valid_states:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid state '{state}'. Must be one of: {valid_states}"
            )

    tweets = get_tweets_by_monitoring_state(username, state_list)

    # Apply pagination
    paginated = tweets[offset:offset + limit]
    total = len(tweets)

    return {
        "tweets": paginated,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(paginated) < total,
        "states": state_list
    }


@router.get("/{username}/posted-tweets/stats")
async def get_posted_tweets_stats(username: str) -> dict:
    """
    Get statistics for posted tweets by monitoring state.
    """
    from backend.data.twitter.posted_tweets_cache import read_posted_tweets_cache

    tweets_map = read_posted_tweets_cache(username)

    stats = {
        "total": 0,
        "active": 0,
        "warm": 0,
        "cold": 0,
        "by_source": {
            "app_posted": 0,
            "external": 0
        }
    }

    for tid, tweet in tweets_map.items():
        if tid == "_order" or not isinstance(tweet, dict):
            continue

        stats["total"] += 1

        state = tweet.get("monitoring_state", "active")
        if state in stats:
            stats[state] += 1

        source = tweet.get("source", "app_posted")
        if source in stats["by_source"]:
            stats["by_source"][source] += 1

    return stats
