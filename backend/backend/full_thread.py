import asyncio
import re

# Match TweetDetail GraphQL calls
TWEET_DETAIL_RE = re.compile(r"/i/api/graphql/[^/]+/TweetDetail")


async def get_thread(ctx, tweet_url: str, root_id: str | None = None):
    """
    Return all tweets in the thread authored by the original poster (self-thread only).
    - Reuses an existing Playwright context `ctx` (no new browser launches).
    - If `root_id` (tweet id) is provided, we use it to lock the root author id.
    - Falls back to first seen author if root cannot be resolved.
    - Preserves newlines; returns list[str] ordered by appearance (you may sort by created_at if needed).
    """
    page = await ctx.new_page()

    results: list[str] = []
    root_author_id: str | None = None
    seen_tweet_ids: set[str] = set()  # Track tweets we've added to avoid duplicates
    thread_tweet_ids: set[str] = set()  # Track which tweets are part of the actual thread chain

    def extract_text(node: dict) -> str:
        """Extract text from tweet node, prioritizing note_tweet for long-form content."""
        # First check for note_tweet (long-form tweets)
        note = ((node.get("note_tweet") or {}).get("note_tweet_results", {}).get("result", {}).get("text"))
        if note:
            return note

        # Then check legacy fields
        legacy = node.get("legacy") or {}
        txt = legacy.get("full_text") or legacy.get("text")
        if txt:
            return txt

        return ""

    async def on_response(resp):
        nonlocal root_author_id
        if not (TWEET_DETAIL_RE.search(resp.url) and resp.ok):
            return
        try:
            data = await resp.json()
        except Exception:
            return

        # Collect instructions from both containers
        instructions = []
        tc_v2 = (data.get("data") or {}).get("threaded_conversation_with_injections_v2") or {}
        instructions.extend(tc_v2.get("instructions", []) or [])
        tc_v1 = (data.get("data") or {}).get("threaded_conversation_with_injections") or {}
        instructions.extend(tc_v1.get("instructions", []) or [])

        for inst in instructions:
            for entry in inst.get("entries", []) or []:
                content = entry.get("content") or {}

                # Candidate shapes containing tweets
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

                    # Skip if we've already processed this tweet
                    if tid in seen_tweet_ids:
                        continue

                    # Resolve root author from the focal tweet if possible
                    if root_author_id is None:
                        if root_id and tid == str(root_id):
                            root_author_id = uid
                            thread_tweet_ids.add(tid)  # Root tweet is always part of thread
                        elif not root_id:
                            # No explicit root tweet id provided; infer from first seen item
                            root_author_id = uid
                            thread_tweet_ids.add(tid)

                    # Get reply info to check if this is part of the thread chain
                    in_reply_to_status_id = legacy.get("in_reply_to_status_id_str")

                    # Keep only tweets by the root author that are part of the thread chain
                    if root_author_id and uid == root_author_id:
                        allow = False

                        # Always allow the focal/root tweet
                        if root_id and tid == str(root_id):
                            allow = True
                            thread_tweet_ids.add(tid)
                        # Allow if it's replying to the root tweet or another tweet in the thread
                        elif in_reply_to_status_id:
                            if in_reply_to_status_id == str(root_id) or in_reply_to_status_id in thread_tweet_ids:
                                allow = True
                                thread_tweet_ids.add(tid)
                        # If no reply chain but it's the first tweet we see (likely the root)
                        elif not root_id and len(thread_tweet_ids) == 0:
                            allow = True
                            thread_tweet_ids.add(tid)

                        if allow:
                            text = extract_text(node)
                            if text and tid not in seen_tweet_ids:
                                results.append(text)
                                seen_tweet_ids.add(tid)

    page.on("response", lambda r: asyncio.create_task(on_response(r)))

    try:
        await page.goto(tweet_url, wait_until="domcontentloaded")
        # Wait for at least one TweetDetail to arrive
        try:
            await page.wait_for_event(
                "response",
                predicate=lambda r: TWEET_DETAIL_RE.search(r.url),
                timeout=30_000,
            )
        except Exception:
            pass

        # More aggressive scrolling to load entire thread
        # Scroll down multiple times to ensure all thread content loads
        for i in range(8):  # Increased from 4 to 8 scrolls
            try:
                await page.mouse.wheel(0, 3000)  # Increased scroll distance
            except Exception:
                pass
            await asyncio.sleep(0.8)  # Slightly longer wait between scrolls

        # Final wait to let any pending responses complete
        await asyncio.sleep(1.0)
    finally:
        await page.close()

    return results
