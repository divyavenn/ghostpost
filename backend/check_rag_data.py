from backend.utlils.supabase_client import get_db, get_twitter_profile

profile = get_twitter_profile("divya_venn")
if profile:
    user_id = profile.get("user_id")
    db = get_db()
    
    # Check memories count
    memories = db.table("memories").select("memory_id", count="exact").eq("user_id", user_id).execute()
    print(f"Memories created: {memories.count}")
    
    # Check feedback count  
    feedback = db.table("feedback").select("feedback_id", count="exact").eq("user_id", user_id).execute()
    print(f"Feedback created: {feedback.count}")
    
    # Show sample if any exist
    if memories.count > 0:
        sample = db.table("memories").select("content, source_type, created_at").eq("user_id", user_id).limit(3).execute()
        print("\nSample memories:")
        for m in sample.data:
            print(f"  - [{m['source_type']}] {m['content'][:80]}...")
