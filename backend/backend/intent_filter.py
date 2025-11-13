"""
Intent-based filtering for scraped tweets.

This module provides a two-stage filtering system:
1. Initial filter: Quick check after each tweet is scraped (loose filter)
2. Final filter: Comprehensive check after full thread is collected (strict filter)
"""

import requests
from dotenv import load_dotenv

from backend.config import OBELISK_KEY
from backend.utils import error, notify, read_user_info

# Load environment variables
load_dotenv()


def ask_llm(system_prompt, prompt):
    url = "https://obelisk.dread.technology/api/chat/completions"
    headers = {"Authorization": f"Bearer {OBELISK_KEY}", "Content-Type": "application/json"}

    payload = {
        "model": "chatgpt-4o",
        "messages": [{
            "role": "system",
            "content": system_prompt
        }, {
            "role": "user",
            "content": prompt
        }]
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

        message = data["choices"][0]["message"]["content"]
        return message
    
    except Exception as e:
        error(f"❌ Error extracting keywords from intent: {e}", status_code=500, function_name="extract_keywords_from_intent", critical=False)
        return []


async def check_tweet_matches_intent_initial(tweet_data: dict, username: str) -> bool:
    user_info = read_user_info(username)
    if not user_info:
        # No user info, allow tweet through
        return True

    intent = user_info.get("intent", "")
    if not intent or not intent.strip():
        # No intent set, allow all tweets through
        print("no intent set")
        return True

    tweet_text = tweet_data.get("text", "")
    tweet_handle = tweet_data.get("handle", "")
    tweet_id = tweet_data.get("id", "unknown")

    if not tweet_text:
        # No text to evaluate, reject
        return False

    # Build a quick prompt for initial filtering
    system_prompt = "You are a content relevance evaluator. Answer only YES or NO."
    prompt = f"""User intent: "{intent}"

    Tweet text: "{tweet_text}"
    Tweet author: @{tweet_handle}

    Could this tweet potentially be relevant to the user's intent? Consider:
    - Does it relate to the topics they're interested in?
    - Could it lead to valuable conversations?
    - Is there ANY connection to their stated interests?

    Be lenient - we want to catch potential matches.

    Answer with only "YES" or "NO"."""

    try:
        message = ask_llm(system_prompt, prompt)
        message = message.strip().upper()

        matches = "YES" in message

        if matches:
            notify(f"✅ Tweet {tweet_id} passed initial intent filter")
        else:
            notify(f"❌ Tweet {tweet_id} filtered out by initial intent check")

        return matches

    except Exception as e:
        error(f"⚠️ Error in initial intent filter for tweet {tweet_id}: {e}", status_code=500, function_name="check_tweet_matches_intent_initial", username=username, critical=False)
        # On error, allow tweet through (fail open)
        return True


async def check_tweet_matches_intent_final(tweet_data: dict, username: str) -> bool:
    user_info = read_user_info(username)
    if not user_info:
        # No user info, allow tweet through
        print("no user info")
        return True

    intent = user_info.get("intent", "")
    if not intent or not intent.strip():
        # No intent set, allow all tweets through
        print("no intent set")
        return True

    thread = tweet_data.get("thread", [])
    tweet_handle = tweet_data.get("handle", "")
    tweet_id = tweet_data.get("id", "unknown")

    if not thread or len(thread) == 0:
        # No thread content, reject
        notify(f"❌ Tweet {tweet_id} has no thread, filtering out")
        return False

    # Build full thread text for evaluation
    full_thread = "\n\n".join(thread) if isinstance(thread, list) else str(thread)

    # Include quoted tweet if present
    quoted_tweet = tweet_data.get("quoted_tweet")
    quoted_context = ""
    if quoted_tweet and quoted_tweet.get("text"):
        qt_author = quoted_tweet.get("author_handle", "unknown")
        qt_text = quoted_tweet.get("text", "")
        quoted_context = f"\n\n[This tweet quotes @{qt_author}: \"{qt_text}\"]"

    # Build comprehensive prompt for final filtering
    system_prompt = "You are a strict content relevance evaluator. Answer only YES or NO."
    prompt = f"""User intent: "{intent}"

    Tweet thread by @{tweet_handle}:
    {full_thread}{quoted_context}

    Does this tweet thread clearly match the user's intent? Consider:
    - Is it directly relevant to their stated interests?
    - Would engaging with this tweet help them achieve their goals?
    - Does it provide value aligned with their intent?

    Be strict - only keep tweets that are genuinely relevant.

    Answer with only "YES" or "NO"."""

    try:
        message = ask_llm(system_prompt, prompt)
        message = message.strip().upper()

        matches = "YES" in message

        if matches:
            notify(f"✅ Tweet {tweet_id} passed final intent filter - keeping in cache")
        else:
            notify(f"❌ Tweet {tweet_id} failed final intent filter - will be removed from cache")

        return matches

    except Exception as e:
        error(f"⚠️ Error in final intent filter for tweet {tweet_id}: {e}", status_code=500, function_name="check_tweet_matches_intent_final", username=username, critical=False)
        # On error, allow tweet through (fail open)
        return True


async def remove_tweet_from_cache(tweet_id: str, username: str) -> bool:
    """
    Remove a specific tweet from the user's cache.

    Args:
        tweet_id: ID of tweet to remove
        username: Username whose cache to modify

    Returns:
        True if tweet was removed, False otherwise
    """
    from backend.tweets_cache import read_from_cache, write_to_cache

    try:
        # Read current cache
        tweets = await read_from_cache(username)

        # Filter out the tweet
        filtered_tweets = [t for t in tweets if str(t.get("id")) != str(tweet_id)]

        if len(filtered_tweets) < len(tweets):
            # Tweet was removed, write back to cache
            await write_to_cache(filtered_tweets, f"Removed tweet {tweet_id} (intent filter)", username=username)
            notify(f"🗑️ Removed tweet {tweet_id} from cache (failed intent filter)")
            return True
        else:
            notify(f"⚠️ Tweet {tweet_id} not found in cache to remove")
            return False

    except Exception as e:
        error(f"❌ Error removing tweet {tweet_id} from cache: {e}", status_code=500, function_name="remove_tweet_from_cache", username=username, critical=False)
        return False
