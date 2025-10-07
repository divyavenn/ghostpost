import asyncio
import os

import requests

from .read_tweets import USERNAME
from .utils import error, notify

try:
    from backend.resolve_imports import ensure_standalone_imports
except ModuleNotFoundError:  # Running from inside backend/
    from resolve_imports import ensure_standalone_imports

ensure_standalone_imports(globals())

# Put your OBELISK_KEY in an environment variable for safety
OBELISK_KEY = os.getenv("OBELISK_KEY")


def ask_model(prompt: str, model: str = "divya-2-bon"):
    url = "https://obelisk.dread.technology/api/chat/completions"

    headers = {"Authorization": f"Bearer {OBELISK_KEY}", "Content-Type": "application/json"}

    payload = {
        "model": model,
        "messages": [{
            "role": "system",
            "content": "you are scrolling twitter. Casually respond to this thread in two to three lines as a stranger"
        }, {
            "role": "user",
            "content": prompt
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

    from utils import read_from_cache, write_to_cache

    tweets = await read_from_cache(username=username)
    count = 0
    for tweet in tweets:
        # Skip if reply already exists and we're not overwriting
        if "reply" in tweet and tweet["reply"] and not overwrite:
            continue

        prompt = str(tweet.get('thread', []))
        tweet.get('handle', 'unknown')
        # Get model's reply with appropriate delay for rate limiting
        try:
            response = ask_model(prompt=prompt)
            reply = response.get('message', '')
            count += 1
            # Add the reply to the tweet object
            tweet['reply'] = reply

            time.sleep(delay_seconds)

        except Exception as e:
            error(f"Error generating reply for tweet {tweet.get('id')}: {e}")
            tweet['reply'] = "Error generating reply"

    # Save the updated tweets back to the file
    await write_to_cache(tweets, f"Generated replies for {count} tweets", username=username)

    return tweets


async def run_all() -> None:
    # Directly process trending_cache.json with hardcoded parameters
    #await read_tweets()
    await generate_replies()

    notify("Done!")


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
