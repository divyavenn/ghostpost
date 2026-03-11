from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any


def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = text.strip("-")
    return text or "thread"




async def convert_tweet(url: str, cookies: dict[str, Any] | None = None) -> tuple[str, str, str, str]:
    from urllib.parse import urlparse
    from tweet_playwright import get_thread

    parsed = urlparse(url)
    segments = [segment for segment in parsed.path.split("/") if segment]
    if len(segments) < 3 or segments[1] != "status":
        raise ValueError("Tweet URL must have the form https://x.com/<handle>/status/<id>")

    handle = segments[0]
    root_id = segments[2]

    tweets = await get_thread(tweet_url=url, root_id=root_id, cookies=cookies)

    if not tweets:
        raise ValueError("No tweets captured. Check that the session is authenticated and the tweet exists.")

    first_tweet_text = tweets[0].strip()

    lines: list[str] = []

    for index, text in enumerate(tweets, start=1):
        lines.append(f"## Tweet {index}")
        lines.append("")
        lines.append(text.strip())
        lines.append("")

    markdown = "\n".join(lines).strip() + "\n"

    return markdown, handle, root_id, first_tweet_text


if __name__ == "__main__":
    markdown, handle, root_id, first_tweet_text = asyncio.run(convert_tweet(url="https://x.com/karpathy/status/1973435013875314729"))
    filename = f"{slugify(handle+'-'+root_id) or root_id}.md"
    
    output_dir = Path("tweet_exports")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename
    output_path.write_text(markdown, encoding="utf-8")
