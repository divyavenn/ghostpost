import asyncio
import os

import requests
from dotenv import load_dotenv

from .read_tweets import USERNAME
from .utils import error, notify

try:
    from backend.resolve_imports import ensure_standalone_imports
except ModuleNotFoundError:  # Running from inside backend/
    from resolve_imports import ensure_standalone_imports

ensure_standalone_imports(globals())

# Load environment variables from .env file
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

# Put your OBELISK_KEY in an environment variable for safety
OBELISK_KEY = os.getenv("OBELISK_KEY")


def ask_model(prompt: str, image_urls: list[str] = None, model: str = "divya-2-bon"):
    """
    Generate a reply using the VLM.
    
    Args:
        prompt: Text content (thread text)
        image_urls: List of image URLs to include in the prompt (for VLM)
        model: Model name
    """
    url = "https://ultra.dread.technology/v1/chat/completions"

    headers = {"Authorization": f"Bearer {OBELISK_KEY}", "Content-Type": "application/json"}

    # Build user message content
    if image_urls and len(image_urls) > 0:
        # Multimodal message with images
        user_content = [
            {
                "type": "text",
                "text": prompt
            }
        ]
        
        # Add each image
        for img_url in image_urls:
            user_content.append({
                "type": "image_url",
                "image_url": {
                    "url": img_url
                }
            })
    else:
        # Text-only message
        user_content = prompt

    payload = {
        "model": model,
        "messages": [{
            "role": "system",
            "content": "you are scrolling twitter. Casually respond to this thread in two to three lines as a stranger"
        }, {
            "role": "user",
            "content": user_content
        }]
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

    data = response.json()

    # Extract message content
    try:
        message = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        return {"error": "Unexpected API response", "raw": data}

    return {"message": message}



async def generate_replies(username=USERNAME, delay_seconds=1, overwrite=False):
    import time
    from backend.tweets_cache import read_from_cache, write_to_cache

    # Check if API key is configured
    if not OBELISK_KEY:
        notify("❌ OBELISK_KEY environment variable is not set")
        raise RuntimeError("OBELISK_KEY environment variable is not set")

    tweets = await read_from_cache(username=username)

    if not tweets:
        notify("⚠️ No tweets found in cache")
        return []

    notify(f"📝 Processing {len(tweets)} tweets for user {username}...")
    count = 0
    skipped = 0
    errors = 0

    for tweet in tweets:
        tweet_id = tweet.get('id') or tweet.get('tweet_id')

        # Skip if reply already exists and we're not overwriting
        if "reply" in tweet and tweet["reply"] and not overwrite:
            skipped += 1
            continue

        # Get thread content for prompt
        thread = tweet.get('thread', [])
        if not thread:
            notify(f"⚠️ Tweet {tweet_id} has no thread content, skipping")
            skipped += 1
            continue

        # Build text prompt
        text_prompt = str(thread)

        # Get media URLs if available
        media = tweet.get('media', [])
        image_urls = [item['url'] for item in media if item.get('type') == 'photo']

        # Add alt text context if available
        alt_texts = [item.get('alt_text', '') for item in media if item.get('alt_text')]
        if alt_texts:
            text_prompt += f"\n\n[Image descriptions: {'; '.join(alt_texts)}]"

        # Get model's reply with appropriate delay for rate limiting
        try:
            if image_urls:
                notify(f"🤖 Generating reply for tweet {tweet_id} with {len(image_urls)} image(s)...")
            else:
                notify(f"🤖 Generating reply for tweet {tweet_id}...")
            response = ask_model(prompt=text_prompt, image_urls=image_urls)

            # Check for errors in response
            if "error" in response:
                notify(f"❌ API error for tweet {tweet_id}: {response['error']}")
                errors += 1
                continue

            reply = response.get('message', '')
            if reply:
                tweet['reply'] = reply
                count += 1
                notify(f"✅ Generated reply for tweet {tweet_id}")
            else:
                notify(f"⚠️ Empty reply received for tweet {tweet_id}")
                errors += 1

            time.sleep(delay_seconds)

        except Exception as e:
            notify(f"❌ Exception generating reply for tweet {tweet_id}: {e}")
            errors += 1

    # Save the updated tweets back to the file
    await write_to_cache(tweets, f"Generated replies for {count} tweets", username=username)

    notify(f"✅ Done! Generated: {count}, Skipped: {skipped}, Errors: {errors}")

    return tweets


async def run_all() -> None:
    # Directly process trending_cache.json with hardcoded parameters
    #await read_tweets()
    await generate_replies()

    notify("Done!")


# API Router
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

router = APIRouter(prefix="/generate", tags=["generate"])


class GenerateRepliesRequest(BaseModel):
    delay_seconds: int = 1
    overwrite: bool = False


@router.post("/{username}/replies")
async def generate_replies_endpoint(username: str, payload: GenerateRepliesRequest | None = None) -> dict:
    """Generate AI replies for tweets in the cache."""
    try:
        if payload is None:
            tweets = await generate_replies(username=username)
        else:
            tweets = await generate_replies(
                username=username,
                delay_seconds=payload.delay_seconds,
                overwrite=payload.overwrite
            )

        # Count tweets with replies
        reply_count = sum(1 for t in tweets if t.get('reply'))

        return {
            "message": "Replies generated successfully",
            "total_tweets": len(tweets),
            "replies_generated": reply_count
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating replies: {str(e)}"
        )


if __name__ == "__main__":
    asyncio.run(run_all())

    # Original example for reference
    # prompt = str([
    #   "i know life happens wherever you are, but I can't help but feel like none of this is real. Like I'm wandering from door to door, temporary home to temporary home. I want to plunge my fingers into earth I own, buy furniture too heavy to move and plant roses",
    #   "I want to walk to the nearby coffeeshop and see familiar faces. I want to take the time to get to know my neighbors, knowing that we'll both be here a few months from now",
    #   "I am so so homesick, but for a home I've never had. I thought i'd have it once. I bought the furniture, met the neighbors. But i chose somewhere I couldn't stay.",
    #   "Everything has been going well for the past few days. Many encouraging signs that I'm getting closer to my goals. and yet I'm miserable and listless. I don't want to put down roots only to dig them up.",
    #   "I don't have the people or the place to put down roots, but I can't help myself. Every room I spend more than two nights in, my mind goes to making it tidier and more cosy. It makes me sad to make those efforts and sadder not to. All I can think of is how I'll have to do it again"
    # ])
    # print(ask_model(prompt))
