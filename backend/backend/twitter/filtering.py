"""
Intent-based filtering for scraped tweets.

This module provides a two-stage filtering system:
1. Initial filter: Quick check after each tweet is scraped (loose filter)
2. Final filter: Comprehensive check after full thread is collected (strict filter)
"""

from dotenv import load_dotenv

from backend.config import OBELISK_KEY
from backend.twitter.logging import TweetAction, read_user_log
from backend.utlils.utils import error, notify, read_user_info

# Load environment variables
load_dotenv()


def get_recent_reply_examples(username: str, limit: int = 5) -> tuple[list[dict], list[dict]]:
    """
    Get examples of recent posts the user replied to and posts they skipped.

    Args:
        username: User's cache key
        limit: Max number of examples for each category

    Returns:
        Tuple of (replied_to_examples, skipped_examples)
    """
    log_entries = read_user_log(username)

    replied_to = []
    skipped = []

    for entry in reversed(log_entries):  # Most recent first
        action = entry.get("action")
        metadata = entry.get("metadata", {})

        if action == TweetAction.POSTED.value and len(replied_to) < limit:
            # This is a post the user replied to
            original_tweet = metadata.get("original_tweet_text", "")
            original_handle = metadata.get("original_handle", "")
            if original_tweet:
                replied_to.append({
                    "author": original_handle,
                    "text": original_tweet[:500],  # Truncate long tweets
                })

        elif action == TweetAction.DELETED.value and len(skipped) < limit:
            # This is a post the user skipped (deleted from cache)
            original_tweet = metadata.get("original_tweet_text", "")
            original_handle = metadata.get("original_handle", "")
            if original_tweet:
                skipped.append({
                    "author": original_handle,
                    "text": original_tweet[:500],
                })

        # Stop once we have enough examples
        if len(replied_to) >= limit and len(skipped) >= limit:
            break

    return replied_to, skipped


def build_examples_context(replied_to: list[dict], skipped: list[dict]) -> str:
    """
    Build a formatted string of examples for the LLM prompt.
    """
    if not replied_to and not skipped:
        return ""

    context = "\n\n[RECENT HISTORY - Examples of what the user has replied to vs skipped]\n"

    if replied_to:
        context += "\n--- TWEETS THE USER REPLIED TO ---\n"
        for i, example in enumerate(replied_to, 1):
            author = example.get("author", "unknown")
            text = example.get("text", "")
            context += f"\n{i}. @{author}: {text}\n"

    if skipped:
        context += "\n--- TWEETS THE USER SKIPPED ---\n"
        for i, example in enumerate(skipped, 1):
            author = example.get("author", "unknown")
            text = example.get("text", "")
            context += f"\n{i}. @{author}: {text}\n"

    context += "\n[END HISTORY]\n"

    return context


def _print_prompt(system_prompt: str, user_prompt: str, model: str, tweet_id: str = "unknown"):
    """Print the full prompt to console for debugging (only if DEBUG_LOGS is enabled)."""
    from backend.utlils.utils import DEBUG_LOGS
    if not DEBUG_LOGS:
        return

    print(f"\n{'='*80}")
    print(f"🔍 INTENT FILTER PROMPT | Model: {model} | Tweet: {tweet_id}")
    print(f"{'='*80}")
    print(f"\n📋 SYSTEM PROMPT:\n{'-'*40}")
    print(system_prompt)
    print(f"\n📝 USER PROMPT:\n{'-'*40}")
    print(user_prompt)
    print(f"\n{'='*80}\n")


async def ask_llm(system_prompt, prompt, tweet_id: str = "unknown", username: str = "unknown"):
    from backend.twitter.rate_limiter import LLM_OBELISK, call_api

    url = "https://obelisk.dread.technology/api/chat/completions"
    headers = {"Authorization": f"Bearer {OBELISK_KEY}", "Content-Type": "application/json"}

    model = "chatgpt-4o"
    payload = {"model": model, "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}]}

    # Print the full prompt to console
    _print_prompt(system_prompt, prompt, model, tweet_id)

    # Use rate limiter with retry
    response = await call_api(
        method="POST",
        url=url,
        bucket=LLM_OBELISK,
        headers=headers,
        json_data=payload,
        username=username
    )

    if not response.success:
        error(f"❌ Error in LLM call for intent filter: {response.error_message}", status_code=response.status_code or 500, function_name="ask_llm", critical=False)
        return ""

    data = response.data

    try:
        message = data["choices"][0]["message"]["content"]
        return message
    except (KeyError, IndexError):
        return ""


def get_intent_filter_examples(username: str, limit: int = 5) -> list[dict]:
    """
    Get examples of original posts the user has replied to.

    Reads from user_info.intent_filter_examples which is updated by:
    - discover_engagement job (uses top-performing replies sorted by engagement)
    - posting.py fallback (adds examples when posting replies)

    Args:
        username: User's handle
        limit: Max number of examples

    Returns:
        List of {"author": handle, "text": original_post_text}
    """
    try:
        user_info = read_user_info(username)
        if user_info:
            return user_info.get("intent_filter_examples", [])[:limit]
        return []
    except Exception:
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

    # Get examples from top-performing replies (sorted by engagement score)
    examples = get_intent_filter_examples(username, limit=5)
    examples_context = ""
    if examples:
        examples_context = "\n\n[EXAMPLES OF POSTS THE USER HAS REPLIED TO (sorted by engagement)]\n"
        for i, ex in enumerate(examples, 1):
            author = ex.get("author", "unknown")
            text = ex.get("text", "")
            examples_context += f"{i}. @{author}: {text}\n"
        examples_context += "[END EXAMPLES]\n"

    # Build a quick prompt for initial filtering
    system_prompt = "You are a content relevance evaluator. Answer only YES or NO."
    prompt = f"""User intent: "{intent}"
{examples_context}
    Tweet text: "{tweet_text}"
    Tweet author: @{tweet_handle}

    Could this tweet potentially be relevant to the user's intent? Consider:
    - Does it relate to the topics they're interested in?
    - Could it lead to valuable conversations?
    - Is there any connection to their stated interests?
    - Is it similar to the examples of posts they've replied to before?

    Answer with only "YES" or "NO"."""

    try:
        message = await ask_llm(system_prompt, prompt, tweet_id=str(tweet_id), username=username)
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



async def remove_tweet_from_cache(tweet_id: str, username: str) -> bool:
    """
    Remove a specific tweet from the user's cache.

    Args:
        tweet_id: ID of tweet to remove
        username: Username whose cache to modify

    Returns:
        True if tweet was removed, False otherwise
    """
    from backend.data.twitter.edit_cache import read_from_cache, write_to_cache

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
