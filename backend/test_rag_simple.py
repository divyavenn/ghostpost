"""Test RAG retrieval directly"""
import asyncio
from backend.rag.retrieval import retrieve_context_for_reply
from backend.utlils.utils import notify

async def test():
    # Test RAG retrieval with a philosophical tweet about relationships
    tweet_text = "The best relationships are the ones where you can be completely yourself, without fear of judgment or rejection. True intimacy requires vulnerability."
    
    notify("🧪 Testing RAG retrieval...")
    notify(f"📝 Tweet: {tweet_text[:100]}...")
    
    # Retrieve context
    context = await retrieve_context_for_reply(
        username="divya_venn",
        tweet_thread=tweet_text,
        target_account="test_user",
        max_memories=5,
        max_feedback=3
    )
    
    notify("\n" + "="*80)
    notify("RAG RETRIEVAL RESULTS:")
    notify("="*80)
    notify(f"📊 Memories retrieved: {context['memory_count']}")
    notify(f"📊 Feedback retrieved: {context['feedback_count']}")
    notify(f"📊 Avg similarity: {context['avg_similarity']:.3f}")
    notify(f"📊 Retrieval time: {context['retrieval_time_ms']}ms")
    
    if context['context_string']:
        notify("\n" + "="*80)
        notify("CONTEXT PROVIDED TO LLM:")
        notify("="*80)
        notify(context['context_string'][:1000] + "\n..." if len(context['context_string']) > 1000 else context['context_string'])
    else:
        notify("\n⚠️ No context retrieved")
    
    return context

asyncio.run(test())
