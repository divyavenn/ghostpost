import os
import pprint
from typing import Optional
from urllib.parse import unquote

import requests
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel


# --- config ---
# OAuth 2.0 *user access token* with permission to create posts (tweets)
# Store securely (e.g., env/secret manager)



async def _get_access_token_for_user(username: str) -> str:
    """Retrieve access token for a user from token store."""
    from backend.oauth import ensure_access_token
    access_token = await ensure_access_token(username)
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No token found for user {username}. User needs to authenticate first."
        )
    return access_token


# API Router
router = APIRouter(prefix="/post", tags=["post"])


class Tweet(BaseModel):
    text: str


class ReplyTweet(BaseModel):
    text: str
    tweet_id: str


async def post(username, payload: dict) -> dict: 
    access_token = await _get_access_token_for_user(username)

    url = "https://api.x.com/2/tweets"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    data = payload

    response = requests.post(url, headers=headers, json=data, timeout=30)

    if response.status_code >= 400:
        raise HTTPException(
            status_code=response.status_code,
            detail=f"Twitter API error: {response.text}"
        )

    return response.json()
    

@router.post("/tweet")
async def post_tweet(username: str, payload: Tweet) -> dict:
    data = {"text": payload.text}
    await post(username, data)


@router.post("/reply")
async def post_reply(username: str, payload: ReplyTweet) -> dict:
    data = {
        "text": payload.text,
        "reply": {
            "in_reply_to_tweet_id": payload.tweet_id
        }
    }

    await post(username, data)


@router.post("/quote")
async def post_quote_tweet(username: str, payload: ReplyTweet) -> dict:
    data = {
        "text": payload.text,
        "quote_tweet_id": payload.tweet_id
    }

    await post(username, data)


# --- example usage ---
if __name__ == "__main__":
    import asyncio
    asyncio.run(post_tweet("proudlurker", Tweet(text="Hello, world!")))
