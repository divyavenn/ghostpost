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

from backend.scraping.twitter.scraping_utils import (
    extract_metrics,
    extract_text,
    extract_user_info,
    scroll,
)


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
                item_content = content.get("itemContent", {})
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

                # Set target user ID from first tweet
                if target_user_id is None:
                    target_user_id = uid

                # Only include tweets from the target user
                if uid != target_user_id:
                    continue

                if tid in tweets:
                    continue

                user_info = extract_user_info(node)
                metrics = extract_metrics(node)
                text = extract_text(node)

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
                    "handle": user_info["handle"] or username,
                    "username": user_info["username"],
                    "author_profile_pic_url": user_info["author_profile_pic_url"],
                    "followers": user_info["followers"],
                    "in_reply_to_status_id": in_reply_to,
                    "created_at": created_at,
                    "url": f"https://x.com/{username}/status/{tid}",
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
