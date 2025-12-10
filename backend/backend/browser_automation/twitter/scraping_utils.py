"""
Shared utilities for Twitter scraping.

Provides common functions used across different scraping modules:
- scroll: Randomized page scrolling
- extract_text: Extract tweet text (including long-form notes)
- extract_user_info: Extract author info from tweet nodes
- extract_metrics: Extract engagement metrics
"""
import asyncio
from typing import Any


async def scroll(page, delay: float = 1.5, scrolls: int = 3, distance: int = 2000):
    """
    Scroll the page with randomization to appear more human-like.

    Args:
        page: Playwright page object
        delay: Base delay between scrolls in seconds
        scrolls: Base number of scroll actions
        distance: Base scroll distance in pixels
    """
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


def extract_text(node: dict) -> str:
    """
    Extract text from tweet node, prioritizing note_tweet for long-form content.

    Args:
        node: Tweet node from GraphQL response

    Returns:
        Tweet text content
    """
    note = ((node.get("note_tweet") or {}).get("note_tweet_results", {}).get("result", {}).get("text"))
    if note:
        return note
    legacy = node.get("legacy") or {}
    txt = legacy.get("full_text") or legacy.get("text")
    if txt:
        return txt
    return ""


def extract_user_info(node: dict) -> dict[str, Any]:
    """
    Extract author info from tweet node.

    Tries multiple strategies to find user info in different API response formats.

    Args:
        node: Tweet node from GraphQL response

    Returns:
        Dict with handle, username, author_profile_pic_url, followers
    """
    result = {
        "handle": "",
        "username": "",
        "author_profile_pic_url": "",
        "followers": 0
    }

    user_result = None

    # Strategy 1: core.user_results.result
    try:
        user_result = node.get("core", {}).get("user_results", {}).get("result", {})
    except (AttributeError, TypeError):
        pass

    # Strategy 2: Check tweet wrapper
    if not user_result:
        try:
            if "tweet" in node and isinstance(node["tweet"], dict):
                user_result = node["tweet"].get("core", {}).get("user_results", {}).get("result", {})
        except (AttributeError, TypeError):
            pass

    # Strategy 3: legacy.user
    if not user_result:
        try:
            user = node.get("legacy", {}).get("user", {})
            if user.get("screen_name"):
                result["handle"] = user.get("screen_name", "")
                result["username"] = user.get("name", "")
                return result
        except (AttributeError, TypeError):
            pass

    # Strategy 4: direct user object
    if not user_result:
        try:
            user = node.get("user", {})
            if user.get("screen_name"):
                result["handle"] = user.get("screen_name", "")
                result["username"] = user.get("name", "")
                return result
        except (AttributeError, TypeError):
            pass

    if user_result and isinstance(user_result, dict):
        legacy_user = user_result.get("legacy", {})

        # Get profile pic - try avatar first (new API), then legacy
        avatar = user_result.get("avatar", {})
        if avatar.get("image_url"):
            profile_pic = avatar.get("image_url", "")
            result["author_profile_pic_url"] = profile_pic.replace("_normal", "_400x400")
        elif legacy_user.get("profile_image_url_https"):
            profile_pic = legacy_user.get("profile_image_url_https", "")
            result["author_profile_pic_url"] = profile_pic.replace("_normal", "_400x400")

        # Get followers from legacy
        if legacy_user:
            result["followers"] = legacy_user.get("followers_count", 0)

        # Get handle/username - try core first (new API), then legacy
        core = user_result.get("core", {})
        if core.get("screen_name"):
            result["handle"] = core.get("screen_name", "")
            result["username"] = core.get("name", "")
        elif legacy_user.get("screen_name"):
            result["handle"] = legacy_user.get("screen_name", "")
            result["username"] = legacy_user.get("name", "")

    return result


def extract_user_info_simple(node: dict) -> tuple[str, str]:
    """
    Extract just handle and display name from tweet node.

    Simpler version for cases where only handle/name are needed.

    Args:
        node: Tweet node from GraphQL response

    Returns:
        Tuple of (handle, display_name)
    """
    info = extract_user_info(node)
    return info["handle"], info["username"]


def extract_metrics(node: dict) -> dict[str, int]:
    """
    Extract engagement metrics from tweet node.

    Args:
        node: Tweet node from GraphQL response

    Returns:
        Dict with likes, retweets, quotes, replies, impressions
    """
    legacy = node.get("legacy") or {}
    return {
        "likes": legacy.get("favorite_count") or 0,
        "retweets": legacy.get("retweet_count") or 0,
        "quotes": legacy.get("quote_count") or 0,
        "replies": legacy.get("reply_count") or 0,
        "impressions": 0  # Not always available
    }


def extract_likes(node: dict) -> int:
    """
    Extract just the like count from tweet node.

    Args:
        node: Tweet node from GraphQL response

    Returns:
        Like count
    """
    legacy = node.get("legacy") or {}
    return legacy.get("favorite_count") or 0
