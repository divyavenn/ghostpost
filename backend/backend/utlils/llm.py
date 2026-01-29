"""
Unified LLM calling module.

All LLM calls should go through ask_llm() to ensure consistent:
- Rate limiting
- Error handling
- Logging
- Message formatting (proper system/user roles)
"""

from backend.config import CLAUDE_API_KEY, OBELISK_KEY, DIVYA_API_KEY, DIVYA_MODEL_NAME
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


async def ask_gemini(
    system_prompt: str,
    user_prompt: str,
    model: str = "gemini-2.0-flash-exp",
    image_urls: list[str] | None = None,
    username: str = "unknown",
    prompt_type: str = "LLM"
) -> dict:
    """
    Call Google Gemini API with rate limiting and error handling.

    Args:
        system_prompt: System instructions (will be included in systemInstruction)
        user_prompt: User message content
        model: Gemini model name (e.g., "gemini-2.0-flash-exp", "gemini-1.5-pro")
        image_urls: Optional list of image URLs to include
        username: Username for logging/rate limiting
        prompt_type: Type of prompt for logging (e.g., "Reply Generation", "Intent Filter")

    Returns:
        dict with either {"message": str} or {"error": str}
    """
    from backend.config import GEMINI_API_KEY
    from backend.twitter.rate_limiter import LLM_GEMINI, call_api

    if not GEMINI_API_KEY:
        error("GEMINI_API_KEY not configured", status_code=500, function_name="ask_gemini", username=username, critical=False)
        return {"error": "GEMINI_API_KEY not configured"}

    # Gemini API endpoint
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"

    # Build user message content (with optional images)
    parts = [{"text": user_prompt}]

    if image_urls and len(image_urls) > 0:
        # Add images as inline data (Gemini supports image URLs in specific format)
        for img_url in image_urls:
            parts.append({
                "inlineData": {
                    "mimeType": "image/jpeg",
                    "data": img_url  # Note: Gemini may require base64 encoded data
                }
            })

    # Print the full prompt to console (debug only)
    _print_prompt(system_prompt, user_prompt, model, len(image_urls) if image_urls else 0, prompt_type)

    # Gemini API format with systemInstruction (available in newer models)
    payload = {
        "systemInstruction": {
            "parts": [{"text": system_prompt}]
        },
        "contents": [
            {
                "role": "user",
                "parts": parts
            }
        ],
        "generationConfig": {
            "temperature": 0.7
        }
    }

    # Use rate limiter with retry
    response = await call_api(
        method="POST",
        url=url,
        bucket=LLM_GEMINI,
        headers={"Content-Type": "application/json"},
        json_data=payload,
        username=username
    )

    if not response.success:
        error(
            f"❌ Error in Gemini call ({prompt_type}): {response.error_message}",
            status_code=response.status_code or 500,
            function_name="ask_gemini",
            username=username,
            critical=False
        )
        return {"error": response.error_message}

    data = response.data

    # Extract message content from Gemini response
    try:
        # Gemini response format: {"candidates": [{"content": {"parts": [{"text": "..."}]}}]}
        message = data["candidates"][0]["content"]["parts"][0]["text"]
        if not message:
            error(
                f"Gemini returned empty message content. Full response: {data}",
                status_code=500,
                function_name="ask_gemini",
                username=username,
                critical=False
            )
            return {"error": "Gemini returned empty message content", "raw": data}
        return {"message": message}
    except (KeyError, IndexError) as e:
        error(
            f"Unexpected Gemini response structure: {e}. Full response: {data}",
            status_code=500,
            exception_text=str(e),
            function_name="ask_gemini",
            username=username,
            critical=True
        )
        return {"error": f"Unexpected Gemini response: {e}", "raw": data}


async def ask_claude(
    system_prompt: str,
    user_prompt: str,
    model: str = "claude-opus-4-5-20251101",
    image_urls: list[str] | None = None,
    username: str = "unknown",
    prompt_type: str = "LLM"
) -> dict:
    """
    Call Anthropic Claude API with rate limiting and error handling.

    Args:
        system_prompt: System instructions
        user_prompt: User message content
        model: Claude model name (e.g., "claude-opus-4-5-20251101", "claude-sonnet-4-5-20250514")
        image_urls: Optional list of image URLs to include
        username: Username for logging/rate limiting
        prompt_type: Type of prompt for logging (e.g., "Reply Generation", "Intent Filter")

    Returns:
        dict with either {"message": str} or {"error": str}
    """
    from backend.twitter.rate_limiter import LLM_CLAUDE, call_api

    if not CLAUDE_API_KEY:
        error("CLAUDE_API_KEY not configured", status_code=500, function_name="ask_claude", username=username, critical=False)
        return {"error": "CLAUDE_API_KEY not configured"}

    # Anthropic API endpoint
    url = "https://api.anthropic.com/v1/messages"

    # Build user message content (with optional images)
    if image_urls and len(image_urls) > 0:
        # Anthropic format: content array with text and image blocks
        user_content = [{"type": "text", "text": user_prompt}]
        for img_url in image_urls:
            # Note: Anthropic requires base64 encoded images with media type
            user_content.append({
                "type": "image",
                "source": {
                    "type": "url",
                    "url": img_url
                }
            })
    else:
        user_content = user_prompt

    # Print the full prompt to console (debug only)
    _print_prompt(system_prompt, user_prompt, model, len(image_urls) if image_urls else 0, prompt_type)

    # Anthropic API format
    payload = {
        "model": model,
        "max_tokens": 1024,
        "system": system_prompt,
        "messages": [
            {
                "role": "user",
                "content": user_content
            }
        ]
    }

    # Use rate limiter with retry
    response = await call_api(
        method="POST",
        url=url,
        bucket=LLM_CLAUDE,
        headers={
            "x-api-key": CLAUDE_API_KEY,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        },
        json_data=payload,
        username=username
    )

    if not response.success:
        error(
            f"❌ Error in Claude call ({prompt_type}): {response.error_message}",
            status_code=response.status_code or 500,
            function_name="ask_claude",
            username=username,
            critical=False
        )
        return {"error": response.error_message}

    data = response.data

    # Extract message content from Claude response
    try:
        # Claude response format: {"content": [{"type": "text", "text": "..."}]}
        message = data["content"][0]["text"]
        if not message:
            error(
                f"Claude returned empty message content. Full response: {data}",
                status_code=500,
                function_name="ask_claude",
                username=username,
                critical=False
            )
            return {"error": "Claude returned empty message content", "raw": data}
        return {"message": message}
    except (KeyError, IndexError) as e:
        error(
            f"Unexpected Claude response structure: {e}. Full response: {data}",
            status_code=500,
            exception_text=str(e),
            function_name="ask_claude",
            username=username,
            critical=True
        )
        return {"error": f"Unexpected Claude response: {e}", "raw": data}


async def ask_llm(
    system_prompt: str,
    user_prompt: str,
    model: str = "chatgpt-4o",
    image_urls: list[str] | None = None,
    username: str = "unknown",
    prompt_type: str = "LLM"
) -> dict:
    """
    Call OpenAI API with DIVYA fine-tuned model.

    Args:
        system_prompt: System instructions
        user_prompt: User message content
        model: Model name (defaults to "chatgpt-4o", but uses DIVYA_MODEL_NAME from .env)
        image_urls: Optional list of image URLs to include
        username: Username for logging/rate limiting
        prompt_type: Type of prompt for logging

    Returns:
        dict with either {"message": str} or {"error": str}
    """

    from backend.twitter.rate_limiter import LLM_OBELISK, call_api

    if not DIVYA_API_KEY:
        error("DIVYA_API_KEY not configured", status_code=500, function_name="ask_llm", username=username, critical=False)
        return {"error": "DIVYA_API_KEY not configured"}

    # Use DIVYA_MODEL_NAME from .env instead of the model parameter
    actual_model = DIVYA_MODEL_NAME or model

    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {DIVYA_API_KEY}", "Content-Type": "application/json"}

    # Build user message content (with optional images)
    if image_urls and len(image_urls) > 0:
        user_content = [{"type": "text", "text": user_prompt}]
        for img_url in image_urls:
            user_content.append({"type": "image_url", "image_url": {"url": img_url}})
    else:
        user_content = user_prompt

    payload = {
        "model": actual_model,
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
        if not data:
            error(
                f"LLM returned empty message content. Full response: {data}",
                status_code=500,
                function_name="ask_llm",
                username=username,
                critical=False
            )
            return {"error": "LLM returned empty message content", "raw": data}
        message = data["choices"][0]["message"]["content"]
        return {"message": message}
    except (KeyError, IndexError) as e:
        error(
            f"Unexpected LLM response structure: {e}. Full response: {data}",
            status_code=500,
            exception_text=str(e),
            function_name="ask_llm",
            username=username,
            critical=True
        )
        return {"error": f"Unexpected LLM response: {e}", "raw": data}
