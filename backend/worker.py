"""Background worker to scrape tweets for all users on a schedule."""

import argparse
import asyncio
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

# Handle imports for both package and standalone execution
try:
    from backend.resolve_imports import ensure_standalone_imports
except ModuleNotFoundError:
    from resolve_imports import ensure_standalone_imports

ensure_standalone_imports(globals())

try:
    from .generate_replies import generate_replies
    from .read_tweets import read_tweets
    from .utils import load_user_info_entries, notify, TOKEN_FILE
except ImportError:
    from generate_replies import generate_replies
    from read_tweets import read_tweets
    from utils import load_user_info_entries, notify, TOKEN_FILE


def has_valid_token(username: str) -> bool:
    """Check if user has a valid OAuth token."""
    if not TOKEN_FILE.exists():
        return False
    
    try:
        import json
        tokens = json.loads(TOKEN_FILE.read_text())
        return username in tokens and tokens[username] is not None
    except Exception:
        return False


def should_scrape_user(user_info: dict[str, Any]) -> bool:
    """Determine if user should be scraped based on their settings."""
    handle = user_info.get("handle")
    
    if not handle:
        return False
    
    # Check if user has valid token
    if not has_valid_token(handle):
        notify(f"Skipping {handle}: no valid OAuth token")
        return False
    
    # Check if user has queries or relevant accounts configured
    queries = user_info.get("queries", [])
    relevant_accounts = user_info.get("relevant_accounts", {})
    validated_accounts = [acc for acc, validated in relevant_accounts.items() if validated]
    
    if not queries and not validated_accounts:
        notify(f"Skipping {handle}: no queries or relevant accounts configured")
        return False
    
    return True


async def process_user(username: str) -> dict[str, Any]:
    """Process a single user: scrape tweets and generate replies."""
    result = {
        "username": username,
        "success": False,
        "tweets_scraped": 0,
        "replies_generated": 0,
        "error": None,
        "timestamp": datetime.now(UTC).isoformat()
    }
    
    try:
        notify(f"\n{'='*60}")
        notify(f"Processing user: {username}")
        notify(f"{'='*60}")
        
        # Step 1: Scrape tweets
        notify(f"Scraping tweets for {username}...")
        tweets = await read_tweets(username=username)
        result["tweets_scraped"] = len(tweets) if tweets else 0
        notify(f"Scraped {result['tweets_scraped']} tweets for {username}")
        
        # Step 2: Generate replies
        notify(f"Generating replies for {username}...")
        tweets_with_replies = await generate_replies(username=username)
        result["replies_generated"] = sum(1 for t in tweets_with_replies if t.get('reply'))
        notify(f"Generated {result['replies_generated']} replies for {username}")
        
        result["success"] = True
        notify(f"Successfully processed {username}")
        
    except Exception as e:
        result["error"] = str(e)
        notify(f"Error processing {username}: {e}")
    
    return result


async def run_worker(target_user: str | None = None) -> list[dict[str, Any]]:
    """Run the worker for all users or a specific user."""
    notify(f"Starting worker at {datetime.now(UTC).isoformat()}")
    
    # Load all users
    all_users = load_user_info_entries()
    
    if not all_users:
        notify("No users found in user_info.json")
        return []
    
    # Filter to target user if specified
    if target_user:
        all_users = [u for u in all_users if u.get("handle") == target_user]
        if not all_users:
            notify(f"User '{target_user}' not found in user_info.json")
            return []
        notify(f"Running for single user: {target_user}")
    else:
        notify(f"Found {len(all_users)} total users")
    
    # Filter to users that should be scraped
    users_to_process = [u for u in all_users if should_scrape_user(u)]
    
    if not users_to_process:
        notify("No users to process (all skipped)")
        return []
    
    notify(f"Processing {len(users_to_process)} users")
    
    # Process each user sequentially
    results = []
    for user_info in users_to_process:
        username = user_info.get("handle")
        result = await process_user(username)
        results.append(result)
    
    # Print summary
    notify(f"\n{'='*60}")
    notify("WORKER RUN SUMMARY")
    notify(f"{'='*60}")
    
    success_count = sum(1 for r in results if r["success"])
    error_count = len(results) - success_count
    total_tweets = sum(r["tweets_scraped"] for r in results)
    total_replies = sum(r["replies_generated"] for r in results)
    
    notify(f"Successful: {success_count}/{len(results)}")
    notify(f"Failed: {error_count}/{len(results)}")
    notify(f"Total tweets scraped: {total_tweets}")
    notify(f"Total replies generated: {total_replies}")
    
    if error_count > 0:
        notify(f"\nErrors:")
        for r in results:
            if not r["success"]:
                notify(f"  - {r['username']}: {r['error']}")
    
    notify(f"\nWorker completed at {datetime.now(UTC).isoformat()}")
    
    return results


async def main():
    """Main entry point with CLI argument parsing."""
    parser = argparse.ArgumentParser(
        description="Background worker to scrape tweets and generate replies for all users."
    )
    parser.add_argument(
        "--user",
        type=str,
        help="Process only a specific user (by handle)"
    )
    
    args = parser.parse_args()
    
    await run_worker(target_user=args.user)


if __name__ == "__main__":
    asyncio.run(main())