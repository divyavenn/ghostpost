"""
Twitter Background Jobs API

Three main background jobs:
1. find_and_reply_to_new_posts - Scrape tweets and generate replies in parallel
2. find_user_activity - Discover user's external posts and resurrect cold tweets
3. find_and_reply_to_engagement - Monitor engagement and generate comment replies in parallel
"""
import asyncio
from datetime import datetime
from typing import Any

try:
    from datetime import UTC
except ImportError:
    from datetime import timezone
    UTC = timezone.utc

from fastapi import APIRouter, BackgroundTasks, HTTPException

from backend.twitter.display_progress import (
    clear_phase_tracking,
    get_job_display_name,
    print_job_complete,
    print_job_error,
    print_job_start,
    print_progress_bar,
)
from backend.utlils.utils import error, notify, read_user_info


router = APIRouter(prefix="/jobs", tags=["jobs"])


# =============================================================================
# Job Status Tracking
# =============================================================================

# Global status tracker for all jobs
# {username: {job_name: {status, phase, progress, results, started_at, triggered_by, error}}}
job_status: dict[str, dict[str, dict]] = {}


def get_job_status(username: str, job_name: str) -> dict:
    """Get the current status of a specific job for a user.

    Returns simplified format:
    - status: idle | running | complete | error
    - phase: current phase (scraping, generating, discovering, etc.)
    - percentage: 0-100
    - details: extra info like which account/query
    """
    user_jobs = job_status.get(username, {})
    job = user_jobs.get(job_name, {
        "status": "idle",
        "phase": "idle",
        "progress": {"current": 0, "total": 0},
        "details": None,
        "results": {},
        "started_at": None,
        "triggered_by": None,
        "error": None
    })

    # Calculate percentage
    progress = job.get("progress", {"current": 0, "total": 0})
    current = progress.get("current", 0)
    total = progress.get("total", 0)

    if job["status"] == "idle":
        percentage = 0
    elif job["status"] == "complete":
        percentage = 100
    elif job["status"] == "error":
        percentage = 0
    elif total > 0:
        percentage = min(99, int((current / total) * 100))  # Cap at 99 until complete
    else:
        # Running but no progress tracking - show indeterminate progress
        percentage = 10

    # Return simplified format
    return {
        "status": job["status"],
        "phase": job["phase"],
        "percentage": percentage,
        "details": job.get("details"),
        "error": job.get("error")
    }


def get_all_job_status(username: str) -> dict:
    """Get status of all jobs for a user."""
    jobs = {
        "find_and_reply_to_new_posts": get_job_status(username, "find_and_reply_to_new_posts"),
        "find_user_activity": get_job_status(username, "find_user_activity"),
        "find_and_reply_to_engagement": get_job_status(username, "find_and_reply_to_engagement"),
    }

    # Calculate overall status
    running_jobs = [name for name, job in jobs.items() if job["status"] == "running"]
    completed_jobs = [name for name, job in jobs.items() if job["status"] == "complete"]
    error_jobs = [name for name, job in jobs.items() if job["status"] == "error"]

    if running_jobs:
        overall_status = "running"
        # Get the currently running job's percentage
        running_job = jobs[running_jobs[0]]
        overall_percentage = running_job["percentage"]
        overall_message = f"{get_job_display_name(running_jobs[0])}: {running_job.get('phase', 'processing')} ({overall_percentage}%)"
    elif error_jobs:
        overall_status = "error"
        overall_percentage = 0
        overall_message = f"Error in {get_job_display_name(error_jobs[0])}"
    elif completed_jobs:
        overall_status = "complete"
        overall_percentage = 100
        overall_message = "All jobs complete"
    else:
        overall_status = "idle"
        overall_percentage = 0
        overall_message = "No jobs running"

    return {
        "jobs": jobs,
        "overall": {
            "status": overall_status,
            "percentage": overall_percentage,
            "message": overall_message,
            "running_jobs": running_jobs,
            "completed_jobs": completed_jobs,
            "error_jobs": error_jobs
        }
    }


def _update_job_status(
    username: str,
    job_name: str,
    status: str,
    phase: str,
    progress: dict | None = None,
    details: str | None = None,
    results: dict | None = None,
    error_msg: str | None = None,
    triggered_by: str | None = None
):
    """Update status for a specific job.

    Args:
        status: idle | running | complete | error
        phase: current phase (scraping, generating, discovering, etc.)
        progress: {"current": N, "total": M} for percentage calculation
        details: extra info like "@handle" or "keyword search"
    """
    if username not in job_status:
        job_status[username] = {}

    current = job_status[username].get(job_name, {})

    # Preserve triggered_by from current if not provided
    if triggered_by is None:
        triggered_by = current.get("triggered_by", "unknown")

    job_status[username][job_name] = {
        "status": status,
        "phase": phase,
        "progress": progress or current.get("progress", {"current": 0, "total": 0}),
        "details": details,
        "results": results or current.get("results", {}),
        "started_at": current.get("started_at") if status not in ["idle", "complete"] else None,
        "triggered_by": triggered_by,
        "error": error_msg
    }

    if status == "running" and not current.get("started_at"):
        job_status[username][job_name]["started_at"] = datetime.now(UTC).isoformat()

    # Print progress bar to console (docker-log friendly)
    if progress and status == "running":
        display_phase = f"{phase}: {details}" if details else phase
        print_progress_bar(
            job_name, display_phase,
            progress.get("current", 0), progress.get("total", 0),
            username, triggered_by
        )


async def _reset_job_to_idle(username: str, job_name: str, delay: float = 5.0):
    """Reset job status to idle after a delay."""
    await asyncio.sleep(delay)
    if username in job_status and job_name in job_status[username]:
        if job_status[username][job_name]["status"] == "complete":
            _update_job_status(username, job_name, "idle", "idle")


# =============================================================================
# Job 1: Find and Reply to New Posts
# =============================================================================

async def _generate_reply_for_tweet_background(tweet: dict, username: str):
    """
    Background task to generate replies for a single tweet.
    Runs in parallel with scraping.
    """
    from backend.data.twitter.edit_cache import write_to_cache
    from backend.twitter.generate_replies import generate_replies_for_tweet

    try:
        user_info = read_user_info(username)
        if not user_info:
            return

        # Only generate for premium users
        if user_info.get("account_type") != "premium":
            return

        models = user_info.get("models", ["claude-3-5-sonnet-20241022"])
        num_generations = user_info.get("number_of_generations", 2)

        tweet_id = tweet.get("id") or tweet.get("tweet_id")
        if not tweet_id:
            return

        # Generate replies
        replies = await generate_replies_for_tweet(
            tweet=tweet,
            models=models,
            needed_generations=num_generations,
            delay_seconds=0.5,
            username=username
        )

        if replies:
            # Update tweet with generated replies
            tweet["generated_replies"] = replies
            await write_to_cache([tweet], "Background reply generation", username=username)
            notify(f"✅ [Background] Generated {len(replies)} replies for tweet {tweet_id}")

    except Exception as e:
        notify(f"⚠️ [Background] Error generating replies for tweet: {e}")


async def find_and_reply_to_new_posts(username: str, triggered_by: str = "user") -> dict:
    """
    Job 1: Scrape tweets from configured accounts/queries and generate AI replies.

    Reply generation happens in parallel as each tweet is discovered and written to cache.

    Args:
        username: The user to run the job for
        triggered_by: "user" for manual trigger, "scheduler" for background scheduler

    Steps:
    1. Cleanup old tweets and seen_tweets
    2. Scrape tweets from accounts and queries (with intent filtering)
    3. For each tweet written to cache, spawn background task to generate replies
    4. Track scrolling_time_saved metrics

    Returns:
        Summary dict with counts
    """
    import time
    from backend.config import MAX_TWEET_AGE_HOURS
    from backend.data.twitter.edit_cache import cleanup_old_tweets, write_to_cache
    from backend.browser_automation.twitter.api import collect_from_page as api_collect_from_page
    from backend.user.user import read_user_settings
    from backend.utlils.utils import cleanup_seen_tweets, is_tweet_seen, write_user_info

    print_job_start("find_and_reply_to_new_posts", username, triggered_by)
    _update_job_status(username, "find_and_reply_to_new_posts", "running", "starting", triggered_by=triggered_by)
    notify(f"🚀 [Job 1] Starting find_and_reply_to_new_posts for {username}")

    start_time = time.time()
    results = {
        "tweets_scraped": 0,
        "tweets_filtered": 0,
        "replies_generating": 0,
        "errors": []
    }

    try:
        user_settings = read_user_settings(username)
        if not user_settings:
            error(f"No settings found for user {username}", critical=True)
            return results

        user_info = read_user_info(username)
        is_premium = user_info.get("account_type") == "premium" if user_info else False

        # Get accounts and queries
        accounts_dict = user_settings.get("relevant_accounts", {})
        relevant_accounts = [handle for handle, validated in accounts_dict.items() if validated]

        # Build query summary map
        query_summary_map = {}
        if user_info:
            stored_queries = user_info.get("queries", [])
            queries = []
            for q in stored_queries:
                if isinstance(q, list) and len(q) == 2:
                    queries.append(q[0])
                    query_summary_map[q[0]] = q[1]
                elif isinstance(q, str):
                    queries.append(q)
                    query_summary_map[q] = q
        else:
            queries = user_settings.get("queries", [])
            for q in queries:
                query_summary_map[q] = q

        max_tweets = user_settings.get("max_tweets_retrieve", 50)

        # Cleanup old tweets
        _update_job_status(username, "find_and_reply_to_new_posts", "running", "cleanup")
        await cleanup_old_tweets(username, hours=MAX_TWEET_AGE_HOURS)
        cleanup_seen_tweets(username, hours=MAX_TWEET_AGE_HOURS)

        # Track background reply generation tasks
        reply_tasks = []

        # Progressive write callback that spawns reply generation
        async def progressive_write_with_replies(tweets_batch, target_username):
            """Write tweets and spawn reply generation in parallel."""
            nonlocal reply_tasks

            filtered_batch = []
            for tweet in tweets_batch:
                tweet_id = tweet.get("id") or tweet.get("tweet_id")
                if tweet_id and not is_tweet_seen(target_username, str(tweet_id)):
                    filtered_batch.append(tweet)

            if filtered_batch:
                await write_to_cache(filtered_batch, "Progressive tweet scraping", username=target_username)
                results["tweets_scraped"] += len(filtered_batch)

                # Spawn reply generation for each tweet (premium only)
                if is_premium:
                    for tweet in filtered_batch:
                        task = asyncio.create_task(
                            _generate_reply_for_tweet_background(tweet, target_username)
                        )
                        reply_tasks.append(task)
                        results["replies_generating"] += 1

        # Scrape accounts
        total_sources = len(relevant_accounts) + len(queries)
        current_source = 0
        all_tweets = {}

        for account in relevant_accounts:
            current_source += 1
            _update_job_status(
                username, "find_and_reply_to_new_posts", "running",
                "scraping",
                progress={"current": current_source, "total": total_sources},
                details=f"@{account}"
            )

            try:
                url = f"https://x.com/{account}"
                tweets = await api_collect_from_page(
                    None, url, handle=account, username=username,
                    write_callback=progressive_write_with_replies
                )
                for tweet_data in tweets.values():
                    tweet_data["scraped_from"] = {"type": "account", "value": account}
                all_tweets.update(tweets)
            except Exception as e:
                notify(f"⚠️ Error scraping @{account}: {e}")
                results["errors"].append(f"Account {account}: {e}")

        # Scrape queries
        from urllib.parse import quote_plus
        for query in queries:
            current_source += 1
            summary = query_summary_map.get(query, query)
            _update_job_status(
                username, "find_and_reply_to_new_posts", "running",
                "searching",
                progress={"current": current_source, "total": total_sources},
                details=summary[:30]
            )

            try:
                url = f"https://x.com/search?q={quote_plus(query)}"
                tweets = await api_collect_from_page(
                    None, url, handle=None, username=username,
                    write_callback=progressive_write_with_replies
                )
                for tweet_data in tweets.values():
                    tweet_data["scraped_from"] = {"type": "query", "value": query, "summary": summary}
                all_tweets.update(tweets)
            except Exception as e:
                notify(f"⚠️ Error searching [{query}]: {e}")
                results["errors"].append(f"Query {query}: {e}")

        # Fetch from home timeline (Following tab) with intent filtering
        _update_job_status(
            username, "find_and_reply_to_new_posts", "running",
            "scanning",
            progress={"current": total_sources, "total": total_sources + 1},
            details="your feed"
        )

        try:
            from backend.browser_automation.twitter.api import fetch_home_timeline_with_intent_filter

            home_tweets = await fetch_home_timeline_with_intent_filter(
                username=username,
                max_tweets=max_tweets,
                write_callback=progressive_write_with_replies,
                generate_replies_inline=is_premium
            )
            for tweet_data in home_tweets.values():
                tweet_data["scraped_from"] = {"type": "home_timeline", "value": "following"}
            all_tweets.update(home_tweets)
            results["home_timeline_tweets"] = len(home_tweets)
            notify(f"✅ Found {len(home_tweets)} tweets from home timeline that match intent")
        except Exception as e:
            notify(f"⚠️ Error fetching home timeline: {e}")
            results["errors"].append(f"Home timeline: {e}")

        # Wait for all reply generation tasks to complete
        if reply_tasks:
            _update_job_status(
                username, "find_and_reply_to_new_posts", "running",
                "generating_replies",
                progress={"current": 0, "total": len(reply_tasks)}
            )
            notify(f"⏳ Waiting for {len(reply_tasks)} reply generation tasks...")
            await asyncio.gather(*reply_tasks, return_exceptions=True)

        # Update scrolling time saved
        end_time = time.time()
        duration = int(end_time - start_time)
        if user_info:
            user_info["scrolling_time_saved"] = user_info.get("scrolling_time_saved", 0) + duration
            write_user_info(user_info)

        results["duration_seconds"] = duration

        _update_job_status(
            username, "find_and_reply_to_new_posts", "complete", "complete",
            results=results
        )

        # Print completion log
        summary = f"{results['tweets_scraped']} tweets, {results['replies_generating']} replies"
        print_job_complete("find_and_reply_to_new_posts", username, triggered_by, summary, duration)
        notify(f"✅ [Job 1] Complete: {results['tweets_scraped']} tweets, {results['replies_generating']} replies generating")

        # Reset to idle after delay
        asyncio.create_task(_reset_job_to_idle(username, "find_and_reply_to_new_posts"))

    except Exception as e:
        error(f"find_and_reply_to_new_posts failed: {e}", status_code=500, function_name="find_and_reply_to_new_posts", username=username, critical=False)
        results["errors"].append(str(e))
        _update_job_status(
            username, "find_and_reply_to_new_posts", "error", "error",
            results=results, error_msg=str(e)
        )

    return results


# =============================================================================
# Job 2: Find User Activity
# =============================================================================

async def find_user_activity(username: str, max_tweets: int = 50, triggered_by: str = "user") -> dict:
    """
    Job 2: Discover user's external posts and resurrect cold tweets.

    Runs discover_recently_posted and discover_resurrected in parallel.
    No reply generation - just discovery.

    Args:
        username: The user to run the job for
        max_tweets: Maximum tweets to retrieve
        triggered_by: "user" for manual trigger, "scheduler" for background scheduler

    Steps:
    1. discover_recently_posted - Find tweets posted externally (last 7 days)
    2. discover_resurrected - Check notifications for cold tweet activity
    (Both run in parallel)

    Returns:
        Combined results from both jobs
    """
    import time
    from backend.twitter.monitoring import discover_recently_posted, discover_resurrected

    start_time = time.time()
    print_job_start("find_user_activity", username, triggered_by)
    _update_job_status(username, "find_user_activity", "running", "starting", triggered_by=triggered_by)
    notify(f"🚀 [Job 2] Starting find_user_activity for {username}")

    user_info = read_user_info(username)
    if not user_info:
        raise HTTPException(status_code=404, detail="User not found")

    user_handle = user_info.get("handle", username)

    results = {
        "discover_recently_posted": {},
        "discover_resurrected": {},
        "total_discovered": 0,
        "total_comments": 0,
        "total_quote_tweets": 0,
        "errors": []
    }

    # Flag to stop progress updater
    job_complete = False

    async def progress_updater():
        """Update progress every second while job is running."""
        progress_val = 0
        while not job_complete:
            progress_val = min(90, progress_val + 5)  # Increment up to 90%
            _update_job_status(
                username, "find_user_activity", "running", "discovering",
                progress={"current": progress_val, "total": 100},
                details="your activity"
            )
            await asyncio.sleep(1)

    try:
        _update_job_status(username, "find_user_activity", "running", "discovering",
                          progress={"current": 0, "total": 100}, details="your activity")

        # Start progress updater in background
        progress_task = asyncio.create_task(progress_updater())

        # Run both jobs in parallel
        recently_posted_task = asyncio.create_task(
            discover_recently_posted(username, user_handle, max_tweets)
        )
        resurrected_task = asyncio.create_task(
            discover_resurrected(username, user_handle)
        )

        # Wait for both
        recently_posted_result, resurrected_result = await asyncio.gather(
            recently_posted_task, resurrected_task, return_exceptions=True
        )

        # Stop progress updater
        job_complete = True
        progress_task.cancel()
        try:
            await progress_task
        except asyncio.CancelledError:
            pass

        # Handle results
        if isinstance(recently_posted_result, Exception):
            results["errors"].append(f"discover_recently_posted: {recently_posted_result}")
            results["discover_recently_posted"] = {"error": str(recently_posted_result)}
        else:
            results["discover_recently_posted"] = recently_posted_result
            results["total_discovered"] += recently_posted_result.get("discovered_tweets", 0)
            results["total_comments"] += recently_posted_result.get("new_comments", 0)
            results["total_quote_tweets"] += recently_posted_result.get("new_quote_tweets", 0)

        if isinstance(resurrected_result, Exception):
            results["errors"].append(f"discover_resurrected: {resurrected_result}")
            results["discover_resurrected"] = {"error": str(resurrected_result)}
        else:
            results["discover_resurrected"] = resurrected_result
            results["total_discovered"] += resurrected_result.get("resurrected_tweets", 0)
            results["total_comments"] += resurrected_result.get("new_comments", 0)
            results["total_quote_tweets"] += resurrected_result.get("new_quote_tweets", 0)

        duration = int(time.time() - start_time)
        _update_job_status(
            username, "find_user_activity", "complete", "complete",
            results=results
        )

        # Print completion log
        summary = f"{results['total_discovered']} discovered, {results['total_comments']} comments"
        print_job_complete("find_user_activity", username, triggered_by, summary, duration)
        notify(f"✅ [Job 2] Complete: {results['total_discovered']} discovered, {results['total_comments']} comments, {results['total_quote_tweets']} QTs")

        # Reset to idle after delay
        asyncio.create_task(_reset_job_to_idle(username, "find_user_activity"))

    except Exception as e:
        # Stop progress updater on error
        job_complete = True
        if 'progress_task' in dir():
            progress_task.cancel()
            try:
                await progress_task
            except asyncio.CancelledError:
                pass
        error(f"find_user_activity failed: {e}", status_code=500, function_name="find_user_activity", username=username, critical=False)
        results["errors"].append(str(e))
        _update_job_status(
            username, "find_user_activity", "error", "error",
            results=results, error_msg=str(e)
        )

    return results


# =============================================================================
# Job 3: Find and Reply to Engagement
# =============================================================================

async def _generate_reply_for_comment_background(
    username: str,
    comment: dict,
    thread_context: list[dict]
):
    """
    Background task to generate replies for a single comment.
    Runs in parallel with scraping.
    """
    from backend.data.twitter.comments_cache import update_comment_generated_replies
    from backend.twitter.comment_replies import generate_replies_for_comment

    try:
        user_info = read_user_info(username)
        if not user_info:
            return

        models = user_info.get("models", ["claude-3-5-sonnet-20241022"])
        num_generations = user_info.get("number_of_generations", 2)

        comment_id = comment.get("id")
        if not comment_id:
            return

        # Generate replies
        replies = await generate_replies_for_comment(
            comment=comment,
            thread_context=thread_context,
            models=models,
            num_generations=num_generations,
            delay_seconds=0.5,
            username=username
        )

        if replies:
            update_comment_generated_replies(username, comment_id, replies)
            notify(f"✅ [Background] Generated {len(replies)} replies for comment {comment_id}")

    except Exception as e:
        notify(f"⚠️ [Background] Error generating reply for comment: {e}")


async def find_and_reply_to_engagement(username: str, triggered_by: str = "user") -> dict:
    """
    Job 3: Monitor engagement on posted tweets and generate comment replies.

    Reply generation happens in parallel as comments are discovered.

    Args:
        username: The user to run the job for
        triggered_by: "user" for manual trigger, "scheduler" for background scheduler

    Order:
    1. Shallow scrape WARM tweets first (to identify promotions)
    2. Deep scrape ACTIVE tweets (including newly promoted)
    3. Generate replies for discovered comments in parallel

    Returns:
        Summary dict with counts
    """
    import time
    from backend.browser_management.context import cleanup_browser_resources, get_authenticated_context
    from backend.data.twitter.comments_cache import (
        get_comment, get_thread_context, process_scraped_quote_tweets, process_scraped_replies
    )
    from backend.data.twitter.posted_tweets_cache import (
        get_tweets_by_monitoring_state, read_posted_tweets_cache, write_posted_tweets_cache
    )
    from backend.browser_automation.twitter.api import deep_scrape_thread, shallow_scrape_thread
    from backend.twitter.monitoring import (
        _determine_monitoring_state, _should_promote_to_active
    )

    start_time = time.time()
    print_job_start("find_and_reply_to_engagement", username, triggered_by)
    _update_job_status(username, "find_and_reply_to_engagement", "running", "starting", triggered_by=triggered_by)
    notify(f"🚀 [Job 3] Starting find_and_reply_to_engagement for {username}")

    user_info = read_user_info(username)
    if not user_info:
        raise HTTPException(status_code=404, detail="User not found")

    user_handle = user_info.get("handle", username)

    playwright = None
    browser = None
    context = None

    results = {
        "warm_scraped": 0,
        "active_scraped": 0,
        "new_comments": 0,
        "new_quote_tweets": 0,
        "replies_generating": 0,
        "promoted_to_active": 0,
        "demoted_to_warm": 0,
        "demoted_to_cold": 0,
        "errors": []
    }

    reply_tasks = []
    promoted_tweet_ids = set()  # Track tweets promoted from warm to active

    try:
        playwright, browser, context = await get_authenticated_context(username)

        # =================================================================
        # STEP 1: Shallow scrape WARM tweets first (to identify promotions)
        # =================================================================
        warm_tweets = get_tweets_by_monitoring_state(username, ["warm"])
        notify(f"📊 Found {len(warm_tweets)} warm tweets to shallow scrape")
        _update_job_status(
            username, "find_and_reply_to_engagement", "running",
            "scanning",
            progress={"current": 0, "total": len(warm_tweets)},
            details="warm tweets"
        )

        warm_idx = 0
        for tweet in warm_tweets:
            warm_idx += 1
            _update_job_status(
                username, "find_and_reply_to_engagement", "running",
                "scanning",
                progress={"current": warm_idx, "total": len(warm_tweets)},
                details="warm tweets"
            )

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
                        promoted_tweet_ids.add(tweet_id)
                        notify(f"🔥 Promoted {tweet_id} to active (new engagement)")
                    else:
                        # Check for demotion to cold
                        new_state = _determine_monitoring_state(tweets_map[tweet_id])
                        if new_state == "cold":
                            tweets_map[tweet_id]["monitoring_state"] = "cold"
                            results["demoted_to_cold"] += 1

                    write_posted_tweets_cache(username, tweets_map)

                await asyncio.sleep(1)

            except Exception as e:
                notify(f"⚠️ Error shallow scraping {tweet_id}: {e}")
                results["errors"].append(f"Shallow scrape {tweet_id}: {e}")

        # =================================================================
        # STEP 2: Deep scrape ACTIVE tweets (including newly promoted)
        # =================================================================
        active_tweets = get_tweets_by_monitoring_state(username, ["active"])
        notify(f"📊 Found {len(active_tweets)} active tweets to deep scrape (includes {len(promoted_tweet_ids)} newly promoted)")
        _update_job_status(
            username, "find_and_reply_to_engagement", "running",
            "scanning",
            progress={"current": 0, "total": len(active_tweets)},
            details="active tweets"
        )

        active_idx = 0
        for tweet in active_tweets:
            active_idx += 1
            _update_job_status(
                username, "find_and_reply_to_engagement", "running",
                "scanning",
                progress={"current": active_idx, "total": len(active_tweets)},
                details="active tweets"
            )

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

                # Spawn background tasks to generate replies for new comments
                for comment_id in new_comment_ids:
                    comment = get_comment(username, comment_id)
                    if comment:
                        thread_context = get_thread_context(comment_id, username)
                        if thread_context:
                            task = asyncio.create_task(
                                _generate_reply_for_comment_background(username, comment, thread_context)
                            )
                            reply_tasks.append(task)
                            results["replies_generating"] += 1

                # Also generate for new quote tweets (they're stored as comments)
                for qt_id in new_qt_ids:
                    comment = get_comment(username, qt_id)
                    if comment:
                        thread_context = get_thread_context(qt_id, username)
                        if thread_context:
                            task = asyncio.create_task(
                                _generate_reply_for_comment_background(username, comment, thread_context)
                            )
                            reply_tasks.append(task)
                            results["replies_generating"] += 1

                # Update tweet metrics
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

                    # Update activity if new comments or QTs found
                    if new_comment_ids or new_qt_ids:
                        tweets_map[tweet_id]["last_activity_at"] = now

                    # Check for demotion
                    new_state = _determine_monitoring_state(tweets_map[tweet_id])
                    if new_state != "active":
                        tweets_map[tweet_id]["monitoring_state"] = new_state
                        if new_state == "warm":
                            results["demoted_to_warm"] += 1
                        else:
                            results["demoted_to_cold"] += 1

                    write_posted_tweets_cache(username, tweets_map)

                await asyncio.sleep(2)

            except Exception as e:
                notify(f"⚠️ Error deep scraping {tweet_id}: {e}")
                results["errors"].append(f"Deep scrape {tweet_id}: {e}")

        # =================================================================
        # STEP 3: Wait for reply generation tasks
        # =================================================================
        if reply_tasks:
            _update_job_status(
                username, "find_and_reply_to_engagement", "running",
                "generating",
                progress={"current": 0, "total": len(reply_tasks)},
                details="replies"
            )
            notify(f"⏳ Waiting for {len(reply_tasks)} reply generation tasks...")
            await asyncio.gather(*reply_tasks, return_exceptions=True)

        duration = int(time.time() - start_time)
        _update_job_status(
            username, "find_and_reply_to_engagement", "complete", "complete",
            results=results
        )

        # Print completion log
        summary = f"{results['active_scraped']} deep, {results['warm_scraped']} shallow, {results['new_comments']} comments"
        print_job_complete("find_and_reply_to_engagement", username, triggered_by, summary, duration)
        notify(f"✅ [Job 3] Complete: {results['active_scraped']} deep, {results['warm_scraped']} shallow, {results['new_comments']} comments, {results['new_quote_tweets']} QTs, {results['replies_generating']} replies generating")

        # Reset to idle after delay
        asyncio.create_task(_reset_job_to_idle(username, "find_and_reply_to_engagement"))

    except Exception as e:
        error(f"find_and_reply_to_engagement failed: {e}", status_code=500, function_name="find_and_reply_to_engagement", username=username, critical=False)
        results["errors"].append(str(e))
        _update_job_status(
            username, "find_and_reply_to_engagement", "error", "error",
            results=results, error_msg=str(e)
        )

    finally:
        await cleanup_browser_resources(playwright, browser, context)

    return results


# =============================================================================
# API Endpoints
# =============================================================================

@router.post("/{username}/find-and-reply-to-new-posts")
async def start_find_and_reply_to_new_posts(
    username: str,
    background_tasks: BackgroundTasks,
    triggered_by: str = "user"
) -> dict:
    """
    Start Job 1: Find and reply to new posts.

    Scrapes tweets from configured accounts/queries and generates AI replies
    in parallel as tweets are discovered.

    Args:
        triggered_by: "user" for manual trigger, "scheduler" for background scheduler
    """
    user_info = read_user_info(username)
    if not user_info:
        raise HTTPException(status_code=404, detail="User not found")

    background_tasks.add_task(find_and_reply_to_new_posts, username, triggered_by)

    return {
        "message": "Job started: find_and_reply_to_new_posts",
        "username": username,
        "status": "running",
        "triggered_by": triggered_by
    }


@router.post("/{username}/find-user-activity")
async def start_find_user_activity(
    username: str,
    background_tasks: BackgroundTasks,
    max_tweets: int = 50,
    triggered_by: str = "user"
) -> dict:
    """
    Start Job 2: Find user activity.

    Discovers user's external posts and resurrects cold tweets.
    Runs discover_recently_posted and discover_resurrected in parallel.

    Args:
        triggered_by: "user" for manual trigger, "scheduler" for background scheduler
    """
    user_info = read_user_info(username)
    if not user_info:
        raise HTTPException(status_code=404, detail="User not found")

    background_tasks.add_task(find_user_activity, username, max_tweets, triggered_by)

    return {
        "message": "Job started: find_user_activity",
        "username": username,
        "status": "running",
        "triggered_by": triggered_by
    }


@router.post("/{username}/find-and-reply-to-engagement")
async def start_find_and_reply_to_engagement(
    username: str,
    background_tasks: BackgroundTasks,
    triggered_by: str = "user"
) -> dict:
    """
    Start Job 3: Find and reply to engagement.

    Monitors engagement on posted tweets and generates comment replies
    in parallel as comments are discovered.

    Order: Shallow scrape warm first, then deep scrape active (including promoted).

    Args:
        triggered_by: "user" for manual trigger, "scheduler" for background scheduler
    """
    user_info = read_user_info(username)
    if not user_info:
        raise HTTPException(status_code=404, detail="User not found")

    background_tasks.add_task(find_and_reply_to_engagement, username, triggered_by)

    return {
        "message": "Job started: find_and_reply_to_engagement",
        "username": username,
        "status": "running",
        "triggered_by": triggered_by
    }


@router.get("/{username}/status")
async def get_jobs_status(username: str) -> dict:
    """Get status of all background jobs for a user."""
    return get_all_job_status(username)


@router.get("/{username}/status/{job_name}")
async def get_single_job_status(username: str, job_name: str) -> dict:
    """Get status of a specific job for a user."""
    valid_jobs = ["find_and_reply_to_new_posts", "find_user_activity", "find_and_reply_to_engagement"]
    if job_name not in valid_jobs:
        raise HTTPException(status_code=400, detail=f"Invalid job name. Must be one of: {valid_jobs}")

    return get_job_status(username, job_name)
