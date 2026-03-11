#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
import asyncio
import base64
import html
import requests
from dataclasses import dataclass
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def fetch_sponsor_segments(video_id: str) -> List[Tuple[float, float]]:
    """Fetch sponsor segments from SponsorBlock API.

    Returns a list of (start, end) tuples in seconds.
    Categories filtered: sponsor, selfpromo, interaction, intro, outro
    """
    try:
        url = f"https://sponsor.ajay.app/api/skipSegments?videoID={video_id}"
        categories = '["sponsor","selfpromo","interaction","intro","outro"]'
        response = requests.get(f"{url}&categories={categories}", timeout=5)

        if response.status_code == 404:
            return []

        response.raise_for_status()
        data = response.json()

        segments = []
        for item in data:
            segment = item.get("segment", [])
            if len(segment) == 2:
                segments.append((float(segment[0]), float(segment[1])))

        print(f"[YouTube] Found {len(segments)} sponsor segments to skip")
        return segments
    except Exception as e:
        print(f"[YouTube] SponsorBlock lookup failed (continuing without filtering): {e}")
        return []


def is_in_sponsor_segment(timestamp: float, sponsor_segments: List[Tuple[float, float]]) -> bool:
    for start, end in sponsor_segments:
        if start <= timestamp <= end:
            return True
    return False


def _create_cookie_file(cookies: Dict[str, str], url: str) -> Path:
    """Create a Netscape cookie file for yt-dlp from a dictionary of cookies."""
    from urllib.parse import urlparse

    parsed = urlparse(url)
    hostname = parsed.hostname or "youtube.com"
    domain = f".{hostname}" if not hostname.startswith(".") else hostname

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", prefix="yt_cookies_", delete=False) as tmp:
        cookie_file = Path(tmp.name)
        tmp.write("# Netscape HTTP Cookie File\n")
        tmp.write("# This file was generated for yt-dlp\n")
        tmp.write("# https://curl.haxx.se/rfc/cookie_spec.html\n")
        tmp.write("# This is a generated file! Do not edit.\n\n")

        for name, value in cookies.items():
            if name.endswith("_same_site") or name.endswith("_expires"):
                continue
            expiration = "2147483647"
            secure = "TRUE"
            tmp.write(f"{domain}\tTRUE\t/\t{secure}\t{expiration}\t{name}\t{value}\n")

    return cookie_file


@dataclass
class VideoSelection:
    video_id: str
    title: str
    chosen_lang: Optional[str]


def parse_timestamp_to_seconds(ts: str) -> Optional[float]:
    """Convert a timestamp string (HH:MM:SS, MM:SS, or S) to seconds. Returns None on error."""
    if not ts or not ts.strip():
        return None
    ts = ts.strip()
    try:
        parts = ts.split(":")
        if len(parts) == 3:
            return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
        elif len(parts) == 2:
            return float(parts[0]) * 60 + float(parts[1])
        else:
            return float(ts)
    except (ValueError, IndexError):
        return None


def extract_video_info(url: str, cookies: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    try:
        from yt_dlp import YoutubeDL
    except Exception as exc:
        raise SystemExit(
            "yt-dlp is required. Install with: pip install yt-dlp"
        ) from exc

    opts: Dict[str, Any] = {
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
    }

    cookie_file = None
    if cookies:
        cookie_file = _create_cookie_file(cookies, url)
        opts["cookiefile"] = str(cookie_file)

    try:
        from yt_dlp import YoutubeDL
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
        return info
    finally:
        if cookie_file and cookie_file.exists():
            cookie_file.unlink()


def select_human_subtitle_lang(info: Dict[str, Any], preferred_lang: Optional[str]) -> Optional[str]:
    human_subs: Dict[str, Any] = info.get("subtitles") or {}
    if not human_subs:
        return None

    if preferred_lang and preferred_lang in human_subs:
        return preferred_lang

    for lang in human_subs.keys():
        return lang

    return None


def download_human_subtitles(url: str, out_dir: Path, video_id: str, lang: str, cookies: Optional[Dict[str, str]] = None) -> Path:
    try:
        from yt_dlp import YoutubeDL
    except Exception as exc:
        raise SystemExit(
            "yt-dlp is required. Install with: pip install yt-dlp"
        ) from exc

    ensure_directory(out_dir)
    outtmpl = str(out_dir / f"{video_id}.%(subtitle_lang)s.%(ext)s")
    opts: Dict[str, Any] = {
        "skip_download": True,
        "writesubtitles": True,
        "subtitleslangs": [lang],
        "subtitlesformat": "vtt",
        "outtmpl": outtmpl,
        "quiet": True,
        "no_warnings": True,
    }

    cookie_file = None
    if cookies:
        cookie_file = _create_cookie_file(cookies, url)
        opts["cookiefile"] = str(cookie_file)

    try:
        from yt_dlp import YoutubeDL
        with YoutubeDL(opts) as ydl:
            ydl.download([url])
    finally:
        if cookie_file and cookie_file.exists():
            cookie_file.unlink()

    vtt_path = out_dir / f"{video_id}.NA.{lang}.vtt"
    return vtt_path


def parse_vtt_timestamp(timestamp: str) -> float:
    """Convert VTT timestamp (HH:MM:SS.mmm or MM:SS.mmm) to seconds."""
    parts = timestamp.split(":")
    if len(parts) == 3:
        hours, minutes, seconds = parts
        return float(hours) * 3600 + float(minutes) * 60 + float(seconds)
    elif len(parts) == 2:
        minutes, seconds = parts
        return float(minutes) * 60 + float(seconds)
    return 0.0


def vtt_to_text(
    vtt_path: Path,
    sponsor_segments: Optional[List[Tuple[float, float]]] = None,
    start_sec: Optional[float] = None,
    end_sec: Optional[float] = None,
) -> str:
    try:
        import webvtt  # type: ignore
    except Exception as exc:
        raise SystemExit(
            "webvtt-py is required to parse VTT. Install with: pip install webvtt-py"
        ) from exc

    sponsor_segments = sponsor_segments or []
    lines: list[str] = []
    skipped_count = 0

    for caption in webvtt.read(str(vtt_path)):
        cap_start = parse_vtt_timestamp(caption.start)

        # Filter to requested time range
        if start_sec is not None and cap_start < start_sec:
            continue
        if end_sec is not None and cap_start > end_sec:
            continue

        if sponsor_segments and is_in_sponsor_segment(cap_start, sponsor_segments):
            skipped_count += 1
            continue

        text = caption.text.replace("\n", " ").strip()
        text = html.unescape(text)
        if text:
            lines.append(text)

    if skipped_count > 0:
        print(f"[YouTube] Skipped {skipped_count} captions in sponsor segments")

    return "\n".join(lines).strip()


def download_audio(url: str, out_dir: Path, video_id: str, cookies: Optional[Dict[str, str]] = None) -> Path:
    try:
        from yt_dlp import YoutubeDL
    except Exception as exc:
        raise RuntimeError(
            "yt-dlp is required. Install with: pip install yt-dlp"
        ) from exc

    ensure_directory(out_dir)
    outtmpl = str(out_dir / f"{video_id}.%(ext)s")
    opts: Dict[str, Any] = {
        "format": "bestaudio/best",
        "outtmpl": outtmpl,
        "quiet": False,
        "no_warnings": False,
    }

    cookie_file = None
    if cookies:
        cookie_file = _create_cookie_file(cookies, url)
        opts["cookiefile"] = str(cookie_file)

    try:
        from yt_dlp import YoutubeDL
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
    except Exception as exc:
        raise RuntimeError(f"Failed to download audio from YouTube: {exc}") from exc
    finally:
        if cookie_file and cookie_file.exists():
            cookie_file.unlink()

    audio_path = Path(filename)
    if not audio_path.exists():
        for ext in ("m4a", "webm", "mp3", "aac", "wav"):
            candidate = out_dir / f"{video_id}.{ext}"
            if candidate.exists():
                audio_path = candidate
                break
    if not audio_path.exists():
        raise RuntimeError("Failed to locate downloaded audio file.")
    return audio_path


def transcribe_with_openai_whisper_api(audio_path: Path, openai_api_key: str, language: Optional[str] = None) -> str:
    print("Using OpenAI Whisper API for transcription")
    try:
        from openai import OpenAI
    except Exception as exc:
        raise SystemExit(
            "openai package is required. Install with: pip install openai"
        ) from exc

    if not openai_api_key:
        raise ValueError("OpenAI API key is required for Whisper API transcription")

    client = OpenAI(api_key=openai_api_key)

    try:
        with open(audio_path, "rb") as audio_file:
            transcript_params: Dict[str, Any] = {
                "model": "whisper-1",
                "file": audio_file,
            }
            if language:
                transcript_params["language"] = language
            transcript = client.audio.transcriptions.create(**transcript_params)
        return transcript.text.strip()
    except Exception as exc:
        raise RuntimeError(f"OpenAI Whisper API transcription failed: {exc}") from exc


def transcribe_with_whisper(
    audio_path: Path,
    model_name: str = "small",
    language: Optional[str] = None,
    sponsor_segments: Optional[List[Tuple[float, float]]] = None,
    start_sec: Optional[float] = None,
    end_sec: Optional[float] = None,
) -> str:
    try:
        from faster_whisper import WhisperModel
    except Exception as exc:
        raise SystemExit(
            "faster-whisper is required. Install with: pip install faster-whisper\n"
            "Note: ffmpeg must also be installed and on PATH."
        ) from exc

    sponsor_segments = sponsor_segments or []
    model = None
    try:
        model = WhisperModel("small", device="cpu", compute_type="int8")
        segments, info = model.transcribe(str(audio_path), language=language)
        text_lines = []
        skipped_count = 0

        for segment in segments:
            # Filter to requested time range
            if start_sec is not None and segment.start < start_sec:
                continue
            if end_sec is not None and segment.start > end_sec:
                continue

            if sponsor_segments and is_in_sponsor_segment(segment.start, sponsor_segments):
                skipped_count += 1
                continue
            if segment.text.strip():
                text_lines.append(segment.text.strip())

        if skipped_count > 0:
            print(f"[YouTube] Skipped {skipped_count} Whisper segments in sponsor sections")

        return "\n".join(text_lines).strip()

    except Exception as exc:
        raise RuntimeError(f"Faster-Whisper transcription failed: {exc}") from exc
    finally:
        if model is not None:
            del model


def build_markdown_transcript(
    title: str,
    source_url: str,
    language: Optional[str],
    body: str,
) -> str:
    body_text = body.strip()
    if body_text:
        return body_text + "\n"
    return "\n"


def _locate_vtt(out_dir: Path, video_id: str) -> Path:
    candidates = sorted(out_dir.glob(f"{video_id}*.vtt"))
    if not candidates:
        raise RuntimeError("Failed to locate downloaded subtitle file.")
    return candidates[0]


def fetch_youtube_markdown(
    url: str,
    *,
    preferred_lang: str = "en",
    whisper_model: str = "small",
    openai_api_key: str | None = None,
    cookies: Optional[Dict[str, str]] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
) -> str:
    print(f"[YouTube] Starting conversion for: {url}")
    print(f"[YouTube] OpenAI API key provided: {bool(openai_api_key)}")
    print(f"[YouTube] Cookies provided: {bool(cookies)}")

    start_sec = parse_timestamp_to_seconds(start_time)
    end_sec = parse_timestamp_to_seconds(end_time)
    if start_sec is not None or end_sec is not None:
        print(f"[YouTube] Time range: {start_time or 'start'} → {end_time or 'end'}")

    with tempfile.TemporaryDirectory(prefix="yt_", suffix="_extract") as tmp:
        out_dir = Path(tmp)
        ensure_directory(out_dir)

        print("[YouTube] Extracting video info...")
        info = extract_video_info(url, cookies=cookies)
        video_id = info.get("id") or "video"
        title = info.get("title") or video_id
        print(f"[YouTube] Video: {title} ({video_id})")

        chosen_lang = select_human_subtitle_lang(info, preferred_lang)

        print("[YouTube] Checking SponsorBlock for sponsor segments...")
        sponsor_segments = fetch_sponsor_segments(video_id)

        if chosen_lang:
            print(f"[YouTube] Found human subtitles in language: {chosen_lang}")
            vtt_path = download_human_subtitles(url, out_dir, video_id, chosen_lang, cookies=cookies)
            try:
                subtitle_path = vtt_path if vtt_path.exists() else _locate_vtt(out_dir, video_id)
            except RuntimeError:
                subtitle_path = _locate_vtt(out_dir, video_id)
            plain_text = vtt_to_text(subtitle_path, sponsor_segments, start_sec=start_sec, end_sec=end_sec)
            print("[YouTube] Subtitles converted successfully")
            return build_markdown_transcript(title, url, chosen_lang, plain_text)

        print("[YouTube] No subtitles found, will need transcription")
        if openai_api_key and openai_api_key.strip():
            print("[YouTube] Using OpenAI Whisper API for transcription")
            audio_path = download_audio(url, out_dir, video_id, cookies=cookies)
            try:
                text = transcribe_with_openai_whisper_api(audio_path, openai_api_key, preferred_lang)
                # OpenAI API doesn't return timestamps so we can't filter by range here;
                # fall through to local Whisper which does support range filtering
                if start_sec is None and end_sec is None:
                    if not text:
                        raise RuntimeError("Transcription produced empty output.")
                    return build_markdown_transcript(title, url, preferred_lang, text)
            except Exception:
                pass
            print("[YouTube] Falling back to local Whisper for range-aware transcription...")
            text = transcribe_with_whisper(audio_path, whisper_model, preferred_lang, sponsor_segments, start_sec=start_sec, end_sec=end_sec)
        else:
            print("[YouTube] Checking for local Whisper installation...")
            try:
                import importlib.util
                if importlib.util.find_spec("faster_whisper") is None:
                    raise ImportError("faster_whisper not found")
            except ImportError:
                raise RuntimeError(
                    "No subtitles found for this video. "
                    "Either provide an OpenAI API key in settings, or install faster-whisper locally: "
                    "pip install faster-whisper"
                )

            audio_path = download_audio(url, out_dir, video_id, cookies=cookies)
            print("[YouTube] Starting local Whisper transcription (this may take a while)...")
            text = transcribe_with_whisper(audio_path, whisper_model, preferred_lang, sponsor_segments, start_sec=start_sec, end_sec=end_sec)

        if not text:
            raise RuntimeError("Transcription produced empty output.")
        print("[YouTube] Conversion complete")
        return build_markdown_transcript(title, url, preferred_lang, text)


def fetch_youtube_original(
    url: str,
    mode: str,  # 'audio' or 'video'
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    cookies: Optional[Dict[str, str]] = None,
) -> Tuple[str, str, str, str]:
    """Download audio or video (optionally clipped to a time range).

    Returns (base64_data, mime_type, video_id, file_extension).
    Uses yt-dlp download_ranges for efficient partial downloads when timestamps are set.
    """
    try:
        from yt_dlp import YoutubeDL
        from yt_dlp.utils import download_range_func
    except Exception as exc:
        raise RuntimeError("yt-dlp is required. Install with: pip install yt-dlp") from exc

    fmt = "bestaudio/best" if mode == "audio" else "bestvideo+bestaudio/best"

    with tempfile.TemporaryDirectory(prefix="yt_orig_", suffix="_dl") as tmp:
        out_dir = Path(tmp)
        ensure_directory(out_dir)

        outtmpl = str(out_dir / "%(id)s.%(ext)s")
        opts: Dict[str, Any] = {
            "format": fmt,
            "outtmpl": outtmpl,
            "quiet": True,
            "no_warnings": True,
        }

        start_sec = parse_timestamp_to_seconds(start_time)
        end_sec = parse_timestamp_to_seconds(end_time)
        if start_sec is not None or end_sec is not None:
            s = start_sec if start_sec is not None else 0.0
            e = end_sec if end_sec is not None else float("inf")
            opts["download_ranges"] = download_range_func(None, [(s, e)])
            opts["force_keyframes_at_cuts"] = True

        cookie_file = None
        if cookies:
            cookie_file = _create_cookie_file(cookies, url)
            opts["cookiefile"] = str(cookie_file)

        try:
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
        except Exception as exc:
            raise RuntimeError(f"Failed to download from YouTube: {exc}") from exc
        finally:
            if cookie_file and cookie_file.exists():
                cookie_file.unlink()

        video_id = (info or {}).get("id", "video")

        file_path = Path(filename)
        if not file_path.exists():
            candidates = sorted(
                (f for f in out_dir.iterdir() if f.is_file() and f.suffix not in (".txt", ".json", ".ytdl")),
                key=lambda f: f.stat().st_size,
                reverse=True,
            )
            if not candidates:
                raise RuntimeError("Download failed: no output file found")
            file_path = candidates[0]

        ext = file_path.suffix.lower().lstrip(".")
        mime_map: Dict[str, str] = {
            "m4a": "audio/mp4",
            "mp3": "audio/mpeg",
            "aac": "audio/aac",
            "ogg": "audio/ogg",
            "wav": "audio/wav",
            "mp4": "video/mp4",
            "mkv": "video/x-matroska",
            "avi": "video/x-msvideo",
            "webm": "audio/webm" if mode == "audio" else "video/webm",
        }
        default_mime = "audio/mp4" if mode == "audio" else "video/mp4"
        mime_type = mime_map.get(ext, default_mime)

        file_bytes = file_path.read_bytes()
        b64 = base64.b64encode(file_bytes).decode("utf-8")

        print(f"[YouTube] {mode} download complete: {file_path.name} ({len(file_bytes) // 1024}KB)")
        return b64, mime_type, video_id, ext


def fetch_youtube_all_sync(
    url: str,
    *,
    download_video: bool = False,
    download_audio: bool = False,
    download_transcript: bool = True,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    openai_api_key: Optional[str] = None,
    cookies: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Orchestrate transcript, audio, and/or video download for a YouTube URL.

    Returns a dict that may contain any of:
      markdown, audioData, audioMimeType, audioFilename,
      videoData, videoMimeType, videoFilename
    """
    result: Dict[str, Any] = {}

    if download_transcript:
        markdown = fetch_youtube_markdown(
            url,
            openai_api_key=openai_api_key,
            cookies=cookies,
            start_time=start_time,
            end_time=end_time,
        )
        result["markdown"] = markdown

    if download_audio:
        b64, mime, video_id, ext = fetch_youtube_original(url, "audio", start_time, end_time, cookies)
        result["audioData"] = b64
        result["audioMimeType"] = mime
        result["audioFilename"] = f"{video_id}.{ext}"

    if download_video:
        b64, mime, video_id, ext = fetch_youtube_original(url, "video", start_time, end_time, cookies)
        result["videoData"] = b64
        result["videoMimeType"] = mime
        result["videoFilename"] = f"{video_id}.{ext}"

    return result


async def convert_youtube(
    url: str,
    *,
    download_video: bool = False,
    download_audio: bool = False,
    download_transcript: bool = True,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    openai_api_key: Optional[str] = None,
    cookies: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    return await asyncio.to_thread(
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


def main(url: str) -> None:
    out = "./documents"
    lang = "en"
    model = "small"

    out_dir = Path(out).absolute()
    ensure_directory(out_dir)

    info = extract_video_info(url)
    video_id = info.get("id") or "video"
    title = info.get("title") or video_id

    chosen_lang = select_human_subtitle_lang(info, lang)
    transcript_path = out_dir / f"{video_id}.transcript.md"

    print("Checking SponsorBlock for sponsor segments...")
    sponsor_segments = fetch_sponsor_segments(video_id)

    if chosen_lang:
        print(f"Found human subtitles in language '{chosen_lang}'. Downloading…")
        vtt_path = download_human_subtitles(url, out_dir, video_id, chosen_lang)
        plain_text = vtt_to_text(vtt_path, sponsor_segments)
        markdown = build_markdown_transcript(title, url, chosen_lang, plain_text)
        transcript_path.write_text(markdown, encoding="utf-8")
        print(f"Transcript written to: {transcript_path}")
        return

    print("No human subtitles found. Downloading audio and transcribing with Whisper…")
    audio_path = download_audio(url, out_dir, video_id)
    text = transcribe_with_whisper(audio_path, model, lang, sponsor_segments)
    if not text:
        raise SystemExit("Transcription produced empty output.")
    markdown = build_markdown_transcript(title, url, lang, text)
    transcript_path.write_text(markdown, encoding="utf-8")
    print(f"Transcript written to: {transcript_path}")
