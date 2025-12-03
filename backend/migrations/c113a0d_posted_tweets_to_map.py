"""
Migration: c113a0d - Convert posted_tweets from array to map format

This migration converts all *_posted_tweets.json files from the old array format:
    [{...}, {...}, ...]

To the new map format with _order array for efficient pagination:
    {
        "_order": ["id3", "id2", "id1"],  // newest first
        "id1": { tweet data },
        "id2": { tweet data },
        ...
    }

Also adds new fields required for engagement monitoring:
    - parent_chain: []
    - source: "app_posted"
    - monitoring_state: "active"|"warm"|"cold"
    - last_activity_at
    - last_deep_scrape
    - last_shallow_scrape
    - last_reply_count
    - last_like_count
    - last_quote_count
    - last_retweet_count
    - resurrected_via: "none"
    - last_scraped_reply_ids: []

Usage:
    python -m migrations.c113a0d_posted_tweets_to_map [--dry-run]
"""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Resolve paths
MIGRATIONS_DIR = Path(__file__).parent
BACKEND_DIR = MIGRATIONS_DIR.parent
CACHE_DIR = BACKEND_DIR / "cache"

# Config constants (duplicated to avoid import issues during migration)
HARDCUTOFF_COLD_DAYS = 7

try:  # Python 3.11+
    from datetime import UTC
except ImportError:
    from datetime import timezone
    UTC = timezone.utc


def is_older_than_days(created_at: str, days: int) -> bool:
    """Check if a tweet is older than the specified number of days."""
    try:
        if "T" in created_at:
            dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        else:
            # Twitter format: "Sun Nov 30 14:26:48 +0000 2025"
            dt = datetime.strptime(created_at, "%a %b %d %H:%M:%S %z %Y")

        now = datetime.now(UTC)
        return (now - dt) > timedelta(days=days)
    except Exception:
        return False


def migrate_file(file_path: Path, dry_run: bool = False) -> dict:
    """
    Migrate a single posted_tweets file from array to map format.

    Returns:
        dict with keys: migrated (bool), tweets_count (int), error (str|None)
    """
    result = {"migrated": False, "tweets_count": 0, "error": None, "already_migrated": False}

    try:
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        result["error"] = f"Failed to read file: {e}"
        return result

    # Check if already migrated
    if isinstance(data, dict) and "_order" in data:
        result["already_migrated"] = True
        result["tweets_count"] = len(data) - 1  # Exclude _order key
        return result

    # Must be an array to migrate
    if not isinstance(data, list):
        result["error"] = f"Invalid format: expected array or map with _order, got {type(data).__name__}"
        return result

    # Build new map structure
    new_data: dict = {"_order": []}

    # Sort by created_at descending for order
    try:
        data.sort(key=lambda t: t.get("created_at", ""), reverse=True)
    except Exception:
        pass

    for tweet in data:
        if not isinstance(tweet, dict):
            continue

        tweet_id = tweet.get("id")
        if not tweet_id:
            continue

        # Add default values for new monitoring fields
        tweet.setdefault("parent_chain", [])
        tweet.setdefault("source", "app_posted")
        tweet.setdefault("monitoring_state",
                        "cold" if is_older_than_days(tweet.get("created_at", ""), HARDCUTOFF_COLD_DAYS) else "active")
        tweet.setdefault("last_activity_at", tweet.get("created_at"))
        tweet.setdefault("last_deep_scrape", None)
        tweet.setdefault("last_shallow_scrape", None)
        tweet.setdefault("last_reply_count", tweet.get("replies", 0))
        tweet.setdefault("last_like_count", tweet.get("likes", 0))
        tweet.setdefault("last_quote_count", tweet.get("quotes", 0))
        tweet.setdefault("last_retweet_count", tweet.get("retweets", 0))
        tweet.setdefault("resurrected_via", "none")
        tweet.setdefault("last_scraped_reply_ids", [])

        new_data[tweet_id] = tweet
        new_data["_order"].append(tweet_id)

    result["tweets_count"] = len(new_data) - 1  # Exclude _order key

    if dry_run:
        result["migrated"] = True
        return result

    # Write migrated data
    try:
        # Create backup
        backup_path = file_path.with_suffix(".json.bak")
        with open(backup_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        # Write new format
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(new_data, f, indent=2, ensure_ascii=False)

        result["migrated"] = True
    except Exception as e:
        result["error"] = f"Failed to write file: {e}"

    return result


def run_migration(dry_run: bool = False) -> int:
    """
    Run migration on all posted_tweets files.

    Returns:
        Exit code (0 = success, 1 = errors)
    """
    print(f"Migration: c113a0d - Convert posted_tweets from array to map format")
    print(f"Cache directory: {CACHE_DIR}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print("-" * 60)

    if not CACHE_DIR.exists():
        print(f"Cache directory does not exist: {CACHE_DIR}")
        return 1

    # Find all posted_tweets files
    files = list(CACHE_DIR.glob("*_posted_tweets.json"))

    if not files:
        print("No posted_tweets files found.")
        return 0

    print(f"Found {len(files)} posted_tweets file(s)\n")

    errors = 0
    migrated = 0
    skipped = 0

    for file_path in files:
        print(f"Processing: {file_path.name}")
        result = migrate_file(file_path, dry_run)

        if result["error"]:
            print(f"  ERROR: {result['error']}")
            errors += 1
        elif result["already_migrated"]:
            print(f"  Already migrated ({result['tweets_count']} tweets)")
            skipped += 1
        elif result["migrated"]:
            print(f"  {'Would migrate' if dry_run else 'Migrated'}: {result['tweets_count']} tweets")
            migrated += 1

    print("-" * 60)
    print(f"Summary: {migrated} migrated, {skipped} skipped, {errors} errors")

    return 1 if errors > 0 else 0


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    exit_code = run_migration(dry_run)
    sys.exit(exit_code)
