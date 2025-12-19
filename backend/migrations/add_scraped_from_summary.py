"""
Migration to add summary field to scraped_from for query-type sources.

This migration fixes tweets scraped before the summary field was added to the
Source model. For query-type sources without a summary, it sets the summary
to the query value itself as a fallback.

This ensures the frontend can display user-friendly labels instead of showing
the full raw query string.
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


def get_tweet_cache_path(username: str) -> Path:
    """Get path to tweet cache."""
    return CACHE_DIR / f"{_cache_key(username)}_tweets.json"


def migrate_tweet_scraped_from(tweet: dict[str, Any]) -> bool:
    """
    Add summary field to scraped_from if it's a query without one.

    Args:
        tweet: Tweet dict with scraped_from

    Returns:
        True if modified, False otherwise
    """
    scraped_from = tweet.get("scraped_from")

    # Skip if no scraped_from
    if not scraped_from:
        return False

    # Skip if not a query type
    if scraped_from.get("type") != "query":
        return False

    # Skip if summary already exists and is not None
    if "summary" in scraped_from and scraped_from["summary"] is not None:
        return False

    # Add summary field - use the query value as fallback
    query_value = scraped_from.get("value", "Custom Query")
    scraped_from["summary"] = query_value

    return True


def migrate_user_tweets(username: str, dry_run: bool = False) -> dict[str, Any]:
    """
    Migrate tweets for a single user.

    Args:
        username: User's handle
        dry_run: If True, show changes without saving

    Returns:
        Migration stats
    """
    cache_path = get_tweet_cache_path(username)

    if not cache_path.exists():
        return {
            "error": f"Tweet cache not found: {cache_path}",
            "username": username
        }

    # Read cache
    with open(cache_path, encoding="utf-8") as f:
        tweets = json.load(f)

    # Stats
    stats = {
        "username": username,
        "total_tweets": len(tweets),
        "modified": 0,
        "query_sources": 0,
        "account_sources": 0,
        "home_timeline_sources": 0,
        "no_scraped_from": 0,
        "dry_run": dry_run
    }

    # Process each tweet
    modified_tweets = []
    for tweet in tweets:
        scraped_from = tweet.get("scraped_from")

        if not scraped_from:
            stats["no_scraped_from"] += 1
            continue

        source_type = scraped_from.get("type")
        if source_type == "query":
            stats["query_sources"] += 1
        elif source_type == "account":
            stats["account_sources"] += 1
        elif source_type == "home_timeline":
            stats["home_timeline_sources"] += 1

        # Try to migrate
        if migrate_tweet_scraped_from(tweet):
            stats["modified"] += 1
            modified_tweets.append({
                "id": tweet.get("id", "unknown"),
                "query": scraped_from.get("value", ""),
                "added_summary": scraped_from.get("summary", "")
            })

    # Save if not dry run
    if not dry_run and stats["modified"] > 0:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(tweets, f, ensure_ascii=False, indent=2)
        print(f"✅ Saved updated cache to {cache_path}")
    elif stats["modified"] == 0:
        print(f"✅ No tweets needed migration")
    else:
        print(f"🔍 DRY RUN - No changes saved")

    # Print sample changes
    if modified_tweets:
        print(f"\n📝 Modified tweets (showing up to 10):")
        for change in modified_tweets[:10]:
            print(f"  • Tweet {change['id']}: added summary for query")
            # Truncate query/summary to 50 chars for readability
            query_preview = change['query'][:50] + "..." if len(change['query']) > 50 else change['query']
            summary_preview = change['added_summary'][:50] + "..." if len(change['added_summary']) > 50 else change['added_summary']
            print(f"    Query: {query_preview}")
            print(f"    Summary: {summary_preview}")

    return stats


def main():
    """Run migration for a user."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python migrations/add_scraped_from_summary.py <username> [--dry-run]")
        print("Example: python migrations/add_scraped_from_summary.py proudlurker")
        print("Example: python migrations/add_scraped_from_summary.py proudlurker --dry-run")
        sys.exit(1)

    username = sys.argv[1]
    dry_run = "--dry-run" in sys.argv

    print("=" * 60)
    print("Scraped From Summary Migration")
    print("=" * 60)
    print(f"User: @{username}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print("=" * 60)

    stats = migrate_user_tweets(username, dry_run=dry_run)

    if "error" in stats:
        print(f"\n❌ Error: {stats['error']}")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("Migration Statistics")
    print("=" * 60)
    print(f"Total tweets: {stats['total_tweets']}")
    print(f"Modified: {stats['modified']}")
    print(f"No changes needed: {stats['total_tweets'] - stats['modified']}")

    print("\n📊 Source Type Breakdown:")
    print(f"  Query sources: {stats['query_sources']}")
    print(f"  Account sources: {stats['account_sources']}")
    print(f"  Home timeline sources: {stats['home_timeline_sources']}")
    print(f"  No scraped_from: {stats['no_scraped_from']}")

    if not dry_run and stats['modified'] > 0:
        print("\n✅ Migration completed successfully!")
    elif stats['modified'] == 0:
        print("\n✅ All tweets already have summaries - no migration needed!")
    else:
        print("\n🔍 This was a dry run. Re-run without --dry-run to apply changes.")

    print("=" * 60)


if __name__ == "__main__":
    main()
