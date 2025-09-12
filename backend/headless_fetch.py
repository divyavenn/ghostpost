import re
import asyncio
from asyncio import sleep
from full_thread import get_thread

TWEET_API_RE = re.compile(
  r"(UserTweets|TimelineTweets|AdaptiveSearchTimeline|SearchTimeline|SearchTimelineV2|HomeTimeline|HomeLatestTimeline)"
)

# --- helpers you already had/asked for ---
def within_hours(created_at: str, hours: int = 72) -> bool:
    from datetime import datetime, timezone, timedelta
    def parse_twitter_date(s: str) -> datetime:
        return datetime.strptime(s, "%a %b %d %H:%M:%S %z %Y")
    try:
        dt = parse_twitter_date(created_at)
    except Exception:
        return False
    now = datetime.now(timezone.utc)
    return dt >= now - timedelta(hours=hours)

def extract_handle(tweet_res: dict, data: dict | None = None) -> str | None:
    """Extract handle by searching for user ID in the data structure"""
    # Try to get a user ID to look for
    uid = (
        tweet_res.get("legacy", {}).get("user_id_str")
        or tweet_res.get("rest_id")
        or (tweet_res.get("core", {}).get("user_results", {}).get("result", {}) or {}).get("rest_id")
    )
    
    # Check for direct screen_name in common paths first
    if isinstance(tweet_res, dict):
        # Direct screen_name in legacy
        if tweet_res.get("legacy", {}).get("screen_name"):
            return tweet_res["legacy"]["screen_name"]
        
        # Check in user object
        if tweet_res.get("user", {}).get("screen_name"):
            return tweet_res["user"]["screen_name"]
        
        # Check in core.user_results
        user_result = (tweet_res.get("core", {}).get("user_results", {}).get("result", {}) or {})
        if user_result.get("legacy", {}).get("screen_name"):
            return user_result["legacy"]["screen_name"]
    
    # Fall back to searching by user ID
    if not uid or not data:
        return None
        
    def walk(obj):
        if isinstance(obj, dict):
            # Direct match by rest_id
            if obj.get("rest_id") == uid:
                legacy = obj.get("legacy", {})
                h = legacy.get("screen_name")
                if h: 
                    return h
            # Direct screen_name check in every dict
            if obj.get("screen_name"):
                return obj.get("screen_name")
            # Continue searching
            for v in obj.values():
                r = walk(v)
                if r: return r
        elif isinstance(obj, list):
            for v in obj:
                r = walk(v)
                if r: return r
        return None
    
    return walk(data)

async def collect_from_page(ctx, url: str, handle: str | None, max_scrolls=10):
    tweets = {}
    page   = await ctx.new_page()
    min_likes = 5
    pending = set()

    def engagement_score (legacy: dict) -> int:
        likes  = int(legacy.get("favorite_count", 0))
        rts    = int(legacy.get("retweet_count", 0))
        quotes = int(legacy.get("quote_count", 0))
        reps   = int(legacy.get("reply_count", 0))
        return likes + 2*rts + 3*quotes + reps

    def is_entry_promoted(entry: dict) -> bool:
        eid = (entry.get("entryId") or "").lower()
        if eid.startswith(("promoted-", "promotedtweet-", "promotedtweet", "promoted")):
            return True
        elem = (
            entry.get("content", {}).get("clientEventInfo", {}).get("element")
            or entry.get("clientEventInfo", {}).get("element")
            or ""
        )
        if isinstance(elem, str) and "promoted" in elem.lower():
            return True
        content = entry.get("content") or {}
        module = content.get("items") or content.get("moduleItems") or []
        if module and (content.get("displayType") or "").lower().startswith("promoted"):
            return True
        return False
    
    def get_tweet_text(tweet_res: dict) -> str:
        legacy = tweet_res.get("legacy", {}) or {}
        if "full_text" in legacy and legacy["full_text"]:
            return legacy["full_text"]
        if "text" in legacy and legacy["text"]:
            return legacy["text"]
        note = (
            tweet_res.get("note_tweet", {})
            .get("note_tweet_results", {})
            .get("result", {})
            .get("text")
        )
        if note:
            return note
        return ""

    def extract_followers(tweet_res: dict) -> int:
        try:
            followers = (
                ((tweet_res or {}).get("core") or {})
                    .get("user_results", {})
                    .get("result", {})
                    .get("legacy", {})
                    .get("followers_count")
            )
            return int(followers) if isinstance(followers, int) else 0
        except Exception:
            return 0
            
    def extract_user_data(tweet_res: dict) -> tuple:
        """Extract username and handle from tweet data"""
        user_handle = None
        user_name = None
        
        # Debug: Print the first level of keys in the tweet_res dict
        # print(f"DEBUG: tweet_res keys: {list(tweet_res.keys() if isinstance(tweet_res, dict) else [])}")
        
        # Try the most common Twitter API response structures
        
        # Structure 1: Direct user property in legacy
        if tweet_res.get("legacy", {}).get("user", {}):
            user = tweet_res["legacy"]["user"]
            user_handle = user.get("screen_name")
            user_name = user.get("name")
            if user_handle:
                # print(f"DEBUG: Found user in legacy.user: {user_name} / @{user_handle}")
                return user_name, user_handle
        
        # Structure 2: User in core.user_results
        if tweet_res.get("core", {}).get("user_results", {}).get("result", {}):
            user_result = tweet_res["core"]["user_results"]["result"]
            if user_result.get("legacy", {}):
                user_handle = user_result["legacy"].get("screen_name")
                user_name = user_result["legacy"].get("name")
                if user_handle:
                    # print(f"DEBUG: Found user in core.user_results: {user_name} / @{user_handle}")
                    return user_name, user_handle
        
        # Structure 3: Direct user property (not in legacy)
        if tweet_res.get("user", {}):
            user = tweet_res["user"]
            user_handle = user.get("screen_name")
            user_name = user.get("name")
            if user_handle:
                # print(f"DEBUG: Found direct user: {user_name} / @{user_handle}")
                return user_name, user_handle
        
        # Structure 4: Look in known potential paths based on observed API response structures
        paths = [
            ["legacy", "user"],
            ["user"],
            ["core", "user_results", "result", "legacy"],
            ["core", "user_results", "result"],
            ["legacy", "retweeted_status_result", "result", "core", "user_results", "result", "legacy"],
            ["legacy", "retweeted_status_result", "result", "legacy", "user"],
            ["tweet", "core", "user_results", "result", "legacy"]
        ]
        
        for path in paths:
            current = tweet_res
            valid_path = True
            for key in path:
                if not isinstance(current, dict) or key not in current:
                    valid_path = False
                    break
                current = current[key]
            
            if valid_path and isinstance(current, dict):
                if current.get("screen_name"):
                    user_handle = current.get("screen_name")
                    user_name = current.get("name")
                    # print(f"DEBUG: Found user through path {path}: {user_name} / @{user_handle}")
                    return user_name, user_handle
        # Structure 5: Deep recursive search for user info
        def search_for_user(obj, depth=0, max_depth=5):
            if depth >= max_depth:
                return None, None
            
            if not isinstance(obj, dict):
                return None, None
                
            # Check if this object has user info
            if "screen_name" in obj and obj.get("screen_name"):
                return obj.get("name"), obj.get("screen_name")
                
            # Check common user containers
            for key in ["user", "legacy", "result"]:
                if key in obj and isinstance(obj[key], dict):
                    user_n, user_h = search_for_user(obj[key], depth + 1, max_depth)
                    if user_h:
                        return user_n, user_h
            
            # Search all other dictionary values
            for val in obj.values():
                if isinstance(val, dict):
                    user_n, user_h = search_for_user(val, depth + 1, max_depth)
                    if user_h:
                        return user_n, user_h
                elif isinstance(val, list):
                    for item in val:
                        if isinstance(item, dict):
                            user_n, user_h = search_for_user(item, depth + 1, max_depth)
                            if user_h:
                                return user_n, user_h
            
            return None, None
        
        # Try deep recursive search if all else failed
        deep_name, deep_handle = search_for_user(tweet_res)
        if deep_handle:
            # print(f"DEBUG: Found user through deep search: {deep_name} / @{deep_handle}")
            return deep_name, deep_handle
        
        # If we get here, we really couldn't find the user info
        # print(f"DEBUG: Could not find user info in tweet_res")
        return user_name, user_handle

    def get(d, *path, default=None):
        x = d
        for k in path:
            if isinstance(x, dict):
                x = x.get(k)
            else:
                return default
        return x if x is not None else default

    # keep your promo filter disabled for now (debug phase)

    def is_original_post(legacy: dict) -> bool:
        if legacy.get("retweeted_status_result"):
            return False
        text = (legacy.get("full_text") or legacy.get("text") or "").lstrip()
        if text.startswith("RT @"):
            return False
        in_reply_to_user = legacy.get("in_reply_to_user_id_str")
        #user_id          = legacy.get("user_id_str")
        is_reply         = legacy.get("in_reply_to_status_id_str") or in_reply_to_user
        #if is_reply and (not user_id or not in_reply_to_user or user_id != in_reply_to_user):
        if is_reply:
            return False
        return True

    def collect_instructions(data: dict) -> list:
        instr = []
        ur = get(data, "data", "user", "result", default={})
        tl = (ur.get("timeline_v2") or ur.get("timeline") or {})
        tl = tl.get("timeline", tl)
        if isinstance(tl, dict):
            instr.extend(tl.get("instructions", []) or [])
        stl = get(data, "data", "search_by_raw_query", "search_timeline", "timeline", default={})
        if isinstance(stl, dict):
            instr.extend(stl.get("instructions", []) or [])
        return instr

    # --- debug helper: print why we dropped an entry ---
    def dbg(reason, tid=None, resp=None):
        return
        op = "n/a"
        try:
            if resp and "/graphql/" in resp.url:
                op = resp.url.split("/graphql/")[1].split("?")[0]
            else:
                op = resp.url
        except Exception:
            pass
        print(f"[drop:{reason}] tid={tid or 'n/a'} op={op}")

    async def grab(resp):
        if not (TWEET_API_RE.search(resp.url)):
            return
        try:
            data = await resp.json()
        except Exception:
            return

        for inst in collect_instructions(data):
            if inst.get("type") not in ("TimelineAddEntries", "TimelineReplaceEntry", "TimelineReplaceEntries", "TimelineAddToModule"):
                continue

            for entry in inst.get("entries", []) or []:
                if is_entry_promoted(entry):
                    continue
                
                content = entry.get("content") or {}
                # direct itemContent (single tweet)
                item = content.get("itemContent") or content.get("item_content") or {}

                # build candidate list including module items (carousels/grouped entries)
                candidates = []
                if item:
                    candidates.append(item)
                for it in (content.get("items") or content.get("moduleItems") or []):
                    ic = (it.get("item") or {}).get("itemContent") or it.get("itemContent") or {}
                    if ic:
                        candidates.append(ic)

                found_any = False
                for it_item in candidates:
                    raw = get(it_item, "tweet_results", "result") \
                       or get(content, "item", "content", "tweet_results", "result")
                    if not isinstance(raw, dict):
                        continue

                    # unwrap TweetWithVisibilityResults
                    node = raw.get("tweet") or raw

                    legacy = node.get("legacy") or {}
                    if not legacy:
                        # sometimes legacy only appears under quoted result
                        qleg = get(node, "quoted_status_result", "result", "legacy")
                        if not qleg:
                            dbg("no_legacy", (raw.get("rest_id") if isinstance(raw, dict) else None), resp=resp)
                            continue
                        legacy = qleg

                    created_at = legacy.get("created_at")
                    if not created_at:
                        dbg("no_created_at", legacy.get("id_str"), resp=resp)
                        continue
                    if not within_hours(created_at, hours=48):  # keep your current 27h test window
                        dbg("too_old", legacy.get("id_str"), resp=resp)
                        continue

                    # optional: re-enable filters once debugged
                    if (not is_original_post(legacy)) or (int(legacy.get("favorite_count", 0)) < min_likes):
                         dbg("filter_original_or_likes", legacy.get("id_str"), resp=resp)
                         continue

                    tid = legacy.get("id_str") or str(node.get("rest_id") or "")
                    if not tid:
                        dbg("no_tid", resp=resp)
                        continue

                    # Get the username and handle from the data first
                    # This will be more accurate than relying on the URL handle
                    user_name, user_handle = extract_user_data(node)
                    
                    # If we couldn't extract the handle, try additional methods
                    if not user_handle:
                        # Try to extract handle using the older extract_handle method
                        extracted_handle = extract_handle(node, data)
                        if extracted_handle:
                            print(f"DEBUG: Got handle from extract_handle: {extracted_handle}")
                            user_handle = extracted_handle
                        elif handle:  # Fall back to URL handle if provided
                            print(f"DEBUG: Falling back to URL handle: {handle}")
                            user_handle = handle
                            
                    # If we have the handle but no username, set a default display name based on the handle
                    if user_handle and not user_name:
                        user_name = user_handle.replace("_", " ")
                        # print(f"DEBUG: Setting default user_name: {user_name} from handle: {user_handle}")
                    
                    tweets[tid] = {
                        "id": tid,
                        "text": get_tweet_text(node),
                        "likes": int(legacy.get("favorite_count", 0)),
                        "retweets": int(legacy.get("retweet_count", 0)),
                        "quotes": int(legacy.get("quote_count", 0)),
                        "replies": int(legacy.get("reply_count", 0)),
                        "score": engagement_score(legacy),
                        "followers": extract_followers(node),
                        "created_at": created_at,
                        "url": f"https://x.com/{user_handle}/status/{tid}" if (user_handle) else f"https://x.com/i/web/status/{tid}",
                        "username": user_name,
                        "handle": user_handle,
                    }
                    found_any = True

                if not found_any:
                    dbg("no_raw", resp=resp)

    def event_handler(resp):
        t = asyncio.create_task(grab(resp))
        pending.add(t)
        t.add_done_callback(lambda _t: pending.discard(_t))

    page.on("response", event_handler)

    await page.goto(url, wait_until="domcontentloaded")
    if handle:
        print(f"Got to @{handle}'s timeline! via {url}")
    else: 
        print(f"Got to search results via {url}")

    await page.wait_for_event(
        "response",
        predicate=lambda r: TWEET_API_RE.search(r.url),
        timeout=30_000,
    )

    for _ in range(max_scrolls):
        await sleep(5)
        await page.mouse.wheel(0, 4000)

    await asyncio.sleep(1.0)
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)

    await page.close()
    
    for t in tweets.values():
        t["thread"] = await get_thread(ctx, t["url"], root_id=t["id"])
        
        # Keep the text in the main tweet for display
        # t.pop("text", None)  # Uncomment if you want to save space
            
    return tweets

