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
    """Add a tweet to the posting queue and immediately process it.

    Flow:
    1. Add to queue (persisted in case of browser close)
    2. Mark source as post_pending=true
    3. Post to Twitter
    4. On success: remove from queue, delete from source cache
    5. On failure: remove from queue, clear post_pending (item reappears)

    Args:
        payload: The queue item with reply text and context
        username: The user's handle

    Returns:
        Success/failure with posted tweet info or error
    """
    import json
    from datetime import datetime, timezone

    from backend.data.twitter.edit_cache import delete_tweet, get_user_tweet_cache
    from backend.utlils.utils import read_user_info, write_user_info

    # Validate type
    if payload.type not in ("reply", "comment_reply"):
        raise HTTPException(status_code=400, detail="Invalid type. Must be 'reply' or 'comment_reply'")

    # Get cache_id for reply type (needed for post function)
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
        # Mark in comments cache
        from backend.data.twitter.comments_cache import read_comments_cache, write_comments_cache
        comments_map = read_comments_cache(username)

        if payload.response_to in comments_map:
            comments_map[payload.response_to]["post_pending"] = True
            # For comment replies, reply to the comment itself (not its parent)
            tweet_id_to_reply = payload.response_to
            write_comments_cache(username, comments_map)

    # Add to user's post_queue (persisted state)
    user_info = read_user_info(username)
    if not user_info:
        raise HTTPException(status_code=404, detail="User not found")

    post_queue = user_info.get("post_queue", [])

    # Check if already in queue (prevent duplicates)
    for item in post_queue:
        if item.get("response_to") == payload.response_to:
            return {"message": "Already in queue", "queued": False, "status": "duplicate"}

    # Create queue item
    queue_item = {
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
        "queued_at": datetime.now(timezone.utc).isoformat(),
    }

    post_queue.append(queue_item)
    user_info["post_queue"] = post_queue
    write_user_info(user_info)

    # Now immediately process the post
    try:
        # Build payload for Twitter API
        twitter_payload = {
            "text": payload.reply,
            "reply": {"in_reply_to_tweet_id": tweet_id_to_reply}
        }

        # Determine post type
        post_type = "comment_reply" if payload.type == "comment_reply" else "reply"

        # Post to Twitter
        result = await post(username, twitter_payload, cache_id=cache_id, reply_index=payload.reply_index, post_type=post_type)

        # Success! Remove from queue
        user_info = read_user_info(username)
        if user_info:
            user_info["post_queue"] = [q for q in user_info.get("post_queue", []) if q.get("response_to") != payload.response_to]
            write_user_info(user_info)

        # Delete from source cache
        if payload.type == "reply":
            await delete_tweet(username, payload.response_to, log_deletion=False)
        else:
            from backend.data.twitter.comments_cache import delete_comment
            delete_comment(username, payload.response_to)

        # Auto-like the tweet we replied to (for replies to others)
        if post_type == "reply":
            try:
                await like_tweet(username, tweet_id_to_reply)
            except Exception:
                pass  # Liking is not critical

        return {
            "message": "Posted successfully",
            "status": "posted",
            "posted_tweet_id": result.get("posted_tweet_id"),
            "data": result
        }

    except HTTPException as e:
        # Posting failed - remove from queue and clear post_pending
        user_info = read_user_info(username)
        if user_info:
            user_info["post_queue"] = [q for q in user_info.get("post_queue", []) if q.get("response_to") != payload.response_to]
            write_user_info(user_info)

        # Clear post_pending flag
        if payload.type == "reply":
            cache_path = get_user_tweet_cache(username)
            if cache_path.exists():
                with open(cache_path, encoding="utf-8") as f:
                    tweets = json.load(f)
                for tweet in tweets:
                    if tweet.get("id") == payload.response_to or tweet.get("cache_id") == payload.response_to:
                        tweet["post_pending"] = False
                        break
                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump(tweets, f, indent=2)
        else:
            from backend.data.twitter.comments_cache import read_comments_cache, write_comments_cache
            comments_map = read_comments_cache(username)
            if payload.response_to in comments_map:
                comments_map[payload.response_to]["post_pending"] = False
                write_comments_cache(username, comments_map)

        # Re-raise the exception for the frontend
        raise

    except Exception as e:
        # Unexpected error - same cleanup
        user_info = read_user_info(username)
        if user_info:
            user_info["post_queue"] = [q for q in user_info.get("post_queue", []) if q.get("response_to") != payload.response_to]
            write_user_info(user_info)

        # Clear post_pending flag
        if payload.type == "reply":
            cache_path = get_user_tweet_cache(username)
            if cache_path.exists():
                with open(cache_path, encoding="utf-8") as f:
                    tweets = json.load(f)
                for tweet in tweets:
                    if tweet.get("id") == payload.response_to or tweet.get("cache_id") == payload.response_to:
                        tweet["post_pending"] = False
                        break
                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump(tweets, f, indent=2)
        else:
            from backend.data.twitter.comments_cache import read_comments_cache, write_comments_cache
            comments_map = read_comments_cache(username)
            if payload.response_to in comments_map:
                comments_map[payload.response_to]["post_pending"] = False
                write_comments_cache(username, comments_map)

        error(f"Unexpected error posting tweet: {e}", status_code=500, exception_text=str(e),
              function_name="add_to_queue", username=username, critical=True)


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


@router.delete("/queue/{response_to}")
async def remove_from_queue(response_to: str, username: str = Query(...)) -> dict:
    """Remove an item from the posting queue (e.g., on failure or cancel).

    Also clears post_pending flag on the source tweet/comment.

    Args:
        response_to: The ID of the tweet/comment that was being replied to
        username: The user's handle

    Returns:
        Success message
    """
    import json

    from backend.utlils.utils import read_user_info, write_user_info

    user_info = read_user_info(username)
    if not user_info:
        raise HTTPException(status_code=404, detail="User not found")

    post_queue = user_info.get("post_queue", [])

    # Find and remove the item
    removed_item = None
    new_queue = []
    for item in post_queue:
        if item.get("response_to") == response_to:
            removed_item = item
        else:
            new_queue.append(item)

    if not removed_item:
        return {"message": "Item not found in queue", "removed": False}

    user_info["post_queue"] = new_queue
    write_user_info(user_info)

    # Clear post_pending flag on source
    if removed_item.get("type") == "reply":
        from backend.data.twitter.edit_cache import get_user_tweet_cache
        cache_path = get_user_tweet_cache(username)
        if cache_path.exists():
            with open(cache_path, encoding="utf-8") as f:
                tweets = json.load(f)

            for tweet in tweets:
                if tweet.get("id") == response_to or tweet.get("cache_id") == response_to:
                    tweet["post_pending"] = False
                    break

            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(tweets, f, indent=2)
    else:
        from backend.data.twitter.comments_cache import read_comments_cache, write_comments_cache
        comments_map = read_comments_cache(username)
        if response_to in comments_map:
            comments_map[response_to]["post_pending"] = False
            write_comments_cache(username, comments_map)

    return {"message": "Removed from queue", "removed": True, "item": removed_item}


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
        pending_post = {
            "id": f"pending-{item.get('response_to')}",
            "originalTweetId": item.get("response_to"),
            "text": item.get("reply", ""),
            "respondingTo": item.get("responding_to", ""),
            "originalTweetUrl": item.get("original_tweet_url", ""),
            "originalThreadText": item.get("response_to_thread", []),
            "source": "discovered" if item.get("type") == "reply" else "comments",
            "startedAt": item.get("queued_at", ""),
            "replyingToPfp": item.get("replying_to_pfp", ""),
            "parentChain": item.get("parent_chain", []),
            "media": item.get("media", []),
        }
        pending_posts.append(pending_post)

    return {"pending_posts": pending_posts, "count": len(pending_posts)}


# --- example usage ---
if __name__ == "__main__":
    import asyncio
    asyncio.run(post_tweet("proudlurker", Tweet(text="Hello, world!")))
