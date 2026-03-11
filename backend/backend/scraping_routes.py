from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from uuid import uuid4
from typing import Any, Awaitable, Callable, Dict

import requests
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, status
from pydantic import BaseModel, Field, HttpUrl

# Import scrapers directly from the daemon's canonical location
_SCRAPERS_PATH = Path(__file__).parents[2] / "daemon" / "tools" / "scrapers"
if str(_SCRAPERS_PATH) not in sys.path:
    sys.path.insert(0, str(_SCRAPERS_PATH))

from substack import convert_html_to_markdown, derive_filename, fetch_html  # noqa: E402
from tweet import convert_tweet, slugify  # noqa: E402
from pdf import convert_pdf_path, convert_pdf_bytes  # noqa: E402
from article import fetch_article_markdown  # noqa: E402
from youtube import fetch_youtube_all_sync  # noqa: E402

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class ConvertRequest(BaseModel):
    url: HttpUrl
    filename: str | None = None
    cookies: dict[str, Any] = Field(default_factory=dict)
    html: str | None = None
    openaiApiKey: str | None = None
    # YouTube-specific
    startTime: str | None = None
    endTime: str | None = None
    downloadVideo: bool = False
    downloadAudio: bool = False
    downloadTranscript: bool = True


# ---------------------------------------------------------------------------
# Cookie helpers (mirrors daemon/scrape_main.py)
# ---------------------------------------------------------------------------

def cookies_to_lookup(cookies: dict[str, Any]) -> dict[str, str]:
    return {str(name): str(value) for name, value in cookies.items() if value is not None}


def cookies_to_storage_state(cookies: dict[str, str]) -> dict[str, Any]:
    same_site_map = {
        "no_restriction": "None",
        "none": "None",
        "unspecified": "None",
        "lax": "Lax",
        "strict": "Strict",
    }

    def build_cookie(name: str, http_only: bool) -> dict[str, Any]:
        cookie: dict[str, Any] = {
            "name": name,
            "value": cookies[name],
            "domain": ".x.com",
            "path": "/",
            "secure": True,
            "httpOnly": http_only,
        }
        same_site_raw = cookies.get(f"{name}_same_site")
        if same_site_raw:
            same_site = same_site_map.get(str(same_site_raw).lower())
            if same_site:
                cookie["sameSite"] = same_site
        expires_raw = cookies.get(f"{name}_expires")
        if expires_raw:
            cookie["expires"] = expires_raw
        return cookie

    playwright_cookies: list[dict[str, Any]] = []
    if "auth_token" in cookies:
        playwright_cookies.append(build_cookie("auth_token", http_only=True))
    if "ct0" in cookies:
        playwright_cookies.append(build_cookie("ct0", http_only=False))
    return {"cookies": playwright_cookies, "origins": []}


# ---------------------------------------------------------------------------
# Filename helpers
# ---------------------------------------------------------------------------

def derive_article_filename(url: str) -> str:
    parsed = urlparse(url)
    stem = Path(parsed.path).stem
    candidate = stem or (parsed.hostname or "article")
    safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in candidate)
    return f"{safe.strip('-_') or 'article'}.md"


def derive_youtube_filename(url: str) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    video_id = query.get("v", [None])[0]
    if not video_id:
        video_id = parsed.path.rstrip("/").split("/")[-1] or "youtube-video"
    safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in video_id)
    return f"{safe.strip('-_') or 'youtube-video'}.md"


def choose_filename(provided: str | None, fallback: str) -> str:
    base = (provided or "").strip() or fallback.strip() or "document"
    return base if base.lower().endswith(".md") else f"{base}.md"


# ---------------------------------------------------------------------------
# Async job queue
# ---------------------------------------------------------------------------

jobs: Dict[str, Dict[str, Any]] = {}
jobs_lock = asyncio.Lock()


async def _set_job_status(
    job_id: str,
    job_status: str,
    result: Dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    async with jobs_lock:
        record = jobs.get(job_id)
        if record is None:
            return
        record["status"] = job_status
        record["result"] = result
        record["error"] = error
        record["updated_at"] = time.time()


async def enqueue_job(task: Callable[[], Awaitable[Dict[str, Any]]]) -> Dict[str, str]:
    job_id = uuid4().hex
    now = time.time()
    async with jobs_lock:
        jobs[job_id] = {"status": "processing", "result": None, "error": None, "created_at": now, "updated_at": now}

    async def runner() -> None:
        try:
            result = await task()
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
            await _set_job_status(job_id, "error", error=detail)
        except Exception as exc:
            await _set_job_status(job_id, "error", error=str(exc))
        else:
            await _set_job_status(job_id, "ready", result=result)

    asyncio.create_task(runner())
    return {"jobId": job_id, "status": "processing"}


# ---------------------------------------------------------------------------
# Sync conversion helpers
# ---------------------------------------------------------------------------

def _convert_remote_pdf_sync(url: str, provided_filename: str | None, cookies: Dict[str, str], openai_api_key: str | None) -> Dict[str, Any]:
    response = None
    temp_path: str | None = None
    try:
        response = requests.get(url, stream=True, timeout=60, cookies=cookies or None)
        response.raise_for_status()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            temp_path = tmp.name
            for chunk in response.iter_content(chunk_size=1 << 20):
                if chunk:
                    tmp.write(chunk)
        if not temp_path or os.path.getsize(temp_path) == 0:
            raise HTTPException(status_code=400, detail="Fetched PDF is empty.")
        markdown = convert_pdf_path(temp_path, openai_api_key)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"PDF conversion failed: {exc}") from exc
    finally:
        if response is not None:
            response.close()
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)
    fallback = Path(urlparse(url).path).stem or "document"
    filename = choose_filename(provided_filename, fallback)
    return {"markdown": markdown, "filename": filename, "metadata": {"title": fallback, "author": None, "publishDate": None, "url": url, "contentType": "pdf"}}


def _convert_pdf_stream_sync(data: bytes, provided_filename: str | None, original_name: str | None, openai_api_key: str | None) -> Dict[str, Any]:
    if not data:
        raise HTTPException(status_code=400, detail="No PDF content received.")
    try:
        markdown = convert_pdf_bytes(data, openai_api_key)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"PDF conversion failed: {exc}") from exc
    source_name = original_name or "document.pdf"
    fallback = Path(source_name).stem or "document"
    filename = choose_filename(provided_filename, fallback)
    return {"markdown": markdown, "filename": filename, "metadata": {"title": fallback, "author": None, "publishDate": None, "url": None, "contentType": "pdf"}}


def _convert_article_sync(url: str, html: str | None, provided_filename: str | None) -> Dict[str, Any]:
    try:
        markdown, metadata = fetch_article_markdown(url=url, html=html, return_metadata=True)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Article conversion failed: {exc}") from exc
    return {"markdown": markdown, "filename": choose_filename(provided_filename, derive_article_filename(url)), "metadata": metadata}


def _convert_substack_sync(url: str, provided_filename: str | None, cookies: Dict[str, str], html: str | None) -> Dict[str, Any]:
    try:
        html_source = html or fetch_html(url, cookies=cookies)
        markdown, raw_metadata = convert_html_to_markdown(html_source, url)
    except requests.HTTPError as exc:
        code = exc.response.status_code if exc.response else 502
        raise HTTPException(status_code=code, detail=f"Substack request failed: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    fallback = derive_filename(url, raw_metadata.get("title", ""))
    return {
        "markdown": markdown,
        "filename": choose_filename(provided_filename, fallback),
        "metadata": {"title": raw_metadata.get("title"), "author": raw_metadata.get("author_text"), "publishDate": raw_metadata.get("date_text"), "url": url, "contentType": "substack"},
    }


# ---------------------------------------------------------------------------
# Async conversion helpers
# ---------------------------------------------------------------------------

async def _convert_youtube_async(
    url: str,
    provided_filename: str | None,
    openai_api_key: str | None,
    cookies: Dict[str, str],
    start_time: str | None,
    end_time: str | None,
    download_video: bool,
    download_audio: bool,
    download_transcript: bool,
) -> Dict[str, Any]:
    try:
        result = await asyncio.to_thread(
            fetch_youtube_all_sync,
            url,
            download_video=download_video,
            download_audio=download_audio,
            download_transcript=download_transcript,
            start_time=start_time,
            end_time=end_time,
            openai_api_key=openai_api_key,
            cookies=cookies,
        )
    except SystemExit as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"YouTube conversion failed: {exc}") from exc
    result["filename"] = choose_filename(provided_filename, derive_youtube_filename(url))
    return result


async def _convert_tweet_async(url: str, provided_filename: str | None, storage_state: Dict[str, Any]) -> Dict[str, Any]:
    try:
        markdown, handle, root_id, _first_tweet = await convert_tweet(url=url, cookies=storage_state)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    base = slugify(handle + "-" + root_id) or root_id or "tweet"
    return {
        "markdown": markdown,
        "filename": choose_filename(provided_filename, base),
        "metadata": {"title": f"Tweet by @{handle}" if handle else None, "author": handle, "publishDate": None, "url": url, "contentType": "tweet"},
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/scrape/jobs/{job_id}")
async def get_job_status(job_id: str) -> Dict[str, Any]:
    async with jobs_lock:
        record = jobs.get(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    payload: Dict[str, Any] = {"jobId": job_id, "status": record["status"]}
    if record["status"] == "ready" and record["result"]:
        r = record["result"]
        payload["filename"] = r.get("filename")
        if r.get("markdown"):
            payload["markdown"] = r["markdown"]
        if r.get("metadata"):
            payload["metadata"] = r["metadata"]
        for key in ("audioData", "audioMimeType", "audioFilename", "videoData", "videoMimeType", "videoFilename"):
            if r.get(key):
                payload[key] = r[key]
    elif record["status"] == "error":
        payload["error"] = record["error"] or "Conversion failed"
    return payload


@router.post("/scrape/convert-pdf", status_code=status.HTTP_202_ACCEPTED)
async def download_pdf(payload: ConvertRequest) -> Dict[str, str]:
    url = str(payload.url)
    cookie_lookup = cookies_to_lookup(payload.cookies)
    openai_api_key = payload.openaiApiKey

    async def task() -> Dict[str, Any]:
        return await asyncio.to_thread(_convert_remote_pdf_sync, url, payload.filename, cookie_lookup, openai_api_key)

    return await enqueue_job(task)


@router.post("/scrape/convert-pdf/stream", status_code=status.HTTP_202_ACCEPTED)
async def upload_pdf(file: UploadFile = File(...), filename: str | None = Form(None), openaiApiKey: str | None = Form(None)) -> Dict[str, str]:
    original_name = file.filename
    try:
        data = await file.read()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read uploaded PDF: {exc}") from exc
    finally:
        await file.close()
    if not data:
        raise HTTPException(status_code=400, detail="No PDF content received.")

    async def task() -> Dict[str, Any]:
        return await asyncio.to_thread(_convert_pdf_stream_sync, data, filename, original_name, openaiApiKey)

    return await enqueue_job(task)


@router.post("/scrape/convert-article", status_code=status.HTTP_202_ACCEPTED)
async def download_article(payload: ConvertRequest) -> Dict[str, str]:
    url = str(payload.url)

    async def task() -> Dict[str, Any]:
        return await asyncio.to_thread(_convert_article_sync, url, payload.html, payload.filename)

    return await enqueue_job(task)


@router.post("/scrape/convert-youtube", status_code=status.HTTP_202_ACCEPTED)
async def download_youtube(payload: ConvertRequest) -> Dict[str, str]:
    url = str(payload.url)
    openai_api_key = payload.openaiApiKey.strip() if payload.openaiApiKey else None
    cookie_lookup = cookies_to_lookup(payload.cookies)

    async def task() -> Dict[str, Any]:
        return await _convert_youtube_async(
            url,
            payload.filename,
            openai_api_key,
            cookie_lookup,
            payload.startTime,
            payload.endTime,
            payload.downloadVideo,
            payload.downloadAudio,
            payload.downloadTranscript,
        )

    return await enqueue_job(task)


@router.post("/scrape/convert-tweet", status_code=status.HTTP_202_ACCEPTED)
async def download_tweet(payload: ConvertRequest) -> Dict[str, str]:
    url = str(payload.url)
    cookie_lookup = cookies_to_lookup(payload.cookies)
    storage_state = cookies_to_storage_state(cookie_lookup)
    if not cookie_lookup.get("auth_token") or not cookie_lookup.get("ct0"):
        raise HTTPException(status_code=400, detail="Both auth_token and ct0 cookies are required to export this thread.")

    async def task() -> Dict[str, Any]:
        return await _convert_tweet_async(url, payload.filename, storage_state)

    return await enqueue_job(task)


@router.post("/scrape/convert-substack", status_code=status.HTTP_202_ACCEPTED)
async def download_substack(payload: ConvertRequest) -> Dict[str, str]:
    url = str(payload.url)
    cookie_lookup = cookies_to_lookup(payload.cookies)

    async def task() -> Dict[str, Any]:
        return await asyncio.to_thread(_convert_substack_sync, url, payload.filename, cookie_lookup, payload.html)

    return await enqueue_job(task)
