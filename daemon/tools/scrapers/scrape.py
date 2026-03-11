"""
Unified scraper dispatcher.

Maps ContentType to the correct scraper function and returns markdown + filename.
Called by Rust daemon as: python scrapers/scrape.py '<json>'

Input JSON:
    - url (required)
    - content_type (required) — lowercase string matching ContentType enum
    - cookies (optional) — dict of cookies for authenticated scraping

Output JSON:
    - markdown (string or null if no scraper available)
    - filename (string or null)
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse

import requests

from article import fetch_article_markdown
from pdf import convert_pdf_bytes
from substack import convert_html_to_markdown, fetch_html
from youtube import fetch_youtube_all_sync


# --- Filename helpers (ported from scrape_main.py) ---

def derive_article_filename(url: str) -> str:
    parsed = urlparse(url)
    stem = Path(parsed.path).stem
    candidate = stem or (parsed.hostname or "article")
    safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in candidate)
    safe = safe.strip("-_") or "article"
    return f"{safe}.md"


def derive_youtube_filename(url: str) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    video_id = query.get("v", [None])[0]
    if not video_id:
        video_id = parsed.path.rstrip("/").split("/")[-1] or "youtube-video"
    safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in video_id)
    safe = safe.strip("-_") or "youtube-video"
    return f"{safe}.md"


def choose_filename(provided: Optional[str], fallback: str) -> str:
    base = (provided or "").strip()
    if not base:
        base = fallback.strip()
    if not base:
        base = "document"
    return base if base.lower().endswith(".md") else f"{base}.md"


# --- Content-type → scraper dispatch ---

SCRAPER_TYPES = {"article", "medium", "substack", "youtube", "pdf", "research paper", "tweet"}


def scrape(
    url: str,
    content_type: str,
    cookies: Optional[Dict[str, str]] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Dispatch to the correct scraper based on content_type.

    Returns {"markdown": str | None, "filename": str | None, ...}.
    For types without a scraper, returns {"markdown": None, "filename": None}.
    extra: additional params forwarded to scrapers (YouTube: startTime, endTime, downloadVideo, etc.)
    """
    extra = extra or {}
    ct = content_type.lower().strip()

    if ct in ("article", "medium"):
        markdown = fetch_article_markdown(url)
        filename = choose_filename(None, derive_article_filename(url))
        return {"markdown": markdown, "filename": filename}

    if ct == "substack":
        html = fetch_html(url, cookies=cookies if cookies is not None else {})
        markdown, _metadata = convert_html_to_markdown(html, url)
        from substack import derive_filename as substack_derive
        filename = choose_filename(None, substack_derive(url, _metadata.get("title", "")))
        return {"markdown": markdown, "filename": filename}

    if ct == "youtube":
        result = fetch_youtube_all_sync(
            url,
            download_video=extra.get("downloadVideo", False),
            download_audio=extra.get("downloadAudio", False),
            download_transcript=extra.get("downloadTranscript", True),
            start_time=extra.get("startTime"),
            end_time=extra.get("endTime"),
            openai_api_key=extra.get("openaiApiKey"),
            cookies=cookies,
        )
        result["filename"] = choose_filename(None, derive_youtube_filename(url))
        return result

    if ct == "tweet":
        import asyncio
        from tweet import convert_tweet, slugify
        markdown, handle, root_id, first_tweet_text = asyncio.run(convert_tweet(url, cookies=cookies))
        fallback = slugify(handle + "-" + root_id) or root_id or "tweet"
        filename = choose_filename(None, fallback)
        return {"markdown": markdown, "filename": filename, "first_tweet": first_tweet_text}

    if ct in ("pdf", "research paper"):
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        markdown = convert_pdf_bytes(resp.content)
        fallback = Path(urlparse(url).path).stem or "document"
        filename = choose_filename(None, fallback)
        return {"markdown": markdown, "filename": filename}

    # No scraper for this content type (book, movie, tv_show, podcast, github, unknown, etc.)
    return {"markdown": None, "filename": None}


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: python scrapers/scrape.py '<json>'"}))
        sys.exit(1)

    try:
        input_data = json.loads(sys.argv[1])
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON input: {e}"}))
        sys.exit(1)

    url = input_data.get("url")
    content_type = input_data.get("content_type")

    if not url:
        print(json.dumps({"error": "Missing required field: url"}))
        sys.exit(1)

    if not content_type:
        print(json.dumps({"error": "Missing required field: content_type"}))
        sys.exit(1)

    try:
        result = scrape(url, content_type, cookies=input_data.get("cookies"), extra=input_data)
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
