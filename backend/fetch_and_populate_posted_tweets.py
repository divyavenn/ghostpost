"""
Reconstruct divya_venn_posted_tweets.json from logs and fetch original tweet data from Twitter API.
"""
import json
import sys
from pathlib import Path

import requests

# Paths
CACHE_DIR = Path("cache")
LOG_FILE = CACHE_DIR / "divya_venn_log.jsonl"
TWEETS_CACHE = CACHE_DIR / "divya_venn_tweets.json"
OUTPUT_FILE = CACHE_DIR / "divya_venn_posted_tweets.json"
TOKEN_FILE = CACHE_DIR / "tokens.json"


def get_access_token():
    """Get access token for divya_venn from tokens.json"""
    if not TOKEN_FILE.exists():
        print(f"❌ Token file not found: {TOKEN_FILE}")
        sys.exit(1)

    with open(TOKEN_FILE, encoding="utf-8") as f:
        tokens = json.load(f)

    divya_token = tokens.get("divya_venn", {}).get("access_token")
    if not divya_token:
        print("❌ No access token found for divya_venn")
        sys.exit(1)

    return divya_token


def fetch_tweets_from_twitter(access_token, tweet_ids):
    """Fetch tweet data from Twitter API"""
    if not tweet_ids:
        return {}

    # Twitter API v2 endpoint
    url = "https://api.twitter.com/2/tweets"

    # Build query params (max 100 tweets at once)
    params = {"ids": ",".join(tweet_ids[:100]), "tweet.fields": "created_at,public_metrics,author_id", "expansions": "author_id", "user.fields": "username"}

    headers = {"Authorization": f"Bearer {access_token}"}

    print(f"🌐 Fetching {len(tweet_ids)} tweets from Twitter API...")

    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)

        if response.status_code != 200:
            print(f"❌ Twitter API error: {response.status_code}")
            print(response.text)
            return {}

        data = response.json()

        # Parse response
        tweets_map = {}
        users_map = {}

        # Build users map
        if "includes" in data and "users" in data["includes"]:
            for user in data["includes"]["users"]:
                users_map[user["id"]] = user["username"]

        # Build tweets map
        if "data" in data:
            for tweet in data["data"]:
                tweet_id = tweet["id"]
                author_id = tweet.get("author_id")
                author_handle = users_map.get(author_id, "")

                tweets_map[tweet_id] = {
                    "text": tweet.get("text", ""),
                    "handle": author_handle,
                    "url": f"https://x.com/{author_handle}/status/{tweet_id}" if author_handle else "",
                    "created_at": tweet.get("created_at", "")
                }

        print(f"✅ Fetched {len(tweets_map)} tweets")
        return tweets_map

    except Exception as e:
        print(f"❌ Error fetching from Twitter: {e}")
        return {}


def main():
    # Get access token
    access_token = get_access_token()

    # Read all posted actions from log
    posted_entries = []

    print(f"📖 Reading log file: {LOG_FILE}")
    with open(LOG_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entry = json.loads(line)
                    if entry.get("action") == "posted":
                        posted_entries.append(entry)
                except json.JSONDecodeError:
                    continue

    print(f"✅ Found {len(posted_entries)} posted tweets")

    # Load tweet cache to get original tweet data (for tweets still in cache)
    tweets_by_cache_id = {}
    if TWEETS_CACHE.exists():
        print(f"📖 Reading tweets cache: {TWEETS_CACHE}")
        with open(TWEETS_CACHE, encoding="utf-8") as f:
            cached_tweets = json.load(f)

        for tweet in cached_tweets:
            cache_id = tweet.get("cache_id")
            if cache_id:
                tweets_by_cache_id[cache_id] = tweet

        print(f"✅ Loaded {len(tweets_by_cache_id)} cached tweets")

    # Collect original tweet IDs to fetch from Twitter
    original_tweet_ids = []
    for entry in posted_entries:
        original_id = entry.get("tweet_id")
        if original_id:
            original_tweet_ids.append(original_id)

    # Fetch original tweets from Twitter
    original_tweets_map = fetch_tweets_from_twitter(access_token, original_tweet_ids)

    # Build posted_tweets array
    posted_tweets = []

    for entry in posted_entries:
        metadata = entry.get("metadata", {})
        cache_id = metadata.get("cache_id")
        posted_tweet_id = metadata.get("posted_tweet_id")
        text = metadata.get("text", "")
        timestamp = entry.get("timestamp")
        original_tweet_id = entry.get("tweet_id")

        # Try to get original tweet data from cache first
        original_tweet = tweets_by_cache_id.get(cache_id, {})

        # If not in cache, try Twitter API data
        if not original_tweet.get("handle") and original_tweet_id:
            twitter_data = original_tweets_map.get(original_tweet_id, {})
            if twitter_data:
                original_tweet = {"thread": [twitter_data.get("text", "")], "handle": twitter_data.get("handle", ""), "url": twitter_data.get("url", "")}

        # Build posted tweet object
        posted_tweet = {
            "id": posted_tweet_id,
            "text": text,
            "likes": 0,
            "retweets": 0,
            "quotes": 0,
            "replies": 0,
            "created_at": timestamp,
            "url": f"https://x.com/divya_venn/status/{posted_tweet_id}",
            "response_to_thread": original_tweet.get("thread", []),
            "responding_to": original_tweet.get("handle", ""),
            "replying_to_pfp": original_tweet.get("author_profile_pic_url", ""),
            "original_tweet_url": original_tweet.get("url", ""),
            "last_metrics_update": timestamp
        }

        posted_tweets.append(posted_tweet)
        print(f"  ✓ {posted_tweet_id} → @{posted_tweet['responding_to']}")

    # Reverse to get newest first
    posted_tweets.reverse()

    # Write to output file
    print(f"\n💾 Writing to: {OUTPUT_FILE}")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(posted_tweets, f, indent=2, ensure_ascii=False)

    print(f"✅ Created {OUTPUT_FILE} with {len(posted_tweets)} tweets")
    print("\n📊 Summary:")
    print(f"  - Total posted tweets: {len(posted_tweets)}")
    print(f"  - With responding_to: {sum(1 for t in posted_tweets if t['responding_to'])}")
    print(f"  - Oldest: {posted_tweets[-1]['created_at'] if posted_tweets else 'N/A'}")
    print(f"  - Newest: {posted_tweets[0]['created_at'] if posted_tweets else 'N/A'}")


if __name__ == "__main__":
    main()
