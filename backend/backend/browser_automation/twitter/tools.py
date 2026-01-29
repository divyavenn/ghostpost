import asyncio
import re

from backend.config import MAX_TWEET_AGE_HOURS
from backend.utlils.utils import notify

from .scraping_utils import scroll
from .thread import get_thread

try:  # Python 3.11+
    from datetime import UTC  # type: ignore[attr-defined]
except ImportError:  # Python <3.11
    from datetime import timezone
    UTC = timezone.utc

try:
    from backend.utlils.resolve_imports import ensure_standalone_imports
except ModuleNotFoundError:  # Running from inside backend/
    from backend.utlils.resolve_imports import ensure_standalone_imports

ensure_standalone_imports(globals())

TWEET_API_RE = re.compile(r"(UserTweets|TimelineTweets|AdaptiveSearchTimeline|SearchTimeline|SearchTimelineV2|HomeTimeline|HomeLatestTimeline)")


# --- helpers you already had/asked for ---
def within_hours(created_at: str, hours: int = 72) -> bool:
    from datetime import datetime, timedelta

    def parse_twitter_date(s: str) -> datetime:
        return datetime.strptime(s, "%a %b %d %H:%M:%S %z %Y")

    try:
        dt = parse_twitter_date(created_at)
    except Exception:
        return False
    now = datetime.now(UTC)
    return dt >= now - timedelta(hours=hours)


def extract_handle(tweet_res: dict, data: dict | None = None) -> str | None:
    """Extract handle by searching for user ID in the data structure - fallback method"""
    if not isinstance(tweet_res, dict):
        return None

    # Strategy 1: Try to get the user ID from the tweet author
    uid = None
    try:
        # First try to get user_id from legacy (most common)
        uid = tweet_res.get("legacy", {}).get("user_id_str")
        if not uid:
            # Try core.user_results.result.rest_id
            uid = (tweet_res.get("core", {}).get("user_results", {}).get("result", {}) or {}).get("rest_id")
        if not uid:
            # Try rest_id at top level (less common)
            uid = tweet_res.get("rest_id")
    except (AttributeError, TypeError):
        pass

    # Strategy 2: Check for direct screen_name in common paths first
    # This is fast and works for most cases
    try:
        # Check in core.user_results.result.legacy (most reliable for author)
        user_result = tweet_res.get("core", {}).get("user_results", {}).get("result", {})
        if user_result and isinstance(user_result, dict):
            handle = user_result.get("legacy", {}).get("screen_name")
            if handle and isinstance(handle, str):
                return handle

        # Check for tweet wrapper
        if "tweet" in tweet_res and isinstance(tweet_res["tweet"], dict):
            inner_tweet = tweet_res["tweet"]
            user_result = inner_tweet.get("core", {}).get("user_results", {}).get("result", {})
            if user_result and isinstance(user_result, dict):
                handle = user_result.get("legacy", {}).get("screen_name")
                if handle and isinstance(handle, str):
                    return handle

        # Check in direct user object
        if tweet_res.get("user", {}).get("screen_name"):
            handle = tweet_res["user"]["screen_name"]
            if handle and isinstance(handle, str):
                return handle

        # Check in legacy.user
        if tweet_res.get("legacy", {}).get("user", {}).get("screen_name"):
            handle = tweet_res["legacy"]["user"]["screen_name"]
            if handle and isinstance(handle, str):
                return handle
    except (AttributeError, TypeError):
        pass

    # Strategy 3: If we have a user ID and the full data payload, search by matching user ID
    if uid and data:

        def walk(obj, depth=0, max_depth=10):
            if depth >= max_depth:
                return None

            if isinstance(obj, dict):
                # Check if this object is a user with matching rest_id
                if obj.get("rest_id") == uid:
                    # Found matching user, look for screen_name
                    handle = obj.get("legacy", {}).get("screen_name")
                    if handle and isinstance(handle, str):
                        return handle

                # Continue searching in nested dicts
                for key, val in obj.items():
                    # Skip quoted/retweeted content to avoid wrong user
                    if key in {"quoted_status_result", "retweeted_status_result", "quoted_tweet", "retweeted_tweet"}:
                        continue
                    result = walk(val, depth + 1, max_depth)
                    if result:
                        return result

            elif isinstance(obj, list):
                for item in obj:
                    result = walk(item, depth + 1, max_depth)
                    if result:
                        return result

            return None

        result = walk(data)
        if result:
            return result

    # Strategy 4: Last resort - broad search for any screen_name (risky, could get wrong user)
    # Only use if we have no other option
    def find_any_screen_name(obj, depth=0, max_depth=5):
        if depth >= max_depth:
            return None

        if isinstance(obj, dict):
            # Avoid quoted/retweeted content
            if any(key in obj for key in {"quoted_status_result", "retweeted_status_result"}):
                return None

            # Check for screen_name at this level
            if "screen_name" in obj and obj.get("screen_name"):
                handle = obj["screen_name"]
                # Validate it looks like a Twitter handle
                if isinstance(handle, str) and handle and " " not in handle and len(handle) <= 15:
                    return handle

            # Search in priority order
            for key in ["core", "user_results", "user", "legacy"]:
                if key in obj:
                    result = find_any_screen_name(obj[key], depth + 1, max_depth)
                    if result:
                        return result

        return None

    return find_any_screen_name(tweet_res)


async def collect_from_page(ctx, url: str, handle: str | None, *, username=None, write_callback=None, stats=None):
    """
    Collect tweets from a page with progressive writing.

    Args:
        ctx: Browser context
        url: URL to scrape
        handle: Twitter handle (if scraping user timeline)
        max_scrolls: Number of scrolls
        username: Username for cache writes
        write_callback: Async function to call when new tweets are found
        stats: Optional ScrapeStats object to track filtering statistics
    """
    from backend.utlils.utils import is_tweet_seen

    tweets = {}
    page = await ctx.new_page()
    min_likes = 5
    min_impressions_for_discovery = 2000  # Only applied to FYP/query scrapes, not user timelines
    pending = set()
    max_scrolls = 5

    def engagement_score(legacy: dict) -> int:
        likes = int(legacy.get("favorite_count", 0))
        rts = int(legacy.get("retweet_count", 0))
        quotes = int(legacy.get("quote_count", 0))
        reps = int(legacy.get("reply_count", 0))
        return likes + 2 * rts + 3 * quotes + reps

    def is_entry_promoted(entry: dict) -> bool:
        eid = (entry.get("entryId") or "").lower()
        if eid.startswith(("promoted-", "promotedtweet-", "promotedtweet", "promoted")):
            return True
        elem = (entry.get("content", {}).get("clientEventInfo", {}).get("element") or entry.get("clientEventInfo", {}).get("element") or "")
        if isinstance(elem, str) and "promoted" in elem.lower():
            return True
        content = entry.get("content") or {}
        module = content.get("items") or content.get("moduleItems") or []
        if module and (content.get("displayType") or "").lower().startswith("promoted"):
            return True
        return False

    def get_tweet_text(tweet_res: dict) -> str:
        """Extract tweet text, prioritizing note_tweet for long-form content."""
        # First check for note_tweet (long-form tweets, priority since they're complete)
        note = (tweet_res.get("note_tweet", {}).get("note_tweet_results", {}).get("result", {}).get("text"))
        if note:
            return note

        # Then check legacy fields
        legacy = tweet_res.get("legacy", {}) or {}
        if "full_text" in legacy and legacy["full_text"]:
            return legacy["full_text"]
        if "text" in legacy and legacy["text"]:
            return legacy["text"]

        return ""

    def extract_followers(tweet_res: dict) -> int:
        try:
            followers = (((tweet_res or {}).get("core") or {}).get("user_results", {}).get("result", {}).get("legacy", {}).get("followers_count"))
            return int(followers) if isinstance(followers, int) else 0
        except Exception:
            return 0

    def extract_author_profile_pic(tweet_res: dict) -> str:
        """Extract the author's profile picture URL from tweet data."""
        try:
            # Strategy 1: Check for avatar object (newer Twitter API structure)
            user_result = tweet_res.get("core", {}).get("user_results", {}).get("result", {})
            if user_result and isinstance(user_result, dict):
                # Check avatar.image_url (new Twitter API structure)
                avatar = user_result.get("avatar", {})
                if avatar and isinstance(avatar, dict):
                    profile_pic = avatar.get("image_url")
                    if profile_pic:
                        # Replace _normal with _400x400 for higher resolution
                        return profile_pic.replace("_normal", "_400x400")

                # Fallback: Check legacy.profile_image_url_https (older structure)
                legacy = user_result.get("legacy", {})
                if legacy:
                    profile_pic = legacy.get("profile_image_url_https")
                    if profile_pic:
                        return profile_pic.replace("_normal.", "_400x400.")

            # Strategy 2: Check if there's a 'tweet' wrapper
            if "tweet" in tweet_res and isinstance(tweet_res["tweet"], dict):
                inner_tweet = tweet_res["tweet"]
                user_result = inner_tweet.get("core", {}).get("user_results", {}).get("result", {})
                if user_result and isinstance(user_result, dict):
                    # Check avatar first
                    avatar = user_result.get("avatar", {})
                    if avatar and isinstance(avatar, dict):
                        profile_pic = avatar.get("image_url")
                        if profile_pic:
                            return profile_pic.replace("_normal", "_400x400")
                    # Fallback to legacy
                    profile_pic = user_result.get("legacy", {}).get("profile_image_url_https")
                    if profile_pic:
                        return profile_pic.replace("_normal.", "_400x400.")

            # Strategy 3: Legacy structure
            if tweet_res.get("legacy", {}).get("user", {}):
                user = tweet_res["legacy"]["user"]
                # Check for avatar first
                if user.get("avatar", {}).get("image_url"):
                    profile_pic = user["avatar"]["image_url"]
                    return profile_pic.replace("_normal", "_400x400")
                # Fallback to profile_image_url_https
                if user.get("profile_image_url_https"):
                    profile_pic = user["profile_image_url_https"]
                    return profile_pic.replace("_normal.", "_400x400.")

            # Default Twitter avatar if not found
            return "https://abs.twimg.com/sticky/default_profile_images/default_profile_400x400.png"
        except Exception:
            return "https://abs.twimg.com/sticky/default_profile_images/default_profile_400x400.png"

    def get_media_types(node: dict) -> set[str]:
        """
        Extract all media types from a tweet.
        Returns set of media types: {"photo", "video", "animated_gif"}
        Empty set if no media.
        """
        inner_node = node.get("tweet") or node
        legacy = inner_node.get("legacy", {})

        media_types = set()

        # Check both entities and extended_entities
        for key in ["entities", "extended_entities"]:
            entities = legacy.get(key, {})
            media_list = entities.get("media", [])

            if media_list and isinstance(media_list, list):
                for media_item in media_list:
                    media_type = media_item.get("type")
                    if media_type:
                        media_types.add(media_type)

        return media_types

    def has_external_urls(node: dict) -> bool:
        """
        Check if tweet contains external URLs (not media URLs).
        Returns True if external links present.
        """
        inner_node = node.get("tweet") or node
        legacy = inner_node.get("legacy", {})
        entities = legacy.get("entities", {})

        urls = entities.get("urls", [])
        # Return True if there are any URLs (these are external links, not media)
        return bool(urls and len(urls) > 0)

    def has_unsupported_content(node: dict) -> bool:
        """
        Returns True if tweet contains content the AI VLM cannot process:
        - Videos (type: "video")
        - Animated GIFs (type: "animated_gif")  
        - External URLs (articles, links)
        - Quoted tweets containing any of the above (recursive)
        
        Returns False for:
        - Pure text-only tweets
        - Tweets with static images (type: "photo")
        - Text/images quoting text/images
        """
        inner_node = node.get("tweet") or node

        # Check for videos or animated GIFs (NOT photos)
        media_types = get_media_types(inner_node)
        unsupported_media = {"video", "animated_gif"}

        if media_types & unsupported_media:  # Intersection - has video or GIF
            return True

        # Check for external URLs
        if has_external_urls(inner_node):
            return True

        # Recursively check quoted tweet
        quoted_result = inner_node.get("quoted_status_result", {})
        if quoted_result:
            quoted_tweet = quoted_result.get("result", {})
            if quoted_tweet and isinstance(quoted_tweet, dict):
                # Recursive call - check if quoted tweet has unsupported content
                if has_unsupported_content(quoted_tweet):
                    return True

        return False

    def extract_media_urls(node: dict) -> list[dict]:
        """
        Extract image URLs and metadata from tweet media.
        Returns list of dicts with structure:
        [
            {
                "type": "photo",
                "url": "https://pbs.twimg.com/media/...",
                "alt_text": "Optional alt text for accessibility"
            }
        ]
        """
        inner_node = node.get("tweet") or node
        legacy = inner_node.get("legacy", {})

        media_items = []

        # Prefer extended_entities over entities (has full resolution)
        extended = legacy.get("extended_entities", {})
        entities = legacy.get("entities", {})

        media_list = extended.get("media") or entities.get("media") or []

        for media_item in media_list:
            media_type = media_item.get("type")

            # Only extract photos (we filter videos/GIFs already)
            if media_type == "photo":
                # Get highest quality image URL
                media_url = media_item.get("media_url_https") or media_item.get("media_url")

                # Get alt text if available
                alt_text = media_item.get("ext_alt_text", "")

                if media_url:
                    media_items.append({"type": "photo", "url": media_url, "alt_text": alt_text})

        return media_items

    def extract_quoted_tweet(node: dict) -> dict | None:
        """
        Extract quoted tweet data if present.
        Returns None if no quoted tweet.
        """
        inner_node = node.get("tweet") or node
        quoted_result = inner_node.get("quoted_status_result", {})

        if not quoted_result:
            return None

        quoted_node = quoted_result.get("result", {})
        if not quoted_node or not isinstance(quoted_node, dict):
            return None

        # Unwrap if needed
        quoted_inner = quoted_node.get("tweet") or quoted_node
        quoted_legacy = quoted_inner.get("legacy", {})

        if not quoted_legacy:
            return None

        # Extract quoted tweet data using existing helper functions
        quoted_text = get_tweet_text(quoted_inner)
        quoted_name, quoted_handle = extract_user_data(quoted_inner)
        quoted_tid = quoted_legacy.get("id_str")

        if not quoted_text or not quoted_handle:
            return None

        return {
            "text": quoted_text,
            "author_name": quoted_name or quoted_handle,
            "author_handle": quoted_handle,
            "author_profile_pic_url": extract_author_profile_pic(quoted_inner),
            "media": extract_media_urls(quoted_inner),
            "created_at": quoted_legacy.get("created_at", ""),
            "url": f"https://x.com/{quoted_handle}/status/{quoted_tid}" if quoted_tid else ""
        }

    def extract_user_data(tweet_res: dict) -> tuple:
        """Extract username and handle from tweet data - for the ACTUAL POSTER, not quoted/retweeted users"""
        user_handle = None
        user_name = None

        # Debug: Uncomment to see tweet structure when debugging
        # print(f"DEBUG: tweet_res keys: {list(tweet_res.keys() if isinstance(tweet_res, dict) else [])}")

        if not isinstance(tweet_res, dict):
            return None, None

        # IMPORTANT: Priority order matters here. We need to get the actual tweet author,
        # NOT the author of any quoted/retweeted content!

        # Strategy 1: HIGHEST PRIORITY - User in core.user_results.result.legacy
        # This is the most reliable location for the tweet author in modern Twitter API responses
        try:
            user_result = tweet_res.get("core", {}).get("user_results", {}).get("result", {})
            if user_result and isinstance(user_result, dict):
                legacy = user_result.get("legacy", {})
                if legacy:
                    user_handle = legacy.get("screen_name")
                    user_name = legacy.get("name")
                    if user_handle:
                        return user_name, user_handle
        except (AttributeError, TypeError):
            pass

        # Strategy 2: Check if there's a 'tweet' wrapper (TweetWithVisibilityResults)
        if "tweet" in tweet_res and isinstance(tweet_res["tweet"], dict):
            inner_tweet = tweet_res["tweet"]
            try:
                user_result = inner_tweet.get("core", {}).get("user_results", {}).get("result", {})
                if user_result and isinstance(user_result, dict):
                    legacy = user_result.get("legacy", {})
                    if legacy:
                        user_handle = legacy.get("screen_name")
                        user_name = legacy.get("name")
                        if user_handle:
                            return user_name, user_handle
            except (AttributeError, TypeError):
                pass

        # Strategy 3: Legacy structure - user embedded directly in legacy
        try:
            if tweet_res.get("legacy", {}).get("user", {}):
                user = tweet_res["legacy"]["user"]
                user_handle = user.get("screen_name")
                user_name = user.get("name")
                if user_handle:
                    return user_name, user_handle
        except (AttributeError, TypeError):
            pass

        # Strategy 4: Direct user property at top level
        try:
            if tweet_res.get("user", {}):
                user = tweet_res["user"]
                user_handle = user.get("screen_name")
                user_name = user.get("name")
                if user_handle:
                    return user_name, user_handle
        except (AttributeError, TypeError):
            pass

        # Strategy 5: Recursive search avoiding quoted/retweeted content
        def search_for_user(obj, depth=0, max_depth=5, parent_key=None):
            # Stop at max depth
            if depth >= max_depth:
                return None, None

            if not isinstance(obj, dict):
                return None, None

            # CRITICAL: Skip quoted/retweeted content to avoid wrong author
            # Don't descend into these keys as they contain OTHER users' data
            avoid_keys = {"quoted_status_result", "retweeted_status_result", "quoted_tweet", "retweeted_tweet", "retweeted_status", "quoted_status"}

            if parent_key in avoid_keys:
                return None, None

            # Check if this object directly contains screen_name
            if "screen_name" in obj and obj.get("screen_name"):
                # Validate it looks like a real handle (not a query term)
                handle = obj.get("screen_name")
                if isinstance(handle, str) and handle and " " not in handle:
                    return obj.get("name"), handle

            # Priority search paths
            for key in ["user_results", "core", "user", "legacy"]:
                if key in obj and isinstance(obj[key], dict):
                    result = search_for_user(obj[key], depth + 1, max_depth, key)
                    if result[1]:  # Found a handle
                        return result

            # Search other dict values (but skip avoid_keys)
            for key, val in obj.items():
                if key in avoid_keys:
                    continue
                if isinstance(val, dict):
                    result = search_for_user(val, depth + 1, max_depth, key)
                    if result[1]:
                        return result
                elif isinstance(val, list):
                    # Search in lists but be more cautious
                    for item in val:
                        if isinstance(item, dict):
                            result = search_for_user(item, depth + 1, max_depth, key)
                            if result[1]:
                                return result

            return None, None

        # Try recursive search as last resort
        deep_name, deep_handle = search_for_user(tweet_res)
        if deep_handle:
            return deep_name, deep_handle

        # If we get here, extraction completely failed
        # Uncomment for debugging:
        # print(f"WARNING: Could not extract user data. Keys available: {list(tweet_res.keys())}")
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
        """Check if tweet is original (not reply or retweet)."""
        if legacy.get("retweeted_status_result"):
            return False
        text = (legacy.get("full_text") or legacy.get("text") or "").lstrip()
        if text.startswith("RT @"):
            return False
        in_reply_to_user = legacy.get("in_reply_to_user_id_str")
        is_reply = legacy.get("in_reply_to_status_id_str") or in_reply_to_user
        if is_reply:
            return False
        return True

    def collect_instructions(data: dict) -> list:
        instr = []
        ur = get(data, "data", "user", "result", default={})
        tl = ur.get("timeline_v2") or ur.get("timeline") or {}
        tl = tl.get("timeline", tl)
        if isinstance(tl, dict):
            instr.extend(tl.get("instructions", []) or [])
        stl = get(
            data,
            "data",
            "search_by_raw_query",
            "search_timeline",
            "timeline",
            default={},
        )
        if isinstance(stl, dict):
            instr.extend(stl.get("instructions", []) or [])
        return instr

    async def grab(resp):
        if not (TWEET_API_RE.search(resp.url)):
            return
        try:
            data = await resp.json()
        except Exception:
            return

        for inst in collect_instructions(data):
            if inst.get("type") not in (
                    "TimelineAddEntries",
                    "TimelineReplaceEntry",
                    "TimelineReplaceEntries",
                    "TimelineAddToModule",
            ):
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
                for it in content.get("items") or content.get("moduleItems") or []:
                    ic = ((it.get("item") or {}).get("itemContent") or it.get("itemContent") or {})
                    if ic:
                        candidates.append(ic)

                for it_item in candidates:
                    raw = get(it_item, "tweet_results", "result") or get(content, "item", "content", "tweet_results", "result")
                    if not isinstance(raw, dict):
                        continue

                    # unwrap TweetWithVisibilityResults
                    node = raw.get("tweet") or raw

                    legacy = node.get("legacy") or {}
                    if not legacy:
                        # sometimes legacy only appears under quoted result
                        qleg = get(node, "quoted_status_result", "result", "legacy")
                        if not qleg:
                            continue
                        legacy = qleg

                    created_at = legacy.get("created_at")
                    if not created_at:
                        continue

                    # Track that we fetched this tweet (before filtering)
                    if stats:
                        stats.fetched += 1

                    # Skip old tweets and track stats
                    if not within_hours(created_at, hours=MAX_TWEET_AGE_HOURS):
                        if stats:
                            stats.filtered_old += 1
                        continue

                    # Skip non-original posts (replies/retweets) and track stats
                    if not is_original_post(legacy):
                        if stats:
                            # Determine if it's a reply or retweet for accurate stat tracking
                            if legacy.get("retweeted_status_result") or (legacy.get("full_text") or "").lstrip().startswith("RT @"):
                                stats.filtered_retweets += 1
                            else:
                                stats.filtered_replies += 1
                        continue

                    # Skip low-engagement tweets (min likes)
                    if int(legacy.get("favorite_count", 0)) < min_likes:
                        continue

                    # For FYP/query scrapes (not user timelines), require minimum impressions
                    if not handle:
                        views_data = node.get("views") or {}
                        tweet_impressions = int(views_data.get("count", 0))
                        if tweet_impressions < min_impressions_for_discovery:
                            if stats:
                                stats.filtered_impressions += 1
                            continue

                    # Filter tweets with videos, GIFs, URLs, or quoted tweets containing them
                    # (Photos are OK - VLM can process them)
                    if has_unsupported_content(node):
                        continue

                    tid = legacy.get("id_str") or str(node.get("rest_id") or "")
                    if not tid:
                        continue

                    # Skip already seen tweets
                    if username and is_tweet_seen(username, tid):
                        if stats:
                            stats.filtered_seen += 1
                        continue

                    # If scraping from a user timeline, use the handle from the URL parameter
                    # Only extract handle from tweet data if it's from a search query
                    if handle:
                        # This is from a user timeline - use the known handle directly
                        user_handle = handle
                        # Extract the username (display name) from the tweet data
                        user_name, _ = extract_user_data(node)
                        if not user_name:
                            # If we couldn't get the name, derive it from the handle
                            user_name = handle.replace("_", " ")
                    else:
                        # This is from a search query - extract both from tweet data
                        user_name, user_handle = extract_user_data(node)

                        # If extraction failed, try additional methods
                        if not user_handle:
                            # Try to extract handle using the older extract_handle method
                            extracted_handle = extract_handle(node, data)
                            if extracted_handle:
                                user_handle = extracted_handle

                        # If we still don't have a handle, we can't create a valid tweet entry
                        if not user_handle:
                            continue

                        # If we have the handle but no username, derive from handle
                        if user_handle and not user_name:
                            user_name = user_handle.replace("_", " ")

                    # Extract view/impression count
                    views_data = node.get("views") or {}
                    impressions = int(views_data.get("count", 0))

                    tweet_data = {
                        "id": tid,
                        "text": get_tweet_text(node),
                        "likes": int(legacy.get("favorite_count", 0)),
                        "retweets": int(legacy.get("retweet_count", 0)),
                        "quotes": int(legacy.get("quote_count", 0)),
                        "replies": int(legacy.get("reply_count", 0)),
                        "impressions": impressions,
                        "score": engagement_score(legacy),
                        "followers": extract_followers(node),
                        "created_at": created_at,
                        "url": (f"https://x.com/{user_handle}/status/{tid}" if (user_handle) else f"https://x.com/i/web/status/{tid}"),
                        "username": user_name,
                        "handle": user_handle,
                        "author_profile_pic_url": extract_author_profile_pic(node),
                        "media": extract_media_urls(node),
                        "quoted_tweet": extract_quoted_tweet(node),
                    }

                    # Apply initial intent filter (loose filter)
                    if username:
                        from backend.twitter.filtering import check_tweet_matches_intent_initial
                        matches_intent = await check_tweet_matches_intent_initial(tweet_data, username)
                        if not matches_intent:
                            # Skip this tweet - doesn't match intent
                            continue

                    tweets[tid] = tweet_data
                    # NOTE: Don't write here - wait until threads are collected
                    # to avoid marking tweets as "seen" before they have thread data

    def event_handler(resp):
        t = asyncio.create_task(grab(resp))
        pending.add(t)
        t.add_done_callback(lambda _t: pending.discard(_t))

    page.on("response", event_handler)

    await page.goto(url, wait_until="domcontentloaded")
    if handle:
        notify(f"Got to @{handle}'s timeline! via {url}")
    else:
        notify(f"Got to search results via {url}")

    await page.wait_for_event(
        "response",
        predicate=lambda r: TWEET_API_RE.search(r.url),
        timeout=30_000,
    )

    await scroll(page, scrolls=max_scrolls, delay=1.8)

    if pending:
        await asyncio.gather(*pending, return_exceptions=True)

    await page.close()

    # Collect threads and other replies for all tweets with progressive writing
    for tid, t in tweets.items():
        thread_data = await get_thread(ctx, t["url"], root_id=t["id"])
        t["thread"] = thread_data.get("thread", [])
        t["thread_ids"] = thread_data.get("thread_ids", [])
        t["other_replies"] = thread_data.get("other_replies", [])

        # Replace the truncated text with the full text from the thread (first element)
        if t["thread"] and len(t["thread"]) > 0:
            t["text"] = t["thread"][0]

            # Progressive write: save thread immediately if callback provided
            if write_callback and username:
                await write_callback([t], username)

    # NOTE: We no longer remove tweets without threads - they stay in cache
    # but frontend will filter them out for display

    return tweets
