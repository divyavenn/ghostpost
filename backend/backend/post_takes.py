
import requests
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from backend.utils import error, notify


# --- config ---
# OAuth 2.0 *user access token* with permission to create posts (tweets)
# Store securely (e.g., env/secret manager)
async def _get_access_token_for_user(username: str) -> str:
    """Retrieve access token for a user from token store."""
    from backend.oauth import ensure_access_token
    access_token = await ensure_access_token(username)
    if not access_token:
        error(f"No token found for user {username}", status_code=404, function_name="_get_access_token_for_user", username=username, critical=True)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No token found for user {username}. User needs to authenticate first.")
    return access_token


# API Router
router = APIRouter(prefix="/post", tags=["post"])


class Tweet(BaseModel):
    text: str
    cache_id: str | None = None


class ReplyTweet(BaseModel):
    text: str
    tweet_id: str
    cache_id: str | None = None
    reply_index: int | None = None


async def post(username, payload: dict, cache_id: str | None = None, reply_index: int | None = None) -> dict:
    from backend.log_interactions import TweetAction, log_tweet_action
    from backend.posted_tweets_cache import add_posted_tweet
    from backend.tweets_cache import get_user_tweet_cache
    from backend.utils import read_user_info, write_user_info, notify
    import json

    access_token = await _get_access_token_for_user(username)

    url = "https://api.x.com/2/tweets"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    data = payload

    response = requests.post(url, headers=headers, json=data, timeout=30)
    if response.status_code == 403:
        error(f"Tweet has been deleted, cannot reply", status_code=response.status_code, exception_text=response.text, function_name="post", username=username, critical=True)
    elif response.status_code >= 400:
        error(f"Twitter API error when posting tweet", status_code=response.status_code, exception_text=response.text, function_name="post", username=username, critical=True)

    result = response.json()

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
        model_name = "unknown"

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

                            # Get model information for the posted reply
                            # generated_replies is now an array of tuples: [(reply_text, model_name), ...]
                            if reply_index is not None:
                                generated_replies = tweet.get("generated_replies", [])
                                if reply_index < len(generated_replies):
                                    # Extract model name from tuple (reply_text, model_name)
                                    if isinstance(generated_replies[reply_index], tuple) and len(generated_replies[reply_index]) >= 2:
                                        model_name = generated_replies[reply_index][1]

                            break
            except Exception as e:
                error(f"Could not fetch original tweet data from cache", status_code=500, exception_text=str(e), function_name="post", username=username)
                notify(f"⚠️ Could not fetch original tweet data from cache: {e}")

        # Add model name to metadata
        metadata["model"] = model_name

        # Log using the original tweet ID as the key if available, otherwise use posted_tweet_id
        log_key = original_tweet_id or posted_tweet_id
        log_tweet_action(username, TweetAction.POSTED, str(log_key), metadata=metadata)

        # Add to posted_tweets.json cache
        try:
            add_posted_tweet(
                username=username,
                posted_tweet_id=posted_tweet_id,
                text=payload.get("text", ""),
                original_tweet_url=original_tweet_url,
                responding_to_handle=responding_to_handle,
                replying_to_pfp=replying_to_pfp,
                response_to_thread=response_to_thread
            )
        except Exception as e:
            error(f"Failed to add to posted_tweets cache", status_code=500, exception_text=str(e), function_name="post", username=username)
            notify(f"⚠️ Failed to add to posted_tweets cache: {e}")

        # Increment lifetime_posts
        try:
            user_info = read_user_info(username)
            if user_info:
                current_posts = user_info.get("lifetime_posts", 0)
                user_info["lifetime_posts"] = current_posts + 1
                write_user_info(user_info)
                notify(f"📝 Post count incremented for @{username} (total: {user_info['lifetime_posts']})")
        except Exception as e:
            error(f"Failed to update post count", status_code=500, exception_text=str(e), function_name="post", username=username)
            notify(f"⚠️ Failed to update post count for {username}: {e}")

    # Return result with posted_tweet_id explicitly for frontend tracking
    return {**result, "posted_tweet_id": posted_tweet_id}


@router.post("/tweet")
async def post_tweet(username: str, payload: Tweet) -> dict:
    data = {"text": payload.text}
    return await post(username, data, cache_id=payload.cache_id)


@router.post("/reply")
async def post_reply(payload: ReplyTweet, username: str = Query(...)) -> dict:
    data = {"text": payload.text, "reply": {"in_reply_to_tweet_id": payload.tweet_id}}
    return await post(username, data, cache_id=payload.cache_id, reply_index=payload.reply_index)


@router.post("/quote")
async def post_quote_tweet(username: str, payload: ReplyTweet) -> dict:
    data = {"text": payload.text, "quote_tweet_id": payload.tweet_id}
    return await post(username, data, cache_id=payload.cache_id)


@router.delete("/tweet/{tweet_id}")
async def delete_posted_tweet(tweet_id: str, username: str = Query(...)) -> dict:
    """Delete a posted tweet from Twitter via API.

    Args:
        tweet_id: The Twitter-assigned ID of the posted tweet
        username: The username who owns the tweet

    Returns:
        Success message and metadata
    """
    from backend.log_interactions import TweetAction, log_tweet_action
    from backend.utils import read_user_info, write_user_info

    access_token = await _get_access_token_for_user(username)

    url = f"https://api.x.com/2/tweets/{tweet_id}"
    headers = {"Authorization": f"Bearer {access_token}"}

    response = requests.delete(url, headers=headers, timeout=30)

    if response.status_code == 200:
        # Successfully deleted - log the action
        log_tweet_action(username, TweetAction.DELETED, tweet_id, metadata={"deleted_from_twitter": True, "posted_tweet_id": tweet_id})

        # Delete from posted_tweets.json cache
        try:
            from backend.posted_tweets_cache import delete_posted_tweet_from_cache
            delete_posted_tweet_from_cache(username, tweet_id)
        except Exception as e:
            error(f"Failed to delete tweet from posted tweets cache", status_code=500, exception_text=str(e), function_name="delete_posted_tweet", username=username)
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
            error(f"Failed to update post count", status_code=500, exception_text=str(e), function_name="delete_posted_tweet", username=username)
            notify(f"⚠️ Failed to update post count for {username}: {e}")

        return {"message": "Tweet deleted successfully", "tweet_id": tweet_id, "deleted": True}
    elif response.status_code == 404:
        # Tweet not found (may already be deleted)
        return {"message": "Tweet not found (may already be deleted)", "tweet_id": tweet_id, "deleted": False}
    else:
        # Other error
        error(f"Twitter API error when deleting tweet", status_code=response.status_code, exception_text=response.text, function_name="delete_posted_tweet", username=username, critical=True)
        raise HTTPException(status_code=response.status_code, detail=f"Twitter API error: {response.text}")


# --- example usage ---
if __name__ == "__main__":
    import asyncio
    asyncio.run(post_tweet("proudlurker", Tweet(text="Hello, world!")))
