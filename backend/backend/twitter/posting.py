from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from backend.utlils.utils import error, notify


# --- config ---
# OAuth 2.0 *user access token* with permission to create posts (tweets)
# Store securely (e.g., env/secret manager)
async def _get_access_token_for_user(username: str) -> str:
    """Retrieve access token for a user from token store."""
    from backend.twitter.authentication import ensure_access_token
    access_token = await ensure_access_token(username)
    if not access_token:
        # Log error but don't raise RuntimeError - we handle it with HTTPException
        error(f"Authentication required for user {username}", status_code=401, function_name="_get_access_token_for_user", username=username, critical=False)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="AUTHENTICATION_REQUIRED")
    return access_token


# API Router
router = APIRouter(prefix="/post", tags=["post"])

ACTIVE_DRAFT_STATUSES = {"awaiting_approval", "queued", "running", "failed", "completed"}


async def like_tweet(username: str, tweet_id: str) -> bool:
    """Like a tweet via Twitter API.

    Args:
        username: User's handle
        tweet_id: ID of the tweet to like

    Returns:
        True if like succeeded or tweet was already liked, False otherwise
    """
    from backend.twitter.rate_limiter import TWITTER_POST, call_api

    access_token = await _get_access_token_for_user(username)

    # First get the user's Twitter ID
    user_url = "https://api.x.com/2/users/me"
    headers = {"Authorization": f"Bearer {access_token}"}

    user_response = await call_api(
        method="GET",
        url=user_url,
        bucket=TWITTER_POST,
        headers=headers,
        username=username
    )

    if not user_response.success:
        error("Failed to get user ID for liking tweet", status_code=user_response.status_code or 500,
              exception_text=user_response.error_message, function_name="like_tweet", username=username, critical=False)
        return False

    user_id = user_response.data.get("data", {}).get("id")
    if not user_id:
        error("No user ID returned from Twitter API", status_code=500, function_name="like_tweet", username=username, critical=False)
        return False

    # Like the tweet
    like_url = f"https://api.x.com/2/users/{user_id}/likes"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

    response = await call_api(
        method="POST",
        url=like_url,
        bucket=TWITTER_POST,
        headers=headers,
        json_data={"tweet_id": tweet_id},
        username=username
    )

    # 200 = success, 400 might mean already liked
    if response.success or response.status_code == 400:
        return True

    # Log but don't fail - liking is not critical
    error("Failed to like tweet", status_code=response.status_code or 500,
          exception_text=response.error_message, function_name="like_tweet", username=username, critical=False)
    return False


class Tweet(BaseModel):
    text: str
    cache_id: str | None = None


class ReplyTweet(BaseModel):
    text: str
    tweet_id: str
    cache_id: str | None = None
    reply_index: int | None = None


class AddToQueueRequest(BaseModel):
    """Request to add a tweet to the posting queue."""
    type: str  # "reply" or "comment_reply"
    response_to: str  # ID of tweet/comment being replied to
    reply: str  # The reply text
    reply_index: int | None = None
    model: str | None = None
    prompt_variant: str | None = None
    # Context for display
    media: list[dict] = []
    parent_chain: list[str] = []
    response_to_thread: list[str] = []
    responding_to: str = ""
    replying_to_pfp: str = ""
    original_tweet_url: str = ""


class AddStandalonePostRequest(BaseModel):
    text: str
    image_url: str | None = None
    link_url: str | None = None
    resource_url: str | None = None
    resource_title: str | None = None
    resource_author: str | None = None
    resource_content_type: str | None = None
    resource_text_sample: str | None = None
    resource_notes: str | None = None


class UpdateStandalonePostRequest(BaseModel):
    text: str | None = None
    image_url: str | None = None
    link_url: str | None = None


async def post(username, payload: dict, cache_id: str | None = None, reply_index: int | None = None, post_type: str = "reply") -> dict:
    """
    Post a tweet via Twitter API.

    Args:
        username: User's handle
        payload: Tweet payload for Twitter API
        cache_id: Optional cache ID for fetching original tweet data
        reply_index: Index of the selected reply
        post_type: Type of post - "original", "reply", or "comment_reply"
    """
    import json

    from backend.data.twitter.edit_cache import get_user_tweet_cache
    from backend.data.twitter.posted_tweets_cache import add_posted_tweet
    from backend.twitter.logging import TweetAction, log_tweet_action
    from backend.twitter.rate_limiter import TWITTER_POST, call_api
    from backend.utlils.utils import notify, read_user_info, write_user_info

    access_token = await _get_access_token_for_user(username)

    url = "https://api.x.com/2/tweets"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

    # Use rate limiter with retry
    response = await call_api(
        method="POST",
        url=url,
        bucket=TWITTER_POST,
        headers=headers,
        json_data=payload,
        username=username
    )

    if not response.success:
        if response.status_code == 403:
            # Tweet was deleted - raise HTTPException so caller can handle gracefully
            error("Tweet has been deleted, cannot reply", status_code=response.status_code, exception_text=response.error_message, function_name="post", username=username, critical=False)
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="TWEET_DELETED")
        elif response.status_code == 401:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="AUTHENTICATION_REQUIRED")
        else:
            error("Twitter API error when posting tweet", status_code=response.status_code or 500, exception_text=response.error_message, function_name="post", username=username, critical=True)

    result = response.data

    # Log the post with posted tweet ID from Twitter
    posted_tweet_id = result.get("data", {}).get("id")  # ID from Twitter API
    original_tweet_id = payload.get("reply", {}).get("in_reply_to_tweet_id") or payload.get("quote_tweet_id")

    if posted_tweet_id:
        metadata = {
            "text": payload.get("text"),
            "posted_tweet_id": posted_tweet_id,  # The ID Twitter assigned to the posted tweet
        }

        if cache_id:
            metadata["cache_id"] = cache_id

        if "reply" in payload:
            metadata["reply_to"] = payload["reply"].get("in_reply_to_tweet_id")
        if "quote_tweet_id" in payload:
            metadata["quote_tweet_id"] = payload["quote_tweet_id"]

        # Include reply_index to track which reply was chosen for posting
        if reply_index is not None:
            metadata["reply_index"] = reply_index

        # Get original tweet data from cache for posted_tweets.json and model info
        response_to_thread = []
        responding_to_handle = ""
        replying_to_pfp = ""
        original_tweet_url = ""
        media = []
        model_name = "unknown"
        prompt_variant = "unknown"

        if cache_id:
            try:
                cache_path = get_user_tweet_cache(username)
                if cache_path.exists():
                    with open(cache_path, encoding="utf-8") as f:
                        cached_tweets = json.load(f)

                    # Find the original tweet by cache_id
                    for tweet in cached_tweets:
                        if tweet.get("cache_id") == cache_id:
                            response_to_thread = tweet.get("thread", [])
                            responding_to_handle = tweet.get("handle", "")
                            replying_to_pfp = tweet.get("author_profile_pic_url", "")
                            original_tweet_url = tweet.get("url", "")
                            media = tweet.get("media", [])

                            # Get model and prompt variant info for the posted reply
                            # generated_replies is now an array of tuples: [(reply_text, model_name, prompt_variant), ...]
                            if reply_index is not None:
                                generated_replies = tweet.get("generated_replies", [])
                                if reply_index < len(generated_replies):
                                    reply_tuple = generated_replies[reply_index]
                                    # Extract model name from tuple
                                    if isinstance(reply_tuple, (list, tuple)) and len(reply_tuple) >= 2:
                                        model_name = reply_tuple[1]
                                    # Extract prompt variant from tuple (3rd element)
                                    if isinstance(reply_tuple, (list, tuple)) and len(reply_tuple) >= 3:
                                        prompt_variant = reply_tuple[2]

                            break
            except Exception as e:
                error("Could not fetch original tweet data from cache", status_code=500, exception_text=str(e), function_name="post", username=username)
                notify(f"⚠️ Could not fetch original tweet data from cache: {e}")

        # Add model and prompt variant to metadata
        metadata["model"] = model_name
        metadata["prompt_variant"] = prompt_variant

        # Add original tweet info for intent filtering examples
        if response_to_thread:
            # Join thread texts for context
            metadata["original_tweet_text"] = " | ".join(response_to_thread)
        if responding_to_handle:
            metadata["original_handle"] = responding_to_handle

        # Log using the original tweet ID as the key if available, otherwise use posted_tweet_id
        log_key = original_tweet_id or posted_tweet_id
        log_tweet_action(username, TweetAction.POSTED, str(log_key), metadata=metadata)

        # Trigger async feedback extraction if this reply was edited
        # (only for replies, not original posts or comment replies)
        if post_type == "reply" and cache_id and reply_index is not None:
            import asyncio

            from backend.twitter.logging import TweetAction as LogAction
            from backend.twitter.logging import get_logs_by_cache_id

            try:
                # Check if there was a recent edit for this cache_id
                logs = get_logs_by_cache_id(username, cache_id)
                edit_log = None

                for log in reversed(logs):  # Most recent first
                    if log.get("action") == LogAction.EDITED.value:
                        edit_log = log
                        break

                if edit_log:
                    notify(f"🔍 Reply was edited before posting, queueing feedback extraction")

                    # Queue async background task for feedback extraction
                    async def extract_feedback_task():
                        try:
                            from backend.rag.feedback_extraction import extract_feedback_from_edit
                            await extract_feedback_from_edit(username, edit_log)
                        except Exception as e:
                            # Log but don't fail the post
                            error(
                                f"Background feedback extraction failed: {e}",
                                status_code=500,
                                exception_text=str(e),
                                function_name="extract_feedback_task",
                                username=username,
                                critical=False
                            )

                    # Run in background without blocking
                    asyncio.create_task(extract_feedback_task())
            except Exception as e:
                # Never let feedback extraction block or fail the post
                error(
                    f"Failed to check for edits for feedback extraction: {e}",
                    status_code=500,
                    exception_text=str(e),
                    function_name="post",
                    username=username,
                    critical=False
                )

        # Add to posted_tweets.json cache with parent_chain support
        # (Examples are now sourced from posted_tweets_cache, sorted by score)
        try:
            # Get the in_reply_to_id for building parent_chain
            in_reply_to_id = payload.get("reply", {}).get("in_reply_to_tweet_id") or payload.get("quote_tweet_id")

            add_posted_tweet(username=username,
                             posted_tweet_id=posted_tweet_id,
                             text=payload.get("text", ""),
                             original_tweet_url=original_tweet_url,
                             responding_to_handle=responding_to_handle,
                             replying_to_pfp=replying_to_pfp,
                             response_to_thread=response_to_thread,
                             in_reply_to_id=in_reply_to_id,
                             parent_media=media,
                             post_type=post_type)
        except Exception as e:
            error("Failed to add to posted_tweets cache", status_code=500, exception_text=str(e), function_name="post", username=username)
            notify(f"⚠️ Failed to add to posted_tweets cache: {e}")

        # Increment lifetime_posts and add to intent filter examples
        try:
            user_info = read_user_info(username)
            if user_info:
                current_posts = user_info.get("lifetime_posts", 0)
                user_info["lifetime_posts"] = current_posts + 1

                # Add to intent_filter_examples if we have < 10 examples and this is a reply to someone else's post
                # Only add "reply" type posts (not comment_reply or original)
                # Only add if intent_filter_last_updated is set (meaning user has an active intent)
                if response_to_thread and responding_to_handle and post_type == "reply":
                    # Check if intent is set (has been updated at least once)
                    intent_last_updated = user_info.get("intent_filter_last_updated")
                    if intent_last_updated:  # Only add examples if intent is actively set
                        examples = user_info.get("intent_filter_examples", [])
                        if len(examples) < 10:
                            # Add the original tweet as an example
                            # (This tweet is being posted NOW, so it's always after intent_filter_last_updated)
                            example = {
                                "author": responding_to_handle,
                                "text": " | ".join(response_to_thread)[:500]  # Truncate long threads
                            }
                            examples.append(example)
                            user_info["intent_filter_examples"] = examples
                            notify(f"📚 Added intent filter example ({len(examples)}/10) for @{username}")

                write_user_info(user_info)
                notify(f"📝 Post count incremented for @{username} (total: {user_info['lifetime_posts']})")
        except Exception as e:
            error("Failed to update post count", status_code=500, exception_text=str(e), function_name="post", username=username)
            notify(f"⚠️ Failed to update post count for {username}: {e}")

    # Return result with posted_tweet_id explicitly for frontend tracking
    return {**result, "posted_tweet_id": posted_tweet_id}


@router.post("/tweet")
async def post_tweet(username: str, payload: Tweet) -> dict:
    data = {"text": payload.text}
    return await post(username, data, cache_id=payload.cache_id, post_type="original")


@router.post("/reply")
async def post_reply(payload: ReplyTweet, username: str = Query(...)) -> dict:
    import json

    from backend.data.twitter.edit_cache import delete_tweet, get_user_tweet_cache

    data = {"text": payload.text, "reply": {"in_reply_to_tweet_id": payload.tweet_id}}

    # Determine post_type based on:
    # 1. Whether parent is the conversation root (original post vs comment)
    # 2. Whether we're replying to ourselves (thread continuation)
    #
    # If replying to root of our own thread → "original"
    # If replying to root of someone else's thread → "reply"
    # If replying to a comment (not root) → "comment_reply"
    post_type = "reply"  # default
    if payload.cache_id:
        try:
            cache_path = get_user_tweet_cache(username)
            if cache_path.exists():
                with open(cache_path, encoding="utf-8") as f:
                    cached_tweets = json.load(f)
                for tweet in cached_tweets:
                    if tweet.get("cache_id") == payload.cache_id:
                        responding_to_handle = tweet.get("handle", "")
                        conversation_id = tweet.get("conversation_id") or tweet.get("id")
                        parent_tweet_id = payload.tweet_id

                        # Check if we're replying to the conversation root
                        is_replying_to_root = (parent_tweet_id == conversation_id)

                        if is_replying_to_root:
                            # Replying to the root/original post
                            if responding_to_handle.lower() == username.lower():
                                post_type = "original"  # Thread continuation
                            else:
                                post_type = "reply"  # Reply to someone else's original post
                        else:
                            # Replying to a comment (not the root)
                            post_type = "comment_reply"
                        break
        except Exception:
            pass  # Default to "reply" on any error

    # Get thread_ids for auto-liking all tweets in thread
    thread_ids_to_like = []
    if payload.cache_id and post_type == "reply":
        try:
            cache_path = get_user_tweet_cache(username)
            if cache_path.exists():
                with open(cache_path, encoding="utf-8") as f:
                    cached_tweets = json.load(f)
                for tweet in cached_tweets:
                    if tweet.get("cache_id") == payload.cache_id:
                        thread_ids_to_like = tweet.get("thread_ids", [])
                        break
        except Exception:
            pass  # Fall back to just liking the reply target

    try:
        result = await post(username, data, cache_id=payload.cache_id, reply_index=payload.reply_index, post_type=post_type)

        # Auto-like all tweets in the thread (only for replies to others, not thread continuations)
        if post_type == "reply":
            # Like all tweets in thread, or just the reply target if no thread_ids
            tweets_to_like = thread_ids_to_like if thread_ids_to_like else [payload.tweet_id]
            liked_count = 0
            for tweet_id in tweets_to_like:
                try:
                    await like_tweet(username, tweet_id)
                    liked_count += 1
                except Exception as e:
                    error(f"Auto-like failed for tweet {tweet_id}", status_code=500, exception_text=str(e),
                          function_name="post_reply", username=username, critical=False)
            if liked_count > 0:
                notify(f"❤️ Auto-liked {liked_count} tweet(s) in thread for @{username}")

        return result
    except HTTPException as e:
        # Handle deleted tweet - remove from cache and return informative response
        if e.status_code == status.HTTP_410_GONE and e.detail == "TWEET_DELETED":
            # Remove from tweet cache if we have a cache_id
            if payload.cache_id:
                await delete_tweet(username, payload.cache_id)
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail={
                    "error": "TWEET_DELETED",
                    "message": "This tweet has been deleted and was removed from your queue",
                    "cache_id": payload.cache_id,
                    "tweet_id": payload.tweet_id
                }
            )
        raise


@router.post("/quote")
async def post_quote_tweet(username: str, payload: ReplyTweet) -> dict:
    from backend.data.twitter.edit_cache import delete_tweet

    data = {"text": payload.text, "quote_tweet_id": payload.tweet_id}
    try:
        return await post(username, data, cache_id=payload.cache_id)
    except HTTPException as e:
        # Handle deleted tweet - remove from cache and return informative response
        if e.status_code == status.HTTP_410_GONE and e.detail == "TWEET_DELETED":
            if payload.cache_id:
                await delete_tweet(username, payload.cache_id)
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail={
                    "error": "TWEET_DELETED",
                    "message": "This tweet has been deleted and was removed from your queue",
                    "cache_id": payload.cache_id,
                    "tweet_id": payload.tweet_id
                }
            )
        raise


@router.delete("/tweet/{tweet_id}")
async def delete_posted_tweet(tweet_id: str, username: str = Query(...)) -> dict:
    """Delete a posted tweet from Twitter via API.

    Args:
        tweet_id: The Twitter-assigned ID of the posted tweet
        username: The username who owns the tweet

    Returns:
        Success message and metadata
    """
    from backend.twitter.logging import TweetAction, log_tweet_action
    from backend.twitter.rate_limiter import TWITTER_POST, call_api
    from backend.utlils.utils import read_user_info, write_user_info

    access_token = await _get_access_token_for_user(username)

    url = f"https://api.x.com/2/tweets/{tweet_id}"
    headers = {"Authorization": f"Bearer {access_token}"}

    # Use rate limiter with retry
    response = await call_api(
        method="DELETE",
        url=url,
        bucket=TWITTER_POST,
        headers=headers,
        username=username
    )

    if response.success:
        # Successfully deleted - log the action
        log_tweet_action(username, TweetAction.DELETED, tweet_id, metadata={"deleted_from_twitter": True, "posted_tweet_id": tweet_id})

        # Delete from posted_tweets.json cache
        try:
            from backend.data.twitter.posted_tweets_cache import delete_posted_tweet_from_cache
            delete_posted_tweet_from_cache(username, tweet_id)
        except Exception as e:
            error("Failed to delete tweet from posted tweets cache", status_code=500, exception_text=str(e), function_name="delete_posted_tweet", username=username)
            notify(f"⚠️ Failed to delete tweet from posted tweets cache: {e}")

        # Decrement lifetime_posts
        try:
            user_info = read_user_info(username)
            if user_info:
                current_posts = user_info.get("lifetime_posts", 0)
                # Only decrement if count is greater than 0
                if current_posts > 0:
                    user_info["lifetime_posts"] = current_posts - 1
                    write_user_info(user_info)
                    notify(f"📝 Post count decremented for @{username} (total: {user_info['lifetime_posts']})")
        except Exception as e:
            error("Failed to update post count", status_code=500, exception_text=str(e), function_name="delete_posted_tweet", username=username)
            notify(f"⚠️ Failed to update post count for {username}: {e}")

        return {"message": "Tweet deleted successfully", "tweet_id": tweet_id, "deleted": True}
    elif response.status_code == 404:
        # Tweet not found (may already be deleted)
        return {"message": "Tweet not found (may already be deleted)", "tweet_id": tweet_id, "deleted": False}
    else:
        # Other error
        error("Twitter API error when deleting tweet", status_code=response.status_code or 500, exception_text=response.error_message, function_name="delete_posted_tweet", username=username, critical=True)
        raise HTTPException(status_code=response.status_code or 500, detail=f"Twitter API error: {response.error_message}")


@router.post("/queue")
async def add_to_queue(payload: AddToQueueRequest, username: str = Query(...)) -> dict:
    """Add a post draft to the queue for manual approval.

    This endpoint does NOT post immediately.
    It creates a draft item in `post_queue` with status `awaiting_approval`.
    Later, frontend calls `/post/pending/{draft_id}/approve` to queue
    actual desktop execution.

    Args:
        payload: The queue item with reply text and context
        username: The user's handle

    Returns:
        Draft queue item with status `awaiting_approval`
    """
    import json
    from datetime import datetime, timezone
    import uuid

    from backend.data.twitter.edit_cache import get_user_tweet_cache
    from backend.utlils.utils import read_user_info, write_user_info

    # Validate type
    if payload.type not in ("reply", "comment_reply"):
        raise HTTPException(status_code=400, detail="Invalid type. Must be 'reply' or 'comment_reply'")

    # Resolve source IDs for reply type (needed later during desktop execution)
    cache_id = None
    tweet_id_to_reply = payload.response_to

    if payload.type == "reply":
        # Mark in tweets cache and get cache_id
        cache_path = get_user_tweet_cache(username)
        if cache_path.exists():
            with open(cache_path, encoding="utf-8") as f:
                tweets = json.load(f)

            for tweet in tweets:
                if tweet.get("id") == payload.response_to or tweet.get("cache_id") == payload.response_to:
                    tweet["post_pending"] = True
                    cache_id = tweet.get("cache_id")
                    tweet_id_to_reply = tweet.get("id")  # Use the actual tweet ID
                    break

            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(tweets, f, indent=2)
    else:
        # For comment replies, reply to the comment itself (not its parent)
        tweet_id_to_reply = payload.response_to

    # Persist draft in post_queue
    user_info = read_user_info(username)
    if not user_info:
        raise HTTPException(status_code=404, detail="User not found")

    post_queue = user_info.get("post_queue", [])

    # Prevent duplicate active drafts for same source
    for item in post_queue:
        if item.get("response_to") != payload.response_to:
            continue
        status = item.get("status", "awaiting_approval")
        if status in {"awaiting_approval", "queued", "running"}:
            return {
                "message": "Already queued for approval",
                "queued": False,
                "status": "duplicate",
                "draft_id": item.get("draft_id"),
            }

    now_iso = datetime.now(timezone.utc).isoformat()
    queue_item = {
        "draft_id": str(uuid.uuid4()),
        "type": payload.type,
        "response_to": payload.response_to,
        "reply": payload.reply,
        "reply_index": payload.reply_index,
        "model": payload.model,
        "prompt_variant": payload.prompt_variant,
        "media": payload.media,
        "parent_chain": payload.parent_chain,
        "response_to_thread": payload.response_to_thread,
        "responding_to": payload.responding_to,
        "replying_to_pfp": payload.replying_to_pfp,
        "original_tweet_url": payload.original_tweet_url,
        "cache_id": cache_id,
        "tweet_id_to_reply": tweet_id_to_reply,
        "status": "awaiting_approval",
        "queued_at": now_iso,
        "updated_at": now_iso,
    }

    post_queue.append(queue_item)
    user_info["post_queue"] = post_queue
    write_user_info(user_info)

    return {
        "message": "Queued for approval",
        "queued": True,
        "status": "awaiting_approval",
        "draft_id": queue_item["draft_id"],
        "item": queue_item,
    }


@router.post("/standalone/queue")
async def queue_standalone_post(payload: AddStandalonePostRequest, username: str = Query(...)) -> dict:
    """Queue a standalone multi-platform post draft for manual approval."""
    from datetime import datetime, timezone
    import uuid

    from backend.utlils.utils import read_user_info, write_user_info

    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Post text cannot be empty")

    user_info = read_user_info(username)
    if not user_info:
        raise HTTPException(status_code=404, detail="User not found")

    post_queue = user_info.get("post_queue", [])

    # De-duplicate active standalone drafts with exact same content/link/image
    for item in post_queue:
        if item.get("type") != "standalone_post":
            continue
        status = item.get("status", "awaiting_approval")
        if status not in {"awaiting_approval", "queued", "running"}:
            continue
        if (
            (item.get("reply") or "").strip() == text
            and (item.get("standalone_image_url") or None) == payload.image_url
            and (item.get("standalone_link_url") or None) == payload.link_url
        ):
            return {
                "message": "Already queued for approval",
                "queued": False,
                "status": "duplicate",
                "draft_id": item.get("draft_id"),
                "item": item,
            }

    now_iso = datetime.now(timezone.utc).isoformat()
    queue_item = {
        "draft_id": str(uuid.uuid4()),
        "type": "standalone_post",
        "reply": text,
        "standalone_image_url": payload.image_url,
        "standalone_link_url": payload.link_url,
        "resource_url": payload.resource_url,
        "resource_title": payload.resource_title,
        "resource_author": payload.resource_author,
        "resource_content_type": payload.resource_content_type,
        "resource_text_sample": payload.resource_text_sample,
        "resource_notes": payload.resource_notes,
        "status": "awaiting_approval",
        "queued_at": now_iso,
        "updated_at": now_iso,
    }

    post_queue.append(queue_item)
    user_info["post_queue"] = post_queue
    write_user_info(user_info)

    return {
        "message": "Standalone post queued for approval",
        "queued": True,
        "status": "awaiting_approval",
        "draft_id": queue_item["draft_id"],
        "item": queue_item,
    }


class UpdatePendingPostRequest(BaseModel):
    reply: str


@router.patch("/pending/{draft_id}")
async def update_pending_post(
    draft_id: str,
    payload: UpdatePendingPostRequest,
    username: str = Query(...),
) -> dict:
    """Edit queued draft text before approval."""
    from datetime import datetime, timezone

    from backend.utlils.utils import read_user_info, write_user_info

    user_info = read_user_info(username)
    if not user_info:
        raise HTTPException(status_code=404, detail="User not found")

    post_queue = user_info.get("post_queue", [])
    updated_item = None
    for item in post_queue:
        if item.get("draft_id") != draft_id:
            continue
        status = item.get("status", "awaiting_approval")
        if status not in {"awaiting_approval", "failed"}:
            raise HTTPException(status_code=409, detail=f"Draft cannot be edited in status '{status}'")
        item["reply"] = payload.reply
        item["updated_at"] = datetime.now(timezone.utc).isoformat()
        updated_item = item
        break

    if not updated_item:
        raise HTTPException(status_code=404, detail="Draft not found")

    user_info["post_queue"] = post_queue
    write_user_info(user_info)
    return {"message": "Draft updated", "draft_id": draft_id, "item": updated_item}


@router.post("/pending/{draft_id}/approve")
async def approve_pending_post(draft_id: str, username: str = Query(...)) -> dict:
    """Approve a draft and queue it for desktop execution."""
    from datetime import datetime, timezone

    from backend.desktop.desktop_jobs import create_desktop_job
    from backend.desktop.task_types import DesktopTaskType
    from backend.utlils.utils import read_user_info, write_user_info

    user_info = read_user_info(username)
    if not user_info:
        raise HTTPException(status_code=404, detail="User not found")

    post_queue = user_info.get("post_queue", [])
    approved_item = None
    for item in post_queue:
        if item.get("draft_id") != draft_id:
            continue
        current_status = item.get("status", "awaiting_approval")
        if current_status in {"queued", "running"}:
            return {
                "message": "Draft already queued",
                "draft_id": draft_id,
                "desktop_job_id": item.get("desktop_job_id"),
                "status": current_status,
            }
        if current_status == "completed":
            return {"message": "Draft already completed", "draft_id": draft_id, "status": "completed"}
        if current_status == "cancelled":
            raise HTTPException(status_code=409, detail="Draft has been cancelled")

        params = {
            "draft_id": item.get("draft_id"),
            "type": item.get("type"),
            "response_to": item.get("response_to"),
            "reply": item.get("reply"),
            "reply_index": item.get("reply_index"),
            "model": item.get("model"),
            "prompt_variant": item.get("prompt_variant"),
            "media": item.get("media", []),
            "parent_chain": item.get("parent_chain", []),
            "response_to_thread": item.get("response_to_thread", []),
            "responding_to": item.get("responding_to", ""),
            "replying_to_pfp": item.get("replying_to_pfp", ""),
            "original_tweet_url": item.get("original_tweet_url", ""),
            "cache_id": item.get("cache_id"),
            "tweet_id_to_reply": item.get("tweet_id_to_reply"),
        }
        desktop_job_id = create_desktop_job(username, DesktopTaskType.POST_X.value, params)
        item["desktop_job_id"] = desktop_job_id
        item["status"] = "queued"
        item["last_error"] = None
        item["updated_at"] = datetime.now(timezone.utc).isoformat()
        approved_item = item
        break

    if not approved_item:
        raise HTTPException(status_code=404, detail="Draft not found")

    user_info["post_queue"] = post_queue
    write_user_info(user_info)
    return {
        "message": "Draft approved and queued for desktop execution",
        "draft_id": draft_id,
        "desktop_job_id": approved_item.get("desktop_job_id"),
        "status": approved_item.get("status"),
        "item": approved_item,
    }


@router.get("/standalone/pending")
async def get_pending_standalone_posts(username: str = Query(...)) -> dict:
    """Get pending standalone posts for approval in the Posts tab."""
    from backend.utlils.utils import read_user_info

    user_info = read_user_info(username)
    if not user_info:
        raise HTTPException(status_code=404, detail="User not found")

    post_queue = user_info.get("post_queue", [])
    standalone_visible_statuses = {"awaiting_approval", "queued", "running", "failed"}
    items = []
    for item in post_queue:
        if item.get("type") != "standalone_post":
            continue
        status = item.get("status", "awaiting_approval")
        if status not in standalone_visible_statuses:
            continue

        items.append({
            "id": f"standalone-{item.get('draft_id')}",
            "draft_id": item.get("draft_id"),
            "status": status,
            "text": item.get("reply", ""),
            "image_url": item.get("standalone_image_url"),
            "link_url": item.get("standalone_link_url"),
            "desktop_job_id": item.get("desktop_job_id"),
            "error": item.get("last_error"),
            "startedAt": item.get("queued_at", ""),
            "updatedAt": item.get("updated_at", ""),
        })

    pending_count = sum(1 for item in items if item["status"] in {"awaiting_approval", "queued", "running"})
    return {"pending_posts": items, "count": len(items), "pending_count": pending_count}


@router.patch("/standalone/{draft_id}")
async def update_standalone_post(
    draft_id: str,
    payload: UpdateStandalonePostRequest,
    username: str = Query(...),
) -> dict:
    """Edit standalone post draft before approval."""
    from datetime import datetime, timezone

    from backend.utlils.utils import read_user_info, write_user_info

    provided_fields = set(getattr(payload, "model_fields_set", set()))
    if not provided_fields:
        # Pydantic v1 fallback
        provided_fields = set(payload.dict(exclude_unset=True).keys())

    if not provided_fields:
        raise HTTPException(status_code=400, detail="No updates provided")

    user_info = read_user_info(username)
    if not user_info:
        raise HTTPException(status_code=404, detail="User not found")

    post_queue = user_info.get("post_queue", [])
    updated_item = None
    for item in post_queue:
        if item.get("draft_id") != draft_id or item.get("type") != "standalone_post":
            continue
        status = item.get("status", "awaiting_approval")
        if status not in {"awaiting_approval", "failed"}:
            raise HTTPException(status_code=409, detail=f"Draft cannot be edited in status '{status}'")

        if "text" in provided_fields:
            text = (payload.text or "").strip()
            if not text:
                raise HTTPException(status_code=400, detail="Post text cannot be empty")
            item["reply"] = text
        if "image_url" in provided_fields:
            item["standalone_image_url"] = payload.image_url
        if "link_url" in provided_fields:
            item["standalone_link_url"] = payload.link_url
        item["updated_at"] = datetime.now(timezone.utc).isoformat()
        updated_item = item
        break

    if not updated_item:
        raise HTTPException(status_code=404, detail="Standalone draft not found")

    user_info["post_queue"] = post_queue
    write_user_info(user_info)
    return {"message": "Standalone draft updated", "draft_id": draft_id, "item": updated_item}


@router.post("/standalone/{draft_id}/approve")
async def approve_standalone_post(draft_id: str, username: str = Query(...)) -> dict:
    """Approve standalone post draft and queue desktop POST_ALL execution."""
    from datetime import datetime, timezone

    from backend.desktop.desktop_jobs import create_desktop_job
    from backend.desktop.task_types import DesktopTaskType
    from backend.utlils.utils import read_user_info, write_user_info

    user_info = read_user_info(username)
    if not user_info:
        raise HTTPException(status_code=404, detail="User not found")

    post_queue = user_info.get("post_queue", [])
    approved_item = None
    for item in post_queue:
        if item.get("draft_id") != draft_id or item.get("type") != "standalone_post":
            continue

        current_status = item.get("status", "awaiting_approval")
        if current_status in {"queued", "running"}:
            return {
                "message": "Standalone draft already queued",
                "draft_id": draft_id,
                "desktop_job_id": item.get("desktop_job_id"),
                "status": current_status,
            }
        if current_status == "completed":
            return {"message": "Standalone draft already completed", "draft_id": draft_id, "status": "completed"}
        if current_status == "cancelled":
            raise HTTPException(status_code=409, detail="Standalone draft has been cancelled")

        params = {
            "draft_id": item.get("draft_id"),
            "type": item.get("type"),
            "task": "post_all",
            "content": item.get("reply", ""),
            "image_url": item.get("standalone_image_url"),
            "url": item.get("standalone_link_url") or "",
            "link_url": item.get("standalone_link_url"),
        }
        desktop_job_id = create_desktop_job(username, DesktopTaskType.POST_ALL.value, params)
        item["desktop_job_id"] = desktop_job_id
        item["status"] = "queued"
        item["last_error"] = None
        item["updated_at"] = datetime.now(timezone.utc).isoformat()
        approved_item = item
        break

    if not approved_item:
        raise HTTPException(status_code=404, detail="Standalone draft not found")

    user_info["post_queue"] = post_queue
    write_user_info(user_info)

    return {
        "message": "Standalone draft approved and queued for desktop execution",
        "draft_id": draft_id,
        "desktop_job_id": approved_item.get("desktop_job_id"),
        "status": approved_item.get("status"),
        "item": approved_item,
    }


@router.delete("/standalone/{draft_id}")
async def remove_standalone_post(draft_id: str, username: str = Query(...)) -> dict:
    """Discard a standalone post draft."""
    from backend.utlils.utils import read_user_info, write_user_info

    user_info = read_user_info(username)
    if not user_info:
        raise HTTPException(status_code=404, detail="User not found")

    post_queue = user_info.get("post_queue", [])
    removed_item = None
    new_queue = []
    for item in post_queue:
        if item.get("draft_id") == draft_id and item.get("type") == "standalone_post":
            removed_item = item
        else:
            new_queue.append(item)

    if not removed_item:
        raise HTTPException(status_code=404, detail="Standalone draft not found")

    user_info["post_queue"] = new_queue
    write_user_info(user_info)

    desktop_job_id = removed_item.get("desktop_job_id")
    if desktop_job_id:
        try:
            from backend.desktop.desktop_jobs import desktop_jobs
            job = desktop_jobs.get(desktop_job_id)
            if job and job.status == "pending":
                del desktop_jobs[desktop_job_id]
        except Exception:
            pass

    return {"message": "Standalone draft removed", "removed": True, "item": removed_item}


@router.get("/queue")
async def get_queue(username: str = Query(...)) -> dict:
    """Get the user's posting queue.

    Returns:
        List of pending posts in the queue
    """
    from backend.utlils.utils import read_user_info

    user_info = read_user_info(username)
    if not user_info:
        raise HTTPException(status_code=404, detail="User not found")

    post_queue = user_info.get("post_queue", [])

    return {"queue": post_queue, "count": len(post_queue)}


@router.delete("/pending/{draft_id}")
async def remove_pending_draft(draft_id: str, username: str = Query(...)) -> dict:
    """Cancel/remove a pending draft."""
    import json

    from backend.utlils.utils import read_user_info, write_user_info

    user_info = read_user_info(username)
    if not user_info:
        raise HTTPException(status_code=404, detail="User not found")

    post_queue = user_info.get("post_queue", [])

    removed_item = None
    new_queue = []
    for item in post_queue:
        if item.get("draft_id") == draft_id:
            removed_item = item
        else:
            new_queue.append(item)

    if not removed_item:
        raise HTTPException(status_code=404, detail="Draft not found")

    user_info["post_queue"] = new_queue
    write_user_info(user_info)

    # If the desktop job is still pending in memory, delete it.
    desktop_job_id = removed_item.get("desktop_job_id")
    if desktop_job_id:
        try:
            from backend.desktop.desktop_jobs import desktop_jobs
            job = desktop_jobs.get(desktop_job_id)
            if job and job.status == "pending":
                del desktop_jobs[desktop_job_id]
        except Exception:
            pass

    # Clear post_pending flag for discovered-tweet source so it can reappear.
    if removed_item.get("type") == "reply":
        from backend.data.twitter.edit_cache import get_user_tweet_cache
        cache_path = get_user_tweet_cache(username)
        if cache_path.exists():
            with open(cache_path, encoding="utf-8") as f:
                tweets = json.load(f)

            for tweet in tweets:
                response_to = removed_item.get("response_to")
                if tweet.get("id") == response_to or tweet.get("cache_id") == response_to:
                    tweet["post_pending"] = False
                    break

            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(tweets, f, indent=2)

    return {"message": "Draft removed", "removed": True, "item": removed_item}


@router.delete("/queue/{response_to}")
async def remove_from_queue_by_response_to(response_to: str, username: str = Query(...)) -> dict:
    """Backward-compatible remove endpoint by source ID."""
    from backend.utlils.utils import read_user_info

    user_info = read_user_info(username)
    if not user_info:
        raise HTTPException(status_code=404, detail="User not found")

    post_queue = user_info.get("post_queue", [])
    match = next((item for item in post_queue if item.get("response_to") == response_to), None)
    if not match:
        return {"message": "Item not found in queue", "removed": False}
    return await remove_pending_draft(str(match.get("draft_id")), username=username)


@router.get("/pending")
async def get_pending_posts(username: str = Query(...)) -> dict:
    """Get pending posts formatted for display in PostedTab.

    Returns posts in a format similar to PostedTweet so they can be displayed
    in the PostingInProgress component.

    Returns:
        List of pending posts with display-ready data
    """
    from backend.utlils.utils import read_user_info

    user_info = read_user_info(username)
    if not user_info:
        raise HTTPException(status_code=404, detail="User not found")

    post_queue = user_info.get("post_queue", [])

    # Format for frontend display
    pending_posts = []
    for item in post_queue:
        if item.get("type") == "standalone_post":
            continue
        status = item.get("status", "awaiting_approval")
        if status not in ACTIVE_DRAFT_STATUSES:
            continue
        pending_post = {
            "id": f"pending-{item.get('draft_id') or item.get('response_to')}",
            "draft_id": item.get("draft_id"),
            "status": status,
            "desktop_job_id": item.get("desktop_job_id"),
            "originalTweetId": item.get("response_to"),
            "text": item.get("reply", ""),
            "respondingTo": item.get("responding_to", ""),
            "originalTweetUrl": item.get("original_tweet_url", ""),
            "originalThreadText": item.get("response_to_thread", []),
            "source": "discovered" if item.get("type") == "reply" else "comments",
            "startedAt": item.get("queued_at", ""),
            "updatedAt": item.get("updated_at", ""),
            "error": item.get("last_error"),
            "posted_tweet_id": item.get("posted_tweet_id"),
            "replyingToPfp": item.get("replying_to_pfp", ""),
            "parentChain": item.get("parent_chain", []),
            "media": item.get("media", []),
        }
        pending_posts.append(pending_post)

    pending_count = sum(
        1 for p in pending_posts
        if p.get("status") in {"awaiting_approval", "queued", "running"}
    )
    return {"pending_posts": pending_posts, "count": len(pending_posts), "pending_count": pending_count}


# --- example usage ---
if __name__ == "__main__":
    import asyncio
    asyncio.run(post_tweet("proudlurker", Tweet(text="Hello, world!")))
