#!/usr/bin/env python3
"""
Script to analyze background scraper statistics for a user.

Usage:
    python scraper_stats.py <username>
    python scraper_stats.py <username> --detailed
"""

import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

try:  # Python 3.11+
    from datetime import UTC  # type: ignore[attr-defined]
except ImportError:  # Python <3.11
    UTC = UTC


def get_cache_key(username: str) -> str:
    """Generate cache key from username (same logic as backend.utils._cache_key)."""
    key = username.strip()
    key = key or "default"
    sanitized = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in key)
    return sanitized or "default"


def get_user_log_path(username: str) -> Path:
    """Get the path to user's log file."""
    cache_dir = Path(__file__).parent / "cache"
    return cache_dir / f"{get_cache_key(username)}_log.jsonl"


def parse_timestamp(ts_str: str) -> datetime:
    """Parse ISO timestamp string."""
    return datetime.fromisoformat(ts_str.replace('Z', '+00:00'))


def analyze_scraper_runs(username: str, detailed: bool = False):
    """Analyze scraper runs for a user."""
    log_path = get_user_log_path(username)

    if not log_path.exists():
        print(f"❌ No log file found for user: {username}")
        print(f"   Expected path: {log_path}")
        return

    # Read all log entries
    scrape_entries = []
    try:
        with open(log_path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entry = json.loads(line)
                        if entry.get('action') == 'scraped':
                            scrape_entries.append(entry)
                    except json.JSONDecodeError:
                        continue
    except Exception as e:
        print(f"❌ Error reading log file: {e}")
        return

    if not scrape_entries:
        print(f"📊 No scraper runs found for user: {username}")
        return

    # Analyze statistics
    total_runs = len(scrape_entries)
    auto_runs = [e for e in scrape_entries if e.get('initiated_by') == 'auto']
    user_runs = [e for e in scrape_entries if e.get('initiated_by') == 'user']

    total_tweets_scraped = sum(e.get('number_of_tweets_written', 0) for e in scrape_entries)
    auto_tweets_scraped = sum(e.get('number_of_tweets_written', 0) for e in auto_runs)
    user_tweets_scraped = sum(e.get('number_of_tweets_written', 0) for e in user_runs)

    # Get time range
    timestamps = [parse_timestamp(e['timestamp']) for e in scrape_entries]
    first_run = min(timestamps)
    last_run = max(timestamps)

    # Calculate daily breakdown
    daily_stats = defaultdict(lambda: {'auto': 0, 'user': 0, 'tweets': 0})
    for entry in scrape_entries:
        ts = parse_timestamp(entry['timestamp'])
        date_key = ts.strftime('%Y-%m-%d')
        initiated_by = entry.get('initiated_by', 'user')
        daily_stats[date_key][initiated_by] += 1
        daily_stats[date_key]['tweets'] += entry.get('number_of_tweets_written', 0)

    # Print summary
    print(f"\n{'='*60}")
    print(f"📊 SCRAPER STATISTICS FOR: {username}")
    print(f"{'='*60}\n")

    print("📅 Time Range:")
    print(f"   First run:  {first_run.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"   Last run:   {last_run.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"   Duration:   {(last_run - first_run).days} days\n")

    print(f"🔄 Total Scraper Runs: {total_runs}")
    print(f"   🤖 Background (auto):  {len(auto_runs)} runs ({len(auto_runs)/total_runs*100:.1f}%)")
    print(f"   👤 Manual (user):      {len(user_runs)} runs ({len(user_runs)/total_runs*100:.1f}%)\n")

    print(f"📝 Total Tweets Scraped: {total_tweets_scraped:,}")
    print(f"   🤖 From background:    {auto_tweets_scraped:,} tweets ({auto_tweets_scraped/total_tweets_scraped*100:.1f}%)")
    print(f"   👤 From manual:        {user_tweets_scraped:,} tweets ({user_tweets_scraped/total_tweets_scraped*100:.1f}%)\n")

    if total_runs > 0:
        avg_tweets_per_run = total_tweets_scraped / total_runs
        print(f"📊 Average: {avg_tweets_per_run:.1f} tweets per run\n")

    # Detailed breakdown
    if detailed:
        print(f"{'='*60}")
        print("📆 DAILY BREAKDOWN")
        print(f"{'='*60}\n")

        sorted_dates = sorted(daily_stats.keys())
        for date in sorted_dates:
            stats = daily_stats[date]
            total_day = stats['auto'] + stats['user']
            print(f"{date}:")
            print(f"   Runs: {total_day} (🤖 {stats['auto']}, 👤 {stats['user']})")
            print(f"   Tweets: {stats['tweets']}")
            print()

        print(f"{'='*60}")
        print("📝 RECENT RUNS (Last 10)")
        print(f"{'='*60}\n")

        recent_entries = sorted(scrape_entries, key=lambda e: e['timestamp'], reverse=True)[:10]
        for i, entry in enumerate(recent_entries, 1):
            ts = parse_timestamp(entry['timestamp'])
            initiated_by = entry.get('initiated_by', 'user')
            tweets = entry.get('number_of_tweets_written', 0)
            icon = '🤖' if initiated_by == 'auto' else '👤'

            print(f"{i}. {ts.strftime('%Y-%m-%d %H:%M:%S')} - {icon} {initiated_by}")
            print(f"   Tweets: {tweets}")
            print()

    print(f"{'='*60}\n")


def main():
    if len(sys.argv) < 2:
        print("Usage: python scraper_stats.py <username> [--detailed]")
        print("\nExample:")
        print("  python scraper_stats.py divya_venn")
        print("  python scraper_stats.py divya_venn --detailed")
        sys.exit(1)

    username = sys.argv[1]
    detailed = '--detailed' in sys.argv or '-d' in sys.argv

    analyze_scraper_runs(username, detailed)


if __name__ == "__main__":
    main()
