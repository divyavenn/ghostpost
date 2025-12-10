"""
Scrape user's recent tweets from their profile.
Used to discover tweets posted externally (not through the app).
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

from backend.browser_automation.twitter.scraping_utils import (
    extract_metrics,
    extract_text,
    extract_user_info,
    scroll,
)


def _extract_media(node: dict) -> list[dict]:
    """
    Extract image URLs and metadata from tweet media.
    Returns list of dicts: [{type: "photo", url: "...", alt_text: "..."}]
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

        # Only extract photos
        if media_type == "photo":
            media_url = media_item.get("media_url_https") or media_item.get("media_url")
            alt_text = media_item.get("ext_alt_text", "")

            if media_url:
                media_items.append({"type": "photo", "url": media_url, "alt_text": alt_text})

    return media_items


def _extract_quoted_tweet(node: dict) -> dict | None:
    """
    Extract quoted tweet data from GraphQL response.

    Args:
        node: Tweet node from GraphQL response

    Returns:
        Quoted tweet dict or None if no quoted tweet
    """
    from backend.utlils.utils import notify

    inner_node = node.get("tweet") or node

    # GraphQL format: quoted_status_result contains the quoted tweet
    quoted_result = inner_node.get("quoted_status_result", {}).get("result", {})
    if not quoted_result:
        # Debug: check if there's quoted tweet data in legacy
        legacy = inner_node.get("legacy", {})
        if legacy.get("is_quote_status"):
            notify(f"⚠️ Tweet is_quote_status=True but no quoted_status_result found")
        return None

    quoted_node = quoted_result.get("tweet") or quoted_result
    quoted_legacy = quoted_node.get("legacy", {})

    if not quoted_legacy:
        return None

    quoted_id = quoted_legacy.get("id_str")
    if not quoted_id:
        return None

    # Extract author info from quoted tweet's core.user_results
    quoted_user_result = quoted_node.get("core", {}).get("user_results", {}).get("result", {})
    quoted_user_legacy = quoted_user_result.get("legacy", {})

    quoted_handle = quoted_user_legacy.get("screen_name", "")
    quoted_name = quoted_user_legacy.get("name", "")
    quoted_pfp = quoted_user_legacy.get("profile_image_url_https", "")

    # Extract text
    quoted_text = quoted_legacy.get("full_text", "") or quoted_legacy.get("text", "")

    # Extract media from quoted tweet
    quoted_media = _extract_media(quoted_node)

    # Build URL
    quoted_url = f"https://x.com/{quoted_handle}/status/{quoted_id}" if quoted_handle else f"https://x.com/i/web/status/{quoted_id}"

    return {
        "text": quoted_text,
        "author_handle": quoted_handle,
        "author_name": quoted_name,
        "author_profile_pic_url": quoted_pfp,
        "url": quoted_url,
        "media": quoted_media
    }


async def scrape_user_recent_tweets(ctx, username: str, max_tweets: int = 50) -> list[dict[str, Any]]:
    """
    Scrape recent tweets from a user's profile (Tweets & Replies tab).
    Used by discover_recently_posted job.

    Args:
        ctx: Playwright browser context
        username: Twitter handle to scrape
        max_tweets: Maximum tweets to collect

    Returns:
        List of tweet dicts with id, text, metrics, etc.
    """
    page = await ctx.new_page()

    tweets: dict[str, dict] = {}
    target_user_id: str | None = None

    # Match UserTweets GraphQL calls
    user_tweets_re = re.compile(r"/i/api/graphql/[^/]+/(UserTweets|UserTweetsAndReplies)")

    async def on_response(resp):
        nonlocal target_user_id
        if not (user_tweets_re.search(resp.url) and resp.ok):
            return
        try:
            data = await resp.json()
        except Exception:
            return

        # Extract timeline instructions
        # Try both API structures: timeline_v2.timeline and timeline.timeline
        user_result = (data.get("data") or {}).get("user", {}).get("result", {})

        # Get target user ID from user_result (more reliable than first tweet)
        # This is the profile owner's ID, not the author of the first tweet in timeline
        if target_user_id is None:
            # Try multiple paths to find the user ID
            target_user_id = user_result.get("rest_id")

            # Try legacy path
            if not target_user_id:
                target_user_id = user_result.get("id_str") or user_result.get("id")

            # Try nested user data
            if not target_user_id:
                legacy_user = user_result.get("legacy", {})
                target_user_id = legacy_user.get("id_str")

            # Debug logging only when target_user_id is found
            # if target_user_id:
            #     notify(f"🔍 [scrape_user_recent_tweets] Captured target_user_id: {target_user_id} for @{username}")

        # Try timeline_v2 first (older API)
        timeline = user_result.get("timeline_v2", {}).get("timeline", {})

        # Fall back to timeline (newer API structure)
        if not timeline:
            timeline = user_result.get("timeline", {}).get("timeline", {})

        instructions = timeline.get("instructions", [])

        for inst in instructions:
            entries = inst.get("entries", [])
            for entry in entries:
                content = entry.get("content", {})

                # Collect all item candidates - handles both direct items and modules
                candidates = []
                item_content = content.get("itemContent", {})
                if item_content:
                    candidates.append(item_content)
                # Handle item wrapper
                ic2 = (content.get("item") or {}).get("itemContent") or {}
                if ic2:
                    candidates.append(ic2)
                # Handle module entries (for pinned tweets, threads, etc.)
                for it in (content.get("items") or content.get("moduleItems") or []):
                    cand = (it.get("item") or {}).get("itemContent") or it.get("itemContent") or {}
                    if cand:
                        candidates.append(cand)

                for item_content in candidates:
                    tweet_results = item_content.get("tweet_results", {})
                    raw = tweet_results.get("result", {})

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

                    # Only include tweets from the target user (profile owner)
                    # Skip tweets from others (e.g., tweets user replied to)
                    tweet_user_info = extract_user_info(node)
                    tweet_handle = (tweet_user_info.get("handle") or "").lower()

                    # Primary filter: by user ID (most reliable when available)
                    if target_user_id and uid != target_user_id:
                        continue

                    # Fallback filter: by handle (when target_user_id is not available)
                    if not target_user_id and tweet_handle != username.lower():
                        continue

                    if tid in tweets:
                        continue

                    # user_info already extracted above for filtering
                    metrics = extract_metrics(node)
                    text = extract_text(node)
                    media = _extract_media(node)
                    quoted_tweet = _extract_quoted_tweet(node)

                    # Get created_at
                    created_at = legacy.get("created_at", "")
                    try:
                        if created_at:
                            dt = datetime.strptime(created_at, "%a %b %d %H:%M:%S %z %Y")
                            created_at = dt.isoformat()
                    except Exception:
                        created_at = datetime.now(UTC).isoformat()

                    in_reply_to = legacy.get("in_reply_to_status_id_str")

                    tweets[tid] = {
                        "id": tid,
                        "text": text,
                        "handle": tweet_user_info["handle"] or username,
                        "username": tweet_user_info["username"],
                        "author_profile_pic_url": tweet_user_info["author_profile_pic_url"],
                        "followers": tweet_user_info["followers"],
                        "in_reply_to_status_id": in_reply_to,
                        "created_at": created_at,
                        "url": f"https://x.com/{username}/status/{tid}",
                        "media": media,
                        "quoted_tweet": quoted_tweet,
                        **metrics
                    }

                    if len(tweets) >= max_tweets:
                        return

    page.on("response", lambda r: asyncio.create_task(on_response(r)))

    try:
        # Go to Tweets & Replies tab
        await page.goto(f"https://x.com/{username}/with_replies", wait_until="domcontentloaded")

        try:
            await page.wait_for_event(
                "response",
                predicate=lambda r: user_tweets_re.search(r.url),
                timeout=30_000,
            )
        except Exception:
            pass

        # Scroll to load more tweets
        last_count = 0
        no_new_count = 0

        while len(tweets) < max_tweets:
            await scroll(page, scrolls=2, delay=1.0)
            await asyncio.sleep(1)

            current_count = len(tweets)
            if current_count == last_count:
                no_new_count += 1
                if no_new_count >= 3:
                    break
            else:
                no_new_count = 0
                last_count = current_count

    finally:
        await page.close()

    return list(tweets.values())
