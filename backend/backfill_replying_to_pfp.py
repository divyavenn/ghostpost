"""
Backfill replying_to_pfp field for existing posted tweets from tweets cache.
"""
import json
from pathlib import Path

# Paths
CACHE_DIR = Path("cache")
POSTED_TWEETS_FILE = CACHE_DIR / "divya_venn_posted_tweets.json"
TWEETS_CACHE = CACHE_DIR / "divya_venn_tweets.json"

def main():
    # Read posted tweets
    print(f"📖 Reading posted tweets: {POSTED_TWEETS_FILE}")
    with open(POSTED_TWEETS_FILE, encoding="utf-8") as f:
        posted_tweets = json.load(f)

    print(f"✅ Loaded {len(posted_tweets)} posted tweets")

    # Read tweets cache
    print(f"📖 Reading tweets cache: {TWEETS_CACHE}")
    with open(TWEETS_CACHE, encoding="utf-8") as f:
        cached_tweets = json.load(f)

    # Build handle to profile pic mapping
    handle_to_pfp = {}
    for tweet in cached_tweets:
        handle = tweet.get("handle")
        pfp = tweet.get("author_profile_pic_url")
        if handle and pfp:
            handle_to_pfp[handle] = pfp

    print(f"✅ Found {len(handle_to_pfp)} unique authors in cache")

    # Update posted tweets with profile pics
    updated_count = 0
    for tweet in posted_tweets:
        responding_to = tweet.get("responding_to", "")

        # Add replying_to_pfp field if missing
        if "replying_to_pfp" not in tweet:
            pfp = handle_to_pfp.get(responding_to, "")
            tweet["replying_to_pfp"] = pfp

            if pfp:
                print(f"  ✓ Added pfp for @{responding_to}")
                updated_count += 1
            else:
                print(f"  ⚠️ No pfp found for @{responding_to} (using empty string)")
                updated_count += 1

    # Write back to file
    print(f"\n💾 Writing updated tweets to: {POSTED_TWEETS_FILE}")
    with open(POSTED_TWEETS_FILE, "w", encoding="utf-8") as f:
        json.dump(posted_tweets, f, indent=2, ensure_ascii=False)

    print(f"✅ Updated {updated_count}/{len(posted_tweets)} tweets with replying_to_pfp field")

if __name__ == "__main__":
    main()
