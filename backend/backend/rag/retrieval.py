"""
RAG retrieval pipeline for reply generation context.

This module provides semantic search and context building for LLM prompts
when generating tweet replies. It retrieves relevant memories (past tweets,
documents) and learned preferences (from user edits) to improve reply quality.
"""
import time
from typing import Any

from backend.rag.embeddings import generate_embedding
from backend.utlils.supabase_client import (
    get_twitter_profile,
    search_feedback_vector,
    search_memories_vector,
)
from backend.utlils.utils import error, notify


async def retrieve_context_for_reply(
    username: str,
    tweet_thread: str | list[str],
    target_account: str | None = None,
    max_memories: int = 10,
    max_feedback: int = 5
) -> dict[str, Any]:
    """
    Retrieve relevant context for generating a reply to a tweet.

    This is the main entry point for RAG retrieval. It:
    1. Generates embedding for the tweet being replied to
    2. Vector searches memories and feedback
    3. Reranks results by relevance
    4. Formats into LLM-ready context string

    Args:
        username: Twitter handle of the user generating the reply
        tweet_thread: Text of tweet/thread being replied to (string or list of strings)
        target_account: Handle of account being replied to (for audience filtering)
        max_memories: Maximum number of memory examples to retrieve
        max_feedback: Maximum number of feedback entries to retrieve

    Returns:
        dict with:
            - context_string: Formatted context for LLM prompt
            - memory_count: Number of memories retrieved
            - feedback_count: Number of feedback entries retrieved
            - avg_similarity: Average cosine similarity score
            - retrieval_time_ms: Time taken for retrieval in milliseconds

    Raises:
        RuntimeError: If retrieval fails critically (falls back to old system)
    """
    start_time = time.time()

    try:
        # Get user_id from username
        profile = get_twitter_profile(username)
        if not profile:
            error(f"Twitter profile not found for {username}", status_code=404, function_name="retrieve_context_for_reply", username=username, critical=False)
            return _empty_context()

        user_id = profile.get("user_id")
        if not user_id:
            error(f"No user_id found for profile {username}", status_code=500, function_name="retrieve_context_for_reply", username=username, critical=False)
            return _empty_context()

        # Convert thread to single string if needed
        if isinstance(tweet_thread, list):
            tweet_text = " | ".join(tweet_thread)
        else:
            tweet_text = tweet_thread

        if not tweet_text or not tweet_text.strip():
            notify(f"⚠️ Empty tweet text for RAG retrieval, using fallback")
            return _empty_context()

        # Generate embedding for the tweet
        notify(f"🔢 Generating embedding for tweet (length: {len(tweet_text)} chars)")
        embedding = await generate_embedding(tweet_text, username=username)

        # Vector search for memories
        notify(f"🔍 Searching memories (limit: {max_memories})")
        memories = search_memories_vector(
            user_id=user_id,
            embedding=embedding,
            limit=max_memories * 2,  # Retrieve 2x for reranking
            visibility_filter="private"  # Only private memories for now
        )

        # Vector search for feedback
        notify(f"🔍 Searching feedback (limit: {max_feedback})")
        feedback_entries = search_feedback_vector(
            user_id=user_id,
            embedding=embedding,
            limit=max_feedback * 2  # Retrieve 2x for reranking
        )

        # Rerank by relevance using LLM
        if memories:
            notify(f"🎯 Reranking {len(memories)} memories by relevance")
            memories = await rerank_memories(memories, tweet_text, max_memories, username)

        if feedback_entries:
            notify(f"🎯 Reranking {len(feedback_entries)} feedback entries by relevance")
            feedback_entries = await rerank_feedback(feedback_entries, tweet_text, max_feedback, username)

        # Cluster memories by topic/source
        if memories:
            memories = cluster_by_topic(memories)

        # Format context string
        context_parts = []

        if memories:
            memories_context = format_memories_as_citations(memories)
            context_parts.append(memories_context)

        if feedback_entries:
            feedback_context = format_feedback_as_constraints(feedback_entries)
            context_parts.append(feedback_context)

        # Calculate metrics
        retrieval_time_ms = int((time.time() - start_time) * 1000)
        avg_similarity = 0.0

        if memories or feedback_entries:
            all_similarities = []
            for mem in memories:
                if "similarity" in mem:
                    all_similarities.append(mem["similarity"])
            for fb in feedback_entries:
                if "similarity" in fb:
                    all_similarities.append(fb["similarity"])

            if all_similarities:
                avg_similarity = sum(all_similarities) / len(all_similarities)

        notify(f"✅ RAG retrieval complete: {len(memories)} memories, {len(feedback_entries)} feedback, {retrieval_time_ms}ms")

        return {
            "context_string": "\n\n".join(context_parts) if context_parts else "",
            "memory_count": len(memories),
            "feedback_count": len(feedback_entries),
            "avg_similarity": avg_similarity,
            "retrieval_time_ms": retrieval_time_ms
        }

    except Exception as e:
        retrieval_time_ms = int((time.time() - start_time) * 1000)
        error(
            f"RAG retrieval failed: {e}",
            status_code=500,
            exception_text=str(e),
            function_name="retrieve_context_for_reply",
            username=username,
            critical=False  # Not critical - we fall back to old system
        )
        return _empty_context()


def _empty_context() -> dict[str, Any]:
    """Return empty context when retrieval fails or has no results."""
    return {
        "context_string": "",
        "memory_count": 0,
        "feedback_count": 0,
        "avg_similarity": 0.0,
        "retrieval_time_ms": 0
    }


async def rerank_memories(
    memories: list[dict[str, Any]],
    tweet_context: str,
    limit: int,
    username: str
) -> list[dict[str, Any]]:
    """
    Rerank memories by relevance to the tweet context using LLM.

    Args:
        memories: List of memory dicts with content, source_type, similarity
        tweet_context: The tweet being replied to
        limit: Maximum number of memories to return after reranking
        username: Username for logging

    Returns:
        Reranked and filtered list of memories (top N most relevant)
    """
    from backend.utlils.llm import ask_llm

    # If we have fewer than limit, just return them sorted by similarity
    if len(memories) <= limit:
        return sorted(memories, key=lambda x: x.get("similarity", 0), reverse=True)

    # Build prompt for LLM reranking
    system_prompt = """You are helping rank retrieved memories by relevance to a tweet.

Given a tweet and a list of memories (past tweets, notes, preferences), score each memory's relevance from 0-10, where:
- 10 = Highly relevant (directly addresses the same topic/question)
- 5 = Somewhat relevant (related context or style guidance)
- 0 = Not relevant (unrelated topic)

Respond with ONLY a JSON array of scores, one per memory, in order. Example: [8, 3, 9, 1, 6]"""

    # Build user prompt with tweet and memories
    user_prompt = f"Tweet being replied to:\n{tweet_context}\n\n"
    user_prompt += "Memories to rank:\n"

    for i, mem in enumerate(memories, 1):
        content_preview = mem["content"][:200] + "..." if len(mem["content"]) > 200 else mem["content"]
        user_prompt += f"\n{i}. [{mem['source_type']}] {content_preview}"

    user_prompt += f"\n\nScore each of the {len(memories)} memories (0-10, JSON array):"

    # Call LLM for reranking
    try:
        response = await ask_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model="chatgpt-4o-mini",  # Use cheaper model for reranking
            username=username,
            prompt_type="RAG_RERANK"
        )

        if "error" in response:
            notify(f"⚠️ LLM reranking failed, falling back to similarity scores")
            return sorted(memories, key=lambda x: x.get("similarity", 0), reverse=True)[:limit]

        # Parse scores from LLM response
        import json
        import re

        message = response["message"]
        # Try to extract JSON array from response
        match = re.search(r'\[[\d\s,]+\]', message)
        if match:
            scores = json.loads(match.group(0))

            if len(scores) == len(memories):
                # Add scores to memories and sort
                for i, score in enumerate(scores):
                    memories[i]["rerank_score"] = score

                # Sort by rerank score, then by similarity
                reranked = sorted(
                    memories,
                    key=lambda x: (x.get("rerank_score", 0), x.get("similarity", 0)),
                    reverse=True
                )
                return reranked[:limit]

        notify(f"⚠️ Could not parse LLM reranking scores, falling back to similarity")
        return sorted(memories, key=lambda x: x.get("similarity", 0), reverse=True)[:limit]

    except Exception as e:
        error(
            f"Reranking failed: {e}",
            status_code=500,
            exception_text=str(e),
            function_name="rerank_memories",
            username=username,
            critical=False
        )
        return sorted(memories, key=lambda x: x.get("similarity", 0), reverse=True)[:limit]


async def rerank_feedback(
    feedback_entries: list[dict[str, Any]],
    tweet_context: str,
    limit: int,
    username: str
) -> list[dict[str, Any]]:
    """
    Rerank feedback entries by relevance to the tweet context using LLM.

    Similar to rerank_memories but optimized for feedback entries.

    Args:
        feedback_entries: List of feedback dicts with dothis/notthat, extracted_rules
        tweet_context: The tweet being replied to
        limit: Maximum number of entries to return
        username: Username for logging

    Returns:
        Reranked and filtered list of feedback entries
    """
    from backend.utlils.llm import ask_llm

    # If we have fewer than limit, just return them sorted by similarity
    if len(feedback_entries) <= limit:
        return sorted(feedback_entries, key=lambda x: x.get("similarity", 0), reverse=True)

    # Build prompt for LLM reranking
    system_prompt = """You are helping rank learned user preferences by relevance to a tweet.

Given a tweet and a list of user preferences (learned from past edits), score each preference's relevance from 0-10, where:
- 10 = Highly relevant (user preference directly applies to this type of reply)
- 5 = Somewhat relevant (general style guidance)
- 0 = Not relevant (unrelated context)

Respond with ONLY a JSON array of scores, one per preference, in order. Example: [7, 2, 9, 4]"""

    # Build user prompt
    user_prompt = f"Tweet being replied to:\n{tweet_context}\n\n"
    user_prompt += "User preferences to rank:\n"

    for i, fb in enumerate(feedback_entries, 1):
        rules = fb.get("extracted_rules", {})
        preview = f"Type: {fb.get('feedback_type', 'unknown')}"
        if rules:
            preview += f" | Rules: {str(rules)[:100]}"
        user_prompt += f"\n{i}. {preview}"

    user_prompt += f"\n\nScore each of the {len(feedback_entries)} preferences (0-10, JSON array):"

    # Call LLM for reranking
    try:
        response = await ask_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model="chatgpt-4o-mini",
            username=username,
            prompt_type="RAG_RERANK_FEEDBACK"
        )

        if "error" in response:
            return sorted(feedback_entries, key=lambda x: x.get("similarity", 0), reverse=True)[:limit]

        # Parse scores
        import json
        import re

        message = response["message"]
        match = re.search(r'\[[\d\s,]+\]', message)
        if match:
            scores = json.loads(match.group(0))

            if len(scores) == len(feedback_entries):
                for i, score in enumerate(scores):
                    feedback_entries[i]["rerank_score"] = score

                reranked = sorted(
                    feedback_entries,
                    key=lambda x: (x.get("rerank_score", 0), x.get("similarity", 0)),
                    reverse=True
                )
                return reranked[:limit]

        return sorted(feedback_entries, key=lambda x: x.get("similarity", 0), reverse=True)[:limit]

    except Exception as e:
        error(
            f"Feedback reranking failed: {e}",
            status_code=500,
            exception_text=str(e),
            function_name="rerank_feedback",
            username=username,
            critical=False
        )
        return sorted(feedback_entries, key=lambda x: x.get("similarity", 0), reverse=True)[:limit]


def cluster_by_topic(memories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Cluster memories by source_type and sort within clusters.

    Groups memories by their source (tweets, blogs, etc.) and sorts
    by relevance within each group.

    Args:
        memories: List of memory dicts

    Returns:
        Reordered list with memories grouped by source_type
    """
    from collections import defaultdict

    # Group by source_type
    clusters = defaultdict(list)
    for mem in memories:
        source_type = mem.get("source_type", "unknown")
        clusters[source_type].append(mem)

    # Sort within each cluster by rerank_score then similarity
    for source_type in clusters:
        clusters[source_type].sort(
            key=lambda x: (x.get("rerank_score", 0), x.get("similarity", 0)),
            reverse=True
        )

    # Flatten back to list, prioritizing tweet sources first
    priority_order = ["tweet", "blog", "file", "manual", "podcast", "unknown"]
    result = []

    for source_type in priority_order:
        if source_type in clusters:
            result.extend(clusters[source_type])

    # Add any remaining source types not in priority order
    for source_type, mems in clusters.items():
        if source_type not in priority_order:
            result.extend(mems)

    return result


def format_memories_as_citations(memories: list[dict[str, Any]]) -> str:
    """
    Format memories as citation-style context for LLM prompt.

    Args:
        memories: List of memory dicts with content, source_type, etc.

    Returns:
        Formatted string with clear section boundaries
    """
    if not memories:
        return ""

    context = "========== RELEVANT MEMORIES ==========\n"
    context += "Below are relevant examples and context from your knowledge base:\n\n"

    for i, mem in enumerate(memories, 1):
        source_type = mem.get("source_type", "unknown")
        content = mem["content"]
        similarity = mem.get("similarity", 0)

        context += f"[Memory {i} - {source_type.upper()}] (similarity: {similarity:.2f})\n"
        context += f"{content}\n\n"

    context += "========== END MEMORIES ==========\n"

    return context


def format_feedback_as_constraints(feedback_entries: list[dict[str, Any]]) -> str:
    """
    Format feedback as raw before/after examples for LLM to infer patterns.

    Args:
        feedback_entries: List of feedback dicts with dothis/notthat, trigger_context

    Returns:
        Formatted string with raw edit examples
    """
    if not feedback_entries:
        return ""

    context = "========== EXAMPLES OF HOW YOU EDIT REPLIES ==========\n"
    context += "Here are examples of how you've edited AI-generated replies in the past.\n"
    context += "Learn from these patterns and apply similar thinking to your response.\n\n"

    for i, fb in enumerate(feedback_entries, 1):
        feedback_type = fb.get("feedback_type", "unknown")
        trigger = fb.get("trigger_context", "")
        notthat = fb.get("notthat")  # What was generated
        dothis = fb.get("dothis")    # What you changed it to

        if not dothis:
            continue  # Skip if no positive example

        context += f"Example {i}:\n"

        # Show the original tweet being replied to (for context)
        if trigger:
            trigger_short = trigger[:150] + "..." if len(trigger) > 150 else trigger
            context += f"[ORIGINAL TWEET]: {trigger_short}\n"

        # Show what was generated vs what you changed it to
        if notthat:
            context += f"[AI GENERATED]: {notthat}\n"
            context += f"[YOU CHANGED IT TO]: {dothis}\n"
        else:
            # For choose_reply feedback (no notthat)
            context += f"[YOU CHOSE TO POST]: {dothis}\n"

        context += "\n"

    context += "========== END EXAMPLES ==========\n"

    return context
