"""
Fetch current performance metrics for all posted tweets from Twitter API.
"""
import json
import sys
from pathlib import Path
from datetime import datetime, timezone
import requests

# Paths
CACHE_DIR = Path("cache")
POSTED_TWEETS_FILE = CACHE_DIR / "divya_venn_posted_tweets.json"
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


def fetch_tweet_metrics(access_token, tweet_ids):
    """Fetch tweet metrics from Twitter API"""
    if not tweet_ids:
        return {}

    # Twitter API v2 endpoint
    url = "https://api.twitter.com/2/tweets"

    # Build query params (max 100 tweets at once)
    params = {
        "ids": ",".join(tweet_ids[:100]),
        "tweet.fields": "public_metrics"
    }

    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    print(f"🌐 Fetching metrics for {len(tweet_ids)} tweets from Twitter API...")

    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)

        if response.status_code != 200:
            print(f"❌ Twitter API error: {response.status_code}")
            print(response.text)
            return {}

        data = response.json()

        # Parse response
        metrics_map = {}

        if "data" in data:
            for tweet in data["data"]:
                tweet_id = tweet["id"]
                public_metrics = tweet.get("public_metrics", {})

                metrics_map[tweet_id] = {
                    "likes": public_metrics.get("like_count", 0),
                    "retweets": public_metrics.get("retweet_count", 0),
                    "quotes": public_metrics.get("quote_count", 0),
                    "replies": public_metrics.get("reply_count", 0)
                }

        print(f"✅ Fetched metrics for {len(metrics_map)} tweets")
        return metrics_map

    except Exception as e:
        print(f"❌ Error fetching from Twitter: {e}")
        return {}


def main():
    # Get access token
    access_token = get_access_token()

    # Read posted tweets
    print(f"📖 Reading posted tweets: {POSTED_TWEETS_FILE}")
    with open(POSTED_TWEETS_FILE, encoding="utf-8") as f:
        posted_tweets = json.load(f)

    print(f"✅ Loaded {len(posted_tweets)} posted tweets")

    # Collect posted tweet IDs
    posted_tweet_ids = [tweet["id"] for tweet in posted_tweets if tweet.get("id")]

    # Fetch metrics from Twitter
    metrics_map = fetch_tweet_metrics(access_token, posted_tweet_ids)

    # Update tweets with metrics
    update_time = datetime.now(timezone.utc).isoformat()
    updated_count = 0

    for tweet in posted_tweets:
        tweet_id = tweet.get("id")
        if tweet_id in metrics_map:
            metrics = metrics_map[tweet_id]
            tweet["likes"] = metrics["likes"]
            tweet["retweets"] = metrics["retweets"]
            tweet["quotes"] = metrics["quotes"]
            tweet["replies"] = metrics["replies"]
            tweet["last_metrics_update"] = update_time
            updated_count += 1

            print(f"  ✓ {tweet_id}: {metrics['likes']}L {metrics['retweets']}RT {metrics['quotes']}Q {metrics['replies']}R")

    # Write back to file
    print(f"\n💾 Writing updated metrics to: {POSTED_TWEETS_FILE}")
    with open(POSTED_TWEETS_FILE, "w", encoding="utf-8") as f:
        json.dump(posted_tweets, f, indent=2, ensure_ascii=False)

    print(f"✅ Updated metrics for {updated_count}/{len(posted_tweets)} tweets")

    # Show summary stats
    total_likes = sum(t["likes"] for t in posted_tweets)
    total_retweets = sum(t["retweets"] for t in posted_tweets)
    total_quotes = sum(t["quotes"] for t in posted_tweets)
    total_replies = sum(t["replies"] for t in posted_tweets)

    print(f"\n📊 Total Performance:")
    print(f"  - Likes: {total_likes}")
    print(f"  - Retweets: {total_retweets}")
    print(f"  - Quotes: {total_quotes}")
    print(f"  - Replies: {total_replies}")

if __name__ == "__main__":
    main()
