import asyncio, re

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

    def extract_text(node: dict) -> str:
        legacy = node.get("legacy") or {}
        txt = legacy.get("full_text") or legacy.get("text")
        if txt:
            return txt
        note = (
            (node.get("note_tweet") or {})
            .get("note_tweet_results", {})
            .get("result", {})
            .get("text")
        )
        return note or ""

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

                    # Resolve root author from the focal tweet if possible
                    if root_author_id is None:
                        if root_id and tid == str(root_id):
                            root_author_id = uid
                        elif not root_id:
                            # No explicit root tweet id provided; infer from first seen item
                            root_author_id = uid

                    # Keep only tweets by the root author that reply **only** to the root author
                    if root_author_id:
                        allow = False
                        # Always allow the focal/root tweet if provided
                        if root_id and tid == str(root_id):
                            allow = True
                        else:
                            reply_to_uid = legacy.get("in_reply_to_user_id_str")
                            mentions = (legacy.get("entities") or {}).get("user_mentions") or []
                            mention_ids = [m.get("id_str") for m in mentions if isinstance(m, dict) and m.get("id_str")]
                            # Only the root author may be mentioned (or none mentioned)
                            only_author_mentioned = (len(mention_ids) == 0) or (len(mention_ids) == 1 and mention_ids[0] == root_author_id)
                            if uid == root_author_id and reply_to_uid == root_author_id and only_author_mentioned:
                                allow = True
                        if allow:
                            text = extract_text(node)
                            if text:
                                results.append(text)

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
        # Nudge to load more thread items
        for _ in range(4):
            try:
                await page.mouse.wheel(0, 2200)
            except Exception:
                pass
            await asyncio.sleep(0.6)
    finally:
        await page.close()

    return results
