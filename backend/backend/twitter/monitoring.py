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
    Compares new metrics against current stored metrics (which represent the previous scrape).
    Returns sum of (new_replies - old_replies) + (new_likes - old_likes) + ...
    """
    delta = 0
    delta += max(0, new_metrics.get("replies", 0) - (tweet.get("replies") or 0))
    delta += max(0, new_metrics.get("likes", 0) - (tweet.get("likes") or 0))
    delta += max(0, new_metrics.get("quotes", 0) - (tweet.get("quotes") or 0))
    delta += max(0, new_metrics.get("retweets", 0) - (tweet.get("retweets") or 0))
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


def _update_intent_filter_examples(username: str, limit: int = 10) -> None:
    """
    Update intent_filter_examples in user_info with top-performing replies.

    Uses get_top_posts_by_type("reply") to get replies sorted by engagement score,
    then extracts the original posts (not the user's reply text) as examples.

    Only includes replies posted AFTER intent_filter_last_updated to ensure
    examples are relevant to the current intent.

    Args:
        username: User's handle
        limit: Max number of examples to store
    """
    from datetime import datetime
    from backend.data.twitter.posted_tweets_cache import get_top_posts_by_type
    from backend.utlils.utils import read_user_info, write_user_info

    # Read user info to get intent_filter_last_updated timestamp
    user_info = read_user_info(username)
    if not user_info:
        return

    intent_last_updated = user_info.get("intent_filter_last_updated")
    intent_last_updated_dt = None
    if intent_last_updated:
        try:
            intent_last_updated_dt = datetime.fromisoformat(intent_last_updated)
        except (ValueError, TypeError):
            pass

    # Get top replies - fetch more than limit to account for filtering
    top_replies = get_top_posts_by_type(username, post_type="reply", limit=limit * 3)

    examples = []
    for post in top_replies:
        # Skip if this reply was posted before intent was last updated
        if intent_last_updated_dt:
            created_at = post.get("created_at")
            if created_at:
                try:
                    created_at_dt = datetime.fromisoformat(created_at)
                    if created_at_dt < intent_last_updated_dt:
                        continue  # Skip this post - it's from before current intent
                except (ValueError, TypeError):
                    pass  # If we can't parse, include it anyway

        response_to_thread = post.get("response_to_thread", [])
        responding_to = post.get("responding_to", "")

        if response_to_thread and responding_to:
            # Join thread texts and truncate - only include original post, not user's reply
            original_text = " | ".join(response_to_thread)[:500]
            examples.append({
                "author": responding_to,
                "text": original_text
            })

            # Stop once we have enough examples
            if len(examples) >= limit:
                break

    # Update user_info with new examples
    user_info["intent_filter_examples"] = examples
    write_user_info(user_info)
    notify(f"📚 Updated intent filter examples ({len(examples)}) for @{username}")


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
        get_user_tweet_ids,
        get_posted_tweet,
    )
    from backend.utlils.supabase_client import (
        add_posted_tweet as sb_add_tweet,
        update_posted_tweet as sb_update_tweet,
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
        notify(f"[DEBUG] Existing tweet IDs in cache: {len(existing_ids)}")

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
                existing_tweet = get_posted_tweet(username, tweet_id) or {}
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

                # Backfill/correct post_type if missing or incorrect
                # Check if post_type needs to be set or corrected
                current_post_type = existing_tweet.get("post_type")
                response_to_thread = existing_tweet.get("response_to_thread", [])
                responding_to = existing_tweet.get("responding_to", "")
                parent_chain = existing_tweet.get("parent_chain", [])

                # Determine correct post_type based on existing data
                correct_post_type = "reply"  # default
                if not parent_chain:
                    correct_post_type = "original"
                elif responding_to and responding_to.lower() == user_handle.lower():
                    correct_post_type = "original"  # Thread continuation
                elif response_to_thread and response_to_thread[0].strip().lower().startswith(f"@{user_handle.lower()}"):
                    correct_post_type = "comment_reply"

                # Update if missing or incorrect (specifically fix "reply" -> "comment_reply" misclassifications)
                if current_post_type != correct_post_type:
                    existing_tweet["post_type"] = correct_post_type
                    updated = True
                    notify(f"📝 Corrected post_type={correct_post_type} (was {current_post_type}) for tweet {tweet_id}")

                if updated:
                    # Build update dict with only changed fields
                    update_fields = {}
                    if existing_tweet.get("quoted_tweet"):
                        update_fields["quoted_tweet"] = existing_tweet["quoted_tweet"]
                    if existing_tweet.get("response_to_thread"):
                        update_fields["response_to_thread"] = existing_tweet["response_to_thread"]
                        update_fields["responding_to"] = existing_tweet.get("responding_to", "")
                        update_fields["replying_to_pfp"] = existing_tweet.get("replying_to_pfp", "")
                        update_fields["original_tweet_url"] = existing_tweet.get("original_tweet_url", "")
                    if existing_tweet.get("post_type"):
                        update_fields["post_type"] = existing_tweet["post_type"]
                    if update_fields:
                        sb_update_tweet(tweet_id, update_fields)
                continue

            # Skip retweets (in_reply_to_status_id would be set for quote tweets too)
            # Only track original tweets and replies by the user
            in_reply_to = tweet.get("in_reply_to_status_id")

            try:
                # Add to posted_tweets
                created_at = tweet.get("created_at", datetime.now(UTC).isoformat())
                url = tweet.get("url", f"https://x.com/{user_handle}/status/{tweet_id}")

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

                # Determine post_type based on reply context
                # - "original": standalone post or thread continuation (replying to self)
                # - "reply": replying to someone else's original post
                # - "comment_reply": replying to a comment on user's own post
                post_type = "reply"  # default
                if not in_reply_to:
                    post_type = "original"
                elif responding_to and responding_to.lower() == user_handle.lower():
                    post_type = "original"  # Thread continuation
                elif response_to_thread and response_to_thread[0].strip().lower().startswith(f"@{user_handle.lower()}"):
                    # The tweet being replied to starts with @user_handle, meaning it was a reply to user
                    post_type = "comment_reply"
                # else: remains "reply" - replying to someone else's post

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
                    "resurrected_via": "none",
                    "last_scraped_reply_ids": [],
                    "post_type": post_type,
                    "score": 0  # Will be updated when metrics are fetched
                }

                sb_add_tweet(tweet_data)

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
                        sb_update_tweet(tweet_id, {
                            "last_scraped_reply_ids": scrape_result.get("all_reply_ids", [])[:50]
                        })

                    except Exception as e:
                        notify(f"⚠️ Error deep scraping {tweet_id}: {e}")
                        results["errors"].append(f"Deep scrape {tweet_id}: {e}")

            except Exception as e:
                notify(f"⚠️ Error processing discovered tweet {tweet_id}: {e}")
                results["errors"].append(f"Process {tweet_id}: {e}")

        notify(f"[DEBUG] Summary: {len(recent_tweets)} fetched, {skipped_existing} already tracked, {skipped_no_id} no ID, {results['discovered_tweets']} discovered")
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
    )
    from backend.utlils.supabase_client import update_posted_tweet as sb_update_tweet
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
            tweet_id = tweet.get("tweet_id")
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
                now = datetime.now(UTC).isoformat()
                updates = {
                    "replies": scrape_result.get("reply_count", 0),
                    "likes": scrape_result.get("like_count", 0),
                    "quotes": scrape_result.get("quote_count", 0),
                    "retweets": scrape_result.get("retweet_count", 0),
                    "last_scraped_reply_ids": scrape_result.get("all_reply_ids", [])[:50],
                }

                # Update activity if new comments or quote tweets found
                if new_comment_ids or new_qt_ids:
                    updates["last_activity_at"] = now

                # Check if should demote - need to build temp tweet for state check
                temp_tweet = dict(tweet)
                temp_tweet.update(updates)
                new_state = _determine_monitoring_state(temp_tweet)
                if new_state != "active":
                    updates["monitoring_state"] = new_state
                    if new_state == "warm":
                        results["demoted_to_warm"] += 1
                    else:
                        results["demoted_to_cold"] += 1

                sb_update_tweet(tweet_id, updates)

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
            tweet_id = tweet.get("tweet_id")
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

                now = datetime.now(UTC).isoformat()
                updates = {
                    "replies": new_metrics["replies"],
                    "likes": new_metrics["likes"],
                    "quotes": new_metrics["quotes"],
                    "retweets": new_metrics["retweets"],
                }

                if should_promote:
                    updates["monitoring_state"] = "active"
                    updates["last_activity_at"] = now
                    updates["resurrected_via"] = "engagement"
                    results["promoted_to_active"] += 1
                    notify(f"🔥 Promoted {tweet_id} to active (new engagement)")
                else:
                    # Check for demotion to cold
                    temp_tweet = dict(tweet)
                    temp_tweet.update(updates)
                    new_state = _determine_monitoring_state(temp_tweet)
                    if new_state == "cold":
                        updates["monitoring_state"] = "cold"
                        results["demoted_to_cold"] += 1

                sb_update_tweet(tweet_id, updates)

                # Rate limiting
                await asyncio.sleep(1)

            except Exception as e:
                notify(f"⚠️ Error shallow scraping {tweet_id}: {e}")
                results["errors"].append(f"Shallow scrape {tweet_id}: {e}")

        notify(f"✅ [discover_engagement] Complete: {results['active_scraped']} deep, {results['warm_scraped']} shallow, {results['new_comments']} comments, {results['new_quote_tweets']} QTs")

        # Update intent_filter_examples with top-performing replies (sorted by engagement)
        try:
            _update_intent_filter_examples(username)
        except Exception as e:
            notify(f"⚠️ Failed to update intent filter examples: {e}")

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
        get_posted_tweet,
    )
    from backend.utlils.supabase_client import update_posted_tweet as sb_update_tweet
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
        cold_tweet_ids = {t.get("tweet_id") for t in cold_tweets if t.get("tweet_id")}

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
                tweet = get_posted_tweet(username, tweet_id)
                if not tweet:
                    continue

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
                sb_update_tweet(tweet_id, {
                    "monitoring_state": "active",
                    "resurrected_via": "notification",
                    "last_activity_at": now,
                    "replies": scrape_result.get("reply_count", 0),
                    "likes": scrape_result.get("like_count", 0),
                    "quotes": scrape_result.get("quote_count", 0),
                    "retweets": scrape_result.get("retweet_count", 0),
                    "last_scraped_reply_ids": scrape_result.get("all_reply_ids", [])[:50],
                })

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
