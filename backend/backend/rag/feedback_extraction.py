"""
Feedback extraction from user edits.

Analyzes diffs between generated and edited replies to learn user preferences,
tone shifts, and constraints for improving future reply generation.
"""
import json
from typing import Any

from backend.rag.embeddings import generate_embedding
from backend.twitter.logging import read_user_log
from backend.utlils.supabase_client import add_feedback, get_twitter_profile
from backend.utlils.utils import error, notify


async def extract_feedback_from_edit(username: str, edit_log_entry: dict[str, Any]) -> dict[str, Any] | None:
    """
    Extract learned preferences from a single edit log entry.

    Uses LLM to analyze the diff between generated and edited reply to identify:
    - Tone shifts (e.g., "confident -> uncertain", "casual -> professional")
    - Confidence shifts (e.g., "definitive -> hedged")
    - Content changes (e.g., "removed technical jargon", "added personal anecdote")
    - Constraints (e.g., "avoid medical advice", "never mention competitors")

    Args:
        username: Twitter handle of the user
        edit_log_entry: Log entry dict with action="edited" and metadata

    Returns:
        Extracted feedback dict or None if extraction fails

    Raises:
        Does not raise - logs errors internally
    """
    from backend.utlils.llm import ask_llm

    try:
        metadata = edit_log_entry.get("metadata", {})

        # Extract required fields
        new_reply = metadata.get("new_reply")
        diff = metadata.get("diff")
        cache_id = metadata.get("cache_id")

        if not new_reply or not diff:
            notify(f"⚠️ Edit log entry missing new_reply or diff, skipping feedback extraction")
            return None

        # Get original tweet context from cache
        from backend.data.twitter.edit_cache import read_from_cache

        tweets = await read_from_cache(username)
        original_tweet = None

        for tweet in tweets:
            if tweet.get("cache_id") == cache_id:
                original_tweet = tweet
                break

        if not original_tweet:
            notify(f"⚠️ Could not find original tweet for cache_id {cache_id}, skipping")
            return None

        # Build context for LLM analysis
        thread = original_tweet.get("thread", [])
        if isinstance(thread, list):
            original_tweet_text = " | ".join(thread)
        else:
            original_tweet_text = str(thread)

        # Build LLM prompt for feedback extraction
        system_prompt = """You are analyzing how a user edited an AI-generated reply to extract their implicit preferences.

Given:
1. The original tweet they were replying to
2. The diff showing what changed (- = removed, + = added)

Extract the user's implicit preferences as JSON with these fields:
{
  "tone_shift": "describe tone change (e.g., 'formal->casual', 'confident->uncertain', 'neutral->enthusiastic')",
  "confidence_shift": "describe confidence change (e.g., 'definitive->hedged', 'certain->questioning')",
  "content_changes": ["list key content modifications (e.g., 'removed technical jargon', 'added empathy', 'shortened length')"],
  "constraints": ["list inferred rules/constraints (e.g., 'avoid absolute statements', 'prefer questions over assertions', 'keep under 280 chars')"],
  "summary": "one-sentence summary of the core preference being expressed"
}

Focus on generalizable patterns, not tweet-specific details. If a field doesn't apply, use empty string or empty array.

Respond with ONLY the JSON, no explanation."""

        user_prompt = f"""Original tweet being replied to:
{original_tweet_text}

Diff (- = original, + = edited):
{diff}

Extract the user's preferences as JSON:"""

        # Call LLM for analysis
        response = await ask_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model="chatgpt-4o-mini",  # Use cheaper model for extraction
            username=username,
            prompt_type="FEEDBACK_EXTRACTION"
        )

        if "error" in response:
            error(
                f"LLM feedback extraction failed: {response['error']}",
                status_code=500,
                function_name="extract_feedback_from_edit",
                username=username,
                critical=False
            )
            return None

        # Parse extracted rules from LLM response
        try:
            import re

            message = response["message"]

            # Try to extract JSON from response
            # Look for JSON object pattern
            match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', message, re.DOTALL)
            if match:
                extracted_rules = json.loads(match.group(0))
            else:
                # Try parsing entire response as JSON
                extracted_rules = json.loads(message)

            # Validate required fields exist
            if not isinstance(extracted_rules, dict):
                notify(f"⚠️ LLM returned non-dict response for feedback extraction")
                return None

            # Get user_id for database storage
            profile = get_twitter_profile(username)
            if not profile:
                error(f"Profile not found for {username}", status_code=404, function_name="extract_feedback_from_edit", username=username, critical=False)
                return None

            user_id = profile.get("user_id")

            # Generate embedding for the original tweet context (trigger context)
            notify(f"🔢 Generating embedding for feedback trigger context")
            trigger_embedding = await generate_embedding(original_tweet_text, username=username)

            # Extract before/after for contrastive learning
            # Parse diff to get old and new versions
            old_lines = []
            new_lines = []

            for line in diff.split("\n"):
                line = line.strip()
                if line.startswith("- "):
                    old_lines.append(line[2:])
                elif line.startswith("+ "):
                    new_lines.append(line[2:])

            notthat = " ".join(old_lines) if old_lines else None
            dothis = " ".join(new_lines) if new_lines else new_reply

            # Store feedback in database
            feedback_data = {
                "user_id": user_id,
                "feedback_type": "edit",
                "dothis": dothis,
                "notthat": notthat,
                "trigger_context": original_tweet_text,
                "trigger_embedding": trigger_embedding,
                "extracted_rules": extracted_rules,
                "source_action": "edited"
            }

            result = add_feedback(**feedback_data)

            notify(f"✅ Extracted feedback from edit: {extracted_rules.get('summary', 'no summary')}")

            return result

        except json.JSONDecodeError as e:
            error(
                f"Failed to parse LLM feedback extraction JSON: {e}",
                status_code=500,
                exception_text=str(e),
                function_name="extract_feedback_from_edit",
                username=username,
                critical=False
            )
            notify(f"⚠️ LLM response for feedback: {message[:200]}")
            return None

    except Exception as e:
        error(
            f"Feedback extraction failed: {e}",
            status_code=500,
            exception_text=str(e),
            function_name="extract_feedback_from_edit",
            username=username,
            critical=False
        )
        return None


async def process_unprocessed_edits(username: str, limit: int = 10) -> int:
    """
    Process recent edit log entries to extract feedback.

    Background job to extract feedback from recent edits that haven't been
    processed yet. This is called periodically or after a user posts a reply.

    Args:
        username: Twitter handle of the user
        limit: Maximum number of edits to process

    Returns:
        Number of feedback entries successfully extracted
    """
    try:
        # Read recent log entries
        log_entries = read_user_log(username, limit=limit * 3)  # Read more to filter

        # Filter to only edited entries
        edit_entries = [entry for entry in log_entries if entry.get("action") == "edited"]

        if not edit_entries:
            notify(f"No edit entries found for {username}")
            return 0

        # Limit to most recent N edits
        edit_entries = edit_entries[:limit]

        notify(f"📝 Processing {len(edit_entries)} edit entries for feedback extraction")

        extracted_count = 0

        for entry in edit_entries:
            # Check if we've already processed this edit
            # (we could track this in feedback table with source metadata)
            # For now, just process all recent edits

            result = await extract_feedback_from_edit(username, entry)

            if result:
                extracted_count += 1

        notify(f"✅ Extracted {extracted_count}/{len(edit_entries)} feedback entries from edits")

        return extracted_count

    except Exception as e:
        error(
            f"Failed to process unprocessed edits: {e}",
            status_code=500,
            exception_text=str(e),
            function_name="process_unprocessed_edits",
            username=username,
            critical=False
        )
        return 0


# Example usage / testing
if __name__ == "__main__":
    import asyncio

    async def test_feedback_extraction():
        # Mock edit log entry
        mock_entry = {
            "action": "edited",
            "timestamp": "2024-01-01T12:00:00Z",
            "tweet_id": "123456789",
            "username": "test_user",
            "metadata": {
                "cache_id": "test-cache-id-123",
                "reply_index": 0,
                "model": "claude-3-5-sonnet",
                "new_reply": "I'm not sure that's entirely correct, but it's an interesting perspective!",
                "diff": "- That's completely wrong!\n+ I'm not sure that's entirely correct, but it's an interesting perspective!",
                "replying_to_tweet_id": "987654321"
            }
        }

        print("Testing feedback extraction with mock edit entry...")
        result = await extract_feedback_from_edit("test_user", mock_entry)

        if result:
            print(f"✅ Feedback extracted successfully")
            print(f"   Extracted rules: {result.get('extracted_rules')}")
        else:
            print(f"❌ Feedback extraction failed")

    asyncio.run(test_feedback_extraction())
