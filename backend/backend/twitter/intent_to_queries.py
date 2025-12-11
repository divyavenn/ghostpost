import asyncio
import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.config import OBELISK_KEY
from backend.twitter.filtering import ask_llm
from backend.utlils.utils import error, notify, read_user_info, write_user_info


class SearchPlan(BaseModel):
    """Structured search plan for Twitter query generation."""
    topics: list[str]  # Main topics to search for
    entities: list[str]  # Specific entities (companies, funds, etc.)
    must: list[str]  # Required terms
    should: list[str]  # Optional terms (synonyms, hashtags)
    negatives: list[str]  # Terms to exclude


async def generate_queries_from_intent(intent: str, username: str) -> list[tuple[str, str]]:
    """
    Generate Twitter search queries with summaries from user intent.

    Returns:
        List of tuples (query, summary) where:
        - query: Full Twitter search query with operators
        - summary: 1-2 word description for display
    """
    if not intent or not intent.strip():
        notify(f"⚠️ No intent provided for {username}, skipping query generation")
        return []

    if not OBELISK_KEY:
        error("OBELISK_KEY not configured", status_code=500, function_name="generate_queries_from_intent", username=username, critical=False)
        return []

    # Create comprehensive prompt for LLM
    system_prompt = "You are a Twitter search query expert. Always return valid JSON."
    prompt = f"""Given a user's intent, generate 5-8 optimized Twitter search queries WITH short summaries.

        User Intent: "{intent}"

        For each query, consider:
        1. **Topics**: Main themes and subjects
        2. **Entities**: Specific organizations, funds, companies, communities
        3. **Must-have terms**: Required keywords that must appear
        4. **Should-have terms**: Synonyms, hashtags, related terms (optional but helpful)
        5. **Negatives**: Spam terms, irrelevant content to exclude
        6. **Author types**: Who typically tweets about this (VCs, founders, engineers, etc.)

        Generate queries that are:
        - Specific enough to filter noise
        - Broad enough to catch relevant content
        - Using Twitter search operators correctly
        - Focused on high-quality discussions

        Return a JSON array of objects. Each object should have:
        - "query": Full Twitter search query with operators
        - "summary": 1-2 word description (e.g., "Seed Funding", "YC Startups", "Tech Hiring")

        Query syntax to use:
        - Use quotes for exact phrases: "raising seed"
        - Use OR for alternatives: (VC OR "venture capital")
        - Use - to exclude: -giveaway -crypto
        - Include filters: -filter:links -filter:replies lang:en

        Example format:
        [
        {{"query": "early stage startup (founder OR founding) (hiring OR recruiting) -filter:links -filter:replies lang:en", "summary": "Tech Hiring"}},
        {{"query": "pre-seed OR preseed (raising OR fundraising) -giveaway -crypto -filter:links lang:en", "summary": "Seed Funding"}},
        {{"query": "YC OR \\"Y Combinator\\" (batch OR portfolio) -filter:replies lang:en", "summary": "YC Startups"}}
        ]

        Generate queries now as a JSON array:"""

    try:
        notify(f"🤖 [Intent→Queries] Generating queries for {username}...")

        message = ask_llm(system_prompt, prompt).strip()
        print(message)

        # Try to extract JSON array from response
        # Handle cases where LLM adds markdown code blocks
        if "```json" in message:
            message = message.split("```json")[1].split("```")[0].strip()
        elif "```" in message:
            message = message.split("```")[1].split("```")[0].strip()

        queries_data = json.loads(message)

        if not isinstance(queries_data, list):
            error(f"LLM returned non-list response: {type(queries_data)}", status_code=500, function_name="generate_queries_from_intent", username=username, critical=False)
            return []

        # Convert to list of tuples (query, summary)
        queries = []
        for item in queries_data:
            if isinstance(item, dict) and "query" in item and "summary" in item:
                query = item["query"].strip()
                summary = item["summary"].strip()
                if query and summary:
                    queries.append((query, summary))
            elif isinstance(item, str):
                # Fallback: if LLM returns just strings, generate simple summary
                query = item.strip()
                if query:
                    # Extract first 1-2 meaningful words as summary
                    words = [w for w in query.split() if not w.startswith('-') and not w.startswith('(')]
                    summary = ' '.join(words[:2]) if words else "Query"
                    queries.append((query, summary))

        notify(f"✅ [Intent→Queries] Generated {len(queries)} queries with summaries for {username}")

        return queries

    except json.JSONDecodeError as e:
        error(f"Failed to parse LLM response as JSON: {e}", status_code=500, function_name="generate_queries_from_intent", username=username, critical=False)
        return []
    except Exception as e:
        error(f"Error generating queries from intent: {e}", status_code=500, function_name="generate_queries_from_intent", username=username, critical=False)
        return []


router = APIRouter(prefix="/intent", tags=["intent"])


class UpdateIntentRequest(BaseModel):
    intent: str


async def _generate_and_update_queries_background(username: str, intent: str):
    """Background task to generate queries from intent and update user settings."""
    try:
        notify(f"🔄 [Background] Generating queries from intent for {username}...")

        # Generate queries from intent
        queries = await generate_queries_from_intent(intent, username)

        if not queries:
            notify(f"⚠️ [Background] No queries generated for {username}")
            return

        # Update user info with new queries
        user_info = read_user_info(username)
        if not user_info:
            error(f"User info not found for {username}", status_code=404, function_name="_generate_and_update_queries_background", username=username, critical=False)
            return

        # Update intent and queries (convert tuples to lists for JSON serialization)
        user_info["intent"] = intent
        user_info["queries"] = [list(q) for q in queries]  # Convert tuples to lists
        write_user_info(user_info)

        notify(f"✅ [Background] Updated {username} with {len(queries)} new queries")

    except Exception as e:
        error(f"Error in background query generation: {e}", status_code=500, function_name="_generate_and_update_queries_background", username=username, critical=False)


@router.post("/{username}/update")
async def update_intent_endpoint(username: str, payload: UpdateIntentRequest):
    try:
        notify(f"📝 [Intent] Received intent update for {username}")

        # Read user info
        user_info = read_user_info(username)
        if not user_info:
            raise HTTPException(status_code=404, detail=f"User {username} not found")

        # Update intent immediately and clear examples (they're no longer relevant to new intent)
        user_info["intent"] = payload.intent
        user_info["intent_filter_examples"] = []  # Clear examples when intent changes
        write_user_info(user_info)

        notify(f"✅ [Intent] Updated intent for {username} (cleared filter examples)")

        # Schedule query generation in background with asyncio.create_task
        asyncio.create_task(_generate_and_update_queries_background(username, payload.intent))

        return {"message": "Intent updated. Queries are being generated in background.", "intent": payload.intent, "background_task": "query_generation_scheduled"}

    except Exception as e:
        notify(f"❌ [Intent] Error updating intent for {username}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating intent: {str(e)}") from e
