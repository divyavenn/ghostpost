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

# Import scraping status tracker from read_tweets for status updates
try:
    from backend.read_tweets import scraping_status
except ImportError:
    from read_tweets import scraping_status


def ask_model(prompt: str, image_urls: list[str] = None, model: str = "divya-2-bon", has_quoted_tweet: bool = False):
    """
    Generate a reply using the VLM.
    
    Args:
        prompt: Text content (thread text)
        image_urls: List of image URLs to include in the prompt (for VLM)
        model: Model name
        has_quoted_tweet: Whether the tweet contains a quoted tweet (affects system prompt)
    """
    url = "https://obelisk.dread.technology/api/chat/completions"

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

    # Choose system prompt based on whether tweet has a quoted tweet
    if has_quoted_tweet:
        system_prompt = (
            "you are scrolling twitter. the user quote-tweeted someone else's post and added their own response. "
            "the quoted content is marked [QUOTED TWEET] and the user's response is marked [RESPONSE]. "
            "they may be agreeing, disagreeing, adding context, or mocking the quote. "
            "casually respond to the user's perspective in two to three lines as a stranger, "
            "considering both the quoted content and their take on it."
        )
    else:
        system_prompt = (
            "you are scrolling twitter. "
            "casually respond to this thread in two to three lines as a stranger"
        )

    payload = {
        "model": model,
        "messages": [{
            "role": "system",
            "content": system_prompt
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
    total_to_process = len([t for t in tweets if not (t.get('reply') and not overwrite) and t.get('thread')])

    for idx, tweet in enumerate(tweets, 1):
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

        # Build structured text prompt with quoted tweet context if present
        text_prompt = ""
        image_urls = []
        
        # Extract quoted tweet if present
        quoted_tweet = tweet.get('quoted_tweet')
        has_quoted_tweet = bool(quoted_tweet and quoted_tweet.get('text'))
        
        if has_quoted_tweet:
            # Add quoted tweet context first
            qt_author = quoted_tweet.get('author_handle', 'unknown')
            qt_name = quoted_tweet.get('author_name', qt_author)
            qt_text = quoted_tweet.get('text', '')
            
            # Truncate QT text to 280 chars if needed
            if len(qt_text) > 280:
                qt_text = qt_text[:280] + "... [truncated]"
            
            text_prompt += f"[QUOTED TWEET by @{qt_author} ({qt_name})]\n"
            text_prompt += f"{qt_text}\n"
            
            # Add QT images first
            qt_media = quoted_tweet.get('media', [])
            qt_images = [item['url'] for item in qt_media if item.get('type') == 'photo']
            if qt_images:
                image_urls.extend(qt_images)
                text_prompt += f"[This quoted tweet contains {len(qt_images)} image(s)]\n"
            
            text_prompt += "\n---\n\n"
        
        # Add main tweet/thread
        username_display = tweet.get('username', tweet.get('handle', 'User'))
        if has_quoted_tweet:
            text_prompt += f"[{username_display}'s RESPONSE]\n"
        
        text_prompt += str(thread)
        
        # Add main tweet images after QT images
        media = tweet.get('media', [])
        main_images = [item['url'] for item in media if item.get('type') == 'photo']
        if main_images:
            image_urls.extend(main_images)
            if has_quoted_tweet:
                text_prompt += f"\n[Response contains {len(main_images)} image(s)]"
        
        # Add alt text context if available (for all images)
        all_media = (quoted_tweet.get('media', []) if quoted_tweet else []) + media
        alt_texts = [item.get('alt_text', '') for item in all_media if item.get('alt_text')]
        if alt_texts:
            text_prompt += f"\n\n[Image descriptions: {'; '.join(alt_texts)}]"

        # Get model's reply with appropriate delay for rate limiting
        try:
            # Update status to show progress
            processed_count = count + skipped + errors + 1
            if username:
                scraping_status[username] = {
                    "type": "generating",
                    "value": f"{processed_count}/{len(tweets)}",
                    "phase": "generating"
                }

            if image_urls:
                notify(f"🤖 Generating reply for tweet {tweet_id} with {len(image_urls)} image(s)... ({processed_count}/{len(tweets)})")
            else:
                notify(f"🤖 Generating reply for tweet {tweet_id}... ({processed_count}/{len(tweets)})")

            # Pass has_quoted_tweet flag to enable appropriate system prompt
            response = ask_model(
                prompt=text_prompt,
                image_urls=image_urls,
                has_quoted_tweet=has_quoted_tweet
            )

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

                # Progressive write: save immediately after generating each reply
                await write_to_cache([tweet], f"Generated reply for tweet {tweet_id}", username=username)
            else:
                notify(f"⚠️ Empty reply received for tweet {tweet_id}")
                errors += 1

            time.sleep(delay_seconds)

        except Exception as e:
            notify(f"❌ Exception generating reply for tweet {tweet_id}: {e}")
            errors += 1

    # Note: No final write_to_cache needed - already saved incrementally

    # Mark generation as complete
    if username:
        scraping_status[username] = {
            "type": "complete",
            "value": "",
            "phase": "complete"
        }

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


@router.post("/{username}/replies/{tweet_id}")
async def regenerate_single_reply_endpoint(username: str, tweet_id: str) -> dict:
    """Regenerate AI reply for a single tweet."""
    from backend.tweets_cache import read_from_cache, write_to_cache

    try:
        # Check if API key is configured
        if not OBELISK_KEY:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="OBELISK_KEY environment variable is not set"
            )

        # Read tweets from cache
        tweets = await read_from_cache(username=username)

        if not tweets:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No tweets found in cache"
            )

        # Find the specific tweet
        tweet = None
        for t in tweets:
            if t.get('id') == tweet_id or t.get('tweet_id') == tweet_id:
                tweet = t
                break

        if not tweet:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tweet {tweet_id} not found in cache"
            )

        # Get thread content for prompt
        thread = tweet.get('thread', [])
        if not thread:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tweet has no thread content"
            )

        prompt = str(thread)

        # Generate new reply
        notify(f"🤖 Regenerating reply for tweet {tweet_id}...")
        response = ask_model(prompt=prompt)

        # Check for errors in response
        if "error" in response:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"API error: {response['error']}"
            )

        reply = response.get('message', '')
        if not reply:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Empty reply received from model"
            )

        # Update the tweet with the new reply
        tweet['reply'] = reply

        # Save back to cache
        await write_to_cache(tweets, f"Regenerated reply for tweet {tweet_id}", username=username)

        notify(f"✅ Regenerated reply for tweet {tweet_id}")

        return {
            "message": "Reply regenerated successfully",
            "tweet_id": tweet_id,
            "new_reply": reply
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error regenerating reply: {str(e)}"
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
