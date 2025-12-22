"""
Migration script to import data from local JSON cache files to Supabase.

This script reads from the cache directory and populates the Supabase database.
Run this once to migrate existing data.

Usage:
    cd backend
    python -m migrations.import_cache_to_supabase
"""
import json
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.config import CACHE_DIR
from backend.utlils.supabase_client import get_db

# Fields to remove from posted tweets (deprecated)
DEPRECATED_TWEET_FIELDS = {
    "last_deep_scrape",
    "last_shallow_scrape",
    "last_reply_count",
    "last_quote_count",
    "last_like_count",
    "last_retweet_count",
}

# Fields to remove from comments (deprecated)
DEPRECATED_COMMENT_FIELDS = {
    "last_deep_scrape",
    "last_shallow_scrape",
    "last_reply_count",
    "last_quote_count",
    "last_like_count",
    "last_retweet_count",
}


def migrate_users_and_profiles():
    """Migrate user_info.json to users and twitter_profiles tables."""
    print("\n=== Migrating Users and Twitter Profiles ===")

    user_info_file = CACHE_DIR / "user_info.json"
    if not user_info_file.exists():
        print(f"  No user_info.json found at {user_info_file}")
        return {}

    with open(user_info_file, encoding="utf-8") as f:
        users_data = json.load(f)

    db = get_db()
    handle_to_user_id = {}

    for user in users_data:
        handle = user.get("handle")
        if not handle:
            print(f"  Skipping user without handle: {user}")
            continue

        # Skip test users
        if "test" in handle.lower() or handle == "debug_user":
            print(f"  Skipping test user: {handle}")
            continue

        print(f"  Processing user: {handle}")

        # Create user record
        user_data = {
            "email": user.get("email"),
            "account_type": user.get("account_type", "trial"),
            "models": user.get("models", []),
            "knowledge_base": user.get("knowledge_base"),
            "intent": user.get("intent", ""),
        }

        try:
            # Check if user exists by email
            existing_user = None
            if user_data["email"]:
                result = db.table("users").select("uid").eq("email", user_data["email"]).execute()
                if result.data:
                    existing_user = result.data[0]

            if existing_user:
                user_id = existing_user["uid"]
                # Update existing user
                db.table("users").update(user_data).eq("uid", user_id).execute()
                print(f"    Updated existing user: {user_id}")
            else:
                # Create new user
                result = db.table("users").insert(user_data).execute()
                user_id = result.data[0]["uid"]
                print(f"    Created new user: {user_id}")

            handle_to_user_id[handle] = user_id

            # Create twitter_profile record
            profile_data = {
                "handle": handle,
                "user_id": user_id,
                "username": user.get("username", handle),
                "profile_pic_url": user.get("profile_pic_url", ""),
                "follower_count": user.get("follower_count", 0),
                "ideal_num_posts": user.get("ideal_num_posts", 30),
                "number_of_generations": user.get("number_of_generations", 2),
                "min_impressions_filter": user.get("min_impressions_filter", 2000),
                "manual_minimum_impressions": user.get("manual_minimum_impressions"),
                "intent_filter_examples": user.get("intent_filter_examples", []),
                "intent_filter_last_updated": user.get("intent_filter_last_updated"),
                "lifetime_new_follows": user.get("lifetime_new_follows", 0),
                "lifetime_posts": user.get("lifetime_posts", 0),
                "scrolling_time_saved": user.get("scrolling_time_saved", 0),
                "scrapes_left": user.get("scrapes_left"),
                "posts_left": user.get("posts_left"),
            }

            # Upsert profile
            db.table("twitter_profiles").upsert(profile_data, on_conflict="handle").execute()
            print(f"    Created/updated profile: @{handle}")

            # Migrate relevant_accounts
            relevant_accounts = user.get("relevant_accounts", {})
            if relevant_accounts:
                rows = [
                    {"handle": handle, "account_handle": acct, "enabled": enabled}
                    for acct, enabled in relevant_accounts.items()
                ]
                if rows:
                    db.table("twitter_relevant_accounts").upsert(
                        rows, on_conflict="handle,account_handle"
                    ).execute()
                    print(f"    Migrated {len(rows)} relevant accounts")

            # Migrate queries
            queries = user.get("queries", [])
            if queries:
                rows = []
                for q in queries:
                    if isinstance(q, list) and len(q) >= 2:
                        rows.append({"handle": handle, "query": q[0], "summary": q[1]})
                    elif isinstance(q, str):
                        rows.append({"handle": handle, "query": q, "summary": None})
                if rows:
                    db.table("twitter_queries").upsert(
                        rows, on_conflict="handle,query"
                    ).execute()
                    print(f"    Migrated {len(rows)} queries")

            # Migrate seen_tweets
            seen_tweets = user.get("seen_tweets", {})
            if seen_tweets:
                rows = [
                    {"handle": handle, "tweet_id": tid, "seen_at": ts}
                    for tid, ts in seen_tweets.items()
                ]
                if rows:
                    # Batch insert in chunks of 100
                    for i in range(0, len(rows), 100):
                        chunk = rows[i:i+100]
                        db.table("twitter_seen_tweets").upsert(
                            chunk, on_conflict="handle,tweet_id"
                        ).execute()
                    print(f"    Migrated {len(rows)} seen tweets")

        except Exception as e:
            print(f"    ERROR migrating {handle}: {e}")

    return handle_to_user_id


def migrate_tokens():
    """Migrate tokens.json to twitter_tokens table."""
    print("\n=== Migrating Tokens ===")

    tokens_file = CACHE_DIR / "tokens.json"
    if not tokens_file.exists():
        print(f"  No tokens.json found at {tokens_file}")
        return

    with open(tokens_file, encoding="utf-8") as f:
        tokens_data = json.load(f)

    db = get_db()

    for handle, token_info in tokens_data.items():
        print(f"  Processing token for: {handle}")

        try:
            if isinstance(token_info, str):
                # Old format: just refresh token string
                token_data = {
                    "handle": handle,
                    "refresh_token": token_info,
                    "access_token": None,
                    "expires_at": None,
                }
            else:
                # New format: object with tokens
                token_data = {
                    "handle": handle,
                    "access_token": token_info.get("access_token"),
                    "refresh_token": token_info.get("refresh_token"),
                    "expires_at": token_info.get("expires_at"),
                }

            # Check if profile exists first
            profile = db.table("twitter_profiles").select("handle").eq("handle", handle).execute()
            if not profile.data:
                print(f"    Skipping - no profile exists for {handle}")
                continue

            db.table("twitter_tokens").upsert(token_data, on_conflict="handle").execute()
            print(f"    Migrated token for @{handle}")

        except Exception as e:
            print(f"    ERROR migrating token for {handle}: {e}")


def migrate_browser_states(handle_to_user_id: dict):
    """Migrate storage_state.json to browser_states table."""
    print("\n=== Migrating Browser States ===")

    storage_file = CACHE_DIR / "storage_state.json"
    if not storage_file.exists():
        print(f"  No storage_state.json found at {storage_file}")
        return

    with open(storage_file, encoding="utf-8") as f:
        storage_data = json.load(f)

    db = get_db()

    for handle, state in storage_data.items():
        print(f"  Processing browser state for: {handle}")

        user_id = handle_to_user_id.get(handle)
        if not user_id:
            # Try to look up by profile
            try:
                profile = db.table("twitter_profiles").select("user_id").eq("handle", handle).execute()
                if profile.data:
                    user_id = profile.data[0]["user_id"]
            except:
                pass

        if not user_id:
            print(f"    Skipping - no user_id found for {handle}")
            continue

        try:
            browser_state = {
                "user_id": user_id,
                "site": "twitter",
                "state": state,
            }

            db.table("browser_states").upsert(
                browser_state, on_conflict="user_id,site"
            ).execute()
            print(f"    Migrated browser state for @{handle}")

        except Exception as e:
            print(f"    ERROR migrating browser state for {handle}: {e}")


def migrate_posted_tweets():
    """Migrate {handle}_posted_tweets.json files to twitter_posted_tweets table."""
    print("\n=== Migrating Posted Tweets ===")

    db = get_db()

    # Find all posted tweets files
    for tweets_file in CACHE_DIR.glob("*_posted_tweets.json"):
        if tweets_file.name.endswith(".bak"):
            continue

        # Extract handle from filename
        handle = tweets_file.stem.replace("_posted_tweets", "")
        print(f"  Processing posted tweets for: {handle}")

        # Check if profile exists
        profile = db.table("twitter_profiles").select("handle").eq("handle", handle).execute()
        if not profile.data:
            print(f"    Skipping - no profile exists for {handle}")
            continue

        with open(tweets_file, encoding="utf-8") as f:
            tweets_data = json.load(f)

        count = 0
        errors = 0

        for tweet_id, tweet in tweets_data.items():
            if tweet_id == "_order" or not isinstance(tweet, dict):
                continue

            try:
                # Transform to new schema
                tweet_data = {
                    "tweet_id": tweet.get("id", tweet_id),  # Rename id to tweet_id
                    "handle": handle,
                    "text": tweet.get("text", ""),
                    "likes": tweet.get("likes", 0),
                    "retweets": tweet.get("retweets", 0),
                    "quotes": tweet.get("quotes", 0),
                    "replies": tweet.get("replies", 0),
                    "impressions": tweet.get("impressions", 0),
                    "score": tweet.get("score", 0),
                    "created_at": tweet.get("created_at"),
                    "url": tweet.get("url", ""),
                    "last_metrics_update": tweet.get("last_metrics_update"),
                    "media": tweet.get("media", []),
                    "parent_chain": tweet.get("parent_chain", []),
                    "response_to_thread": tweet.get("response_to_thread", []),
                    "responding_to": tweet.get("responding_to", ""),
                    "replying_to_pfp": tweet.get("replying_to_pfp", ""),
                    "original_tweet_url": tweet.get("original_tweet_url", ""),
                    "parent_media": tweet.get("parent_media", []),
                    "source": tweet.get("source", "app_posted"),
                    "monitoring_state": tweet.get("monitoring_state", "active"),
                    "post_type": tweet.get("post_type", "reply"),
                    "last_activity_at": tweet.get("last_activity_at"),
                    "last_scraped_reply_ids": tweet.get("last_scraped_reply_ids", []),
                    "resurrected_via": tweet.get("resurrected_via", "none"),
                    "quoted_tweet": tweet.get("quoted_tweet"),
                }

                # Remove deprecated fields (they shouldn't be in tweet_data anyway)
                for field in DEPRECATED_TWEET_FIELDS:
                    tweet_data.pop(field, None)

                # Fix invalid enum values
                if tweet_data["resurrected_via"] not in ("none", "notification", "search"):
                    tweet_data["resurrected_via"] = "none"
                if tweet_data["source"] not in ("app_posted", "external"):
                    tweet_data["source"] = "external"
                if tweet_data["monitoring_state"] not in ("active", "warm", "cold"):
                    tweet_data["monitoring_state"] = "cold"
                if tweet_data["post_type"] not in ("original", "reply", "comment_reply"):
                    tweet_data["post_type"] = "reply"

                db.table("twitter_posted_tweets").upsert(
                    tweet_data, on_conflict="tweet_id"
                ).execute()
                count += 1

            except Exception as e:
                errors += 1
                if errors <= 3:
                    print(f"    ERROR migrating tweet {tweet_id}: {e}")

        print(f"    Migrated {count} tweets ({errors} errors)")


def migrate_comments():
    """Migrate {handle}_comments.json files to twitter_comments table."""
    print("\n=== Migrating Comments ===")

    db = get_db()

    # Find all comments files
    for comments_file in CACHE_DIR.glob("*_comments.json"):
        # Extract handle from filename
        handle = comments_file.stem.replace("_comments", "")
        print(f"  Processing comments for: {handle}")

        # Check if profile exists
        profile = db.table("twitter_profiles").select("handle").eq("handle", handle).execute()
        if not profile.data:
            print(f"    Skipping - no profile exists for {handle}")
            continue

        with open(comments_file, encoding="utf-8") as f:
            comments_data = json.load(f)

        count = 0
        errors = 0

        for comment_id, comment in comments_data.items():
            if comment_id == "_order" or not isinstance(comment, dict):
                continue

            try:
                # Transform to new schema
                comment_data = {
                    "tweet_id": comment.get("id", comment_id),  # Rename id to tweet_id
                    "handle": handle,
                    "text": comment.get("text", ""),
                    "commenter_handle": comment.get("handle", ""),
                    "commenter_username": comment.get("username", ""),
                    "author_profile_pic_url": comment.get("author_profile_pic_url", ""),
                    "followers": comment.get("followers", 0),
                    "likes": comment.get("likes", 0),
                    "retweets": comment.get("retweets", 0),
                    "quotes": comment.get("quotes", 0),
                    "replies": comment.get("replies", 0),
                    "impressions": comment.get("impressions", 0),
                    "created_at": comment.get("created_at"),
                    "url": comment.get("url", ""),
                    "last_metrics_update": comment.get("last_metrics_update"),
                    "parent_chain": comment.get("parent_chain", []),
                    "in_reply_to_status_id": comment.get("in_reply_to_status_id"),
                    "status": comment.get("status", "pending"),
                    "generated_replies": comment.get("generated_replies", []),
                    "edited": comment.get("edited", False),
                    "source": comment.get("source", "external"),
                    "monitoring_state": comment.get("monitoring_state", "active"),
                    "last_activity_at": comment.get("last_activity_at"),
                    "resurrected_via": comment.get("resurrected_via", "none"),
                    "last_scraped_reply_ids": comment.get("last_scraped_reply_ids", []),
                    "thread": comment.get("thread", []),
                    "other_replies": comment.get("other_replies", []),
                    "quoted_tweet": comment.get("quoted_tweet"),
                    "media": comment.get("media", []),
                    "engagement_type": comment.get("engagement_type", "reply"),
                }

                # Remove deprecated fields
                for field in DEPRECATED_COMMENT_FIELDS:
                    comment_data.pop(field, None)

                # Fix invalid enum values
                if comment_data["status"] not in ("pending", "replied", "skipped"):
                    comment_data["status"] = "pending"
                if comment_data["engagement_type"] not in ("reply", "quote_tweet"):
                    comment_data["engagement_type"] = "reply"

                db.table("twitter_comments").upsert(
                    comment_data, on_conflict="tweet_id"
                ).execute()
                count += 1

            except Exception as e:
                errors += 1
                if errors <= 3:
                    print(f"    ERROR migrating comment {comment_id}: {e}")

        print(f"    Migrated {count} comments ({errors} errors)")


def main():
    """Run all migrations."""
    print("=" * 60)
    print("Starting Cache to Supabase Migration")
    print("=" * 60)
    print(f"Cache directory: {CACHE_DIR}")

    # Step 1: Migrate users and profiles (returns handle -> user_id mapping)
    handle_to_user_id = migrate_users_and_profiles()

    # Step 2: Migrate tokens
    migrate_tokens()

    # Step 3: Migrate browser states
    migrate_browser_states(handle_to_user_id)

    # Step 4: Migrate posted tweets
    migrate_posted_tweets()

    # Step 5: Migrate comments
    migrate_comments()

    print("\n" + "=" * 60)
    print("Migration Complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
