"""
Populate RAG memories from user's existing tweets.
Creates embeddings for all past tweets to enable semantic retrieval.
"""
import asyncio
from backend.utlils.supabase_client import get_db, get_twitter_profile
from backend.rag.embeddings import generate_embedding
from backend.utlils.utils import notify
from datetime import datetime


async def populate_memories_from_tweets(handle: str, limit: int = 500):
    """
    Populate memories table from user's past tweets.

    Args:
        handle: Twitter handle
        limit: Max number of tweets to process (default 500, most recent)
    """

    # Get user profile
    profile = get_twitter_profile(handle)
    if not profile:
        notify(f"❌ Profile not found for {handle}")
        return

    user_id = profile.get("user_id")
    if not user_id:
        notify(f"❌ user_id not found in profile. Make sure twitter_profiles.user_id is set.")
        return

    notify(f"📊 Populating memories for @{handle} (user_id: {user_id})")

    db = get_db()

    # Get all posted tweets for this user
    result = db.table("twitter_posted_tweets")\
        .select("tweet_id, text, created_at")\
        .eq("handle", handle)\
        .order("created_at", desc=True)\
        .limit(limit)\
        .execute()

    tweets = result.data or []
    notify(f"📊 Found {len(tweets)} tweets to process")

    if not tweets:
        notify("⚠️ No tweets found. Make sure you have tweets in twitter_posted_tweets table.")
        return

    memories_created = 0
    skipped = 0
    errors = 0

    for idx, tweet in enumerate(tweets, 1):
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
            continue  # Skip if already exists

        # Generate embedding
        try:
            notify(f"[{idx}/{len(tweets)}] Embedding: {text[:60]}...")
            embedding = await generate_embedding(text, handle)

            # Insert memory
            db.table("memories").insert({
                "user_id": user_id,
                "content": text,
                "embedding": embedding,
                "source_type": "tweet",
                "source_id": tweet_id,
                "visibility": "private",
                "created_at": tweet.get("created_at", datetime.now().isoformat())
            }).execute()

            memories_created += 1

            # Rate limit to avoid API throttling
            if memories_created % 10 == 0:
                notify(f"✅ Created {memories_created} memories so far...")

            await asyncio.sleep(0.3)

        except Exception as e:
            notify(f"⚠️ Failed to create memory for {tweet_id}: {e}")
            errors += 1
            continue

    notify(f"\n{'='*80}")
    notify(f"🎉 COMPLETE!")
    notify(f"✅ Created: {memories_created} memories")
    notify(f"⏭️  Skipped: {skipped} (already exist or too short)")
    notify(f"❌ Errors: {errors}")
    notify(f"{'='*80}\n")

    # Verify
    total_memories = db.table("memories")\
        .select("memory_id", count="exact")\
        .eq("user_id", user_id)\
        .execute()

    notify(f"📊 Total memories in database for @{handle}: {total_memories.count}")


if __name__ == "__main__":
    import sys

    handle = sys.argv[1] if len(sys.argv) > 1 else "divya_venn"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 500

    notify(f"🚀 Starting memory population for @{handle}")
    notify(f"📊 Will process up to {limit} most recent tweets\n")

    asyncio.run(populate_memories_from_tweets(handle, limit))
