"""
Re-classify posted tweets by checking if user is mentioned in the tweet being replied to.

Simple and fast classification logic:
- If response_to_thread contains @{username} → "comment_reply" (someone was replying TO you, you're replying back)
- If responding_to == username → "original" (thread continuation)
- Otherwise → "reply" (replying to someone else's original post)

This doesn't require any API calls!
"""
import json
from pathlib import Path
from typing import Any

# Setup paths
PROJECT_DIR = Path(__file__).resolve().parent.parent
CACHE_DIR = PROJECT_DIR / "backend" / "cache"


def _cache_key(username: str) -> str:
    """Generate cache key for username."""
    key = (username or "default").strip()
    key = key or "default"
    sanitized = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in key)
    return sanitized or "default"


def get_posted_tweets_path(username: str) -> Path:
    """Get path to posted tweets cache."""
    return CACHE_DIR / f"{_cache_key(username)}_posted_tweets.json"


def reclassify_by_mention(username: str, dry_run: bool = False) -> dict[str, Any]:
    """
    Re-classify posted tweets by checking for @mentions.

    Args:
        username: User's handle
        dry_run: If True, show changes without saving

    Returns:
        Migration stats
    """
    cache_path = get_posted_tweets_path(username)

    if not cache_path.exists():
        return {
            "error": f"Posted tweets cache not found: {cache_path}",
            "username": username
        }

    # Read cache
    with open(cache_path, encoding="utf-8") as f:
        data = json.load(f)

    # Get tweet IDs (skip _order)
    tweet_ids = [k for k in data.keys() if k != "_order"]

    # Stats
    stats = {
        "username": username,
        "total_tweets": len(tweet_ids),
        "changed": 0,
        "unchanged": 0,
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

    # Re-classify each tweet
    changed_tweets = []
    username_lower = username.lower()
    mention_pattern = f"@{username}"  # Case-insensitive check

    for tid in tweet_ids:
        tweet = data[tid]
        old_type = tweet.get("post_type", "reply")

        response_to_thread = tweet.get("response_to_thread", [])
        responding_to = tweet.get("responding_to", "")

        # Determine new post type
        if not response_to_thread:
            # No response_to_thread means original post
            new_type = "original"
        elif responding_to.lower() == username_lower:
            # Replying to yourself = thread continuation
            new_type = "original"
        else:
            # Check if any tweet in response_to_thread mentions the user
            thread_text = " | ".join(response_to_thread)

            if mention_pattern.lower() in thread_text.lower():
                # Someone mentioned you, you're replying back = comment-back
                new_type = "comment_reply"
            else:
                # Not mentioned = replying to someone else's original post
                new_type = "reply"

        # Update if changed
        if old_type != new_type:
            stats["changed"] += 1
            stats["changes"][f"to_{new_type}"] += 1

            changed_tweets.append({
                "id": tid,
                "old_type": old_type,
                "new_type": new_type,
                "responding_to": responding_to,
                "has_mention": mention_pattern.lower() in " | ".join(response_to_thread).lower()
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
        print(f"✅ Saved updated cache to {cache_path}")
    elif dry_run:
        print(f"🔍 DRY RUN - No changes saved")

    # Print sample changes
    if changed_tweets:
        print(f"\n📝 Sample changes (showing up to 10):")
        for change in changed_tweets[:10]:
            mention_indicator = "[@you]" if change["has_mention"] else "[original]"
            print(f"  • {change['old_type']:15} → {change['new_type']:15} @{change['responding_to']:20} {mention_indicator}")

    return stats


def main():
    """Run migration."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python migrations/reclassify_by_mention.py <username> [--dry-run]")
        print("Example: python migrations/reclassify_by_mention.py divya_venn")
        print("Example: python migrations/reclassify_by_mention.py divya_venn --dry-run")
        sys.exit(1)

    username = sys.argv[1]
    dry_run = "--dry-run" in sys.argv

    print("=" * 60)
    print("Post Type Re-classification by @Mention Detection")
    print("=" * 60)
    print(f"User: @{username}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print("=" * 60)
    print(f"\nLogic:")
    print(f"  • Tweet mentions @{username} → comment_reply (comment-back)")
    print(f"  • Replying to yourself → original (thread continuation)")
    print(f"  • Otherwise → reply (to someone's original post)")
    print("=" * 60)

    stats = reclassify_by_mention(username, dry_run=dry_run)

    if "error" in stats:
        print(f"\n❌ Error: {stats['error']}")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("Migration Statistics")
    print("=" * 60)
    print(f"Total tweets: {stats['total_tweets']}")
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
    main()
