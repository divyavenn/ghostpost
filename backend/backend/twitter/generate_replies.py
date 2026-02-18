import asyncio
import os
from typing import Any

from dotenv import load_dotenv
from fastapi import APIRouter
from pydantic import BaseModel, ValidationError

from backend.config import DIVYA_API_KEY
from backend.data.twitter.data_validation import ScrapedTweet

from ..browser_automation.twitter.timeline import USERNAME
from ..utlils.utils import error, notify, read_user_info

try:
    from backend.utlils.resolve_imports import ensure_standalone_imports
except ModuleNotFoundError:  # Running from inside backend/
    from backend.utlils.resolve_imports import ensure_standalone_imports

# NOTE: Status tracking is now handled by job_status in twitter_jobs.py

ensure_standalone_imports(globals())

# Load environment variables from .env file
# Load .env from backend/ directory (one level up from backend/backend/)
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# Import prompt builders from dedicated module
from backend.twitter.reply_prompt_builder import get_prompt_builder

# Prompt variants to randomly choose from during generation
# Options: "original", "toned_down", "minimal"
# Set to a single item to use only that variant, or multiple for A/B testing
ACTIVE_PROMPT_VARIANTS = ["toned_down", "original"]


async def build_reply_examples_context(username: str, tweet_thread: str | list[str] = "", target_account: str | None = None, limit: int = 10) -> str:
    """
    Build a formatted string of example replies for the LLM prompt.

    If RAG retrieval is enabled for the user, uses semantic search to find
    relevant memories and learned preferences. Otherwise, falls back to
    engagement-score-based example selection.

    Args:
        username: User's handle
        tweet_thread: The tweet/thread being replied to (for RAG semantic search)
        target_account: Handle of account being replied to (prioritize replies to them)
        limit: Maximum number of examples to include

    Returns:
        Formatted string with examples or empty string if none
    """
    from backend.utlils.supabase_client import get_twitter_profile, log_activity

    # HYBRID APPROACH:
    # 1. First get replies to same account (simple DB query, no RAG)
    # 2. Then get topic-relevant examples (RAG semantic search)
    from backend.data.twitter.posted_tweets_cache import build_examples_from_posts, get_replies_to_account, get_top_posts_by_type

    context_parts = []

    # Part 1: Account-based examples (no RAG needed)
    if target_account:
        notify(f"📋 Getting replies to @{target_account} (DB query, no RAG)")
        same_account_replies = get_replies_to_account(username, target_account, min(5, limit))

        if same_account_replies:
            account_context = build_examples_from_posts(same_account_replies, title=f"Past replies to @{target_account}")
            if account_context:
                context_parts.append(account_context)
                notify(f"✅ Found {len(same_account_replies)} past replies to @{target_account}")

    # Part 2: Topic-based examples (RAG semantic search)
    if tweet_thread:
        try:
            from backend.rag.retrieval import retrieve_context_for_reply

            notify(f"🔍 RAG semantic search for topic-relevant examples")

            rag_context = await retrieve_context_for_reply(
                username=username,
                tweet_thread=tweet_thread,
                target_account=None,  # Don't filter by account in RAG (that's part 1)
                max_memories=limit,
                max_feedback=5
            )

            # Log retrieval metrics
            log_activity(
                handle=username,
                action="rag_retrieval",
                tweet_id=None,
                metadata={
                    "memory_count": rag_context["memory_count"],
                    "feedback_count": rag_context["feedback_count"],
                    "avg_similarity": rag_context["avg_similarity"],
                    "retrieval_time_ms": rag_context["retrieval_time_ms"]
                }
            )

            if rag_context["context_string"]:
                notify(f"✅ RAG found: {rag_context['memory_count']} memories, {rag_context['feedback_count']} feedback")
                context_parts.append(rag_context["context_string"])

        except Exception as e:
            error(
                f"RAG retrieval failed: {e}",
                status_code=500,
                exception_text=str(e),
                function_name="build_reply_examples_context",
                username=username,
                critical=False
            )

    # Combine both parts
    if context_parts:
        combined = "\n\n".join(context_parts)
        combined += "\n\n========== NOW WRITE A REPLY TO THIS TWEET ==========\n"
        return combined

    # Fall back to engagement-based if both failed
    from backend.data.twitter.posted_tweets_cache import build_examples_from_posts, get_replies_to_account, get_top_posts_by_type

    same_account_replies = []
    other_replies = []

    # First: try to get replies to the same account
    if target_account:
        same_account_replies = get_replies_to_account(username, target_account, limit)
        notify(f"📝 Found {len(same_account_replies)} previous replies to @{target_account}")

    # Second: get top-performing replies to other people (avoid duplicates)
    remaining_slots = limit - len(same_account_replies)
    if remaining_slots > 0:
        top_replies = get_top_posts_by_type(username, "reply", limit + len(same_account_replies))
        same_account_ids = {r.get("id") for r in same_account_replies}

        for reply in top_replies:
            if reply.get("id") not in same_account_ids:
                other_replies.append(reply)
                if len(other_replies) >= remaining_slots:
                    break

    # Build examples for each category
    same_account_examples = build_examples_from_posts(same_account_replies, "reply")
    other_examples = build_examples_from_posts(other_replies, "reply")

    if not same_account_examples and not other_examples:
        return ""

    # Use clear boundaries so the model doesn't confuse examples with the actual tweet
    context = "\n\n========== EXAMPLES OF YOUR PAST REPLIES (for reference only) ==========\n"

    # Section 1: Replies to this specific user
    if same_account_examples:
        context += f"\nPast replies to @{target_account}:\n"
        for i, example in enumerate(same_account_examples, 1):
            context += f"\nExample {i}:\n{example}\n"

    # Section 2: Top-performing replies to other people
    if other_examples:
        context += "\nTop-performing replies to other people:\n"
        for i, example in enumerate(other_examples, 1):
            context += f"\nExample {i}:\n{example}\n"

    context += "\n========== END EXAMPLES ==========\n"
    context += "\n========== NOW WRITE A REPLY TO THIS TWEET ==========\n"

    return context


async def ask_model(prompt: str, image_urls: list[str] = None, model: str = "nakul-1", target_handle: str | None = None, prompt_variant: str = "toned_down", username: str = "unknown") -> dict:
    """Generate a tweet reply using the unified LLM caller with Claude fallback."""
    from backend.utlils.llm import ask_llm, ask_claude

    # Build system prompt personalized with target handle using specified variant
    prompt_builder = get_prompt_builder(prompt_variant)
    system_prompt = prompt_builder(target_handle)

    # If no model specified, use Claude directly (user has no model configured)
    if not model or model == "":
        notify(f"ℹ️ No model configured, using Claude")
        return await ask_claude(
            system_prompt=system_prompt,
            user_prompt=prompt,
            model="claude-opus-4-5-20251101",
            image_urls=image_urls,
            username=username,
            prompt_type="TWEET REPLY"
        )

    # Try DIVYA model (OpenAI fine-tuned) first
    response = await ask_llm(
        system_prompt=system_prompt,
        user_prompt=prompt,
        model=model,
        image_urls=image_urls,
        username=username,
        prompt_type="TWEET REPLY"
    )

    # If DIVYA model failed, fallback to Claude
    if "error" in response:
        notify(f"⚠️ DIVYA model failed, falling back to Claude: {response.get('error')}")
        response = await ask_claude(
            system_prompt=system_prompt,
            user_prompt=prompt,
            model="claude-opus-4-5-20251101",
            image_urls=image_urls,
            username=username,
            prompt_type="TWEET REPLY"
        )
        if "message" in response:
            notify(f"✅ Claude fallback successful")

    return response


def build_prompt(tweet: dict[str, Any] | ScrapedTweet) -> tuple[str, list[str], bool, str | None] | None:
    """
    Build a prompt for reply generation from a tweet.

    Args:
        tweet: Tweet data (dict or ScrapedTweet model)

    Returns:
        Tuple of (text_prompt, image_urls, has_quoted_tweet, tweet_id) or None if invalid
    """
    # Validate and convert to model if needed
    if isinstance(tweet, dict):
        try:
            validated_tweet = ScrapedTweet.model_validate(tweet)
        except ValidationError as e:
            tweet_id = tweet.get('id') or tweet.get('tweet_id')
            # Build detailed error message showing which fields are missing
            missing_fields = []
            for err in e.errors():
                # Show full path for nested fields (e.g., scraped_from.type)
                loc = err.get('loc', ['unknown'])
                field = '.'.join(str(x) for x in loc)
                msg = err.get('msg', 'unknown error')
                missing_fields.append(f"{field}: {msg}")
            error_detail = "; ".join(missing_fields)
            notify(f"⚠️ Tweet {tweet_id} validation failed: {error_detail}")
            notify(f"   Tweet data keys: {list(tweet.keys())}")
            return None
    else:
        validated_tweet = tweet

    tweet_id = validated_tweet.id

    # Check thread content
    if not validated_tweet.thread:
        notify(f"⚠️ Tweet {tweet_id} has no thread content, skipping")
        return None

    # Build structured text prompt
    text_prompt = ""
    image_urls: list[str] = []

    # Extract quoted tweet info
    has_quoted = bool(validated_tweet.quoted_tweet and validated_tweet.quoted_tweet.text)

    if has_quoted:
        qt = validated_tweet.quoted_tweet
        text_prompt += f"[QUOTED TWEET by @{qt.author_handle} ({qt.author_name})]\n"
        text_prompt += f"{qt.text}\n"

        # Add QT images first
        qt_images = [item.url for item in qt.media if item.type == 'photo']
        if qt_images:
            image_urls.extend(qt_images)
            text_prompt += f"[This quoted tweet contains {len(qt_images)} image(s)]\n"

        text_prompt += "\n---\n\n"

    # Add main tweet/thread
    display_name = validated_tweet.username or validated_tweet.handle or "User"
    if has_quoted:
        text_prompt += f"[{display_name}'s RESPONSE]\n"

    text_prompt += str(validated_tweet.thread)

    # Add main tweet images
    main_images = [item.url for item in validated_tweet.media if item.type == 'photo']
    if main_images:
        image_urls.extend(main_images)
        if has_quoted:
            text_prompt += f"\n[Response contains {len(main_images)} image(s)]"

    # Add alt text context if available
    alt_texts: list[str] = []
    if validated_tweet.quoted_tweet:
        alt_texts.extend([item.alt_text for item in validated_tweet.quoted_tweet.media if item.alt_text])
    alt_texts.extend([item.alt_text for item in validated_tweet.media if item.alt_text])
    if alt_texts:
        text_prompt += f"\n\n[Image descriptions: {'; '.join(alt_texts)}]"

    # Add other replies context (top 5)
    if validated_tweet.other_replies:
        text_prompt += "\n\n---\n\n[TOP REPLIES FROM OTHERS]\n"
        for reply in validated_tweet.other_replies[:5]:
            text_prompt += f"\n@{reply.author_handle} ({reply.author_name}) - {reply.likes} likes:\n{reply.text}\n"

    return text_prompt, image_urls, has_quoted, tweet_id


def _save_prompt_to_file(prompt: str, tweet_id: str, model: str, variant: str, username: str, examples_context: str = ""):
    """Save prompt to debug file if LOG_PROMPTS is enabled."""
    from backend.config import LOG_PROMPTS, PROMPTS_LOG_DIR
    from datetime import datetime

    if not LOG_PROMPTS:
        return

    try:
        # Create prompts directory if it doesn't exist
        PROMPTS_LOG_DIR.mkdir(parents=True, exist_ok=True)

        # Create filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{username}_{tweet_id}_{model.replace('/', '_')}_{variant}.txt"
        filepath = PROMPTS_LOG_DIR / filename

        # Write prompt with metadata
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"=== PROMPT LOG ===\n")
            f.write(f"Timestamp: {datetime.now().isoformat()}\n")
            f.write(f"Username: {username}\n")
            f.write(f"Tweet ID: {tweet_id}\n")
            f.write(f"Model: {model}\n")
            f.write(f"Variant: {variant}\n")
            f.write(f"\n{'='*80}\n")
            f.write(f"=== EXAMPLES CONTEXT ({len(examples_context)} chars) ===\n")
            f.write(f"{'='*80}\n\n")
            f.write(examples_context if examples_context else "(No examples context)\n")
            f.write(f"\n{'='*80}\n")
            f.write(f"=== FULL PROMPT ===\n")
            f.write(f"{'='*80}\n\n")
            f.write(prompt)

        notify(f"📝 Logged prompt to: {filepath.name}")
    except Exception as e:
        notify(f"⚠️ Failed to log prompt: {e}")


async def generate_replies_for_tweet(
    tweet: dict[str, Any] | ScrapedTweet,
    models: list[str],
    needed_generations: int,
    delay_seconds: float = 1,
    batch: bool = False,
    username: str = "unknown"
) -> list[tuple[str, str, str]]:
    """
    Generate AI replies for a single tweet.

    Args:
        tweet: Tweet data (dict or validated TweetForGeneration)
        models: List of model names to use for generation
        needed_generations: Number of replies to generate
        delay_seconds: Delay between API calls
        batch: If True, don't raise critical errors (batch processing mode)
        username: Username for logging

    Returns:
        List of (reply_text, model_name, prompt_variant) tuples
    """
    import random

    replies: list[tuple[str, str, str]] = []

    if needed_generations <= 0:
        return replies

    # Build prompt (includes validation)
    prompt_result = build_prompt(tweet)
    if prompt_result is None:
        return []

    text_prompt, image_urls, has_quoted_tweet, tweet_id = prompt_result

    # Extract target account (who we're replying to) for example selection
    target_account = None
    if isinstance(tweet, dict):
        target_account = tweet.get("handle") or tweet.get("username")
    else:
        target_account = getattr(tweet, "handle", None) or getattr(tweet, "username", None)

    # Get tweet thread text for RAG semantic search
    tweet_thread_text = ""
    if isinstance(tweet, dict):
        tweet_thread_text = tweet.get("thread", "")
    else:
        tweet_thread_text = getattr(tweet, "thread", "")

    # Add examples context to the prompt (prioritizes replies to same account)
    # If RAG is enabled, this will use semantic search; otherwise, engagement scores
    examples_context = await build_reply_examples_context(
        username,
        tweet_thread=tweet_thread_text,
        target_account=target_account
    )
    if examples_context:
        text_prompt = examples_context + "\n" + text_prompt

    for gen_idx in range(needed_generations):
        # Model selection logic:
        # - If fewer models than replies: cycle through models
        # - If more models than replies: randomly select a model for each reply
        if len(models) < needed_generations:
            selected_model = models[gen_idx % len(models)]
        else:
            selected_model = random.choice(models)

        # Prompt variant selection (same logic as model selection)
        if len(ACTIVE_PROMPT_VARIANTS) < needed_generations:
            selected_variant = ACTIVE_PROMPT_VARIANTS[gen_idx % len(ACTIVE_PROMPT_VARIANTS)]
        else:
            selected_variant = random.choice(ACTIVE_PROMPT_VARIANTS)

        if image_urls:
            notify(f"🤖 Generating reply {gen_idx+1} for {tweet_id} using {selected_model} [{selected_variant}] with {len(image_urls)} image(s)...")
        else:
            notify(f"🤖 Generating reply {gen_idx+1} for {tweet_id} using {selected_model} [{selected_variant}]...")

        # Log prompt to file if debugging is enabled
        _save_prompt_to_file(text_prompt, tweet_id, selected_model, selected_variant, username, examples_context or "")

        # Pass target handle and prompt variant for personalized system prompt
        response = await ask_model(
            prompt=text_prompt,
            model=selected_model,
            image_urls=image_urls,
            target_handle=target_account,
            prompt_variant=selected_variant,
            username=username
        )

        reply = response.get('message', '')
        if reply:
            replies.append((reply, selected_model, selected_variant))
            notify(f"✅ Generated reply {gen_idx+1} for tweet {tweet_id}")
        else:
            error_msg = response.get('error', 'Unknown error')
            error(
                f"⚠️ Empty reply received for generation {gen_idx+1} of tweet {tweet_id}: {error_msg}",
                status_code=500,
                function_name="generate_replies_for_tweet",
                username=username,
                critical=(not batch)
            )

        # Delay between generations to avoid rate limiting
        if gen_idx < needed_generations - 1:
            await asyncio.sleep(delay_seconds)

    return replies


async def generate_replies(username=USERNAME, delay_seconds=1, overwrite=False):
    from backend.data.twitter.edit_cache import purge_empty_thread_tweets, read_from_cache, write_to_cache
    from backend.config import GEMINI_API_KEY

    # Check if at least one API key is configured
    if not DIVYA_API_KEY and not GEMINI_API_KEY:
        error("❌ Neither DIVYA_API_KEY nor GEMINI_API_KEY environment variable is set", status_code=500, function_name="generate_replies_endpoint", username=username, critical=True)

    # Purge tweets with empty thread content from cache and seen_tweets
    # so they can be re-scraped with proper thread data
    purged_count = await purge_empty_thread_tweets(username)
    if purged_count > 0:
        notify(f"🧹 Purged {purged_count} tweet(s) with empty thread before generating replies")

    tweets = await read_from_cache(username=username)
    user_info = read_user_info(username)

    # Get models array - if not configured, use None to trigger Gemini
    models = user_info["models"] if "models" in user_info and user_info["models"] else [None]
    number_of_generations = user_info["number_of_generations"] if "number_of_generations" in user_info else 1

    if not tweets:
        notify("⚠️ No tweets found in cache")
        return []

    notify(f"📝 Processing {len(tweets)} tweets for user {username} using models: {models}...")
    count = 0
    skipped = 0
    errors = 0
    total_to_process = len([t for t in tweets if not (('generated_replies' in t and t['generated_replies']) and not overwrite) and ('thread' in t and t['thread'])])

    for tweet in tweets:
        needed_generations = number_of_generations - len(tweet.get('generated_replies', []))
        if overwrite:
            needed_generations = number_of_generations

        if needed_generations <= 0:
            skipped += 1
            continue

        if 'thread' not in tweet or not tweet['thread']:
            tweet_id = tweet.get('id', tweet.get('tweet_id', 'unknown'))
            notify(f"⚠️ Tweet {tweet_id} has no thread content, skipping")
            skipped += 1
            continue

        # Generate replies using the reusable function
        try:
            replies = await generate_replies_for_tweet(tweet, models, needed_generations, delay_seconds, batch=True, username=username)

            # Store all replies as array of tuples (reply_text, model_name)
            if replies:
                if overwrite:
                    # Replace all replies
                    tweet['generated_replies'] = replies
                else:
                    # Append new replies to existing ones
                    existing_replies = tweet.get('generated_replies', [])
                    tweet['generated_replies'] = existing_replies + replies

                count += 1
                tweet_id = tweet.get('id', tweet.get('tweet_id', 'unknown'))
                notify(f"✅ Generated {len(replies)} replies for tweet {tweet_id}")

                # Progressive write: save immediately after generating all replies
                await write_to_cache([tweet], f"Generated {len(replies)} replies for tweet {tweet_id}", username=username)
            else:
                tweet_id = tweet.get('id', tweet.get('tweet_id', 'unknown'))
                notify(f"⚠️ No replies generated for tweet {tweet_id}")
                errors += 1

            await asyncio.sleep(delay_seconds)

        except Exception as e:
            tweet_id = tweet.get('id', tweet.get('tweet_id', 'unknown'))
            error(f"❌ Exception generating replies for tweet {tweet_id}: {e}", status_code=500, exception_text=str(e), function_name="generate_replies", username=username, critical=False)
            errors += 1

    if errors > 0:
        error(f"{errors} errors batch-generating replies for tweets", status_code=500, function_name="generate_replies", username=username, critical=True)

    notify(f"✅ Done! Generated: {count}, Skipped: {skipped}, Errors: {errors}")

    return tweets


async def run_all() -> None:
    # Directly process trending_cache.json with hardcoded parameters
    #await read_tweets()
    await generate_replies()

    notify("Done!")


# API Router
router = APIRouter(prefix="/generate", tags=["generate"])


class GenerateRepliesRequest(BaseModel):
    delay_seconds: int = 1
    overwrite: bool = False


class GeneratePostRequest(BaseModel):
    """Request model for generating a recommendation post about a resource."""
    title: str
    author: str | None = None
    publishDate: str | None = None
    url: str | None = None
    contentType: str = "pdf"  # pdf, article, video, podcast, book, etc.
    textSample: str | None = None  # optional sample text from the resource


@router.post("/{username}/replies")
async def generate_replies_endpoint(username: str, payload: GenerateRepliesRequest | None = None) -> dict:
    """Generate AI replies for tweets in the cache."""
    try:
        if payload is None:
            tweets = await generate_replies(username=username)
        else:
            tweets = await generate_replies(username=username, delay_seconds=payload.delay_seconds, overwrite=payload.overwrite)

        # Count tweets with replies
        reply_count = sum(1 for t in tweets if t.get('replies'))

        return {"message": "Replies generated successfully", "total_tweets": len(tweets), "replies_generated": reply_count}
    except Exception as e:
        error("Error generating replies", status_code=500, exception_text=str(e), function_name="generate_replies_endpoint", username=username)


@router.post("/{username}/replies/{tweet_id}")
async def regenerate_single_reply_endpoint(username: str, tweet_id: str) -> dict:
    """Regenerate AI reply for a single tweet."""
    from backend.data.twitter.edit_cache import read_from_cache, write_to_cache
    from backend.config import GEMINI_API_KEY

    # Check if at least one API key is configured
    if not DIVYA_API_KEY and not GEMINI_API_KEY:
        error("Neither DIVYA nor Gemini API key configured", status_code=500, function_name="regenerate_single_reply_endpoint", username=username, critical=True)

    # Read tweets from cache
    tweets = await read_from_cache(username=username)
    user_info = read_user_info(username)
    # If models not configured, use None to trigger Gemini
    models = user_info["models"] if "models" in user_info and user_info["models"] else [None]
    number_of_generations = user_info["number_of_generations"] if "number_of_generations" in user_info else 1

    if not tweets:
        error("No tweets found in cache", status_code=404, function_name="regenerate_single_reply_endpoint", username=username, critical=True)

    # Find the specific tweet
    tweet = None
    for t in tweets:
        if ('id' in t and t['id'] == tweet_id) or ('tweet_id' in t and t['tweet_id'] == tweet_id):
            tweet = t
            break

    if not tweet:
        error("Tweet not found in cache", status_code=404, function_name="regenerate_single_reply_endpoint", username=username, critical=True)

    # Check if tweet has thread content before generating
    if 'thread' not in tweet or not tweet['thread']:
        error(f"Tweet {tweet_id} has no thread content - cannot generate reply. Try re-scraping this tweet.", status_code=400, function_name="regenerate_single_reply_endpoint", username=username, critical=True)

    # Generate replies using the reusable function
    replies = await generate_replies_for_tweet(
        tweet=tweet,
        models=models,
        needed_generations=number_of_generations,
        delay_seconds=0,  # No delay for single tweet regeneration
        username=username
    )

    if not replies:
        error(f"Failed to generate replies for tweet {tweet_id} - LLM returned empty response. Check API credentials and rate limits.", status_code=500, function_name="regenerate_single_reply_endpoint", username=username, critical=True)

    # Store all regenerated replies as array of tuples (reply_text, model_name)
    tweet['generated_replies'] = replies
    await write_to_cache([tweet], f"Regenerated {len(replies)} replies for tweet {tweet_id}", username=username)

    return {"message": "Replies regenerated successfully", "tweet_id": tweet_id, "new_replies": replies}


@router.post("/{username}/post")
async def generate_post_endpoint(username: str, payload: GeneratePostRequest) -> dict:
    """
    Generate a recommendation post about a resource using RAG on memories.

    Uses the user's memories (past tweets, notes, preferences) to write a personalized
    blurb about why they liked/recommend the resource.
    """
    from backend.rag.embeddings import generate_embedding
    from backend.utlils.supabase_client import get_twitter_profile, search_memories_vector
    from backend.utlils.llm import ask_claude

    # Get user_id from username
    profile = get_twitter_profile(username)
    if not profile:
        error(
            f"Twitter profile not found for {username}",
            status_code=404,
            function_name="generate_post_endpoint",
            username=username,
            critical=True
        )
        return {"error": "Profile not found"}

    user_id = profile.get("user_id")
    if not user_id:
        error(
            f"No user_id found for profile {username}",
            status_code=500,
            function_name="generate_post_endpoint",
            username=username,
            critical=True
        )
        return {"error": "User ID not found"}

    # Build search query from resource metadata
    search_parts = [payload.title]
    if payload.author:
        search_parts.append(f"by {payload.author}")
    if payload.textSample:
        # Use a portion of the text sample for semantic search
        search_parts.append(payload.textSample[:500])

    search_query = " ".join(search_parts)

    # Generate embedding for the resource
    notify(f"🔢 Generating embedding for resource: {payload.title}")
    embedding = await generate_embedding(search_query, username=username)

    # Search memories for relevant context
    notify(f"🔍 Searching memories for relevant context")
    memories = search_memories_vector(
        user_id=user_id,
        embedding=embedding,
        limit=10,
        visibility_filter="private"
    )

    # Build context from memories
    memory_context = ""
    if memories:
        memory_context = "\n\nHere are some of your past thoughts and writings that may be relevant:\n"
        for i, mem in enumerate(memories, 1):
            content = mem.get("content", "")[:300]
            source_type = mem.get("source_type", "unknown")
            memory_context += f"\n[{source_type}] {content}\n"

    # Build the LLM prompt
    resource_info = f"Title: {payload.title}"
    if payload.author:
        resource_info += f"\nAuthor: {payload.author}"
    if payload.publishDate:
        resource_info += f"\nPublished: {payload.publishDate}"
    if payload.url:
        resource_info += f"\nURL: {payload.url}"
    resource_info += f"\nType: {payload.contentType}"

    text_sample_section = ""
    if payload.textSample:
        text_sample_section = f"\n\nExcerpt from the resource:\n\"\"\"\n{payload.textSample[:1000]}\n\"\"\""

    system_prompt = """You are helping write a short, authentic social media post recommending a resource (article, book, PDF, video, etc.).

Write in the user's voice based on their past writings provided as context. The post should:
- Be concise (1-3 sentences, under 280 characters if possible)
- Feel personal and authentic, not like a generic review
- Mention why YOU specifically found it valuable or interesting
- Avoid generic phrases like "must-read" or "game-changer"
- Sound like something you'd casually share with friends

If the context shows the user has related interests or past thoughts on similar topics, weave that connection in naturally."""

    user_prompt = f"""Write a short recommendation post for this resource:

{resource_info}{text_sample_section}{memory_context}

Write the post now (just the post text, no quotes or preamble):"""

    # Generate the post
    notify(f"🤖 Generating recommendation post for: {payload.title}")
    response = await ask_claude(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model="claude-sonnet-4-20250514",
        username=username,
        prompt_type="GENERATE_POST"
    )

    if "error" in response:
        error(
            f"Failed to generate post: {response.get('error')}",
            status_code=500,
            function_name="generate_post_endpoint",
            username=username,
            critical=True
        )
        return {"error": response.get("error")}

    post_text = response.get("message", "").strip()

    notify(f"✅ Generated post: {post_text[:100]}...")

    return {
        "post": post_text,
        "memories_used": len(memories),
        "resource_title": payload.title
    }


if __name__ == "__main__":
    asyncio.run(run_all())

    # Original example for reference
    # prompt = str([
    #   "i know life happens wherever you are, but I can't help but feel like none of this is real. Like I'm wandering from door to door, temporary home to temporary home. I want to plunge my fingers into earth I own, buy furniture too heavy to move and plant roses",
    #   "I want to walk to the nearby coffeeshop and see familiar faces. I want to take the time to get to know my neighbors, knowing that we'll both be here a few months from now",
    #   "I am so so homesick, but for a home I've never had. I thought i'd have it once. I bought the furniture, met the neighbors. But i chose somewhere I couldn't stay.",
    #   "Everything has been going well for the past few days. Many encouraging signs that I'm getting closer to my goals. and yet I'm miserable and listless. I don't want to put down roots only to dig them up.",
    #   "I don't have the people or the place to put down roots, but I can't help myself. Every room I spend more than two nights in, my mind goes to making it tidier and more cosy. It makes me sad to make those efforts and sadder not to. All I can think of is how I'll have to do it again"
    # ])
    # print(ask_model(prompt))
