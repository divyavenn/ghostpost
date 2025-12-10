"""
Background jobs for engagement monitoring and comment discovery.

Jobs:
- discover_recently_posted: Find user's tweets not posted from app
- discover_engagement: Monitor active/warm tweets for new engagement
- discover_resurrected: Check notifications for cold tweet activity
"""
import asyncio
from datetime import datetime, timedelta
from typing import Any

try:
    from datetime import UTC
except ImportError:
    from datetime import timezone
    UTC = timezone.utc

from backend.browser_management.context import cleanup_browser_resources, get_authenticated_context
from backend.config import (
    ACTIVE_MAX_AGE_HOURS,
    ACTIVITY_PROMOTION_THRESHOLD,
    HARDCUTOFF_COLD_DAYS,
    INACTIVITY_TO_COLD_HOURS,
    WARM_MAX_AGE_DAYS,
)
from backend.utlils.utils import error, notify


# NOTE: Status tracking is now handled by job_status in twitter_jobs.py
# The monitoring functions below are called by parent jobs which track their own status


def _calculate_activity_delta(tweet: dict, new_metrics: dict) -> int:
    """
    Calculate the activity delta from last scrape.
    Returns sum of (new_replies - last_replies) + (new_likes - last_likes) + ...
    """
    delta = 0
    delta += max(0, new_metrics.get("replies", 0) - (tweet.get("last_reply_count") or 0))
    delta += max(0, new_metrics.get("likes", 0) - (tweet.get("last_like_count") or 0))
    delta += max(0, new_metrics.get("quotes", 0) - (tweet.get("last_quote_count") or 0))
    delta += max(0, new_metrics.get("retweets", 0) - (tweet.get("last_retweet_count") or 0))
    return delta


def _should_promote_to_active(tweet: dict, new_metrics: dict, new_reply_ids: list[str]) -> bool:
    """
    Determine if a warm/cold tweet should be promoted to active.
    True if new replies detected or activity delta >= threshold.
    """
    # Check for new reply IDs
    last_ids = set(tweet.get("last_scraped_reply_ids", []))
    new_ids = set(new_reply_ids)
    has_new_replies = bool(new_ids - last_ids)

    if has_new_replies:
        return True

    # Check activity delta
    delta = _calculate_activity_delta(tweet, new_metrics)
    return delta >= ACTIVITY_PROMOTION_THRESHOLD


def _determine_monitoring_state(tweet: dict) -> str:
    """
    Determine what monitoring state a tweet should be in based on age and activity.
    """
    created_at = tweet.get("created_at", "")
    last_activity_at = tweet.get("last_activity_at", created_at)

    try:
        # Parse timestamp
        if "T" in last_activity_at:
            last_activity = datetime.fromisoformat(last_activity_at.replace("Z", "+00:00"))
        else:
            last_activity = datetime.strptime(last_activity_at, "%a %b %d %H:%M:%S %z %Y")

        now = datetime.now(UTC)
        hours_since_activity = (now - last_activity).total_seconds() / 3600

        # Hard cutoff
        if hours_since_activity > HARDCUTOFF_COLD_DAYS * 24:
            return "cold"

        # Inactivity threshold
        if hours_since_activity > INACTIVITY_TO_COLD_HOURS:
            return "cold"

        # Active window
        if hours_since_activity <= ACTIVE_MAX_AGE_HOURS:
            return "active"

        # Warm window
        if hours_since_activity <= WARM_MAX_AGE_DAYS * 24:
            return "warm"

        return "cold"

    except Exception:
        # Default to warm if we can't determine
        return "warm"


async def discover_recently_posted(username: str, user_handle: str, max_tweets: int = 50) -> dict[str, Any]:
    """
    Job 1: Discover user's recently posted tweets not tracked by the app.

    Scrapes user's Tweets & Replies tab to find:
    - Tweets posted from Twitter website/other clients
    - Old threads user wants to monitor

    For each discovered tweet:
    - Add to posted_tweets with source="external"
    - Set monitoring_state based on age
    - Deep scrape to get initial replies

    Args:
        username: User's cache key
        user_handle: User's Twitter handle
        max_tweets: Max tweets to scan

    Returns:
        Summary dict with counts
    """
    from backend.data.twitter.comments_cache import process_scraped_replies, process_scraped_quote_tweets
    from backend.data.twitter.posted_tweets_cache import (
        add_posted_tweet,
        get_user_tweet_ids,
        read_posted_tweets_cache,
        update_monitoring_state,
        write_posted_tweets_cache,
    )
    from backend.browser_automation.twitter.api import scrape_user_recent_tweets, get_thread, deep_scrape_thread

    notify(f"🔍 [discover_recently_posted] Starting for @{user_handle}")

    playwright = None
    browser = None
    context = None
    results = {
        "discovered_tweets": 0,
        "new_comments": 0,
        "new_quote_tweets": 0,
        "errors": []
    }

    try:
        playwright, browser, context = await get_authenticated_context(username)
        existing_ids = get_user_tweet_ids(username)
        print(f"[DEBUG] Existing tweet IDs in cache: {len(existing_ids)}")

        # Scrape user's recent tweets
        recent_tweets = await scrape_user_recent_tweets(context, user_handle, max_tweets)
        notify(f"📊 Found {len(recent_tweets)} recent tweets for @{user_handle}")

        skipped_existing = 0
        skipped_no_id = 0

        processed_count = 0
        for tweet in recent_tweets:
            processed_count += 1
            tweet_id = tweet.get("id")
            if not tweet_id:
                skipped_no_id += 1
                continue

            # Check if already tracked
            if tweet_id in existing_ids:
                skipped_existing += 1
                # Update existing tweet with missing data (quoted_tweet, response_to_thread)
                tweets_map = read_posted_tweets_cache(username)
                existing_tweet = tweets_map.get(tweet_id, {})
                updated = False

                # Backfill quoted_tweet if missing
                quoted_tweet = tweet.get("quoted_tweet")
                if quoted_tweet and not existing_tweet.get("quoted_tweet"):
                    existing_tweet["quoted_tweet"] = quoted_tweet
                    updated = True
                    notify(f"📝 Backfilled quoted_tweet for tweet {tweet_id}")

                # Backfill response_to_thread if missing but tweet is a reply
                in_reply_to = existing_tweet.get("parent_chain", [])[-1] if existing_tweet.get("parent_chain") else tweet.get("in_reply_to_status_id")
                if in_reply_to and not existing_tweet.get("response_to_thread"):
                    try:
                        original_url = f"https://x.com/i/status/{in_reply_to}"
                        thread_result = await get_thread(context, original_url, root_id=in_reply_to)
                        if thread_result and thread_result.get("thread"):
                            existing_tweet["response_to_thread"] = thread_result["thread"]
                            existing_tweet["responding_to"] = thread_result.get("author_handle", existing_tweet.get("responding_to", ""))
                            existing_tweet["replying_to_pfp"] = thread_result.get("author_profile_pic_url", existing_tweet.get("replying_to_pfp", ""))
                            if thread_result.get("author_handle"):
                                existing_tweet["original_tweet_url"] = f"https://x.com/{thread_result['author_handle']}/status/{in_reply_to}"
                            updated = True
                            notify(f"📝 Backfilled response_to_thread for tweet {tweet_id}")
                    except Exception as e:
                        notify(f"⚠️ Could not backfill context for {tweet_id}: {e}")

                if updated:
                    tweets_map[tweet_id] = existing_tweet
                    write_posted_tweets_cache(username, tweets_map)
                continue

            # Skip retweets (in_reply_to_status_id would be set for quote tweets too)
            # Only track original tweets and replies by the user
            in_reply_to = tweet.get("in_reply_to_status_id")

            try:
                # Add to posted_tweets
                created_at = tweet.get("created_at", datetime.now(UTC).isoformat())
                url = tweet.get("url", f"https://x.com/{user_handle}/status/{tweet_id}")

                # For external tweets, we set source="external" and calculate monitoring state
                # We'll create a minimal entry and then update it
                tweets_map = read_posted_tweets_cache(username)

                # Determine initial monitoring state based on age
                temp_tweet = {"created_at": created_at, "last_activity_at": created_at}
                initial_state = _determine_monitoring_state(temp_tweet)

                # Get media from scraped tweet
                media = tweet.get("media", [])

                # Default reply context (empty for original tweets)
                response_to_thread = []
                responding_to = ""
                replying_to_pfp = ""
                original_tweet_url = ""

                # For replies, fetch the original tweet to get context
                if in_reply_to:
                    try:
                        original_url = f"https://x.com/i/status/{in_reply_to}"
                        thread_result = await get_thread(context, original_url, root_id=in_reply_to)

                        if thread_result:
                            # Get thread text from the original tweet
                            thread_texts = thread_result.get("thread", [])
                            if thread_texts:
                                response_to_thread = thread_texts

                            # Get author info
                            responding_to = thread_result.get("author_handle", "")
                            replying_to_pfp = thread_result.get("author_profile_pic_url", "")

                            # Build original tweet URL
                            if responding_to:
                                original_tweet_url = f"https://x.com/{responding_to}/status/{in_reply_to}"

                    except Exception as e:
                        notify(f"⚠️ Could not fetch original tweet {in_reply_to}: {e}")

                tweet_data = {
                    "id": tweet_id,
                    "text": tweet.get("text", ""),
                    "likes": tweet.get("likes", 0),
                    "retweets": tweet.get("retweets", 0),
                    "quotes": tweet.get("quotes", 0),
                    "replies": tweet.get("replies", 0),
                    "impressions": tweet.get("impressions", 0),
                    "created_at": created_at,
                    "url": url,
                    "last_metrics_update": datetime.now(UTC).isoformat(),
                    "media": media,
                    "quoted_tweet": tweet.get("quoted_tweet"),  # Quoted tweet data if present
                    "parent_chain": [in_reply_to] if in_reply_to else [],
                    "response_to_thread": response_to_thread,
                    "responding_to": responding_to,
                    "replying_to_pfp": replying_to_pfp,
                    "original_tweet_url": original_tweet_url,
                    "source": "external",
                    "monitoring_state": initial_state,
                    "last_activity_at": created_at,
                    "last_deep_scrape": None,
                    "last_shallow_scrape": None,
                    "last_reply_count": tweet.get("replies", 0),
                    "last_like_count": tweet.get("likes", 0),
                    "last_quote_count": tweet.get("quotes", 0),
                    "last_retweet_count": tweet.get("retweets", 0),
                    "resurrected_via": "none",
                    "last_scraped_reply_ids": []
                }

                tweets_map[tweet_id] = tweet_data
                order = tweets_map.get("_order", [])
                tweets_map["_order"] = [tweet_id] + [oid for oid in order if oid != tweet_id]
                write_posted_tweets_cache(username, tweets_map)

                results["discovered_tweets"] += 1
                notify(f"✅ Discovered external tweet {tweet_id} ({initial_state})")

                # Deep scrape if active state to get initial replies and QTs
                if initial_state == "active":
                    try:
                        scrape_result = await deep_scrape_thread(context, url, tweet_id, user_handle)

                        # Process replies
                        scraped_replies = scrape_result.get("replies", [])
                        new_comment_ids = process_scraped_replies(username, scraped_replies, user_handle)
                        results["new_comments"] += len(new_comment_ids)

                        # Process quote tweets
                        scraped_qts = scrape_result.get("quote_tweets", [])
                        new_qt_ids = process_scraped_quote_tweets(username, scraped_qts, user_handle, tweet_id)
                        results["new_quote_tweets"] += len(new_qt_ids)

                        # Update tweet with scrape info
                        tweets_map = read_posted_tweets_cache(username)
                        if tweet_id in tweets_map:
                            tweets_map[tweet_id]["last_deep_scrape"] = datetime.now(UTC).isoformat()
                            tweets_map[tweet_id]["last_scraped_reply_ids"] = scrape_result.get("all_reply_ids", [])[:50]
                            write_posted_tweets_cache(username, tweets_map)

                    except Exception as e:
                        notify(f"⚠️ Error deep scraping {tweet_id}: {e}")
                        results["errors"].append(f"Deep scrape {tweet_id}: {e}")

            except Exception as e:
                notify(f"⚠️ Error processing discovered tweet {tweet_id}: {e}")
                results["errors"].append(f"Process {tweet_id}: {e}")

        print(f"[DEBUG] Summary: {len(recent_tweets)} fetched, {skipped_existing} already tracked, {skipped_no_id} no ID, {results['discovered_tweets']} discovered")
        notify(f"✅ [discover_recently_posted] Complete: {results['discovered_tweets']} tweets, {results['new_comments']} comments, {results['new_quote_tweets']} QTs")

    except Exception as e:
        error(f"discover_recently_posted failed: {e}", status_code=500, function_name="discover_recently_posted", username=username, critical=False)
        results["errors"].append(str(e))

    finally:
        await cleanup_browser_resources(playwright, browser, context)

    return results


async def discover_engagement(username: str, user_handle: str) -> dict[str, Any]:
    """
    Job 2: Monitor active/warm tweets for new engagement.

    Active tweets (< 12h since activity): Deep scrape
    Warm tweets (< 3 days since activity): Shallow scrape

    For each tweet:
    - Check for new activity
    - Process new replies as comments
    - Update monitoring state
    - Demote inactive tweets to colder states

    Args:
        username: User's cache key
        user_handle: User's Twitter handle

    Returns:
        Summary dict with counts
    """
    from backend.data.twitter.comments_cache import process_scraped_replies, process_scraped_quote_tweets
    from backend.data.twitter.posted_tweets_cache import (
        get_tweets_by_monitoring_state,
        read_posted_tweets_cache,
        write_posted_tweets_cache,
    )
    from backend.browser_automation.twitter.api import shallow_scrape_thread, deep_scrape_thread

    notify(f"🔍 [discover_engagement] Starting for @{user_handle}")

    playwright = None
    browser = None
    context = None
    results = {
        "active_scraped": 0,
        "warm_scraped": 0,
        "new_comments": 0,
        "new_quote_tweets": 0,
        "promoted_to_active": 0,
        "demoted_to_warm": 0,
        "demoted_to_cold": 0,
        "errors": []
    }

    try:
        playwright, browser, context = await get_authenticated_context(username)

        # Get active tweets for deep scraping
        active_tweets = get_tweets_by_monitoring_state(username, ["active"])
        notify(f"📊 Found {len(active_tweets)} active tweets to deep scrape")

        active_idx = 0
        for tweet in active_tweets:
            active_idx += 1
            tweet_id = tweet.get("id")
            url = tweet.get("url", f"https://x.com/{user_handle}/status/{tweet_id}")

            try:
                scrape_result = await deep_scrape_thread(context, url, tweet_id, user_handle)
                results["active_scraped"] += 1

                # Process replies
                scraped_replies = scrape_result.get("replies", [])
                new_comment_ids = process_scraped_replies(username, scraped_replies, user_handle)
                results["new_comments"] += len(new_comment_ids)

                # Process quote tweets
                scraped_qts = scrape_result.get("quote_tweets", [])
                new_qt_ids = process_scraped_quote_tweets(username, scraped_qts, user_handle, tweet_id)
                results["new_quote_tweets"] += len(new_qt_ids)

                # Update tweet
                tweets_map = read_posted_tweets_cache(username)
                if tweet_id in tweets_map:
                    now = datetime.now(UTC).isoformat()
                    tweets_map[tweet_id]["last_deep_scrape"] = now
                    tweets_map[tweet_id]["last_reply_count"] = scrape_result.get("reply_count", 0)
                    tweets_map[tweet_id]["last_like_count"] = scrape_result.get("like_count", 0)
                    tweets_map[tweet_id]["last_quote_count"] = scrape_result.get("quote_count", 0)
                    tweets_map[tweet_id]["last_retweet_count"] = scrape_result.get("retweet_count", 0)
                    tweets_map[tweet_id]["replies"] = scrape_result.get("reply_count", 0)
                    tweets_map[tweet_id]["likes"] = scrape_result.get("like_count", 0)
                    tweets_map[tweet_id]["quotes"] = scrape_result.get("quote_count", 0)
                    tweets_map[tweet_id]["retweets"] = scrape_result.get("retweet_count", 0)
                    tweets_map[tweet_id]["last_scraped_reply_ids"] = scrape_result.get("all_reply_ids", [])[:50]

                    # Update activity if new comments or quote tweets found
                    if new_comment_ids or new_qt_ids:
                        tweets_map[tweet_id]["last_activity_at"] = now

                    # Check if should demote to warm
                    new_state = _determine_monitoring_state(tweets_map[tweet_id])
                    if new_state != "active":
                        tweets_map[tweet_id]["monitoring_state"] = new_state
                        if new_state == "warm":
                            results["demoted_to_warm"] += 1
                        else:
                            results["demoted_to_cold"] += 1

                    write_posted_tweets_cache(username, tweets_map)

                # Rate limiting
                await asyncio.sleep(2)

            except Exception as e:
                notify(f"⚠️ Error deep scraping {tweet_id}: {e}")
                results["errors"].append(f"Deep scrape {tweet_id}: {e}")

        # Get warm tweets for shallow scraping
        warm_tweets = get_tweets_by_monitoring_state(username, ["warm"])
        notify(f"📊 Found {len(warm_tweets)} warm tweets to shallow scrape")

        warm_idx = 0
        for tweet in warm_tweets:
            warm_idx += 1
            tweet_id = tweet.get("id")
            url = tweet.get("url", f"https://x.com/{user_handle}/status/{tweet_id}")

            try:
                scrape_result = await shallow_scrape_thread(context, url, tweet_id)
                results["warm_scraped"] += 1

                new_metrics = {
                    "replies": scrape_result.get("reply_count", 0),
                    "likes": scrape_result.get("like_count", 0),
                    "quotes": scrape_result.get("quote_count", 0),
                    "retweets": scrape_result.get("retweet_count", 0)
                }
                new_reply_ids = scrape_result.get("latest_reply_ids", [])

                # Check for promotion
                should_promote = _should_promote_to_active(tweet, new_metrics, new_reply_ids)

                tweets_map = read_posted_tweets_cache(username)
                if tweet_id in tweets_map:
                    now = datetime.now(UTC).isoformat()
                    tweets_map[tweet_id]["last_shallow_scrape"] = now
                    tweets_map[tweet_id]["last_reply_count"] = new_metrics["replies"]
                    tweets_map[tweet_id]["last_like_count"] = new_metrics["likes"]
                    tweets_map[tweet_id]["last_quote_count"] = new_metrics["quotes"]
                    tweets_map[tweet_id]["last_retweet_count"] = new_metrics["retweets"]
                    tweets_map[tweet_id]["replies"] = new_metrics["replies"]
                    tweets_map[tweet_id]["likes"] = new_metrics["likes"]
                    tweets_map[tweet_id]["quotes"] = new_metrics["quotes"]
                    tweets_map[tweet_id]["retweets"] = new_metrics["retweets"]

                    if should_promote:
                        tweets_map[tweet_id]["monitoring_state"] = "active"
                        tweets_map[tweet_id]["last_activity_at"] = now
                        tweets_map[tweet_id]["resurrected_via"] = "engagement"
                        results["promoted_to_active"] += 1
                        notify(f"🔥 Promoted {tweet_id} to active (new engagement)")
                    else:
                        # Check for demotion to cold
                        new_state = _determine_monitoring_state(tweets_map[tweet_id])
                        if new_state == "cold":
                            tweets_map[tweet_id]["monitoring_state"] = "cold"
                            results["demoted_to_cold"] += 1

                    write_posted_tweets_cache(username, tweets_map)

                # Rate limiting
                await asyncio.sleep(1)

            except Exception as e:
                notify(f"⚠️ Error shallow scraping {tweet_id}: {e}")
                results["errors"].append(f"Shallow scrape {tweet_id}: {e}")

        notify(f"✅ [discover_engagement] Complete: {results['active_scraped']} deep, {results['warm_scraped']} shallow, {results['new_comments']} comments, {results['new_quote_tweets']} QTs")

    except Exception as e:
        error(f"discover_engagement failed: {e}", status_code=500, function_name="discover_engagement", username=username, critical=False)
        results["errors"].append(str(e))

    finally:
        await cleanup_browser_resources(playwright, browser, context)

    return results


async def discover_resurrected(username: str, user_handle: str) -> dict[str, Any]:
    """
    Job 3: Check for activity on cold tweets via notifications.

    Scrapes Twitter notifications to find:
    - Replies to cold tweets
    - Likes/retweets on cold tweets that exceed threshold

    For resurrected tweets:
    - Promote to active state
    - Set resurrected_via = "notification"
    - Deep scrape to get new replies

    Args:
        username: User's cache key
        user_handle: User's Twitter handle

    Returns:
        Summary dict with counts
    """
    from backend.data.twitter.comments_cache import process_scraped_replies, process_scraped_quote_tweets
    from backend.data.twitter.posted_tweets_cache import (
        get_tweets_by_monitoring_state,
        read_posted_tweets_cache,
        write_posted_tweets_cache,
    )
    from backend.browser_automation.twitter.api import deep_scrape_thread

    notify(f"🔍 [discover_resurrected] Starting for @{user_handle}")

    playwright = None
    browser = None
    context = None
    results = {
        "resurrected_tweets": 0,
        "new_comments": 0,
        "new_quote_tweets": 0,
        "errors": []
    }

    try:
        playwright, browser, context = await get_authenticated_context(username)

        # Get cold tweet IDs for matching
        cold_tweets = get_tweets_by_monitoring_state(username, ["cold"])
        cold_tweet_ids = {t.get("id") for t in cold_tweets if t.get("id")}

        notify(f"📊 Monitoring {len(cold_tweet_ids)} cold tweets for resurrection")

        # Scrape notifications page
        page = await context.new_page()
        resurrected_ids = set()

        try:
            await page.goto("https://x.com/notifications", wait_until="domcontentloaded")
            await asyncio.sleep(3)

            # Look for tweet IDs in notification links
            # Notifications contain links to tweets that got engagement
            links = await page.locator("a[href*='/status/']").all()

            for link in links[:50]:  # Limit to first 50 links
                try:
                    href = await link.get_attribute("href")
                    if not href or "/status/" not in href:
                        continue

                    # Extract tweet ID from URL
                    parts = href.split("/status/")
                    if len(parts) < 2:
                        continue

                    tweet_id = parts[1].split("/")[0].split("?")[0]

                    # Check if this is one of user's cold tweets
                    if tweet_id in cold_tweet_ids:
                        resurrected_ids.add(tweet_id)

                except Exception:
                    continue

            await page.close()

        except Exception as e:
            notify(f"⚠️ Error scraping notifications: {e}")
            results["errors"].append(f"Notifications: {e}")
            try:
                await page.close()
            except Exception:
                pass

        # Process resurrected tweets
        notify(f"📊 Found {len(resurrected_ids)} potentially resurrected tweets")

        resurrected_idx = 0
        for tweet_id in resurrected_ids:
            resurrected_idx += 1
            try:
                tweets_map = read_posted_tweets_cache(username)
                if tweet_id not in tweets_map:
                    continue

                tweet = tweets_map[tweet_id]
                url = tweet.get("url", f"https://x.com/{user_handle}/status/{tweet_id}")

                # Deep scrape the resurrected tweet
                scrape_result = await deep_scrape_thread(context, url, tweet_id, user_handle)

                # Process replies
                scraped_replies = scrape_result.get("replies", [])
                new_comment_ids = process_scraped_replies(username, scraped_replies, user_handle)
                results["new_comments"] += len(new_comment_ids)

                # Process quote tweets
                scraped_qts = scrape_result.get("quote_tweets", [])
                new_qt_ids = process_scraped_quote_tweets(username, scraped_qts, user_handle, tweet_id)
                results["new_quote_tweets"] += len(new_qt_ids)

                # Promote to active
                now = datetime.now(UTC).isoformat()
                tweets_map = read_posted_tweets_cache(username)
                if tweet_id in tweets_map:
                    tweets_map[tweet_id]["monitoring_state"] = "active"
                    tweets_map[tweet_id]["resurrected_via"] = "notification"
                    tweets_map[tweet_id]["last_activity_at"] = now
                    tweets_map[tweet_id]["last_deep_scrape"] = now
                    tweets_map[tweet_id]["last_reply_count"] = scrape_result.get("reply_count", 0)
                    tweets_map[tweet_id]["last_like_count"] = scrape_result.get("like_count", 0)
                    tweets_map[tweet_id]["last_quote_count"] = scrape_result.get("quote_count", 0)
                    tweets_map[tweet_id]["last_retweet_count"] = scrape_result.get("retweet_count", 0)
                    tweets_map[tweet_id]["replies"] = scrape_result.get("reply_count", 0)
                    tweets_map[tweet_id]["likes"] = scrape_result.get("like_count", 0)
                    tweets_map[tweet_id]["quotes"] = scrape_result.get("quote_count", 0)
                    tweets_map[tweet_id]["retweets"] = scrape_result.get("retweet_count", 0)
                    tweets_map[tweet_id]["last_scraped_reply_ids"] = scrape_result.get("all_reply_ids", [])[:50]
                    write_posted_tweets_cache(username, tweets_map)

                results["resurrected_tweets"] += 1
                notify(f"🔥 Resurrected cold tweet {tweet_id}")

                # Rate limiting
                await asyncio.sleep(2)

            except Exception as e:
                notify(f"⚠️ Error processing resurrected {tweet_id}: {e}")
                results["errors"].append(f"Resurrect {tweet_id}: {e}")

        notify(f"✅ [discover_resurrected] Complete: {results['resurrected_tweets']} resurrected, {results['new_comments']} comments, {results['new_quote_tweets']} QTs")

    except Exception as e:
        error(f"discover_resurrected failed: {e}", status_code=500, function_name="discover_resurrected", username=username, critical=False)
        results["errors"].append(str(e))

    finally:
        await cleanup_browser_resources(playwright, browser, context)

    return results


async def run_engagement_monitoring(username: str, user_handle: str) -> dict[str, Any]:
    """
    Run all engagement monitoring jobs in the correct order.

    Order:
    1. discover_recently_posted - Find external tweets first
    2. discover_engagement - Monitor active/warm tweets
    3. discover_resurrected - Check notifications for cold tweets

    This ensures new tweets are tracked before engagement checks.

    Args:
        username: User's cache key
        user_handle: User's Twitter handle

    Returns:
        Combined results from all jobs
    """
    notify(f"🚀 [run_engagement_monitoring] Starting full engagement monitoring for @{user_handle}")

    results = {
        "discover_recently_posted": {},
        "discover_engagement": {},
        "discover_resurrected": {},
        "total_new_comments": 0,
        "errors": []
    }

    try:
        # Job 1: Discover recently posted
        notify("📍 Running discover_recently_posted...")
        results["discover_recently_posted"] = await discover_recently_posted(username, user_handle)
        results["total_new_comments"] += results["discover_recently_posted"].get("new_comments", 0)

        # Brief pause between jobs
        await asyncio.sleep(2)

        # Job 2: Discover engagement
        notify("📍 Running discover_engagement...")
        results["discover_engagement"] = await discover_engagement(username, user_handle)
        results["total_new_comments"] += results["discover_engagement"].get("new_comments", 0)

        # Brief pause between jobs
        await asyncio.sleep(2)

        # Job 3: Discover resurrected
        notify("📍 Running discover_resurrected...")
        results["discover_resurrected"] = await discover_resurrected(username, user_handle)
        results["total_new_comments"] += results["discover_resurrected"].get("new_comments", 0)

        notify(f"✅ [run_engagement_monitoring] Complete. Total new comments: {results['total_new_comments']}")

    except Exception as e:
        error(f"run_engagement_monitoring failed: {e}", status_code=500, function_name="run_engagement_monitoring", username=username, critical=False)
        results["errors"].append(str(e))

    return results
