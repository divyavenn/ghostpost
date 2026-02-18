"""Test RAG-enhanced reply generation"""
import asyncio
from backend.twitter.generate_replies import generate_replies_for_tweet
from backend.utlils.utils import notify

async def test():
    # Test tweet - a philosophical tweet about relationships
    test_tweet = {
        "thread": [
            "The best relationships are the ones where you can be completely yourself, without fear of judgment or rejection. True intimacy requires vulnerability."
        ],
        "handle": "test_user",
        "id": "test_rag_123"
    }
    
    notify("🧪 Testing RAG-enhanced reply generation...")
    notify(f"📝 Tweet: {test_tweet['thread'][0][:100]}...")
    
    # Generate replies
    result = await generate_replies_for_tweet(
        tweet=test_tweet,
        models=["divya-upgraded-g"],
        needed_generations=1,
        username="divya_venn"
    )
    
    notify("\n" + "="*80)
    notify("GENERATED REPLIES:")
    notify("="*80)
    if result:
        for i, reply_data in enumerate(result, 1):
            reply_text = reply_data[0] if isinstance(reply_data, tuple) else reply_data
            notify(f"\nReply {i}: {reply_text}")
    else:
        notify("No replies generated")
    
    notify(f"\n✅ Check cache/prompts/ for the prompt log to see RAG context")
    return result

asyncio.run(test())
