"""
Re-classify posted tweets using Twitter API to fetch actual conversation_id.

This migration properly classifies tweets by:
1. Fetching the parent tweet's data from Twitter API
2. Checking if parent_tweet_id == conversation_id (reply to root)
3. Updating post_type accordingly

Classification logic:
- If no parent → "original"
- If parent_tweet_id == conversation_id:
  - Replying to yourself → "original" (thread continuation)
  - Replying to others → "reply" (reply to original post)
- If parent_tweet_id != conversation_id → "comment_reply"
"""
import asyncio
import json
from pathlib import Path
from typing import Any

# Setup paths
PROJECT_DIR = Path(__file__).resolve().parent.parent
import sys
sys.path.insert(0, str(PROJECT_DIR / "backend"))

from backend.browser_automation.twitter.api import ensure_access_token, _get_tweet_by_id, DEFAULT_AUTH_USER


def _cache_key(username: str) -> str:
    """Generate cache key for username."""
    key = (username or "default").strip()
    key = key or "default"
    sanitized = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in key)
    return sanitized or "default"


def get_posted_tweets_path(username: str) -> Path:
    """Get path to posted tweets cache."""
    return PROJECT_DIR / "backend" / "cache" / f"{_cache_key(username)}_posted_tweets.json"


async def fetch_conversation_id(access_token: str, tweet_id: str) -> tuple[str | None, str | None]:
    """
    Fetch conversation_id and in_reply_to_user_id for a tweet.

    Returns:
        Tuple of (conversation_id, in_reply_to_user_id)
    """
    try:
        response = await _get_tweet_by_id(access_token, tweet_id)
        data = response.get("data")

        if not data:
            return None, None

        conversation_id = data.get("conversation_id")
        in_reply_to_user_id = data.get("in_reply_to_user_id")

        return conversation_id, in_reply_to_user_id

    except Exception as e:
        print(f"  ⚠️  Error fetching tweet {tweet_id}: {e}")
        return None, None


async def reclassify_with_api(username: str, dry_run: bool = False, max_tweets: int = None) -> dict[str, Any]:
    """
    Re-classify posted tweets using Twitter API.

    Args:
        username: User's handle
        dry_run: If True, show changes without saving
        max_tweets: Max number of tweets to process (None = all)

    Returns:
        Migration stats
    """
    cache_path = get_posted_tweets_path(username)

    if not cache_path.exists():
        return {
            "error": f"Posted tweets cache not found: {cache_path}",
            "username": username
        }

    # Get access token
    print(f"🔑 Getting access token for {DEFAULT_AUTH_USER}...")
    access_token = await ensure_access_token(DEFAULT_AUTH_USER)

    if not access_token:
        return {
            "error": f"No access token available for {DEFAULT_AUTH_USER}",
            "username": username
        }

    # Read cache
    with open(cache_path, encoding="utf-8") as f:
        data = json.load(f)

    # Get tweet IDs (skip _order)
    tweet_ids = [k for k in data.keys() if k != "_order"]

    if max_tweets:
        tweet_ids = tweet_ids[:max_tweets]

    # Stats
    stats = {
        "username": username,
        "total_tweets": len(tweet_ids),
        "processed": 0,
        "changed": 0,
        "unchanged": 0,
        "errors": 0,
        "changes": {
            "to_reply": 0,
            "to_comment_reply": 0,
            "to_original": 0
        },
        "before": {
            "reply": 0,
            "comment_reply": 0,
            "original": 0
        },
        "after": {
            "reply": 0,
            "comment_reply": 0,
            "original": 0
        },
        "dry_run": dry_run
    }

    # Count before
    for tid in tweet_ids:
        tweet = data[tid]
        old_type = tweet.get("post_type", "reply")
        stats["before"][old_type] += 1

    print(f"\n🔍 Processing {len(tweet_ids)} tweets...")

    # Re-classify each tweet
    changed_tweets = []

    for idx, tid in enumerate(tweet_ids, 1):
        tweet = data[tid]
        old_type = tweet.get("post_type", "reply")

        # Get parent chain - last item is immediate parent
        parent_chain = tweet.get("parent_chain", [])

        if len(parent_chain) == 0:
            # No parent - original post
            new_type = "original"
        else:
            # Has a parent - need to check if it's the conversation root
            immediate_parent = parent_chain[-1]

            # Fetch the parent tweet's conversation_id from API
            print(f"  [{idx}/{len(tweet_ids)}] Fetching tweet {immediate_parent}...", end=" ")
            conversation_id, in_reply_to_user_id = await fetch_conversation_id(access_token, immediate_parent)

            if conversation_id is None:
                print("❌ Failed")
                stats["errors"] += 1
                # Keep old classification if API fails
                new_type = old_type
            else:
                print("✓")

                # Check if parent is the conversation root
                if immediate_parent == conversation_id:
                    # Replying to root
                    responding_to = tweet.get("responding_to", "")
                    if responding_to.lower() == username.lower():
                        new_type = "original"  # Thread continuation
                    else:
                        new_type = "reply"  # Reply to someone else's original post
                else:
                    # Replying to a comment (not the root)
                    new_type = "comment_reply"

                stats["processed"] += 1

        # Update if changed
        if old_type != new_type:
            stats["changed"] += 1
            stats["changes"][f"to_{new_type}"] += 1

            changed_tweets.append({
                "id": tid,
                "old_type": old_type,
                "new_type": new_type,
                "responding_to": tweet.get("responding_to", ""),
                "parent_chain_length": len(parent_chain)
            })

            # Update the tweet
            tweet["post_type"] = new_type
        else:
            stats["unchanged"] += 1

        stats["after"][new_type] += 1

    # Save if not dry run
    if not dry_run and stats["changed"] > 0:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"\n✅ Saved updated cache to {cache_path}")
    elif dry_run:
        print(f"\n🔍 DRY RUN - No changes saved")

    # Print sample changes
    if changed_tweets:
        print(f"\n📝 Sample changes (showing up to 10):")
        for change in changed_tweets[:10]:
            print(f"  • {change['old_type']:15} → {change['new_type']:15} @{change['responding_to']}")

    return stats


async def main():
    """Run migration."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python migrations/reclassify_with_api.py <username> [--dry-run] [--limit N]")
        print("Example: python migrations/reclassify_with_api.py divya_venn")
        print("Example: python migrations/reclassify_with_api.py divya_venn --dry-run")
        print("Example: python migrations/reclassify_with_api.py divya_venn --limit 20")
        sys.exit(1)

    username = sys.argv[1]
    dry_run = "--dry-run" in sys.argv

    # Get limit if specified
    max_tweets = None
    if "--limit" in sys.argv:
        try:
            limit_idx = sys.argv.index("--limit")
            max_tweets = int(sys.argv[limit_idx + 1])
        except (IndexError, ValueError):
            print("⚠️  Invalid --limit value")
            sys.exit(1)

    print("=" * 60)
    print("Post Type Re-classification with Twitter API")
    print("=" * 60)
    print(f"User: @{username}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    if max_tweets:
        print(f"Limit: {max_tweets} tweets")
    print("=" * 60)

    stats = await reclassify_with_api(username, dry_run=dry_run, max_tweets=max_tweets)

    if "error" in stats:
        print(f"\n❌ Error: {stats['error']}")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("Migration Statistics")
    print("=" * 60)
    print(f"Total tweets: {stats['total_tweets']}")
    print(f"Processed: {stats['processed']}")
    print(f"Errors: {stats['errors']}")
    print(f"Changed: {stats['changed']}")
    print(f"Unchanged: {stats['unchanged']}")

    print("\n📊 Before:")
    print(f"  Reply: {stats['before']['reply']}")
    print(f"  Comment Reply: {stats['before']['comment_reply']}")
    print(f"  Original: {stats['before']['original']}")

    print("\n📊 After:")
    print(f"  Reply: {stats['after']['reply']}")
    print(f"  Comment Reply: {stats['after']['comment_reply']}")
    print(f"  Original: {stats['after']['original']}")

    print("\n📝 Changes:")
    print(f"  → reply: {stats['changes']['to_reply']}")
    print(f"  → comment_reply: {stats['changes']['to_comment_reply']}")
    print(f"  → original: {stats['changes']['to_original']}")

    if not dry_run:
        print("\n✅ Migration completed successfully!")
        print("\nNext steps:")
        print(f"  Run: python -c \"import sys; sys.path.insert(0, 'backend'); from backend.twitter.monitoring import _update_intent_filter_examples; _update_intent_filter_examples('{username}')\"")
    else:
        print("\n🔍 This was a dry run. Re-run without --dry-run to apply changes.")

    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
