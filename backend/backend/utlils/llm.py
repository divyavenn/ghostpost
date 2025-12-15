"""
Unified LLM calling module.

All LLM calls should go through ask_llm() to ensure consistent:
- Rate limiting
- Error handling
- Logging
- Message formatting (proper system/user roles)
"""

from backend.config import OBELISK_KEY
from backend.utlils.utils import DEBUG_LOGS, error, notify


def _print_prompt(system_prompt: str, user_prompt: str, model: str, image_count: int = 0, prompt_type: str = "LLM"):
    """Print the full prompt to console for debugging (only if DEBUG_LOGS is enabled)."""
    if not DEBUG_LOGS:
        return

    print(f"\n{'='*80}")
    print(f"🤖 {prompt_type} | Model: {model}")
    print(f"{'='*80}")
    print(f"\n📋 SYSTEM PROMPT:\n{'-'*40}")
    print(system_prompt)
    print(f"\n📝 USER PROMPT:\n{'-'*40}")
    print(user_prompt)
    if image_count > 0:
        print(f"\n🖼️  IMAGES: {image_count} attached")
    print(f"\n{'='*80}\n")


async def ask_llm(
    system_prompt: str,
    user_prompt: str,
    model: str = "chatgpt-4o",
    image_urls: list[str] | None = None,
    username: str = "unknown",
    prompt_type: str = "LLM"
) -> dict:
    """
    Unified LLM calling function.

    All LLM calls should route through this function to ensure consistent
    rate limiting, error handling, and message formatting.

    Args:
        system_prompt: The system message content
        user_prompt: The user message content
        model: Model to use (default: "chatgpt-4o")
        image_urls: Optional list of image URLs for multimodal requests
        username: Username for logging and rate limiting
        prompt_type: Description for logging (e.g., "TWEET REPLY", "INTENT FILTER")

    Returns:
        dict with either:
        - {"message": str} on success
        - {"error": str, ...} on failure
    """
    from backend.twitter.rate_limiter import LLM_OBELISK, call_api

    if not OBELISK_KEY:
        error("OBELISK_KEY not configured", status_code=500, function_name="ask_llm", username=username, critical=False)
        return {"error": "OBELISK_KEY not configured"}

    url = "https://obelisk.dread.technology/api/chat/completions"
    headers = {"Authorization": f"Bearer {OBELISK_KEY}", "Content-Type": "application/json"}

    # Build user message content (with optional images)
    if image_urls and len(image_urls) > 0:
        user_content = [{"type": "text", "text": user_prompt}]
        for img_url in image_urls:
            user_content.append({"type": "image_url", "image_url": {"url": img_url}})
    else:
        user_content = user_prompt

    # Print the full prompt to console (debug only)
    _print_prompt(system_prompt, user_prompt, model, len(image_urls) if image_urls else 0, prompt_type)

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
        error(
            f"❌ Error in LLM call ({prompt_type}): {response.error_message}",
            status_code=response.status_code or 500,
            function_name="ask_llm",
            username=username,
            critical=False
        )
        return {"error": response.error_message}

    data = response.data

    # Extract message content
    try:
        message = data["choices"][0]["message"]["content"]
        if not message:
            notify(f"⚠️ LLM returned empty message content. Full response: {data}")
            return {"error": "LLM returned empty message content", "raw": data}
        return {"message": message}
    except (KeyError, IndexError) as e:
        notify(f"⚠️ Unexpected LLM response structure: {e}. Full response: {data}")
        return {"error": f"Unexpected LLM response: {e}", "raw": data}
