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


COMMENT_REPLY_PROMPT = """You are an expert at online conversation.
Your job is to craft a reply to someone who commented on your tweet (or thread).
Your reply should be concise, warm, and natural — like texting a friend.

The conversation context shows:
- Your original post(s) that started this thread
- The comment you're replying to
- Any intermediate replies in the chain

Key principles:
1. Acknowledge their point genuinely — don't be dismissive
2. Be conversational, not formal
3. Add value: clarify, elaborate, or build on the discussion
4. Match the energy of the comment (playful reply to playful comment, thoughtful to thoughtful)
5. Keep it brief: 1-3 sentences for casual replies, slightly longer for substantive discussions
6. Don't be defensive — even if they disagree, engage constructively

If the comment is:
- A compliment → Accept gracefully, maybe add a related thought
- A question → Answer helpfully with specifics
- A disagreement → Engage the strongest version of their point
- A joke → Play along or build on it
- Criticism → Address it directly but not defensively

Your reply should feel natural and make the commenter feel heard.
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
        username = ctx.get("username", handle)
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


async def ask_model_for_comment(prompt: str, image_urls: list[str] = None, model: str = "nakul-1", username: str = "unknown") -> dict:
    """Call the Obelisk API to generate a comment reply."""
    import requests

    url = "https://obelisk.dread.technology/api/chat/completions"
    headers = {"Authorization": f"Bearer {OBELISK_KEY}", "Content-Type": "application/json"}

    # Build user message content
    if image_urls and len(image_urls) > 0:
        user_content = [{"type": "text", "text": prompt}]
        for img_url in image_urls:
            user_content.append({"type": "image_url", "image_url": {"url": img_url}})
    else:
        user_content = prompt

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": COMMENT_REPLY_PROMPT},
            {"role": "user", "content": user_content}
        ]
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        error_detail = str(e)
        try:
            if hasattr(e, 'response') and e.response is not None:
                error_detail = f"{str(e)} | Response: {e.response.text}"
        except Exception:
            pass
        error(f"Error communicating with Obelisk API: {error_detail}", status_code=500, function_name='ask_model_for_comment', username=username, critical=False)
        return {"error": error_detail}

    data = response.json()

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
) -> list[tuple[str, str]]:
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
        List of (reply_text, model_name) tuples
    """
    import random

    replies = []
    comment_id = comment.get("id", "unknown")

    text_prompt, image_urls = build_comment_prompt(comment, thread_context)

    for gen_idx in range(num_generations):
        # Model selection
        if len(models) < num_generations:
            selected_model = models[gen_idx % len(models)]
        else:
            selected_model = random.choice(models)

        notify(f"🤖 Generating reply {gen_idx+1} for comment {comment_id} using {selected_model}...")

        response = await ask_model_for_comment(
            prompt=text_prompt,
            image_urls=image_urls,
            model=selected_model,
            username=username
        )

        reply = response.get('message', '')
        if reply:
            replies.append((reply, selected_model))
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
