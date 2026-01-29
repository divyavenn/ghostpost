#!/usr/bin/env python3
"""
Backfill script for RAG data migration.

Migrates historical data into the RAG system:
1. Posted tweets → memories table
2. Edit logs → feedback table

Usage:
    # Backfill for single user
    python -m backend.scripts.backfill_rag_data --username test_user

    # Backfill for all users
    python -m backend.scripts.backfill_rag_data --all

    # Dry run (preview only)
    python -m backend.scripts.backfill_rag_data --username test_user --dry-run
"""
import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any

# Ensure .env is loaded (import config which loads dotenv)
import backend.config  # noqa: F401

from backend.rag.embeddings import generate_embeddings_batch
from backend.rag.feedback_extraction import extract_feedback_from_edit
from backend.twitter.logging import read_user_log
from backend.utlils.supabase_client import (
    add_memory,
    get_memories_by_source,
    get_posted_tweets,
    get_twitter_profile,
)
from backend.utlils.utils import notify


async def backfill_posted_tweets_to_memories(username: str, dry_run: bool = False) -> int:
    """
    Backfill posted tweets into memories table.

    Args:
        username: Twitter handle to backfill
        dry_run: If True, preview only without writing to database

    Returns:
        Number of memories created
    """
    notify(f"📝 Backfilling posted tweets → memories for @{username}")

    # Get user profile
    profile = get_twitter_profile(username)
    if not profile:
        notify(f"⚠️ Profile not found for @{username}, skipping")
        return 0

    user_id = profile.get("user_id")
    if not user_id:
        notify(f"⚠️ No user_id for @{username}, skipping")
        return 0

    # Get all posted tweets from database
    posted_tweets = get_posted_tweets(username)

    if not posted_tweets:
        notify(f"✅ No posted tweets found for @{username}")
        return 0

    notify(f"📊 Found {len(posted_tweets)} posted tweets for @{username}")

    # Filter to only replies (skip originals and comment_replies for now)
    reply_tweets = [t for t in posted_tweets if t.get("post_type") == "reply"]

    if not reply_tweets:
        notify(f"✅ No reply tweets found for @{username}")
        return 0

    notify(f"📊 Found {len(reply_tweets)} reply tweets to backfill")

    # Check which ones are already in memories
    existing_memory_ids = set()
    for tweet in reply_tweets:
        tweet_id = tweet.get("tweet_id")
        if tweet_id:
            existing = get_memories_by_source(user_id, "tweet", tweet_id)
            if existing:
                existing_memory_ids.add(tweet_id)

    new_tweets = [t for t in reply_tweets if t.get("tweet_id") not in existing_memory_ids]

    if not new_tweets:
        notify(f"✅ All reply tweets already in memories for @{username}")
        return 0

    notify(f"📊 Found {len(new_tweets)} new tweets to add (skipping {len(existing_memory_ids)} already in memories)")

    if dry_run:
        notify(f"🔍 DRY RUN: Would backfill {len(new_tweets)} tweets to memories")
        return len(new_tweets)

    # Batch generate embeddings
    tweet_texts = []
    for tweet in new_tweets:
        # Use the reply text as the memory content
        text = tweet.get("text", "")
        if not text:
            continue

        # Optionally include context of what they were replying to
        response_to_thread = tweet.get("response_to_thread", [])
        if response_to_thread and isinstance(response_to_thread, list):
            context = " | ".join(response_to_thread)
            text = f"[REPLYING TO]: {context}\n[YOUR REPLY]: {text}"

        tweet_texts.append(text)

    if not tweet_texts:
        notify(f"⚠️ No valid tweet texts found for embedding")
        return 0

    notify(f"🔢 Generating {len(tweet_texts)} embeddings in batches of 100...")

    try:
        embeddings = await generate_embeddings_batch(tweet_texts, batch_size=100, username=username)
    except Exception as e:
        notify(f"❌ Failed to generate embeddings: {e}")
        return 0

    # Insert memories
    memories_created = 0

    for i, tweet in enumerate(new_tweets):
        if i >= len(embeddings):
            break

        try:
            tweet_id = tweet.get("tweet_id")
            text = tweet_texts[i]
            embedding = embeddings[i]

            # Determine audience from responding_to handle
            audience = None
            responding_to = tweet.get("responding_to")
            if responding_to:
                # Simple heuristic: if responding to a technical account, mark as technical
                # For now, leave as None to keep it general
                pass

            add_memory(
                user_id=user_id,
                content=text,
                embedding=embedding,
                source_type="tweet",
                source_id=tweet_id,
                visibility="private",
                audience=audience
            )

            memories_created += 1

            if memories_created % 10 == 0:
                notify(f"✅ Created {memories_created}/{len(new_tweets)} memories...")

        except Exception as e:
            notify(f"⚠️ Failed to create memory for tweet {tweet_id}: {e}")
            continue

    # Estimate cost
    cost = len(embeddings) * 0.0001
    notify(f"💰 Estimated cost: ${cost:.4f} (${len(embeddings)} embeddings × $0.0001)")

    notify(f"✅ Created {memories_created} memories from posted tweets for @{username}")

    return memories_created


async def backfill_edit_logs_to_feedback(username: str, dry_run: bool = False, limit: int | None = None) -> int:
    """
    Backfill edit logs into feedback table.

    Args:
        username: Twitter handle to backfill
        dry_run: If True, preview only without writing to database
        limit: Maximum number of edits to process (None = all)

    Returns:
        Number of feedback entries created
    """
    notify(f"📝 Backfilling edit logs → feedback for @{username}")

    # Get user profile
    profile = get_twitter_profile(username)
    if not profile:
        notify(f"⚠️ Profile not found for @{username}, skipping")
        return 0

    # Read edit logs
    log_entries = read_user_log(username)

    # Filter to only edited actions
    edit_entries = [e for e in log_entries if e.get("action") == "edited"]

    if not edit_entries:
        notify(f"✅ No edit entries found for @{username}")
        return 0

    notify(f"📊 Found {len(edit_entries)} edit entries for @{username}")

    # Limit if specified
    if limit:
        edit_entries = edit_entries[-limit:]  # Most recent N
        notify(f"📊 Processing most recent {len(edit_entries)} edits (limited by --limit)")

    if dry_run:
        notify(f"🔍 DRY RUN: Would process {len(edit_entries)} edit entries for feedback")
        return len(edit_entries)

    # Process each edit
    feedback_created = 0

    for i, entry in enumerate(edit_entries):
        try:
            result = await extract_feedback_from_edit(username, entry)

            if result:
                feedback_created += 1

            if (i + 1) % 10 == 0:
                notify(f"✅ Processed {i + 1}/{len(edit_entries)} edits ({feedback_created} feedback extracted)...")

        except Exception as e:
            notify(f"⚠️ Failed to extract feedback from edit {i + 1}: {e}")
            continue

    notify(f"✅ Created {feedback_created} feedback entries from {len(edit_entries)} edits for @{username}")

    return feedback_created


async def backfill_user(username: str, dry_run: bool = False, limit: int | None = None) -> dict[str, int]:
    """
    Backfill all RAG data for a single user.

    Args:
        username: Twitter handle to backfill
        dry_run: If True, preview only
        limit: Maximum number of edits to process (None = all)

    Returns:
        dict with counts: {"memories": N, "feedback": N}
    """
    notify(f"\n{'='*60}")
    notify(f"Backfilling RAG data for @{username}")
    notify(f"{'='*60}\n")

    memories_count = await backfill_posted_tweets_to_memories(username, dry_run)
    feedback_count = await backfill_edit_logs_to_feedback(username, dry_run, limit)

    notify(f"\n{'='*60}")
    notify(f"Summary for @{username}:")
    notify(f"  Memories created: {memories_count}")
    notify(f"  Feedback created: {feedback_count}")
    notify(f"{'='*60}\n")

    return {"memories": memories_count, "feedback": feedback_count}


async def backfill_all_users(dry_run: bool = False, limit: int | None = None) -> dict[str, Any]:
    """
    Backfill RAG data for all users in the system.

    Args:
        dry_run: If True, preview only
        limit: Maximum number of edits per user (None = all)

    Returns:
        dict with per-user stats
    """
    from backend.utlils.supabase_client import get_all_twitter_profiles

    profiles = get_all_twitter_profiles()

    if not profiles:
        notify("⚠️ No Twitter profiles found")
        return {}

    notify(f"📊 Found {len(profiles)} profiles to backfill")

    results = {}

    for i, profile in enumerate(profiles):
        username = profile.get("handle")
        if not username:
            continue

        notify(f"\n[{i + 1}/{len(profiles)}] Processing @{username}...")

        try:
            result = await backfill_user(username, dry_run, limit)
            results[username] = result
        except Exception as e:
            notify(f"❌ Failed to backfill @{username}: {e}")
            results[username] = {"memories": 0, "feedback": 0, "error": str(e)}

    # Print overall summary
    notify(f"\n{'='*60}")
    notify(f"OVERALL SUMMARY")
    notify(f"{'='*60}")

    total_memories = sum(r.get("memories", 0) for r in results.values())
    total_feedback = sum(r.get("feedback", 0) for r in results.values())

    notify(f"Total users processed: {len(results)}")
    notify(f"Total memories created: {total_memories}")
    notify(f"Total feedback created: {total_feedback}")

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Backfill historical data into RAG system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Backfill for single user
  python -m backend.scripts.backfill_rag_data --username test_user

  # Backfill for all users
  python -m backend.scripts.backfill_rag_data --all

  # Dry run (preview only)
  python -m backend.scripts.backfill_rag_data --username test_user --dry-run

  # Limit edit processing (for testing)
  python -m backend.scripts.backfill_rag_data --username test_user --limit 10
        """
    )

    parser.add_argument(
        "--username",
        type=str,
        help="Twitter handle to backfill (e.g., 'divya_venn')"
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Backfill all users in the system"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing to database"
    )

    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of edits to process per user (for testing)"
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.username and not args.all:
        parser.error("Must specify either --username or --all")

    if args.username and args.all:
        parser.error("Cannot specify both --username and --all")

    # Run backfill
    try:
        if args.all:
            results = asyncio.run(backfill_all_users(args.dry_run, args.limit))
        else:
            results = asyncio.run(backfill_user(args.username, args.dry_run, args.limit))

        notify("\n✅ Backfill complete!")

    except KeyboardInterrupt:
        notify("\n⚠️ Backfill interrupted by user")
        sys.exit(1)
    except Exception as e:
        notify(f"\n❌ Backfill failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
