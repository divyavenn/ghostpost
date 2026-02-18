"""
Backfill RAG tables (memories and feedback) from existing data.

This script:
1. Backfills memories from twitter_posted_tweets (original tweets only)
2. Backfills feedback from activity logs (skipped/edited tweets)
"""
import asyncio
import json
from pathlib import Path
from datetime import datetime

from backend.utlils.supabase_client import get_db, get_twitter_profile
from backend.rag.embeddings import generate_embedding
from backend.utlils.utils import notify, error


async def backfill_memories_from_posted_tweets(handle: str, limit: int = 1000):
    """Create memories from posted original tweets in twitter_posted_tweets table."""

    profile = get_twitter_profile(handle)
    if not profile:
        notify(f"❌ Profile not found for {handle}")
        return

    user_id = profile.get("user_id")
    if not user_id:
        notify(f"❌ No user_id found for {handle}")
        return

    db = get_db()

    # Get all original tweets (not replies) from twitter_posted_tweets
    result = db.table("twitter_posted_tweets")\
        .select("tweet_id, text, created_at, post_type")\
        .eq("handle", handle)\
        .eq("post_type", "original")\
        .order("created_at", desc=True)\
        .limit(limit)\
        .execute()

    tweets = result.data or []
    notify(f"📊 Found {len(tweets)} original tweets to process")

    if not tweets:
        notify("⚠️ No original tweets found")
        return

    memories_created = 0
    skipped = 0
    errors = 0

    # Filter tweets and check for existing memories
    tweets_to_process = []
    for tweet in tweets:
        tweet_id = tweet["tweet_id"]
        text = tweet["text"]

        # Skip empty or very short tweets
        if not text or len(text.strip()) < 10:
            skipped += 1
            continue

        # Check if memory already exists
        existing = db.table("memories")\
            .select("memory_id")\
            .eq("user_id", user_id)\
            .eq("source_type", "tweet")\
            .eq("source_id", tweet_id)\
            .execute()

        if existing.data:
            skipped += 1
            continue

        tweets_to_process.append(tweet)

    if not tweets_to_process:
        notify("✅ All tweets already have memories")
        return

    notify(f"📊 Processing {len(tweets_to_process)} tweets in batches...")

    # Generate embeddings in batches (much faster!)
    try:
        from backend.rag.embeddings import generate_embeddings_batch

        texts = [t["text"] for t in tweets_to_process]
        notify(f"🔢 Generating {len(texts)} embeddings in batch...")
        embeddings = await generate_embeddings_batch(texts, batch_size=100, username=handle)

        # Insert all memories
        for tweet, embedding in zip(tweets_to_process, embeddings):
            try:
                db.table("memories").insert({
                    "user_id": user_id,
                    "content": tweet["text"],
                    "embedding": embedding,
                    "source_type": "tweet",
                    "source_id": tweet["tweet_id"],
                    "visibility": "private",
                    "created_at": tweet.get("created_at") or datetime.now().isoformat()
                }).execute()

                memories_created += 1

                if memories_created % 10 == 0:
                    notify(f"✅ Inserted {memories_created}/{len(tweets_to_process)} memories...")

            except Exception as e:
                notify(f"⚠️ Failed to insert memory for {tweet['tweet_id']}: {e}")
                errors += 1

    except Exception as e:
        notify(f"⚠️ Batch processing failed: {e}")
        notify("⚠️ Falling back to one-by-one processing...")
        errors += 1

        # Fallback to individual processing if batch fails
        for idx, tweet in enumerate(tweets_to_process, 1):
            try:
                notify(f"[{idx}/{len(tweets_to_process)}] Embedding: {tweet['text'][:60]}...")
                embedding = await generate_embedding(tweet["text"], handle)

                db.table("memories").insert({
                    "user_id": user_id,
                    "content": tweet["text"],
                    "embedding": embedding,
                    "source_type": "tweet",
                    "source_id": tweet["tweet_id"],
                    "visibility": "private",
                    "created_at": tweet.get("created_at") or datetime.now().isoformat()
                }).execute()

                memories_created += 1

                if memories_created % 10 == 0:
                    notify(f"✅ Created {memories_created} memories so far...")

                await asyncio.sleep(0.3)

            except Exception as e:
                notify(f"⚠️ Failed to create memory for {tweet['tweet_id']}: {e}")
                errors += 1
                continue

    notify(f"\n{'='*80}")
    notify(f"🎉 MEMORIES BACKFILL COMPLETE!")
    notify(f"✅ Created: {memories_created}")
    notify(f"⏭️  Skipped: {skipped}")
    notify(f"❌ Errors: {errors}")
    notify(f"{'='*80}\n")


async def backfill_feedback_from_logs(handle: str):
    """Create feedback entries from activity log files (skipped tweets)."""

    profile = get_twitter_profile(handle)
    if not profile:
        notify(f"❌ Profile not found for {handle}")
        return

    user_id = profile.get("user_id")
    if not user_id:
        notify(f"❌ No user_id found for {handle}")
        return

    # Find log file
    log_file = Path(f"cache/{handle}_log.jsonl")
    if not log_file.exists():
        notify(f"❌ Log file not found: {log_file}")
        return

    notify(f"📄 Reading log file: {log_file}")

    db = get_db()
    feedback_created = 0
    skipped = 0
    errors = 0

    with open(log_file, 'r') as f:
        for line_num, line in enumerate(f, 1):
            try:
                entry = json.loads(line.strip())
                action = entry.get("action")

                # We're interested in "skipped" actions for feedback
                if action != "skipped":
                    continue

                metadata = entry.get("metadata", {})
                original_text = metadata.get("original_tweet_text", "")
                original_handle = metadata.get("original_handle", "")
                tweet_id = entry.get("tweet_id")

                if not original_text or not tweet_id:
                    skipped += 1
                    continue

                # Check if feedback already exists
                existing = db.table("feedback")\
                    .select("feedback_id")\
                    .eq("user_id", user_id)\
                    .eq("source_action", f"skipped_{tweet_id}")\
                    .execute()

                if existing.data:
                    skipped += 1
                    continue

                # Generate embedding for the original tweet (trigger context)
                notify(f"[Line {line_num}] Processing skipped tweet from @{original_handle}")
                trigger_embedding = await generate_embedding(original_text, handle)

                # Insert feedback entry
                # "skip" type with no "dothis" - indicates user didn't want to reply
                db.table("feedback").insert({
                    "user_id": user_id,
                    "feedback_type": "skip",
                    "dothis": None,  # User chose not to reply
                    "notthat": None,  # No generated reply to compare against
                    "trigger_context": original_text,
                    "trigger_embedding": trigger_embedding,
                    "source_action": f"skipped_{tweet_id}",
                    "extracted_rules": {}
                }).execute()

                feedback_created += 1

                if feedback_created % 10 == 0:
                    notify(f"✅ Created {feedback_created} feedback entries so far...")

                # Rate limit
                await asyncio.sleep(0.3)

            except json.JSONDecodeError:
                notify(f"⚠️ Invalid JSON at line {line_num}")
                errors += 1
                continue
            except Exception as e:
                notify(f"⚠️ Error processing line {line_num}: {e}")
                errors += 1
                continue

    notify(f"\n{'='*80}")
    notify(f"🎉 FEEDBACK BACKFILL COMPLETE!")
    notify(f"✅ Created: {feedback_created}")
    notify(f"⏭️  Skipped: {skipped}")
    notify(f"❌ Errors: {errors}")
    notify(f"{'='*80}\n")


async def main():
    """Run backfill for all handles."""
    import sys

    handle = sys.argv[1] if len(sys.argv) > 1 else "divya_venn"

    notify(f"🚀 Starting RAG backfill for @{handle}\n")

    # Step 1: Backfill memories from posted tweets
    notify("=" * 80)
    notify("STEP 1: Backfilling memories from posted tweets")
    notify("=" * 80)
    await backfill_memories_from_posted_tweets(handle)

    # Step 2: Backfill feedback from activity logs
    notify("\n" + "=" * 80)
    notify("STEP 2: Backfilling feedback from activity logs")
    notify("=" * 80)
    await backfill_feedback_from_logs(handle)

    notify("\n🎊 ALL BACKFILL COMPLETE!")


if __name__ == "__main__":
    asyncio.run(main())
