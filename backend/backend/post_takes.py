
import requests
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel


# --- config ---
# OAuth 2.0 *user access token* with permission to create posts (tweets)
# Store securely (e.g., env/secret manager)
async def _get_access_token_for_user(username: str) -> str:
    """Retrieve access token for a user from token store."""
    from backend.oauth import ensure_access_token
    access_token = await ensure_access_token(username)
    if not access_token:
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


async def post(username, payload: dict, cache_id: str | None = None) -> dict:
    from backend.log_interactions import TweetAction, log_tweet_action

    access_token = await _get_access_token_for_user(username)

    url = "https://api.x.com/2/tweets"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    data = payload

    response = requests.post(url, headers=headers, json=data, timeout=30)

    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=f"Twitter API error: {response.text}")

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

        # Log using the original tweet ID as the key if available, otherwise use posted_tweet_id
        log_key = original_tweet_id or posted_tweet_id
        log_tweet_action(username, TweetAction.POSTED, str(log_key), metadata=metadata)

    # Return result with posted_tweet_id explicitly for frontend tracking
    return {**result, "posted_tweet_id": posted_tweet_id}


@router.post("/tweet")
async def post_tweet(username: str, payload: Tweet) -> dict:
    data = {"text": payload.text}
    return await post(username, data, cache_id=payload.cache_id)


@router.post("/reply")
async def post_reply(payload: ReplyTweet, username: str = Query(...)) -> dict:
    data = {"text": payload.text, "reply": {"in_reply_to_tweet_id": payload.tweet_id}}
    return await post(username, data, cache_id=payload.cache_id)


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

    access_token = await _get_access_token_for_user(username)

    url = f"https://api.x.com/2/tweets/{tweet_id}"
    headers = {"Authorization": f"Bearer {access_token}"}

    response = requests.delete(url, headers=headers, timeout=30)

    if response.status_code == 200:
        # Successfully deleted - log the action
        log_tweet_action(username, TweetAction.DELETED, tweet_id, metadata={"deleted_from_twitter": True, "posted_tweet_id": tweet_id})
        return {"message": "Tweet deleted successfully", "tweet_id": tweet_id, "deleted": True}
    elif response.status_code == 404:
        # Tweet not found (may already be deleted)
        return {"message": "Tweet not found (may already be deleted)", "tweet_id": tweet_id, "deleted": False}
    else:
        # Other error
        raise HTTPException(status_code=response.status_code, detail=f"Twitter API error: {response.text}")


# --- example usage ---
if __name__ == "__main__":
    import asyncio
    asyncio.run(post_tweet("proudlurker", Tweet(text="Hello, world!")))
