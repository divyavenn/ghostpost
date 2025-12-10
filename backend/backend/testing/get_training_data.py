import asyncio
import json
from pathlib import Path

try:
    from backend.utlils.resolve_imports import ensure_standalone_imports
except ModuleNotFoundError:
    from backend.utlils.resolve_imports import ensure_standalone_imports

ensure_standalone_imports(globals())

try:
    from ..browser_automation.twitter.timeline import gather_trending
    from ..user.user import read_user_settings
    from ..utlils.utils import error, notify
except ImportError:
    from backend.browser_automation.twitter.timeline import gather_trending
    from backend.user.user import read_user_settings
    from backend.utlils.utils import error, notify

# Constants
BACKEND_DIR = Path(__file__).resolve().parent
CACHE_DIR = BACKEND_DIR / "cache"


async def scrape_tweets_for_training(handle: str,
                                     max_scrolls=3,
                                     output_filename: str | None = None,
                                     limit_accounts: int | None = None,
                                     limit_queries: int | None = None,
                                     max_tweets: int | None = None):
    """
    Scrape tweets using proudlurker's browser state and user info settings.

    Args:
        handle: The handle to lookup in user_info.json
        max_scrolls: Number of scrolls per account/query
        output_filename: Optional custom output filename (without extension)
        limit_accounts: Limit number of accounts to scrape (to avoid rate limits)
        limit_queries: Limit number of queries to scrape (to avoid rate limits)
        max_tweets: Maximum number of tweets to save (None = unlimited, sorted by engagement score)

    Returns:
        Path to the output .jsonl file
    """
    import time

    from backend.utlils.utils import read_user_info, write_user_info

    start_time = time.time()

    notify(f"Loading user info for handle: {handle}")
    user_settings = read_user_settings(handle)

    if not user_settings:
        error(f"No settings found for user {handle}. Please configure settings first.")
        return None

    # Extract relevant accounts and queries using same logic as read_tweets
    relevant_accounts_dict = user_settings.get("relevant_accounts", {})
    relevant_accounts = [acc for acc, validated in relevant_accounts_dict.items() if validated]
    queries = user_settings.get("queries", [])

    # Apply limits to avoid rate limiting
    if limit_accounts and len(relevant_accounts) > limit_accounts:
        notify(f"Limiting accounts from {len(relevant_accounts)} to {limit_accounts}")
        relevant_accounts = relevant_accounts[:limit_accounts]

    if limit_queries and len(queries) > limit_queries:
        notify(f"Limiting queries from {len(queries)} to {limit_queries}")
        queries = queries[:limit_queries]

    notify(f"Found {len(relevant_accounts)} relevant accounts and {len(queries)} queries")

    if not relevant_accounts and not queries:
        notify("No relevant accounts or queries found for this user")
        return None

    # Use gather_trending from read_tweets.py (reuses proudlurker browser state)
    notify("Scraping tweets using proudlurker's session...")
    notify("NOTE: This may take a while and some accounts may timeout if rate limited")

    all_tweets = await gather_trending(relevant_accounts, queries, max_scrolls=max_scrolls)

    notify(f"Total unique tweets collected: {len(all_tweets)}")

    # Sort by engagement score (descending) to get best tweets first
    sorted_tweets = sorted(all_tweets.values(), key=lambda x: x.get("score", 0), reverse=True)

    # Limit number of tweets if specified
    if max_tweets and len(sorted_tweets) > max_tweets:
        notify(f"Limiting tweets from {len(sorted_tweets)} to {max_tweets} (sorted by engagement)")
        sorted_tweets = sorted_tweets[:max_tweets]

    # Format tweets for training data
    training_data = []
    for tweet_data in sorted_tweets:
        # Get scraped_from info (added by gather_trending)
        scraped_from = tweet_data.get("scraped_from", {})
        source_type = scraped_from.get("type", "unknown")  # "account" or "query"
        source_value = scraped_from.get("value", "unknown")  # handle or query text

        formatted_tweet = {
            "thread": tweet_data.get("thread", []),
            "url": tweet_data.get("url", ""),
            "poster": tweet_data.get("handle", "unknown"),
            "likes": tweet_data.get("likes", 0),
            "discovered_via": source_type,  # "account" or "query"
            "discovered_from": source_value,  # handle or query text
            "reply": ""
        }
        training_data.append(formatted_tweet)

    # Save to .jsonl file
    if output_filename is None:
        output_filename = f"training_data_{handle}"

    output_path = CACHE_DIR / f"{output_filename}.jsonl"

    with open(output_path, "w") as f:
        for item in training_data:
            # Format with each key-value pair on its own line for readability
            f.write(json.dumps(item, ensure_ascii=False, indent=2) + "\n")

    notify(f"Saved {len(training_data)} tweets to {output_path}")

    # Update scrolling_time_saved
    elapsed_seconds = int(time.time() - start_time)
    try:
        user_info = read_user_info(handle)
        if user_info:
            current_time_saved = user_info.get("scrolling_time_saved", 0)
            user_info["scrolling_time_saved"] = current_time_saved + elapsed_seconds
            write_user_info(user_info)
            notify(f"⏱️ Added {elapsed_seconds}s to scrolling time for @{handle} (total: {user_info['scrolling_time_saved']}s)")
    except Exception as e:
        notify(f"⚠️ Failed to update scrolling time for {handle}: {e}")

    return output_path


async def main():
    """Example usage."""

    handle = "nakul"

    max_scrolls = 5

    # Limit accounts and queries to avoid rate limiting (57 accounts is too many)
    # Scrape 10 accounts and 5 queries at a time
    limit_accounts = None
    limit_queries = None

    # Optional: limit total tweets (sorted by engagement score)
    max_tweets = None

    await scrape_tweets_for_training(handle, max_scrolls=max_scrolls, limit_accounts=limit_accounts, limit_queries=limit_queries, max_tweets=max_tweets)


if __name__ == "__main__":
    asyncio.run(main())
