"""
Generate AI replies for comments (replies from others on user's tweets).

Uses the same reply generation system as regular tweets, but with context
from the parent_chain to provide full thread context.
"""
import asyncio

from fastapi import APIRouter, Query
from pydantic import BaseModel

from backend.config import OBELISK_KEY
from backend.utlils.utils import error, notify, read_user_info

# Prompt variants for comment replies - can add more for A/B testing
# Currently only has "default" variant
ACTIVE_COMMENT_PROMPT_VARIANTS = ["default"]


def build_comment_reply_examples_context(username: str, target_account: str | None = None, limit: int = 10) -> str:
    """
    Build a formatted string of example comment replies for the LLM prompt.
    Prioritizes replies to the same commenter, then falls back to top-performing replies.

    Args:
        username: User's handle
        target_account: Handle of the commenter (prioritize replies to them)
        limit: Maximum number of examples to include

    Returns:
        Formatted string with examples or empty string if none
    """
    from backend.data.twitter.posted_tweets_cache import build_examples_from_posts, get_replies_to_account, get_top_posts_by_type

    same_account_replies = []
    other_replies = []

    # First: try to get replies to the same commenter
    if target_account:
        same_account_replies = get_replies_to_account(username, target_account, limit, post_type="comment_reply")
        if same_account_replies:
            notify(f"📝 Found {len(same_account_replies)} previous replies to @{target_account}")

    # Second: get top-performing replies to other people (avoid duplicates)
    remaining_slots = limit - len(same_account_replies)
    if remaining_slots > 0:
        top_replies = get_top_posts_by_type(username, "comment_reply", limit + len(same_account_replies))
        same_account_ids = {r.get("id") for r in same_account_replies}

        for reply in top_replies:
            if reply.get("id") not in same_account_ids:
                other_replies.append(reply)
                if len(other_replies) >= remaining_slots:
                    break

    # Build examples for each category
    same_account_examples = build_examples_from_posts(same_account_replies, "comment_reply")
    other_examples = build_examples_from_posts(other_replies, "comment_reply")

    if not same_account_examples and not other_examples:
        return ""

    context = ""

    # Section 1: Replies to this specific commenter
    if same_account_examples:
        context += f"\n\n[HOW YOU RESPOND TO @{target_account}]\n"
        for i, example in enumerate(same_account_examples, 1):
            context += f"\n--- Example {i} ---\n{example}\n"

    # Section 2: Top-performing replies to other people
    if other_examples:
        context += "\n\n[TOP-PERFORMING COMMENT REPLIES TO OTHER PEOPLE]\n"
        for i, example in enumerate(other_examples, 1):
            context += f"\n--- Example {i} ---\n{example}\n"

    context += "\n[END EXAMPLES]\n"

    return context


def build_comment_reply_system_prompt(commenter_handle: str | None = None) -> str:
    """
    Build the system prompt for comment reply generation, personalized with the commenter's handle.

    Args:
        commenter_handle: The handle of the person who commented (e.g., "rebelcrayon")

    Returns:
        System prompt with "the commenter" replaced by the actual handle
    """
    # Use handle with @ or fallback to "the commenter"
    commenter = f"@{commenter_handle}" if commenter_handle else "the commenter"
    commenter_possessive = f"@{commenter_handle}'s" if commenter_handle else "the commenter's"

    return f"""You are an expert at online conversation.
Your job is to craft a reply to {commenter} who commented on your tweet (or thread).
Your reply should be short, warm, and natural — like acknowledging a friend.


The conversation context shows:
- Your original post(s) that started this thread
- {commenter_possessive} comment you're replying to
- Any intermediate replies in the chain

If {commenter} is agreeing or complimenting you, a simple "thank you" ":)" or emoji is sufficient.

If {commenter} is sharing their own story,
new information, or asking a question,
that merits a longer response (1-3 sentences)

Key principles:
1. Acknowledge {commenter_possessive} point genuinely — don't be dismissive
2. Be conversational, not formal
3. Add value: clarify, elaborate, or build on the discussion
4. Match the energy of the comment (playful reply to playful comment, thoughtful to thoughtful)
5. Keep it brief: just an emoji for casual replies. if {commenter} compliments you, say thank you. for
 substantive replies that introduce a new idea, put in a high effort reply that matches the length of the original comment
6. Don't be defensive — even if {commenter} disagrees, engage constructively
7. Someone disparaging you for being normal, mid, or a midwit is not a critcism. most of us are average, it's not an insult.
8. If {commenter} makes a statement about your race, ethnicity, or gender, respond with "well spotted."

If the comment is:
- A question → Answer helpfully with specifics, if needed look up relevant information from the web
- A disagreement → State the strongest version of {commenter_possessive} point ("If you mean...") and then engage with that.
- A joke → laughing face emoji
- Criticism → Address it directly but not defensively

Your reply should feel natural and make {commenter} feel heard.
"""


def build_comment_prompt(comment: dict, thread_context: list[dict]) -> tuple[str, list[str]]:
    """
    Build a prompt for generating a reply to a comment.

    Args:
        comment: The comment to reply to
        thread_context: List of dicts representing the thread from root to comment

    Returns:
        Tuple of (text_prompt, image_urls)
    """
    text_prompt = ""
    image_urls = []

    # Add thread context (from root to immediate parent)
    text_prompt += "[CONVERSATION CONTEXT]\n\n"

    for i, ctx in enumerate(thread_context[:-1]):  # Exclude the comment itself
        is_user = ctx.get("is_user", False)
        handle = ctx.get("handle", "Unknown")
        text = ctx.get("text", "<deleted>")

        if ctx.get("deleted"):
            text_prompt += f"[Tweet #{i+1} - DELETED]\n\n"
            continue

        role = "YOU" if is_user else f"@{handle}"
        text_prompt += f"[{role}]:\n{text}\n\n"

    # Add the comment we're replying to
    comment_handle = comment.get("handle", "Unknown")
    comment_username = comment.get("username", comment_handle)
    comment_text = comment.get("text", "")

    text_prompt += "---\n\n"
    text_prompt += f"[COMMENT from @{comment_handle} ({comment_username})]:\n"
    text_prompt += f"{comment_text}\n"

    # Add comment engagement stats for context
    followers = comment.get("followers", 0)
    if followers > 1000:
        text_prompt += f"\n[This person has {followers:,} followers]\n"

    # Add media from comment if present
    media = comment.get("media", [])
    comment_images = [item.get("url") for item in media if item.get("type") == "photo"]
    if comment_images:
        image_urls.extend(comment_images)
        text_prompt += f"\n[Comment includes {len(comment_images)} image(s)]\n"

    # Add quoted tweet from comment if present
    quoted_tweet = comment.get("quoted_tweet")
    if quoted_tweet:
        qt_text = quoted_tweet.get("text", "")
        qt_handle = quoted_tweet.get("author_handle", "unknown")
        qt_name = quoted_tweet.get("author_name", qt_handle)
        text_prompt += f"\n[Comment quotes @{qt_handle} ({qt_name})]:\n\"{qt_text}\"\n"

        # Add quoted tweet images to context
        qt_media = quoted_tweet.get("media", [])
        qt_images = [item.get("url") for item in qt_media if item.get("type") == "photo"]
        if qt_images:
            image_urls.extend(qt_images)
            text_prompt += f"[Quoted tweet includes {len(qt_images)} image(s)]\n"

    # Add other replies context if available
    other_replies = comment.get("other_replies", [])
    if other_replies:
        text_prompt += "\n\n[OTHER REPLIES TO THIS COMMENT]\n"
        for reply in other_replies[:3]:  # Limit to 3
            r_handle = reply.get("author_handle", "unknown")
            r_text = reply.get("text", "")
            r_likes = reply.get("likes", 0)
            text_prompt += f"\n@{r_handle} ({r_likes} likes):\n{r_text}\n"

    text_prompt += "\n---\n\nWrite your reply to this comment:"

    return text_prompt, image_urls


def _print_prompt(system_prompt: str, user_prompt: str, model: str, image_count: int = 0, prompt_type: str = "REPLY"):
    """Print the full prompt to console for debugging (only if DEBUG_LOGS is enabled)."""
    from backend.utlils.utils import DEBUG_LOGS
    if not DEBUG_LOGS:
        return

    print(f"\n{'='*80}")
    print(f"🤖 {prompt_type} GENERATION PROMPT | Model: {model}")
    print(f"{'='*80}")
    print(f"\n📋 SYSTEM PROMPT:\n{'-'*40}")
    print(system_prompt)
    print(f"\n📝 USER PROMPT:\n{'-'*40}")
    print(user_prompt)
    if image_count > 0:
        print(f"\n🖼️  IMAGES: {image_count} attached")
    print(f"\n{'='*80}\n")


async def ask_model_for_comment(prompt: str, image_urls: list[str] = None, model: str = "nakul-1", commenter_handle: str | None = None, prompt_variant: str = "default", username: str = "unknown") -> dict:
    """Call the Obelisk API to generate a comment reply."""
    from backend.twitter.rate_limiter import LLM_OBELISK, call_api

    url = "https://obelisk.dread.technology/api/chat/completions"
    headers = {"Authorization": f"Bearer {OBELISK_KEY}", "Content-Type": "application/json"}

    # Build user message content
    if image_urls and len(image_urls) > 0:
        user_content = [{"type": "text", "text": prompt}]
        for img_url in image_urls:
            user_content.append({"type": "image_url", "image_url": {"url": img_url}})
    else:
        user_content = prompt

    # Build system prompt personalized with commenter handle
    # TODO: Add variant selection when more variants are available
    system_prompt = build_comment_reply_system_prompt(commenter_handle)

    # Print the full prompt to console
    _print_prompt(system_prompt, prompt, model, len(image_urls) if image_urls else 0, "COMMENT REPLY")

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]
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
        error(f"Error communicating with Obelisk API: {response.error_message}", status_code=response.status_code or 500, function_name='ask_model_for_comment', username=username, critical=False)
        return {"error": response.error_message}

    data = response.data

    try:
        message = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        return {"error": "Unexpected API response", "raw": data}

    return {"message": message}


async def generate_replies_for_comment(
    comment: dict,
    thread_context: list[dict],
    models: list[str],
    num_generations: int,
    delay_seconds: float = 1.0,
    username: str = "unknown"
) -> list[tuple[str, str, str]]:
    """
    Generate AI replies for a single comment.

    Args:
        comment: The comment dict
        thread_context: Thread context from get_thread_context()
        models: List of models to use
        num_generations: Number of replies to generate
        delay_seconds: Delay between generations
        username: Username for logging

    Returns:
        List of (reply_text, model_name, prompt_variant) tuples
    """
    import random

    replies: list[tuple[str, str, str]] = []
    comment_id = comment.get("id", "unknown")

    # Extract commenter handle for personalization
    commenter_handle = comment.get("handle") or comment.get("username")

    text_prompt, image_urls = build_comment_prompt(comment, thread_context)

    # Add examples context to the prompt (prioritizes replies to same commenter)
    examples_context = build_comment_reply_examples_context(username, target_account=commenter_handle)
    if examples_context:
        text_prompt = examples_context + "\n" + text_prompt

    for gen_idx in range(num_generations):
        # Model selection
        if len(models) < num_generations:
            selected_model = models[gen_idx % len(models)]
        else:
            selected_model = random.choice(models)

        # Prompt variant selection (same logic as model selection)
        if len(ACTIVE_COMMENT_PROMPT_VARIANTS) < num_generations:
            selected_variant = ACTIVE_COMMENT_PROMPT_VARIANTS[gen_idx % len(ACTIVE_COMMENT_PROMPT_VARIANTS)]
        else:
            selected_variant = random.choice(ACTIVE_COMMENT_PROMPT_VARIANTS)

        notify(f"🤖 Generating reply {gen_idx+1} for comment {comment_id} using {selected_model} [{selected_variant}]...")

        response = await ask_model_for_comment(
            prompt=text_prompt,
            image_urls=image_urls,
            model=selected_model,
            commenter_handle=commenter_handle,
            prompt_variant=selected_variant,
            username=username
        )

        reply = response.get('message', '')
        if reply:
            replies.append((reply, selected_model, selected_variant))
            notify(f"✅ Generated reply {gen_idx+1} for comment {comment_id}")
        else:
            error_msg = response.get('error', 'Unknown error')
            error(f"Empty reply for comment {comment_id}: {error_msg}", status_code=500, function_name="generate_replies_for_comment", username=username, critical=False)

        if gen_idx < num_generations - 1:
            await asyncio.sleep(delay_seconds)

    return replies


async def generate_comment_replies(
    username: str,
    comment_ids: list[str] | None = None,
    overwrite: bool = False,
    delay_seconds: float = 1.0
) -> dict:
    """
    Generate replies for pending comments.

    Args:
        username: User's cache key
        comment_ids: Specific comment IDs to process (None = all pending)
        overwrite: If True, regenerate even if replies exist
        delay_seconds: Delay between comments

    Returns:
        Summary dict with counts
    """
    from backend.data.twitter.comments_cache import (
        get_comment,
        get_comments_list,
        get_thread_context,
        update_comment_generated_replies,
    )

    if not OBELISK_KEY:
        error("OBELISK_KEY not configured", status_code=500, function_name="generate_comment_replies", username=username, critical=True)
        raise ValueError("OBELISK_KEY not configured")

    user_info = read_user_info(username)
    models = user_info.get("models", ["claude-3-5-sonnet-20241022"]) if user_info else ["claude-3-5-sonnet-20241022"]
    num_generations = user_info.get("number_of_generations", 2) if user_info else 2

    results = {
        "processed": 0,
        "skipped": 0,
        "errors": 0,
        "total_replies_generated": 0
    }

    # Get comments to process
    if comment_ids:
        comments = []
        for cid in comment_ids:
            comment = get_comment(username, cid)
            if comment:
                comments.append(comment)
    else:
        # Get all pending comments
        comments = get_comments_list(username, status_filter="pending")

    if not comments:
        notify(f"📝 No comments to process for @{username}")
        return results

    notify(f"📝 Processing {len(comments)} comments for @{username}")

    for comment in comments:
        comment_id = comment.get("id")

        # Skip if already has replies and not overwriting
        existing_replies = comment.get("generated_replies", [])
        if existing_replies and not overwrite:
            results["skipped"] += 1
            continue

        try:
            # Get thread context
            thread_context = get_thread_context(comment_id, username)
            if not thread_context:
                notify(f"⚠️ No thread context for comment {comment_id}")
                results["errors"] += 1
                continue

            # Generate replies
            replies = await generate_replies_for_comment(
                comment=comment,
                thread_context=thread_context,
                models=models,
                num_generations=num_generations,
                delay_seconds=delay_seconds,
                username=username
            )

            if replies:
                update_comment_generated_replies(username, comment_id, replies)
                results["processed"] += 1
                results["total_replies_generated"] += len(replies)
                notify(f"✅ Generated {len(replies)} replies for comment {comment_id}")
            else:
                results["errors"] += 1

            await asyncio.sleep(delay_seconds)

        except Exception as e:
            error(f"Error generating replies for comment {comment_id}: {e}", status_code=500, function_name="generate_comment_replies", username=username, critical=False)
            results["errors"] += 1

    notify(f"✅ Comment reply generation complete: {results['processed']} processed, {results['skipped']} skipped, {results['errors']} errors")

    return results


# API Router
router = APIRouter(prefix="/comments", tags=["comments"])


class GenerateCommentRepliesRequest(BaseModel):
    comment_ids: list[str] | None = None
    overwrite: bool = False
    delay_seconds: float = 1.0


@router.post("/{username}/generate")
async def generate_comment_replies_endpoint(
    username: str,
    payload: GenerateCommentRepliesRequest | None = None
) -> dict:
    """Generate AI replies for pending comments."""
    try:
        if payload is None:
            result = await generate_comment_replies(username=username)
        else:
            result = await generate_comment_replies(
                username=username,
                comment_ids=payload.comment_ids,
                overwrite=payload.overwrite,
                delay_seconds=payload.delay_seconds
            )

        return {
            "message": "Comment reply generation complete",
            **result
        }
    except Exception as e:
        error(f"Error generating comment replies: {e}", status_code=500, function_name="generate_comment_replies_endpoint", username=username, critical=True)


class EditCommentReplyRequest(BaseModel):
    new_reply: str
    reply_index: int = 0


@router.patch("/{username}/{comment_id}/edit")
async def edit_comment_reply_endpoint(
    username: str,
    comment_id: str,
    payload: EditCommentReplyRequest
) -> dict:
    """Edit a generated reply for a comment."""
    from backend.data.twitter.comments_cache import (
        get_comment,
        update_comment_generated_replies,
    )
    from backend.data.twitter.posted_tweets_cache import read_posted_tweets_cache
    from backend.twitter.logging import TweetAction, log_tweet_action

    comment = get_comment(username, comment_id)
    if not comment:
        error(f"Comment {comment_id} not found", status_code=404, function_name="edit_comment_reply_endpoint", username=username, critical=True)

    # Find the original posted tweet this comment is on
    posted_tweets = read_posted_tweets_cache(username)
    posted_tweet_text = ""
    posted_tweet_id = ""

    parent_chain = comment.get("parent_chain", [])
    in_reply_to = comment.get("in_reply_to_status_id")

    if in_reply_to and in_reply_to in posted_tweets:
        post_data = posted_tweets[in_reply_to]
        if isinstance(post_data, dict):
            posted_tweet_text = post_data.get("text", "")
            posted_tweet_id = in_reply_to
    else:
        for pid in reversed(parent_chain):
            if pid in posted_tweets:
                post_data = posted_tweets[pid]
                if isinstance(post_data, dict):
                    posted_tweet_text = post_data.get("text", "")
                    posted_tweet_id = pid
                    break

    # Update the specific reply in the generated_replies array
    generated_replies = list(comment.get("generated_replies", []))

    if payload.reply_index >= len(generated_replies):
        error(f"Reply index {payload.reply_index} out of range", status_code=400, function_name="edit_comment_reply_endpoint", username=username, critical=True)

    # Preserve the model name and prompt variant, update the text
    old_reply = generated_replies[payload.reply_index]
    old_text = old_reply[0] if isinstance(old_reply, (list, tuple)) else old_reply
    model_name = old_reply[1] if isinstance(old_reply, (list, tuple)) and len(old_reply) > 1 else "edited"
    prompt_variant = old_reply[2] if isinstance(old_reply, (list, tuple)) and len(old_reply) > 2 else "unknown"

    generated_replies[payload.reply_index] = (payload.new_reply, model_name, prompt_variant)

    update_comment_generated_replies(username, comment_id, generated_replies)

    # Log the edit action
    log_tweet_action(
        username=username,
        action=TweetAction.COMMENT_REPLY_EDITED,
        tweet_id=comment_id,
        metadata={
            "comment_id": comment_id,
            "comment_text": comment.get("text", ""),
            "comment_author": comment.get("handle", ""),
            "reply_index": payload.reply_index,
            "old_reply": old_text,
            "new_reply": payload.new_reply,
            "original_posted_tweet_id": posted_tweet_id,
            "original_posted_tweet_text": posted_tweet_text,
        }
    )

    return {
        "message": "Reply edited successfully",
        "comment_id": comment_id,
        "reply_index": payload.reply_index,
        "new_reply": payload.new_reply
    }


@router.post("/{username}/generate/{comment_id}")
async def regenerate_single_comment_reply_endpoint(
    username: str,
    comment_id: str
) -> dict:
    """Regenerate AI reply for a single comment."""
    from backend.data.twitter.comments_cache import (
        get_comment,
        get_thread_context,
        update_comment_generated_replies,
    )

    if not OBELISK_KEY:
        error("OBELISK_KEY not configured", status_code=500, function_name="regenerate_single_comment_reply_endpoint", username=username, critical=True)

    comment = get_comment(username, comment_id)
    if not comment:
        error(f"Comment {comment_id} not found", status_code=404, function_name="regenerate_single_comment_reply_endpoint", username=username, critical=True)

    thread_context = get_thread_context(comment_id, username)
    if not thread_context:
        error(f"No thread context for comment {comment_id}", status_code=500, function_name="regenerate_single_comment_reply_endpoint", username=username, critical=True)

    user_info = read_user_info(username)
    models = user_info.get("models", ["claude-3-5-sonnet-20241022"]) if user_info else ["claude-3-5-sonnet-20241022"]
    num_generations = user_info.get("number_of_generations", 2) if user_info else 2

    replies = await generate_replies_for_comment(
        comment=comment,
        thread_context=thread_context,
        models=models,
        num_generations=num_generations,
        delay_seconds=0,
        username=username
    )

    if not replies:
        error(f"No replies generated for comment {comment_id}", status_code=500, function_name="regenerate_single_comment_reply_endpoint", username=username, critical=True)

    update_comment_generated_replies(username, comment_id, replies)

    return {
        "message": "Comment reply regenerated",
        "comment_id": comment_id,
        "new_replies": replies
    }
