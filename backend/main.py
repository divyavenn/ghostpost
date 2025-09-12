

from fastapi import FastAPI
import requests
import os

# Put your OBELISK_KEY in an environment variable for safety
OBELISK_KEY = os.getenv("OBELISK_KEY", "sk-9aef8f5c845e4d6aa0cff6d41ff456bb")

app = FastAPI()



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

def generate_replies_for_trending_tweets(json_path='trending_cache.json', overwrite_existing=False, max_tweets=None, delay_seconds=1):
    """
    Read tweets from trending_cache.json, generate a reply for each using ask_model,
    and add the reply to each tweet object.
    
    Args:
        json_path (str): Path to the trending_cache.json file
        overwrite_existing (bool): If True, regenerate replies even if they already exist
        max_tweets (int, optional): Maximum number of tweets to process
        delay_seconds (float): Seconds to wait between API calls to avoid rate limiting
        
    Returns:
        list: Updated list of tweet objects with replies added
    """
    import json
    import os
    import time
    from pathlib import Path
    
    # Determine the correct path to the json file
    if not os.path.isabs(json_path):
        # If it's a relative path, check current directory and one level up
        if os.path.exists(json_path):
            file_path = json_path
        elif os.path.exists(os.path.join('..', json_path)):
            file_path = os.path.join('..', json_path)
        else:
            # Try to find the file in the backend directory
            backend_dir = Path(__file__).parent
            root_dir = backend_dir.parent
            if os.path.exists(os.path.join(backend_dir, json_path)):
                file_path = os.path.join(backend_dir, json_path)
            elif os.path.exists(os.path.join(root_dir, json_path)):
                file_path = os.path.join(root_dir, json_path)
            else:
                raise FileNotFoundError(f"Could not find {json_path}")
    else:
        file_path = json_path
    
    print(f"Reading tweets from: {file_path}")
    
    # Read the trending tweets
    try:
        with open(file_path, 'r') as f:
            tweets = json.load(f)
    except Exception as e:
        print(f"Error reading JSON file: {e}")
        return []
    
    # Limit the number of tweets to process if specified
    if max_tweets is not None and max_tweets > 0:
        tweets_to_process = tweets[:max_tweets]
    else:
        tweets_to_process = tweets
    
    # Process each tweet
    processed_count = 0
    for tweet in tweets_to_process:
        # Skip if reply already exists and we're not overwriting
        if not overwrite_existing and 'reply' in tweet and tweet['reply']:
            print(f"Skipping tweet {tweet.get('id')} as it already has a reply")
            continue
        
        prompt = str(tweet.get('thread', []))
        handle = tweet.get('handle', 'unknown')
        
        
        # Get model's reply with appropriate delay for rate limiting
        try:
            response = ask_model(prompt = prompt)
            print(response)
            reply = response.get('message', '')
            
            # Add the reply to the tweet object
            tweet['reply'] = reply
            print(f"Generated reply for tweet {prompt} by @{handle}: {reply[:50]}...")
            processed_count += 1
            
            # Add delay between requests to avoid rate limiting
            if delay_seconds > 0 and processed_count < len(tweets_to_process):
                time.sleep(delay_seconds)
        except Exception as e:
            print(f"Error generating reply for tweet {tweet.get('id')}: {e}")
            tweet['reply'] = "Error generating reply"
    
    # Save the updated tweets back to the file
    try:
        with open(file_path, 'w') as f:
            json.dump(tweets, f, indent=2)
        print(f"Updated {processed_count} tweets with replies in {file_path}")
    except Exception as e:
        print(f"Error saving updated JSON file: {e}")
    
    return tweets

if __name__ == "__main__":
    # Directly process trending_cache.json with hardcoded parameters
    print("Starting to generate replies for tweets in trending_cache.json...")
    
    # Hardcoded configuration
    json_path = 'trending_cache.json'  # Path relative to the script
    overwrite_existing = True          # Set to True to regenerate all replies
    max_tweets = None                  # Process all tweets
    delay_seconds = 1.0                # 1 second delay between API calls
    
    # Run the reply generation
    tweets = generate_replies_for_trending_tweets(
        json_path=json_path,
        overwrite_existing=overwrite_existing,
        max_tweets=max_tweets,
        delay_seconds=delay_seconds
    )
    
    # Print summary
    print(f"Completed generating replies for {len(tweets)} tweets")
    print("Done!")
    
    # Original example for reference
    # prompt = str([
    #   "i know life happens wherever you are, but I can't help but feel like none of this is real. Like I'm wandering from door to door, temporary home to temporary home. I want to plunge my fingers into earth I own, buy furniture too heavy to move and plant roses",
    #   "I want to walk to the nearby coffeeshop and see familiar faces. I want to take the time to get to know my neighbors, knowing that we'll both be here a few months from now",
    #   "I am so so homesick, but for a home I've never had. I thought i'd have it once. I bought the furniture, met the neighbors. But i chose somewhere I couldn't stay.",
    #   "Everything has been going well for the past few days. Many encouraging signs that I'm getting closer to my goals. and yet I'm miserable and listless. I don't want to put down roots only to dig them up.",
    #   "I don't have the people or the place to put down roots, but I can't help myself. Every room I spend more than two nights in, my mind goes to making it tidier and more cosy. It makes me sad to make those efforts and sadder not to. All I can think of is how I'll have to do it again"
    # ])
    # print(ask_model(prompt))