"""
Reconstruct divya_venn_posted_tweets.json from logs and cached tweet data.
"""
import json
from pathlib import Path

# Paths
CACHE_DIR = Path("cache")
LOG_FILE = CACHE_DIR / "divya_venn_log.jsonl"
TWEETS_CACHE = CACHE_DIR / "divya_venn_tweets.json"
OUTPUT_FILE = CACHE_DIR / "divya_venn_posted_tweets.json"

def main():
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

    # Load tweet cache to get original tweet data
    print(f"📖 Reading tweets cache: {TWEETS_CACHE}")
    with open(TWEETS_CACHE, encoding="utf-8") as f:
        cached_tweets = json.load(f)

    # Build cache_id index for fast lookup
    tweets_by_cache_id = {}
    for tweet in cached_tweets:
        cache_id = tweet.get("cache_id")
        if cache_id:
            tweets_by_cache_id[cache_id] = tweet

    print(f"✅ Loaded {len(tweets_by_cache_id)} cached tweets")

    # Build posted_tweets array
    posted_tweets = []

    for entry in posted_entries:
        metadata = entry.get("metadata", {})
        cache_id = metadata.get("cache_id")
        posted_tweet_id = metadata.get("posted_tweet_id")
        text = metadata.get("text", "")
        timestamp = entry.get("timestamp")

        # Get original tweet data from cache
        original_tweet = tweets_by_cache_id.get(cache_id, {})

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
            "original_tweet_url": original_tweet.get("url", ""),
            "last_metrics_update": None
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
    print(f"\n📊 Summary:")
    print(f"  - Total posted tweets: {len(posted_tweets)}")
    print(f"  - Oldest: {posted_tweets[-1]['created_at'] if posted_tweets else 'N/A'}")
    print(f"  - Newest: {posted_tweets[0]['created_at'] if posted_tweets else 'N/A'}")

if __name__ == "__main__":
    main()
