"""
Migration to re-classify post_type for all posted tweets using parent_chain.

This migration fixes the post_type classification for tweets posted before the
conversation_id logic was implemented. It uses the existing parent_chain data
to determine if a reply is to an original post or a comment.

Classification logic:
- If parent_chain is empty → "original" (standalone post)
- If parent_chain[-1] == parent_chain[0] (parent is root):
  - If responding_to == username → "original" (thread continuation)
  - If responding_to != username → "reply" (reply to someone else's original)
- If parent_chain[-1] != parent_chain[0] (parent is not root):
  - "comment_reply" (replying to a comment)
"""
import json
from pathlib import Path
from typing import Any

# Setup paths
# migrations/ is in backend/migrations, so parent is backend/, cache is at backend/cache
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
CACHE_DIR = BACKEND_DIR / "cache"


def _cache_key(username: str) -> str:
    """Generate cache key for username."""
    key = (username or "default").strip()
    key = key or "default"
    sanitized = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in key)
    return sanitized or "default"


def get_posted_tweets_path(username: str) -> Path:
    """Get path to posted tweets cache."""
    return CACHE_DIR / f"{_cache_key(username)}_posted_tweets.json"


def reclassify_post_type(tweet: dict[str, Any], username: str) -> str:
    """
    Re-classify post_type using parent_chain logic.

    Args:
        tweet: Tweet dict with parent_chain and responding_to
        username: The user's handle

    Returns:
        New post_type: "original", "reply", or "comment_reply"
    """
    parent_chain = tweet.get("parent_chain", [])
    responding_to = tweet.get("responding_to", "")

    if len(parent_chain) == 0:
        # No parent - this is an original post
        return "original"

    # Get root and immediate parent
    conversation_root = parent_chain[0]
    immediate_parent = parent_chain[-1]

    if immediate_parent == conversation_root:
        # Replying to the root/original post
        if responding_to.lower() == username.lower():
            return "original"  # Thread continuation (replying to own root)
        else:
            return "reply"  # Reply to someone else's original post
    else:
        # Replying to a comment (not the root)
        return "comment_reply"


def migrate_user_posted_tweets(username: str, dry_run: bool = False) -> dict[str, Any]:
    """
    Migrate posted tweets for a single user.

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

    # Re-classify
    changed_tweets = []
    for tid in tweet_ids:
        tweet = data[tid]
        old_type = tweet.get("post_type", "reply")
        new_type = reclassify_post_type(tweet, username)

        if old_type != new_type:
            stats["changed"] += 1
            stats["changes"][f"to_{new_type}"] += 1

            changed_tweets.append({
                "id": tid,
                "old_type": old_type,
                "new_type": new_type,
                "responding_to": tweet.get("responding_to", ""),
                "parent_chain_length": len(tweet.get("parent_chain", []))
            })

            # Update the tweet
            tweet["post_type"] = new_type
        else:
            stats["unchanged"] += 1

        stats["after"][new_type] += 1

    # Save if not dry run
    if not dry_run:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✅ Saved updated cache to {cache_path}")
    else:
        print(f"🔍 DRY RUN - No changes saved")

    # Print sample changes
    if changed_tweets:
        print(f"\n📝 Sample changes (showing up to 10):")
        for change in changed_tweets[:10]:
            print(f"  • {change['old_type']} → {change['new_type']}: "
                  f"@{change['responding_to']} (parent_chain: {change['parent_chain_length']})")

    return stats


def main():
    """Run migration for all users."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python migrations/reclassify_post_types.py <username> [--dry-run]")
        print("Example: python migrations/reclassify_post_types.py divya_venn")
        print("Example: python migrations/reclassify_post_types.py divya_venn --dry-run")
        sys.exit(1)

    username = sys.argv[1]
    dry_run = "--dry-run" in sys.argv

    print("=" * 60)
    print("Post Type Re-classification Migration")
    print("=" * 60)
    print(f"User: @{username}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print("=" * 60)

    stats = migrate_user_posted_tweets(username, dry_run=dry_run)

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
        print(f"  1. Update intent filter examples by running discover_engagement job")
        print(f"  2. Or manually trigger: python -c \"import sys; sys.path.insert(0, 'backend'); from backend.twitter.monitoring import _update_intent_filter_examples; _update_intent_filter_examples('{username}')\"")
    else:
        print("\n🔍 This was a dry run. Re-run without --dry-run to apply changes.")

    print("=" * 60)


if __name__ == "__main__":
    main()
