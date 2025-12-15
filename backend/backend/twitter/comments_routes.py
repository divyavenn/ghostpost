"""
API routes for comment management.

Provides endpoints for:
- Listing comments with pagination
- Getting single comment with thread context
- Updating comment status
- Posting replies to comments
- Running engagement monitoring jobs
"""
import asyncio

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.utlils.utils import error, notify, read_user_info


async def _run_with_error_handling(coro, func_name: str, username: str):
    """
    Wrapper that catches and logs any exceptions from background coroutines.
    asyncio.create_task() silently swallows exceptions, so we need explicit handling.
    """
    try:
        return await coro
    except Exception as e:
        import traceback
        error_msg = f"{func_name} crashed: {e}\n{traceback.format_exc()}"
        notify(f"❌ [Background] {error_msg}")
        error(error_msg, status_code=500, function_name=func_name, username=username, critical=False)


router = APIRouter(prefix="/comments", tags=["comments"])


class UpdateCommentStatusRequest(BaseModel):
    status: str  # "pending", "replied", "skipped"


class PostCommentReplyRequest(BaseModel):
    text: str
    reply_index: int | None = None


@router.get("/{username}/grouped")
async def get_comments_grouped_by_post(
    username: str,
    status: str | None = Query(default="pending", description="Filter by status: pending, replied, skipped")
) -> dict:
    """
    Get comments grouped by the parent post they're replying to.

    Returns a list of posts with their associated comments.
    Each post includes all comments on that post with generated replies.
    """
    from backend.data.twitter.comments_cache import get_comments_list, get_thread_context
    from backend.data.twitter.posted_tweets_cache import read_posted_tweets_cache

    # Get all comments with the specified status
    comments = get_comments_list(username, limit=1000, offset=0, status_filter=status)

    # Get posted tweets for lookup
    posted_tweets = read_posted_tweets_cache(username)

    # Group comments by the user's tweet/comment that was replied to
    # This could be a posted tweet OR a comment by the user that got a reply
    grouped: dict[str, dict] = {}

    for comment in comments:
        # Find the user's tweet/comment that this is a reply to
        # Walk up the parent_chain to find the most recent user-owned item
        parent_chain = comment.get("parent_chain", [])
        in_reply_to = comment.get("in_reply_to_status_id")

        # The immediate parent is what they replied to
        user_post_id = in_reply_to

        # Check if immediate parent is user's posted tweet
        if user_post_id and user_post_id in posted_tweets:
            # Direct reply to user's posted tweet - use it
            pass
        elif parent_chain:
            # Find the last user-owned item in the chain (closest to this comment)
            # Walk backwards through parent_chain to find user's tweet/comment
            for pid in reversed(parent_chain):
                if pid in posted_tweets:
                    user_post_id = pid
                    break
            else:
                # No user tweet in chain - skip this comment
                continue
        else:
            continue

        if not user_post_id:
            continue

        # Initialize group if not exists
        if user_post_id not in grouped:
            # Get the post data
            post_data = posted_tweets.get(user_post_id)
            if not post_data or not isinstance(post_data, dict):
                # Post not found in cache, skip these comments
                continue

            grouped[user_post_id] = {
                "post": {
                    "id": user_post_id,
                    "text": post_data.get("text", ""),
                    "url": post_data.get("url", ""),
                    "created_at": post_data.get("created_at", ""),
                    "likes": post_data.get("likes", 0),
                    "retweets": post_data.get("retweets", 0),
                    "quotes": post_data.get("quotes", 0),
                    "replies": post_data.get("replies", 0),
                    "impressions": post_data.get("impressions", 0),
                    "response_to_thread": post_data.get("response_to_thread", []),
                    "responding_to": post_data.get("responding_to", ""),
                    "original_tweet_url": post_data.get("original_tweet_url", ""),
                    "media": post_data.get("media", []),
                },
                "comments": [],
                "total_pending": 0,
            }

        # Add comment to group with its thread context
        thread_context = get_thread_context(comment["id"], username)
        grouped[user_post_id]["comments"].append({
            **comment,
            "thread_context": thread_context
        })

        if comment.get("status") == "pending":
            grouped[user_post_id]["total_pending"] += 1

    # Convert to list and sort by most recent comment activity
    result = list(grouped.values())

    # Sort posts by number of pending comments (most first), then by recency
    result.sort(key=lambda x: (-x["total_pending"], -len(x["comments"])))

    return {
        "posts_with_comments": result,
        "total_posts": len(result),
        "total_comments": sum(len(p["comments"]) for p in result),
    }


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
    3. Delete the comment from cache (cache is only for un-responded comments)
    4. Log the action
    """
    from backend.data.twitter.comments_cache import (
        delete_comment,
        get_comment as get_comment_from_cache,
    )
    from backend.data.twitter.posted_tweets_cache import read_posted_tweets_cache
    from backend.twitter.logging import TweetAction, log_tweet_action
    from backend.twitter.posting import post

    # Get the comment
    comment = get_comment_from_cache(username, comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    # Find the original posted tweet this comment is on
    posted_tweets = read_posted_tweets_cache(username)
    posted_tweet_text = ""
    posted_tweet_id = ""

    # Check parent_chain to find the user's original post
    parent_chain = comment.get("parent_chain", [])
    in_reply_to = comment.get("in_reply_to_status_id")

    # First check if immediate parent is user's post
    if in_reply_to and in_reply_to in posted_tweets:
        post_data = posted_tweets[in_reply_to]
        if isinstance(post_data, dict):
            posted_tweet_text = post_data.get("text", "")
            posted_tweet_id = in_reply_to
    else:
        # Walk parent_chain to find user's post
        for pid in reversed(parent_chain):
            if pid in posted_tweets:
                post_data = posted_tweets[pid]
                if isinstance(post_data, dict):
                    posted_tweet_text = post_data.get("text", "")
                    posted_tweet_id = pid
                    break

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
            reply_index=payload.reply_index,
            post_type="comment_reply"
        )

        # Log the comment reply action
        log_tweet_action(
            username=username,
            action=TweetAction.COMMENT_REPLY_POSTED,
            tweet_id=comment_id,
            metadata={
                "comment_id": comment_id,
                "comment_text": comment.get("text", ""),
                "comment_author": comment.get("handle", ""),
                "reply_text": payload.text,
                "reply_index": payload.reply_index,
                "new_posted_tweet_id": result.get("posted_tweet_id"),
                "original_posted_tweet_id": posted_tweet_id,
                "original_posted_tweet_text": posted_tweet_text,
            }
        )

        # Auto-like the comment we're replying to
        try:
            from backend.twitter.posting import like_tweet
            await like_tweet(username, comment_id)
            notify(f"❤️ Auto-liked comment {comment_id} for @{username}")
        except Exception as e:
            # Log but don't fail - liking is not critical
            error("Auto-like failed for comment reply", status_code=500, exception_text=str(e),
                  function_name="post_comment_reply", username=username, critical=False)

        # Delete comment from cache (cache is only for un-responded comments)
        # (Examples are now sourced from posted_tweets_cache with post_type="comment_reply", sorted by score)
        delete_comment(username, comment_id)

        return {
            "message": "Reply posted successfully",
            "comment_id": comment_id,
            "posted_tweet_id": result.get("posted_tweet_id"),
            "twitter_response": result
        }

    except HTTPException as e:
        # Handle deleted tweet - remove from cache and return informative response
        if e.status_code == 410 and e.detail == "TWEET_DELETED":
            # Log the deletion
            log_tweet_action(
                username=username,
                action=TweetAction.COMMENT_DELETED,
                tweet_id=comment_id,
                metadata={
                    "comment_id": comment_id,
                    "comment_text": comment.get("text", ""),
                    "comment_author": comment.get("handle", ""),
                    "reason": "tweet_deleted_on_twitter"
                }
            )
            # Remove from cache since it no longer exists
            delete_comment(username, comment_id)
            # Return a proper response instead of raising
            raise HTTPException(
                status_code=410,
                detail={
                    "error": "TWEET_DELETED",
                    "message": "This tweet has been deleted and was removed from your queue",
                    "comment_id": comment_id
                }
            )
        raise
    except Exception as e:
        error(f"Error posting reply to comment {comment_id}: {e}", status_code=500, function_name="post_comment_reply", username=username, critical=True)


@router.delete("/{username}/{comment_id}")
async def skip_comment(username: str, comment_id: str) -> dict:
    """
    Skip a comment (delete from cache - cache is only for pending comments).
    """
    from backend.data.twitter.comments_cache import delete_comment, get_comment as get_comment_from_cache
    from backend.data.twitter.posted_tweets_cache import read_posted_tweets_cache
    from backend.twitter.logging import TweetAction, log_tweet_action

    # Get comment data before deletion for logging
    comment = get_comment_from_cache(username, comment_id)

    # Find the original posted tweet this comment is on
    posted_tweet_text = ""
    posted_tweet_id = ""
    if comment:
        posted_tweets = read_posted_tweets_cache(username)
        parent_chain = comment.get("parent_chain", [])
        in_reply_to = comment.get("in_reply_to_status_id")

        if in_reply_to and in_reply_to in posted_tweets:
            post_data = posted_tweets[in_reply_to]
            if isinstance(post_data, dict):
                posted_tweet_text = post_data.get("text", "")
                posted_tweet_id = in_reply_to
        else:
            for pid in reversed(parent_chain):
                if pid in posted_tweets:
                    post_data = posted_tweets[pid]
                    if isinstance(post_data, dict):
                        posted_tweet_text = post_data.get("text", "")
                        posted_tweet_id = pid
                        break

    success = delete_comment(username, comment_id)
    if not success:
        raise HTTPException(status_code=404, detail="Comment not found")

    # Log the skip action
    log_tweet_action(
        username=username,
        action=TweetAction.COMMENT_SKIPPED,
        tweet_id=comment_id,
        metadata={
            "comment_id": comment_id,
            "comment_text": comment.get("text", "") if comment else "",
            "comment_author": comment.get("handle", "") if comment else "",
            "original_posted_tweet_id": posted_tweet_id,
            "original_posted_tweet_text": posted_tweet_text,
        }
    )

    return {
        "message": "Comment skipped",
        "comment_id": comment_id
    }


@router.get("/{username}/stats/summary")
async def get_comments_stats(username: str) -> dict:
    """
    Get summary statistics for comments.

    Note: Cache only contains pending (un-responded) comments.
    Replied and skipped comments are deleted from cache.
    """
    from backend.data.twitter.comments_cache import read_comments_cache

    comments_map = read_comments_cache(username)

    # Count all comments in cache (all are pending since replied/skipped are deleted)
    pending_count = sum(
        1 for cid in comments_map.keys()
        if cid != "_order" and isinstance(comments_map.get(cid), dict)
    )

    return {
        "total": pending_count,
        "pending": pending_count
    }


# Engagement monitoring endpoints
@router.get("/{username}/monitor/status")
async def get_engagement_monitoring_status(username: str) -> dict:
    """
    Get the current status of engagement monitoring jobs.

    Returns:
        - job: Current job running (idle, discover_recently_posted, discover_engagement, discover_resurrected, complete, error)
        - phase: Current phase within the job (starting, scraping, processing, etc.)
        - progress: Progress info (current, total)
        - results: Results from completed jobs
        - started_at: When the job started
        - error: Error message if any
    """
    from backend.twitter.monitoring import get_monitoring_status

    status = get_monitoring_status(username)
    return status


@router.post("/{username}/monitor/start")
async def start_engagement_monitoring(
    username: str,
) -> dict:
    """
    Start background engagement monitoring.

    Runs the two engagement jobs:
    1. find_user_activity - Discover user's external posts
    2. find_and_reply_to_engagement - Monitor engagement and generate replies

    Uses asyncio.create_task() for true parallel execution with other background jobs.
    """
    from backend.twitter.twitter_jobs import find_user_activity, find_and_reply_to_engagement

    user_info = read_user_info(username)
    if not user_info:
        raise HTTPException(status_code=404, detail="User not found")

    user_handle = user_info.get("handle", username)

    # Run jobs sequentially (activity discovery then engagement monitoring)
    # but use asyncio.create_task so they don't block other endpoints' tasks
    async def run_jobs():
        await find_user_activity(username, triggered_by="refresh")
        await find_and_reply_to_engagement(username, triggered_by="refresh")

    asyncio.create_task(_run_with_error_handling(run_jobs(), "engagement_monitoring", username))

    notify(f"🚀 Started engagement monitoring for @{user_handle}")

    return {
        "message": "Engagement monitoring started in background",
        "username": username,
        "handle": user_handle
    }


@router.post("/{username}/monitor/discover-recent")
async def run_discover_recently_posted(
    username: str,
    max_tweets: int = Query(default=50, ge=1, le=200)
) -> dict:
    """
    Run discover_recently_posted job to find external tweets.
    """
    from backend.twitter.monitoring import discover_recently_posted

    user_info = read_user_info(username)
    if not user_info:
        raise HTTPException(status_code=404, detail="User not found")

    user_handle = user_info.get("handle", username)

    # Run in background with asyncio.create_task for parallel execution
    asyncio.create_task(_run_with_error_handling(
        discover_recently_posted(username, user_handle, max_tweets),
        "discover_recently_posted", username
    ))

    return {
        "message": "discover_recently_posted started",
        "username": username,
        "handle": user_handle,
        "max_tweets": max_tweets
    }


@router.post("/{username}/monitor/discover-engagement")
async def run_discover_engagement(
    username: str,
) -> dict:
    """
    Run discover_engagement job to monitor active/warm tweets.
    """
    from backend.twitter.monitoring import discover_engagement

    user_info = read_user_info(username)
    if not user_info:
        raise HTTPException(status_code=404, detail="User not found")

    user_handle = user_info.get("handle", username)

    # Run in background with asyncio.create_task for parallel execution
    asyncio.create_task(_run_with_error_handling(
        discover_engagement(username, user_handle),
        "discover_engagement", username
    ))

    return {
        "message": "discover_engagement started",
        "username": username,
        "handle": user_handle
    }


@router.post("/{username}/monitor/discover-resurrected")
async def run_discover_resurrected(
    username: str,
) -> dict:
    """
    Run discover_resurrected job to check notifications for cold tweets.
    """
    from backend.twitter.monitoring import discover_resurrected

    user_info = read_user_info(username)
    if not user_info:
        raise HTTPException(status_code=404, detail="User not found")

    user_handle = user_info.get("handle", username)

    # Run in background with asyncio.create_task for parallel execution
    asyncio.create_task(_run_with_error_handling(
        discover_resurrected(username, user_handle),
        "discover_resurrected", username
    ))

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
