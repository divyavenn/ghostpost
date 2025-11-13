import asyncio
import os

import requests
from dotenv import load_dotenv
from fastapi import APIRouter
from pydantic import BaseModel

from .read_tweets import USERNAME
from .utils import error, notify, read_user_info

try:
    from backend.resolve_imports import ensure_standalone_imports
except ModuleNotFoundError:  # Running from inside backend/
    from resolve_imports import ensure_standalone_imports

ensure_standalone_imports(globals())

# Load environment variables from .env file
# Load .env from backend/ directory (one level up from backend/backend/)
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from backend.config import OBELISK_KEY

# Import scraping status tracker from read_tweets for status updates
try:
    from backend.read_tweets import scraping_status, update_status_to_reflect_finished_scraping
except ImportError:
    from read_tweets import scraping_status, update_status_to_reflect_finished_scraping


REPLY_GAME = """You are an expert at online conversation. 
Your job is to craft replies, comments, and recommendations that support the original poster (OP), elevate the discussion, 
and make the OP feel accurately understood. Your tone should feel like an insightful, socially intelligent expert texting a friend — concise, intuitive, supportive, never pompous.

The quoted content is marked [QUOTED TWEET] if it exists and the user's response is marked [RESPONSE].


I. Core Philosophy: What every reply must accomplish
	1.	Support the OP’s intention, not your own impulses. First infer: What game is OP proposing? What emotional or conversational move are they making? Match that move and build on it.
	2.	Disagree only in a way that still supports the OP’s project. Never “mis-support” by agreeing stupidly or derailing. If correcting, make it collaborative: “here’s how to make this land even better.”
	3.	Replies should feel like invitations, not verdicts. Build shared understanding. Add signal, not noise.
	4.	Follow Grice’s Maxims:
        Quantity: give as much info as needed, no more.
        Quality: be truthful + grounded, no bullshit.
        Relation: stay relevant to OP’s aim.
        Manner: be clear, crisp, and unambiguous.


Use these as invisible rules for tone and vibe:
    1) Respect others; assume good faith.
    2) Ask questions that people can look good answering
    3) Don’t intimidate or show off.
    4) Take all admonition thankfully
    5) Elevate the mood and repair it if someone else ruins it
    6) Never laugh at misfortune.
    7) Never lecture someone in their own domain (“teach not your equal in the art he professes”).
    8) When someone shares something vulnerable, respond with generosity, not cleverness.



Reply Crafting Workflow

    1) The important thing is not to speak your mind, but to “support” the OP. 
    You can support them by disagreeing well & you can “mis-support”  them by agreeing stupidly

    Every “utterance” (status, tweet, whatever) is a bit of an invitation, a bit of a proposal. 
    “Let’s play this game”.
    When strangers read the proposal accurately, and support the game, a shared understanding develops. 
    You can make friends this way.

    When generating a reply, infer OP’s intention - in other words, the “game” OP wants to play.

    Example categories: 
    seeking validation, 
    joking, 
    storytelling, 
    sharing an insight, 
    venting, 
    persuading, 
    asking for advice, 
    celebrating, 
    banter, 
    vibe-sharing, 
    seeking validation, 
    serious discussion, 
    co-analysis, 
    info-trading, 
    emotional resonance, 
    intellectual sparring, 
    cheerleading


    2) Reply in a way that strengthens that game. Scan the other replies (if provided) and beat them.  
    Add a missing angle. Be clearer, kinder, sharper, or more specific. Bring a higher-resolution insight. 
    Offer the line everyone else wished they’d written.

    3) Deliver a concise, high-signal comment. 
    1–3 sentences for casual replies. slightly longer for thoughtful takes. 
    always clean, warm, and original

⸻

Recommendation Style

If you had to sell a book about local music. you would go around asking people about *their* stories and *their* experiences re: music. 
You would interview musicians and fans. You should adopt a similar attitude when recommending your own or other people's work.

When recommending anything (book, video, place, food, artist), follow this structure:
	1.	Lower the activation energy. “Start with this one track / one chapter / one episode.”
	2.	Be Specific, Never Vague. Recommend ONE entry point, not a whole genre or entire channel.
	3.	Explain WHY. State at least one concrete reason, such as “this video is the cleanest explanation of X I’ve ever seen"
	4.	Share the personal angle.
 
“What it did for me” is more convincing than “objectively good.”

⸻

Critique & Creative Support

When responding to ideas, drafts, or creative work:
	•	Never kill the idea — show how to make it shine.
	•	Use the professor’s framing: “How can we make this work?”
	•	Identify the strongest seed and grow from there.
	•	Suggest improvements without superiority or condescension.


Final Instruction

Given an OP’s text and a conversation context, generate:
	•	an excellent reply that supports OP’s intention and elevates the discourse
OR
	•	a compelling, specific recommendation with a clear on-ramp and reason why

Your reply should feel like something people would screenshot because it’s that good.

"""

async def ask_model(prompt: str, image_urls: list[str] = None, model: str = "nakul-1", has_quoted_tweet: bool = False, username: str = "unknown") -> dict:
    url = "https://obelisk.dread.technology/api/chat/completions"

    headers = {"Authorization": f"Bearer {OBELISK_KEY}", "Content-Type": "application/json"}

    # Build user message content
    if image_urls and len(image_urls) > 0:
        # Multimodal message with images
        user_content = [{"type": "text", "text": prompt}]

        # Add each image
        for img_url in image_urls:
            user_content.append({"type": "image_url", "image_url": {"url": img_url}})
    else:
        # Text-only message
        user_content = prompt

    # Choose system prompt based on whether tweet has a quoted tweet
    system_prompt = REPLY_GAME

    payload = {"model": model, "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_content}]}

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        # Try to get the error response body
        error_detail = str(e)
        try:
            if hasattr(e, 'response') and e.response is not None:
                error_detail = f"{str(e)} | Response: {e.response.text}"
        except Exception:
            pass
        error(f"❌ Error communicating with Obelisk API: {error_detail}", status_code=500, function_name='ask_model', username=username, critical=False)
        return {"error": error_detail}

    data = response.json()

    # Extract message content
    try:
        message = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        return {"error": "Unexpected API response", "raw": data}

    return {"message": message}


def build_prompt(tweet):
    tweet_id = tweet['id'] if 'id' in tweet else (tweet['tweet_id'] if 'tweet_id' in tweet else None)

    thread = tweet['thread'] if 'thread' in tweet else []
    if not thread:
        notify(f"⚠️ Tweet {tweet_id} has no thread content, skipping")
        return None

    # Build structured text prompt with quoted tweet context if present
    text_prompt = ""
    image_urls = []

    # Extract quoted tweet if present
    quoted_tweet = tweet['quoted_tweet'] if 'quoted_tweet' in tweet else None
    has_quoted_tweet = bool(quoted_tweet and ('text' in quoted_tweet and quoted_tweet['text']))

    if has_quoted_tweet:
        # Add quoted tweet context first
        qt_author = quoted_tweet['author_handle'] if 'author_handle' in quoted_tweet else 'unknown'
        qt_name = quoted_tweet['author_name'] if 'author_name' in quoted_tweet else qt_author
        qt_text = quoted_tweet['text'] if 'text' in quoted_tweet else ''

        text_prompt += f"[QUOTED TWEET by @{qt_author} ({qt_name})]\n"
        text_prompt += f"{qt_text}\n"

        # Add QT images first
        qt_media = quoted_tweet['media'] if 'media' in quoted_tweet else []
        qt_images = [item['url'] for item in qt_media if 'type' in item and item['type'] == 'photo']
        if qt_images:
            image_urls.extend(qt_images)
            text_prompt += f"[This quoted tweet contains {len(qt_images)} image(s)]\n"

        text_prompt += "\n---\n\n"

    # Add main tweet/thread
    username_display = tweet['username'] if 'username' in tweet else (tweet['handle'] if 'handle' in tweet else 'User')
    if has_quoted_tweet:
        text_prompt += f"[{username_display}'s RESPONSE]\n"

    text_prompt += str(thread)

    # Add main tweet images after QT images
    media = tweet['media'] if 'media' in tweet else []
    main_images = [item['url'] for item in media if 'type' in item and item['type'] == 'photo']
    if main_images:
        image_urls.extend(main_images)
        if has_quoted_tweet:
            text_prompt += f"\n[Response contains {len(main_images)} image(s)]"

    # Add alt text context if available (for all images)
    all_media = (quoted_tweet['media'] if quoted_tweet and 'media' in quoted_tweet else []) + media
    alt_texts = [item['alt_text'] for item in all_media if 'alt_text' in item and item['alt_text']]
    if alt_texts:
        text_prompt += f"\n\n[Image descriptions: {'; '.join(alt_texts)}]"

    return text_prompt, image_urls, has_quoted_tweet, tweet_id


async def generate_replies_for_tweet(tweet, models, needed_generations, delay_seconds=1, batch=False, username="unknown"):
    import random

    replies = []

    if needed_generations > 0:
        prompt = build_prompt(tweet)
        if prompt is None:
            return []

        text_prompt, image_urls, has_quoted_tweet, tweet_id = prompt

        for gen_idx in range(needed_generations):
            # Model selection logic:
            # - If fewer models than replies: cycle through models
            # - If more models than replies: randomly select a model for each reply
            if len(models) < (needed_generations):
                # Cycle through models
                selected_model = models[gen_idx % len(models)]
            else:
                # Randomly select from available models
                selected_model = random.choice(models)

            if image_urls:
                notify(f"🤖 Generating reply {gen_idx+1} for {tweet_id} using {selected_model} with {len(image_urls)} image(s)...")
            else:
                notify(f"🤖 Generating reply {gen_idx+1} for {tweet_id} using {selected_model}...")

            # Pass has_quoted_tweet flag to enable appropriate system prompt
            response = await ask_model(prompt=text_prompt, model=selected_model, image_urls=image_urls, has_quoted_tweet=has_quoted_tweet, username=username)

            reply = response.get('message', '')
            if reply:
                replies.append((reply, selected_model))
                notify(f"✅ Generated reply {gen_idx+1} for tweet {tweet_id}")
            else:
                error_msg = response.get('error', 'Unknown error')
                error(f"⚠️ Empty reply received for generation {gen_idx+1} of tweet {tweet_id}: {error_msg}",
                      status_code=500,
                      function_name="generate_replies_for_tweet",
                      username=username,
                      critical=(not batch))

            # Delay between generations to avoid rate limiting
            if gen_idx < needed_generations - 1:
                await asyncio.sleep(delay_seconds)

    return replies


async def generate_replies(username=USERNAME, delay_seconds=1, overwrite=False):
    from backend.tweets_cache import read_from_cache, write_to_cache

    # Check if API key is configured
    if not OBELISK_KEY:
        error("❌ OBELISK_KEY environment variable is not set", status_code=500, function_name="generate_replies_endpoint", username=username, critical=True)

    scraping_status[username] = {"type": "generating", "value": "Starting...", "phase": "generating"}

    tweets = await read_from_cache(username=username)
    user_info = read_user_info(username)

    # Get models array - use bracket notation to ensure we get the value
    models = user_info["models"] if "models" in user_info and user_info["models"] else ["claude-3-5-sonnet-20241022"]
    number_of_generations = user_info["number_of_generations"] if "number_of_generations" in user_info else 1

    if not tweets:
        notify("⚠️ No tweets found in cache")
        # Update status to complete and then idle since there's nothing to process
        await update_status_to_reflect_finished_scraping(username)
        return []

    notify(f"📝 Processing {len(tweets)} tweets for user {username} using models: {models}...")
    count = 0
    skipped = 0
    errors = 0
    total_to_process = len([t for t in tweets if not (('generated_replies' in t and t['generated_replies']) and not overwrite) and ('thread' in t and t['thread'])])

    for tweet in tweets:
        needed_generations = number_of_generations - len(tweet.get('generated_replies', []))
        if overwrite:
            needed_generations = number_of_generations

        if needed_generations <= 0:
            skipped += 1
            continue

        if 'thread' not in tweet or not tweet['thread']:
            tweet_id = tweet.get('id', tweet.get('tweet_id', 'unknown'))
            notify(f"⚠️ Tweet {tweet_id} has no thread content, skipping")
            skipped += 1
            continue

        # Generate replies using the reusable function
        try:
            # Update status BEFORE generation to show current progress
            processed_count = count + skipped + errors + 1
            if username:
                scraping_status[username] = {"type": "generating", "value": f"{processed_count}/{total_to_process}", "phase": "generating"}

            replies = await generate_replies_for_tweet(tweet, models, needed_generations, delay_seconds, batch=True, username=username)

            # Store all replies as array of tuples (reply_text, model_name)
            if replies:
                if overwrite:
                    # Replace all replies
                    tweet['generated_replies'] = replies
                else:
                    # Append new replies to existing ones
                    existing_replies = tweet.get('generated_replies', [])
                    tweet['generated_replies'] = existing_replies + replies

                count += 1
                tweet_id = tweet.get('id', tweet.get('tweet_id', 'unknown'))
                notify(f"✅ Generated {len(replies)} replies for tweet {tweet_id}")

                # Progressive write: save immediately after generating all replies
                await write_to_cache([tweet], f"Generated {len(replies)} replies for tweet {tweet_id}", username=username)
            else:
                tweet_id = tweet.get('id', tweet.get('tweet_id', 'unknown'))
                notify(f"⚠️ No replies generated for tweet {tweet_id}")
                errors += 1

            await asyncio.sleep(delay_seconds)

        except Exception as e:
            tweet_id = tweet.get('id', tweet.get('tweet_id', 'unknown'))
            error(f"❌ Exception generating replies for tweet {tweet_id}: {e}", status_code=500, exception_text=str(e), function_name="generate_replies", username=username, critical=False)
            errors += 1

    if errors > 0:
        error(f"{errors} errors batch-generating replies for tweets", status_code=500, function_name="generate_replies", username=username, critical=True)

    # Mark generation as complete and reset to idle after 5 seconds
    await update_status_to_reflect_finished_scraping(username)

    notify(f"✅ Done! Generated: {count}, Skipped: {skipped}, Errors: {errors}")

    return tweets


async def run_all() -> None:
    # Directly process trending_cache.json with hardcoded parameters
    #await read_tweets()
    await generate_replies()

    notify("Done!")


# API Router
router = APIRouter(prefix="/generate", tags=["generate"])


class GenerateRepliesRequest(BaseModel):
    delay_seconds: int = 1
    overwrite: bool = False


@router.post("/{username}/replies")
async def generate_replies_endpoint(username: str, payload: GenerateRepliesRequest | None = None) -> dict:
    """Generate AI replies for tweets in the cache."""
    try:
        # Set status to generating immediately when endpoint is called
        scraping_status[username] = {"type": "generating", "value": "Starting...", "phase": "generating"}

        if payload is None:
            tweets = await generate_replies(username=username)
        else:
            tweets = await generate_replies(username=username, delay_seconds=payload.delay_seconds, overwrite=payload.overwrite)

        # Count tweets with replies
        reply_count = sum(1 for t in tweets if t.get('replies'))

        return {"message": "Replies generated successfully", "total_tweets": len(tweets), "replies_generated": reply_count}
    except Exception as e:
        error("Error generating replies", status_code=500, exception_text=str(e), function_name="generate_replies_endpoint", username=username)


@router.post("/{username}/replies/{tweet_id}")
async def regenerate_single_reply_endpoint(username: str, tweet_id: str) -> dict:
    """Regenerate AI reply for a single tweet."""
    from backend.tweets_cache import read_from_cache, write_to_cache

    # Check if API key is configured
    if not OBELISK_KEY:
        error("Obelisk API key not configured", status_code=500, function_name="regenerate_single_reply_endpoint", username=username, critical=True)

    # Read tweets from cache
    tweets = await read_from_cache(username=username)
    user_info = read_user_info(username)
    models = user_info["models"] if "models" in user_info and user_info["models"] else ["claude-3-5-sonnet-20241022"]
    number_of_generations = user_info["number_of_generations"] if "number_of_generations" in user_info else 1

    if not tweets:
        error("No tweets found in cache", status_code=404, function_name="regenerate_single_reply_endpoint", username=username, critical=True)

    # Find the specific tweet
    tweet = None
    for t in tweets:
        if ('id' in t and t['id'] == tweet_id) or ('tweet_id' in t and t['tweet_id'] == tweet_id):
            tweet = t
            break

    if not tweet:
        error("Tweet not found in cache", status_code=404, function_name="regenerate_single_reply_endpoint", username=username, critical=True)

    # Generate replies using the reusable function
    replies = await generate_replies_for_tweet(
        tweet=tweet,
        models=models,
        needed_generations=number_of_generations,
        delay_seconds=0  # No delay for single tweet regeneration
    )

    if not replies:
        error(f"Received no replies for tweet {tweet_id}", status_code=500, function_name="regenerate_single_reply_endpoint", username=username, critical=True)

    # Store all regenerated replies as array of tuples (reply_text, model_name)
    tweet['generated_replies'] = replies
    await write_to_cache([tweet], f"Regenerated {len(replies)} replies for tweet {tweet_id}", username=username)

    return {"message": "Replies regenerated successfully", "tweet_id": tweet_id, "new_replies": replies}


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
