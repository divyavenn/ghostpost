

import asyncio
from fastapi import FastAPI
import requests
import os
from read_tweets import read_tweets
from utils import notify, error 

# Put your OBELISK_KEY in an environment variable for safety
OBELISK_KEY = os.getenv("OBELISK_KEY", "sk-9aef8f5c845e4d6aa0cff6d41ff456bb")

app = FastAPI(title="FloodMe API")



@app.post("/comment")
def ask_model(prompt: str, system_message: str = None):
    """
    Generate a reply to a tweet or thread using the Obelisk API.
    
    Args:
        prompt (str): The tweet content to respond to
        system_message (str, optional): Custom system message. If None, default is used.
        
    Returns:
        dict: Response containing the generated message or error
    """
    url = "https://obelisk.dread.technology/api/chat/completions"

    headers = {
        "Authorization": f"Bearer {OBELISK_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "divya-2-bon",
        "messages": [ 
          {"role": "system", "content": "you are scrolling twitter. Casually respond to this thread in two to three lines as a stranger"},
          {"role": "user", "content": prompt}
        ]
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

async def generate_replies(delay_seconds=1, overwrite = False):
    from read_tweets import write_to_cache
    import time
    from read_tweets import read_from_cache
    
    tweets = await read_from_cache()
    
    for tweet in tweets:
        # Skip if reply already exists and we're not overwriting
        if 'reply' in tweet and tweet['reply'] and not overwrite:
            continue
        
        prompt = str(tweet.get('thread', []))
        handle = tweet.get('handle', 'unknown')
        # Get model's reply with appropriate delay for rate limiting
        try:
            response = ask_model(prompt = prompt)
            reply = response.get('message', '')
            
            # Add the reply to the tweet object
            tweet['reply'] = reply
            notify(f"Generated reply for tweet {prompt} by @{handle}: {reply[:50]}...")
            
            time.sleep(delay_seconds)
            
        except Exception as e:
            error(f"Error generating reply for tweet {tweet.get('id')}: {e}")
            tweet['reply'] = "Error generating reply"
    
    # Save the updated tweets back to the file
    await write_to_cache(tweets, "Generated replies for tweets")
    
    return tweets

async def run_all() -> None:
    # Directly process trending_cache.json with hardcoded parameters
    await read_tweets()
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
