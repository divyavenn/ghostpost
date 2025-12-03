"""
Thread scraping for tweet threads and replies.
Provides functions to extract thread content and engagement data.
"""
import asyncio
import re
from datetime import datetime
from typing import Any

try:
    from datetime import UTC
except ImportError:
    from datetime import timezone
    UTC = timezone.utc

from backend.scraping.twitter.scraping_utils import (
    extract_likes,
    extract_metrics,
    extract_text,
    extract_user_info,
    extract_user_info_simple,
    scroll,
)

# Match TweetDetail GraphQL calls
TWEET_DETAIL_RE = re.compile(r"/i/api/graphql/[^/]+/TweetDetail")

MAX_TOP_REPLIES = 5


async def get_thread(ctx, tweet_url: str, root_id: str | None = None) -> dict:
    """
    Return thread tweets and top replies for a tweet.
    Used for building prompts for reply generation.

    Args:
        ctx: Playwright browser context
        tweet_url: URL of the tweet to scrape
        root_id: Optional root tweet ID for thread detection

    Returns:
        dict with:
            - thread: list[str] - texts from the original poster's thread
            - other_replies: list[dict] - up to 5 top replies from other users
              Each reply has: text, author_handle, author_name, likes
    """
    page = await ctx.new_page()

    thread_results: list[str] = []
    top_replies: list[dict] = []
    root_author_id: str | None = None
    seen_tweet_ids: set[str] = set()
    thread_tweet_ids: set[str] = set()

    async def on_response(resp):
        nonlocal root_author_id
        if not (TWEET_DETAIL_RE.search(resp.url) and resp.ok):
            return
        try:
            data = await resp.json()
        except Exception:
            return

        instructions = []
        tc_v2 = (data.get("data") or {}).get("threaded_conversation_with_injections_v2") or {}
        instructions.extend(tc_v2.get("instructions", []) or [])
        tc_v1 = (data.get("data") or {}).get("threaded_conversation_with_injections") or {}
        instructions.extend(tc_v1.get("instructions", []) or [])

        for inst in instructions:
            for entry in inst.get("entries", []) or []:
                content = entry.get("content") or {}

                candidates = []
                ic = content.get("itemContent") or {}
                if ic:
                    candidates.append(ic)
                ic2 = (content.get("item") or {}).get("itemContent") or {}
                if ic2:
                    candidates.append(ic2)
                for it in (content.get("items") or content.get("moduleItems") or []):
                    cand = (it.get("item") or {}).get("itemContent") or it.get("itemContent") or {}
                    if cand:
                        candidates.append(cand)

                for cand in candidates:
                    raw = (cand.get("tweet_results") or {}).get("result")
                    if not isinstance(raw, dict):
                        continue
                    node = raw.get("tweet") or raw
                    legacy = node.get("legacy") or {}
                    if not legacy:
                        continue

                    tid = legacy.get("id_str") or str(node.get("rest_id") or "")
                    uid = legacy.get("user_id_str")
                    if not tid or not uid:
                        continue

                    if tid in seen_tweet_ids:
                        continue

                    # Resolve root author from the focal tweet
                    if root_author_id is None:
                        if root_id and tid == str(root_id):
                            root_author_id = uid
                            thread_tweet_ids.add(tid)
                        elif not root_id:
                            root_author_id = uid
                            thread_tweet_ids.add(tid)

                    in_reply_to_status_id = legacy.get("in_reply_to_status_id_str")

                    # Check if this is by the root author (thread) or someone else (reply)
                    if root_author_id and uid == root_author_id:
                        # This is part of the thread (same author)
                        allow = False
                        if root_id and tid == str(root_id):
                            allow = True
                            thread_tweet_ids.add(tid)
                        elif in_reply_to_status_id:
                            if in_reply_to_status_id == str(root_id) or in_reply_to_status_id in thread_tweet_ids:
                                allow = True
                                thread_tweet_ids.add(tid)
                        elif not root_id and len(thread_tweet_ids) == 0:
                            allow = True
                            thread_tweet_ids.add(tid)

                        if allow:
                            text = extract_text(node)
                            if text and tid not in seen_tweet_ids:
                                thread_results.append(text)
                                seen_tweet_ids.add(tid)

                    elif root_author_id and uid != root_author_id:
                        # This is a reply from someone else - capture top replies
                        if len(top_replies) < MAX_TOP_REPLIES:
                            # Only capture replies to the root tweet or thread tweets
                            if in_reply_to_status_id and (
                                in_reply_to_status_id == str(root_id) or
                                in_reply_to_status_id in thread_tweet_ids
                            ):
                                text = extract_text(node)
                                if text:
                                    handle, name = extract_user_info_simple(node)
                                    likes = extract_likes(node)
                                    top_replies.append({
                                        "text": text,
                                        "author_handle": handle,
                                        "author_name": name,
                                        "likes": likes
                                    })
                                    seen_tweet_ids.add(tid)

    page.on("response", lambda r: asyncio.create_task(on_response(r)))

    try:
        await page.goto(tweet_url, wait_until="domcontentloaded")
        try:
            await page.wait_for_event(
                "response",
                predicate=lambda r: TWEET_DETAIL_RE.search(r.url),
                timeout=30_000,
            )
        except Exception:
            pass

        await scroll(page, scrolls=2)
        await asyncio.sleep(1)

    finally:
        await page.close()

    # Log error if thread scraping failed to get any results
    if len(thread_results) == 0 and root_id:
        from backend.utlils.utils import error
        error(
            f"Thread scraping returned empty for tweet {root_id}",
            status_code=500,
            function_name="get_thread",
            critical=False
        )

    return {
        "thread": thread_results,
        "other_replies": top_replies
    }


async def deep_scrape_thread(ctx, tweet_url: str, tweet_id: str, author_handle: str) -> dict[str, Any]:
    """
    Perform a deep scrape to get full thread with all replies.
    Scrolls to load more content. Used for engagement monitoring.

    Args:
        ctx: Playwright browser context
        tweet_url: URL of the tweet to scrape
        tweet_id: ID of the main tweet
        author_handle: Handle of the tweet author

    Returns:
        {
            "reply_count": int,
            "like_count": int,
            "quote_count": int,
            "retweet_count": int,
            "all_reply_ids": list[str],
            "replies": list[dict]  # Full reply data with in_reply_to_status_id
        }
    """
    page = await ctx.new_page()

    result = {
        "reply_count": 0,
        "like_count": 0,
        "quote_count": 0,
        "retweet_count": 0,
        "all_reply_ids": [],
        "replies": []
    }

    replies_map: dict[str, dict] = {}
    author_user_id: str | None = None

    async def on_response(resp):
        nonlocal result, author_user_id
        if not (TWEET_DETAIL_RE.search(resp.url) and resp.ok):
            return
        try:
            data = await resp.json()
        except Exception:
            return

        instructions = []
        tc_v2 = (data.get("data") or {}).get("threaded_conversation_with_injections_v2") or {}
        instructions.extend(tc_v2.get("instructions", []) or [])
        tc_v1 = (data.get("data") or {}).get("threaded_conversation_with_injections") or {}
        instructions.extend(tc_v1.get("instructions", []) or [])

        for inst in instructions:
            for entry in inst.get("entries", []) or []:
                content = entry.get("content") or {}

                candidates = []
                ic = content.get("itemContent") or {}
                if ic:
                    candidates.append(ic)
                ic2 = (content.get("item") or {}).get("itemContent") or {}
                if ic2:
                    candidates.append(ic2)
                for it in (content.get("items") or content.get("moduleItems") or []):
                    cand = (it.get("item") or {}).get("itemContent") or it.get("itemContent") or {}
                    if cand:
                        candidates.append(cand)

                for cand in candidates:
                    raw = (cand.get("tweet_results") or {}).get("result")
                    if not isinstance(raw, dict):
                        continue
                    node = raw.get("tweet") or raw
                    legacy = node.get("legacy") or {}
                    if not legacy:
                        continue

                    tid = legacy.get("id_str") or str(node.get("rest_id") or "")
                    uid = legacy.get("user_id_str")
                    if not tid:
                        continue

                    # If this is the main tweet, get metrics and author
                    if tid == tweet_id:
                        metrics = extract_metrics(node)
                        result["reply_count"] = metrics["replies"]
                        result["like_count"] = metrics["likes"]
                        result["quote_count"] = metrics["quotes"]
                        result["retweet_count"] = metrics["retweets"]
                        author_user_id = uid
                        continue

                    # Skip if already seen
                    if tid in replies_map:
                        continue

                    # Extract reply data
                    in_reply_to = legacy.get("in_reply_to_status_id_str")
                    if not in_reply_to:
                        continue

                    user_info = extract_user_info(node)
                    metrics = extract_metrics(node)
                    text = extract_text(node)

                    # Get created_at
                    created_at = legacy.get("created_at", "")
                    # Convert Twitter date to ISO format
                    try:
                        if created_at:
                            dt = datetime.strptime(created_at, "%a %b %d %H:%M:%S %z %Y")
                            created_at = dt.isoformat()
                    except Exception:
                        created_at = datetime.now(UTC).isoformat()

                    reply_data = {
                        "id": tid,
                        "text": text,
                        "handle": user_info["handle"],
                        "username": user_info["username"],
                        "author_profile_pic_url": user_info["author_profile_pic_url"],
                        "followers": user_info["followers"],
                        "in_reply_to_status_id": in_reply_to,
                        "created_at": created_at,
                        "url": f"https://x.com/{user_info['handle']}/status/{tid}",
                        "user_id": uid,
                        **metrics
                    }

                    replies_map[tid] = reply_data

    page.on("response", lambda r: asyncio.create_task(on_response(r)))

    try:
        await page.goto(tweet_url, wait_until="domcontentloaded")
        try:
            await page.wait_for_event(
                "response",
                predicate=lambda r: TWEET_DETAIL_RE.search(r.url),
                timeout=30_000,
            )
        except Exception:
            pass

        # Scroll to load more replies
        last_count = 0
        no_new_count = 0
        maxscrolls = 10

        for _ in range(maxscrolls):
            await scroll(page, scrolls=2, delay=1.0)
            await asyncio.sleep(1)

            current_count = len(replies_map)
            if current_count == last_count:
                no_new_count += 1
                if no_new_count >= 2:
                    break
            else:
                no_new_count = 0
                last_count = current_count

    finally:
        await page.close()

    # Filter out the author's own replies (those are thread continuations, not comments)
    filtered_replies = []
    for reply in replies_map.values():
        if author_user_id and reply.get("user_id") == author_user_id:
            continue
        # Remove user_id from output (internal use only)
        reply_copy = {k: v for k, v in reply.items() if k != "user_id"}
        filtered_replies.append(reply_copy)

    result["all_reply_ids"] = list(replies_map.keys())
    result["replies"] = filtered_replies

    return result
