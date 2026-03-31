"""
Embedding service using OpenAI API (text-embedding-3-small).

Generates 1536-dimensional embeddings for RAG semantic search.
"""
import asyncio

from backend.config import OPENAI_API_KEY
from backend.twitter.rate_limiter import LLM_OBELISK, call_api
from backend.utlils.utils import error, notify


async def generate_embedding(text: str, username: str = "system") -> list[float]:
    """
    Generate a single embedding vector using OpenAI text-embedding-3-small.

    Args:
        text: Input text to embed
        username: Username for logging and rate limiting

    Returns:
        1536-dimensional embedding vector

    Raises:
        RuntimeError: If embedding generation fails after retries
    """
    if not text or not text.strip():
        error("Cannot generate embedding for empty text", status_code=400, function_name="generate_embedding", username=username, critical=True)

    if not OPENAI_API_KEY:
        error("OPENAI_API_KEY not configured", status_code=500, function_name="generate_embedding", username=username, critical=True)

    url = "https://api.openai.com/v1/embeddings"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}

    payload = {
        "model": "text-embedding-3-small",
        "input": text
    }

    # Use rate limiter with retry
    response = await call_api(
        method="POST",
        url=url,
        bucket=LLM_OBELISK,
        headers=headers,
        json_data=payload,
        username=username
    )

    if not response.success:
        error(
            f"Failed to generate embedding: {response.error_message}",
            status_code=response.status_code or 500,
            function_name="generate_embedding",
            username=username,
            critical=True
        )

    data = response.data

    # Extract embedding from response
    try:
        embedding = data["data"][0]["embedding"]

        # Validate embedding dimensions
        if len(embedding) != 1536:
            error(
                f"Invalid embedding dimensions: expected 1536, got {len(embedding)}",
                status_code=500,
                function_name="generate_embedding",
                username=username,
                critical=True
            )

        return embedding

    except (KeyError, IndexError, TypeError) as e:
        error(
            f"Unexpected embedding API response structure: {e}",
            status_code=500,
            exception_text=str(e),
            function_name="generate_embedding",
            username=username,
            critical=True
        )


async def generate_embeddings_batch(
    texts: list[str],
    batch_size: int = 100,
    username: str = "system"
) -> list[list[float]]:
    """
    Generate embeddings for multiple texts with batch processing.

    Args:
        texts: List of input texts to embed
        batch_size: Number of texts to process in each API call (max 100)
        username: Username for logging and rate limiting

    Returns:
        List of 1536-dimensional embedding vectors (same order as input)

    Raises:
        RuntimeError: If embedding generation fails after retries
    """
    if not texts:
        return []

    # Filter out empty texts
    non_empty_texts = [t for t in texts if t and t.strip()]
    if len(non_empty_texts) < len(texts):
        notify(f"⚠️ Filtered out {len(texts) - len(non_empty_texts)} empty texts from batch")

    if not non_empty_texts:
        error("Cannot generate embeddings for batch of empty texts", status_code=400, function_name="generate_embeddings_batch", username=username, critical=True)

    if not OPENAI_API_KEY:
        error("OPENAI_API_KEY not configured", status_code=500, function_name="generate_embeddings_batch", username=username, critical=True)

    url = "https://api.openai.com/v1/embeddings"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}

    all_embeddings = []
    total_batches = (len(non_empty_texts) + batch_size - 1) // batch_size

    for batch_idx in range(total_batches):
        start_idx = batch_idx * batch_size
        end_idx = min(start_idx + batch_size, len(non_empty_texts))
        batch_texts = non_empty_texts[start_idx:end_idx]

        notify(f"🔢 Generating embeddings for batch {batch_idx + 1}/{total_batches} ({len(batch_texts)} texts)")

        payload = {
            "model": "text-embedding-3-small",
            "input": batch_texts
        }

        # Use rate limiter with retry
        response = await call_api(
            method="POST",
            url=url,
            bucket=LLM_OBELISK,
            headers=headers,
            json_data=payload,
            username=username
        )

        if not response.success:
            error(
                f"Failed to generate embeddings for batch {batch_idx + 1}/{total_batches}: {response.error_message}",
                status_code=response.status_code or 500,
                function_name="generate_embeddings_batch",
                username=username,
                critical=True
            )

        data = response.data

        # Extract embeddings from response
        try:
            batch_embeddings = data["data"]

            # Sort by index to ensure correct order
            batch_embeddings.sort(key=lambda x: x["index"])

            for item in batch_embeddings:
                embedding = item["embedding"]

                # Validate embedding dimensions
                if len(embedding) != 1536:
                    error(
                        f"Invalid embedding dimensions in batch: expected 1536, got {len(embedding)}",
                        status_code=500,
                        function_name="generate_embeddings_batch",
                        username=username,
                        critical=True
                    )

                all_embeddings.append(embedding)

        except (KeyError, IndexError, TypeError) as e:
            error(
                f"Unexpected embedding API response structure in batch {batch_idx + 1}: {e}",
                status_code=500,
                exception_text=str(e),
                function_name="generate_embeddings_batch",
                username=username,
                critical=True
            )

        # Small delay between batches to avoid overwhelming the API
        if batch_idx < total_batches - 1:
            await asyncio.sleep(0.5)

    notify(f"✅ Generated {len(all_embeddings)} embeddings across {total_batches} batch(es)")

    # Validate we got embeddings for all texts
    if len(all_embeddings) != len(non_empty_texts):
        error(
            f"Embedding count mismatch: expected {len(non_empty_texts)}, got {len(all_embeddings)}",
            status_code=500,
            function_name="generate_embeddings_batch",
            username=username,
            critical=True
        )

    return all_embeddings


# Example usage / testing
if __name__ == "__main__":
    async def test_embeddings():
        # Test single embedding
        text = "I prefer concise replies over verbose explanations"
        embedding = await generate_embedding(text)
        print(f"✅ Single embedding generated: {len(embedding)} dimensions")
        print(f"   First 5 values: {embedding[:5]}")

        # Test batch embeddings
        texts = [
            "Machine learning is fascinating",
            "Python is a great programming language",
            "I love building AI systems"
        ]
        embeddings = await generate_embeddings_batch(texts)
        print(f"\n✅ Batch embeddings generated: {len(embeddings)} vectors")
        for i, emb in enumerate(embeddings):
            print(f"   Text {i+1}: {len(emb)} dimensions, first 3 values: {emb[:3]}")

    asyncio.run(test_embeddings())
