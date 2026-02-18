import asyncio
from backend.rag.embeddings import generate_embedding

async def test():
    print("🧪 Testing OpenAI embeddings...")
    try:
        embedding = await generate_embedding("Hello, this is a test tweet about AI and machine learning!", "divya_venn")
        print(f"✅ SUCCESS! Generated embedding with {len(embedding)} dimensions")
        print(f"   First 5 values: {embedding[:5]}")
        return True
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False

success = asyncio.run(test())
exit(0 if success else 1)
