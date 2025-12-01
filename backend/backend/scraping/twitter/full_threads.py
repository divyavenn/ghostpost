import asyncio
import re

# Match TweetDetail GraphQL calls
TWEET_DETAIL_RE = re.compile(r"/i/api/graphql/[^/]+/TweetDetail")

MAX_TOP_REPLIES = 5


# it will scroll randomly slightly more or less than delay
async def scroll(page, delay: float = 1.5, scrolls: int = 3, distance: int = 2000):
    import random
    rand_scrolls = int(random.random() * 2.5) + scrolls - 1
    rand_distance = int(random.random() * 500) + distance - 250
    rand_time = random.random() * delay / 10 - delay / 20 + delay
    for _ in range(rand_scrolls):
        try:
            await page.mouse.wheel(0, rand_distance)
        except Exception:
            pass
        await asyncio.sleep(rand_time)


async def get_thread(ctx, tweet_url: str, root_id: str | None = None) -> dict:
    """
    Return thread tweets and top replies for a tweet.

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

    def extract_text(node: dict) -> str:
        """Extract text from tweet node, prioritizing note_tweet for long-form content."""
        note = ((node.get("note_tweet") or {}).get("note_tweet_results", {}).get("result", {}).get("text"))
        if note:
            return note
        legacy = node.get("legacy") or {}
        txt = legacy.get("full_text") or legacy.get("text")
        if txt:
            return txt
        return ""

    def extract_user_info(node: dict) -> tuple[str, str]:
        """Extract author handle and display name from tweet node."""
        # Strategy 1: core.user_results.result.core (new Twitter API structure)
        try:
            user_result = node.get("core", {}).get("user_results", {}).get("result", {})
            if user_result and isinstance(user_result, dict):
                core = user_result.get("core", {})
                if core.get("screen_name"):
                    return core.get("screen_name", ""), core.get("name", "")
        except (AttributeError, TypeError):
            pass

        # Strategy 2: core.user_results.result.legacy (older Twitter API structure)
        try:
            user_result = node.get("core", {}).get("user_results", {}).get("result", {})
            if user_result and isinstance(user_result, dict):
                legacy = user_result.get("legacy", {})
                if legacy.get("screen_name"):
                    return legacy.get("screen_name", ""), legacy.get("name", "")
        except (AttributeError, TypeError):
            pass

        # Strategy 3: Check for tweet wrapper (both core and legacy paths)
        try:
            if "tweet" in node and isinstance(node["tweet"], dict):
                inner = node["tweet"]
                user_result = inner.get("core", {}).get("user_results", {}).get("result", {})
                if user_result and isinstance(user_result, dict):
                    # Try core first (new API)
                    core = user_result.get("core", {})
                    if core.get("screen_name"):
                        return core.get("screen_name", ""), core.get("name", "")
                    # Fall back to legacy
                    legacy = user_result.get("legacy", {})
                    if legacy.get("screen_name"):
                        return legacy.get("screen_name", ""), legacy.get("name", "")
        except (AttributeError, TypeError):
            pass

        # Strategy 4: legacy.user
        try:
            user = node.get("legacy", {}).get("user", {})
            if user.get("screen_name"):
                return user.get("screen_name", ""), user.get("name", "")
        except (AttributeError, TypeError):
            pass

        # Strategy 5: direct user object
        try:
            user = node.get("user", {})
            if user.get("screen_name"):
                return user.get("screen_name", ""), user.get("name", "")
        except (AttributeError, TypeError):
            pass

        return "", ""

    def extract_likes(node: dict) -> int:
        """Extract like count from tweet node."""
        legacy = node.get("legacy") or {}
        return legacy.get("favorite_count") or 0

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
                                    handle, name = extract_user_info(node)
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
