"""
Twitter Background Jobs API

Four main background jobs:
1. find_and_reply_to_new_posts - Scrape tweets and generate replies in parallel
2. find_user_activity - Discover user's external posts and resurrect cold tweets
3. find_and_reply_to_engagement - Monitor engagement and generate comment replies in parallel
4. analyze - Analyze user's posting history and preferences
"""
import asyncio
from datetime import datetime

try:
    from datetime import UTC
except ImportError:
    from datetime import timezone
    UTC = timezone.utc

from fastapi import APIRouter, HTTPException

from backend.twitter.display_progress import (
    get_job_display_name,
    print_job_complete,
    print_job_start,
)
from backend.twitter.logging import log_job_complete, log_job_error
from backend.utlils.utils import error, notify, read_user_info


async def _run_job_with_error_handling(coro, job_name: str, username: str):
    """
    Wrapper that catches and logs any exceptions from background job coroutines.
    asyncio.create_task() silently swallows exceptions, so we need explicit handling.
    """
    try:
        return await coro
    except Exception as e:
        import traceback
        error_msg = f"{job_name} crashed: {e}\n{traceback.format_exc()}"
        notify(f"❌ [Background] {error_msg}")
        error(error_msg, status_code=500, function_name=job_name, username=username, critical=False)


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

    # Progress bars disabled - job logging happens to user log files instead
    pass


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

        # If models not configured, use None to trigger Gemini
        models = user_info.get("models", [None]) if user_info.get("models") else [None]
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


async def find_and_reply_to_new_posts(username: str, triggered_by: str = "manual") -> dict:
    """
    Job 1: Scrape tweets using efficient 4-phase approach.

    Phase 1: Lightweight discovery from queries + home timeline (no threads)
    Phase 2: Select top N by impressions
    Phase 3: Lightweight fetch from user timelines (no impressions filter)
    Phase 4: Fetch threads for ALL final tweets and write incrementally

    Args:
        username: The user to run the job for
        triggered_by: "user" for manual trigger, "scheduler" for background scheduler

    Returns:
        Summary dict with counts
    """
    import time
    import asyncio

    from backend.browser_automation.twitter.api import (
        fetch_search_raw,
        fetch_home_timeline_raw,
        fetch_user_timeline_raw,
        populate_thread_for_tweet
    )
    from backend.twitter.filtering import check_tweet_matches_intent_initial
    from backend.data.twitter.edit_cache import cleanup_old_tweets, write_to_cache
    from backend.user.user import read_user_settings
    from backend.utlils.utils import cleanup_seen_tweets, read_user_info, write_user_info

    print_job_start("find_and_reply_to_new_posts", username, triggered_by)
    _update_job_status(username, "find_and_reply_to_new_posts", "running", "starting", triggered_by=triggered_by)
    notify(f"🚀 [Job 1] Starting OPTIMIZED find_and_reply_to_new_posts for {username}")

    start_time = time.time()
    initiated_time = datetime.now(UTC)
    results = {
        "tweets_scraped": 0,
        "tweets_discovered": 0,
        "discovery_tweets_selected": 0,
        "account_tweets": 0,
        "threads_fetched": 0,
        "replies_generating": 0,
        "errors": []
    }

    try:
        # Load settings
        user_settings = read_user_settings(username)
        if not user_settings:
            error(f"No settings found for user {username}", critical=True)
            return results

        user_info = read_user_info(username)
        is_premium = user_info.get("account_type") == "premium" if user_info else False

        # Get configuration
        accounts_dict = user_settings.get("relevant_accounts", {})

        # Build list of (handle, user_id) tuples for validated accounts
        # Support both old format {handle: bool} and new format {handle: {"user_id": ..., "validated": ...}}
        relevant_accounts = []
        for handle, data in accounts_dict.items():
            if isinstance(data, dict):
                # New format: {"user_id": str | None, "validated": bool}
                if data.get("validated", False):
                    user_id = data.get("user_id")
                    relevant_accounts.append((handle, user_id))
            elif data:
                # Old format: boolean (True means validated)
                relevant_accounts.append((handle, None))

        # Parse queries and build summary map
        stored_queries = user_info.get("queries", []) if user_info else []
        queries = []
        query_summary_map = {}
        for q in stored_queries:
            if isinstance(q, list) and len(q) == 2:
                # New format: [query, summary]
                queries.append(q[0])
                query_summary_map[q[0]] = q[1]
            elif isinstance(q, str):
                # Legacy format: just query string
                queries.append(q)
                query_summary_map[q] = q  # Use query itself as fallback

        ideal_num_posts = user_settings.get("ideal_num_posts", 30)

        # Determine filter
        manual_override = user_settings.get("manual_minimum_impressions")
        auto_filter = user_settings.get("min_impressions_filter", 2000)
        min_impressions_filter = manual_override if manual_override is not None else auto_filter

        if manual_override is not None:
            notify(f"🔒 [Job 1] Using manual impressions filter: {manual_override}")
        else:
            notify(f"⚙️ [Job 1] Using auto impressions filter: {auto_filter}")

        # Cleanup old data
        notify(f"🗑️ [Job 1] Cleaning up old tweets and seen_tweets...")
        await cleanup_old_tweets(username)
        cleanup_seen_tweets(username)

        # =======================================================================
        # PHASE 1: LIGHTWEIGHT DISCOVERY (Queries + Home Timeline)
        # =======================================================================
        notify(f"🔍 [Phase 1] Discovering tweets from {len(queries)} queries and home timeline...")
        _update_job_status(username, "find_and_reply_to_new_posts", "running", "Phase 1: Discovery")

        discovered_tweets = []  # List of {id, impressions, source, raw_tweet}
        all_search_stats = []  # Collect stats from each search for structured logging

        # 1A. Queries
        for query in queries:
            try:
                raw_tweets, stats = await fetch_search_raw(query, username, min_impressions_filter)

                # Track tweets from this query for selection counting
                query_tweet_ids = []
                for tweet_id, tweet in raw_tweets.items():
                    # Check intent
                    if await check_tweet_matches_intent_initial(tweet, username):
                        summary = query_summary_map.get(query, query)
                        discovered_tweets.append({
                            'id': tweet_id,
                            'impressions': tweet.get('impressions', 0),
                            'source': {'type': 'query', 'value': query, 'summary': summary},
                            'raw_tweet': tweet
                        })
                        query_tweet_ids.append(tweet_id)

                # Store stats with tweet IDs for later selection counting
                all_search_stats.append((stats, query_summary_map.get(query, query), query_tweet_ids))
            except Exception as e:
                notify(f"⚠️ Error fetching query [{query}]: {e}")
                results["errors"].append(f"Query {query}: {e}")

        # 1B. Home Timeline
        if is_premium:  # Only scrape home timeline for premium users
            try:
                home_tweets, stats = await fetch_home_timeline_raw(username, ideal_num_posts, min_impressions_filter)

                home_tweet_ids = []
                for tweet_id, tweet in home_tweets.items():
                    # Check intent
                    if await check_tweet_matches_intent_initial(tweet, username):
                        discovered_tweets.append({
                            'id': tweet_id,
                            'impressions': tweet.get('impressions', 0),
                            'source': {'type': 'home_timeline', 'value': 'following'},
                            'raw_tweet': tweet
                        })
                        home_tweet_ids.append(tweet_id)

                # Store stats with tweet IDs
                all_search_stats.append((stats, "Home Timeline", home_tweet_ids))
            except Exception as e:
                notify(f"⚠️ Error fetching home timeline: {e}")
                results["errors"].append(f"Home timeline: {e}")

        results["tweets_discovered"] = len(discovered_tweets)
        notify(f"✅ [Phase 1] Discovered {len(discovered_tweets)} tweets from queries/home")

        # =======================================================================
        # PHASE 2: SELECT TOP N BY IMPRESSIONS
        # =======================================================================
        notify(f"📊 [Phase 2] Selecting top {ideal_num_posts} tweets by impressions...")
        _update_job_status(username, "find_and_reply_to_new_posts", "running", "Phase 2: Selection")

        discovered_tweets.sort(key=lambda t: t['impressions'], reverse=True)
        selected_discovery = discovered_tweets[:ideal_num_posts]

        # Count how many tweets from each source were selected
        selected_tweet_ids = {t['id'] for t in selected_discovery}
        for i, (stats, label, tweet_ids) in enumerate(all_search_stats):
            selection_count = sum(1 for tid in tweet_ids if tid in selected_tweet_ids)
            # Update the tuple with selection count
            all_search_stats[i] = (stats, label, tweet_ids, selection_count)

        results["discovery_tweets_selected"] = len(selected_discovery)
        notify(f"✅ [Phase 2] Selected {len(selected_discovery)} tweets (from {len(discovered_tweets)} discovered)")

        # =======================================================================
        # PHASE 3: LIGHTWEIGHT USER TIMELINES (No Impressions Filter)
        # =======================================================================
        notify(f"👥 [Phase 3] Fetching tweets from {len(relevant_accounts)} user timelines...")
        _update_job_status(username, "find_and_reply_to_new_posts", "running", "Phase 3: User timelines")

        account_tweets_list = []  # List of {id, source, raw_tweet}

        for account_handle, account_user_id in relevant_accounts:
            try:
                raw_tweets, stats = await fetch_user_timeline_raw(username, account_handle, ideal_num_posts, user_id=account_user_id)

                account_tweet_ids = []
                for tweet_id, tweet in raw_tweets.items():
                    # Check intent
                    if await check_tweet_matches_intent_initial(tweet, username):
                        account_tweets_list.append({
                            'id': tweet_id,
                            'source': {'type': 'account', 'value': account_handle},
                            'raw_tweet': tweet
                        })
                        account_tweet_ids.append(tweet_id)

                # Store stats (all account tweets are selected, no impressions filter)
                all_search_stats.append((stats, f"@{account_handle}", account_tweet_ids, len(account_tweet_ids)))
            except Exception as e:
                notify(f"⚠️ Error fetching timeline for @{account_handle}: {e}")
                results["errors"].append(f"Account {account_handle}: {e}")

        results["account_tweets"] = len(account_tweets_list)
        notify(f"✅ [Phase 3] Found {len(account_tweets_list)} tweets from user timelines")

        # =======================================================================
        # PHASE 4: COMBINE AND FETCH THREADS INCREMENTALLY
        # =======================================================================
        final_tweets_list = selected_discovery + account_tweets_list
        total_to_fetch = len(final_tweets_list)

        notify(f"🧵 [Phase 4] Fetching threads for {total_to_fetch} tweets and writing to cache...")

        tweets_written = 0
        threads_fetched = 0

        for idx, item in enumerate(final_tweets_list, 1):
            try:
                tweet = item['raw_tweet']
                source = item['source']

                # Update progress
                _update_job_status(
                    username, "find_and_reply_to_new_posts", "running",
                    f"Phase 4: Fetching threads ({idx}/{total_to_fetch})",
                    progress={"current": idx, "total": total_to_fetch}
                )

                # Fetch thread data (expensive operation)
                populated = await populate_thread_for_tweet(tweet)

                if populated:
                    threads_fetched += 1
                    # Add source metadata
                    populated['scraped_from'] = source

                    # Write to cache IMMEDIATELY
                    await write_to_cache(
                        [populated],
                        f"Tweet from {source['type']}: {source['value'][:30]}",
                        username=username
                    )
                    tweets_written += 1

                    # Trigger reply generation in background
                    if is_premium:
                        asyncio.create_task(
                            _generate_replies_for_tweet_background(populated, username, user_settings)
                        )
                        results["replies_generating"] += 1

            except Exception as e:
                notify(f"⚠️ Failed to process tweet {item['id']}: {e}")
                results["errors"].append(f"Tweet {item['id']}: {e}")

        notify(f"✅ [Phase 4] Wrote {tweets_written} tweets with {threads_fetched} threads")

        results["tweets_scraped"] = tweets_written
        results["threads_fetched"] = threads_fetched

        # Update scrolling time saved
        end_time = time.time()
        duration = int(end_time - start_time)
        if user_info:
            user_info["scrolling_time_saved"] = user_info.get("scrolling_time_saved", 0) + duration
            write_user_info(user_info)

        results["duration_seconds"] = duration

        # Build structured logging results
        from backend.twitter.logging import NewPostDiscoveryResults

        per_search_results = []
        for stats, label, tweet_ids, selection_count in all_search_stats:
            # Count threads and replies for this source
            # Note: For now we can't easily track threads/replies per source without more refactoring
            # Set to 0 for initial implementation
            search_result = stats.to_search_results(
                source_label=label,
                discovery_tweets_selected=selection_count,
                threads_fetched=0,  # TODO: Track per-source
                replies_generated=0  # TODO: Track per-source
            )
            per_search_results.append(search_result)

        structured_results = NewPostDiscoveryResults(
            total_tweets_found=sum(sr.tweets_found for sr in per_search_results),
            per_search_results=per_search_results
        )

        _update_job_status(
            username, "find_and_reply_to_new_posts", "complete", "complete",
            results=results
        )

        # Print completion log
        summary = f"{results['tweets_scraped']} tweets, {results['replies_generating']} replies"
        print_job_complete("find_and_reply_to_new_posts", username, triggered_by, summary, duration)
        log_job_complete(username, "find_and_reply_to_new_posts", triggered_by, initiated_time, structured_results)
        notify(f"✅ [Job 1] Complete: {summary}")

        # Reset to idle after delay
        asyncio.create_task(_reset_job_to_idle(username, "find_and_reply_to_new_posts"))

    except Exception as e:
        duration = int(time.time() - start_time)

        # Build empty structured results for error case
        from backend.twitter.logging import NewPostDiscoveryResults, SearchResults

        empty_structured_results = NewPostDiscoveryResults(
            total_tweets_found=0,
            per_search_results=[]
        )

        log_job_error(username, "find_and_reply_to_new_posts", triggered_by, initiated_time, str(e), empty_structured_results)
        error(f"find_and_reply_to_new_posts failed: {e}", status_code=500, function_name="find_and_reply_to_new_posts", username=username, critical=False)
        results["errors"].append(str(e))
        _update_job_status(
            username, "find_and_reply_to_new_posts", "error", "error",
            results=results, error_msg=str(e)
        )

    return results


async def _generate_replies_for_tweet_background(tweet: dict, username: str, user_settings: dict):
    """
    Background task to generate replies for a single tweet.
    Runs in parallel with scraping for optimal performance.
    """
    try:
        from backend.twitter.generate_replies import generate_replies_for_tweet

        # Generate replies using the configured models and number_of_generations
        number_of_generations = user_settings.get("number_of_generations", 1)
        models = user_settings.get("models", ["claude-3-5-sonnet-20241022"])

        await generate_replies_for_tweet(
            tweet=tweet,
            username=username,
            number_of_generations=number_of_generations,
            models=models
        )

    except Exception as e:
        notify(f"⚠️ [Background] Error generating replies for tweet: {e}")



async def find_and_reply_to_new_posts_with_retry(username: str, triggered_by: str = "manual") -> dict:
    """
    Wrapper for find_and_reply_to_new_posts that retries with reduced impressions filter if not enough tweets are found.

    Retry logic:
    - Target: At least ideal_num_posts - 10 tweets
    - If fewer tweets, clear seen_tweets and halve the impressions filter
    - If more tweets, that's fine - show them all (better to have more content)
    - Retry until we have enough tweets or filter reaches minimum of 100
    - If manual_minimum_impressions is set, skip retry logic entirely

    Args:
        username: The user to run the job for
        triggered_by: "user" for manual trigger, "scheduler" for background scheduler

    Returns:
        Results dict from the final attempt
    """
    from backend.twitter.logging import log_filter_adjustment
    from backend.user.user import read_user_settings, write_user_settings
    from backend.utlils.utils import read_user_info

    # Get user settings first to check for manual override
    user_settings = read_user_settings(username)
    if not user_settings:
        notify(f"⚠️ [Job 1] Cannot proceed: No user settings found")
        return {"tweets_scraped": 0, "tweets_filtered": 0, "replies_generating": 0, "errors": ["No user settings"]}

    # Check if user has set manual override - if so, skip retry logic
    manual_override = user_settings.get("manual_minimum_impressions")
    if manual_override is not None:
        notify(f"🔒 [Job 1] Manual impressions filter set ({manual_override}) - skipping auto-adjustment")
        # Run job once without retry logic
        return await find_and_reply_to_new_posts(username, triggered_by)

    # Normal retry logic with auto-adjustment
    MIN_FILTER_THRESHOLD = 100
    attempt = 1
    max_attempts = 10  # Safety limit to prevent infinite loops

    while attempt <= max_attempts:
        notify(f"🔄 [Job 1 Attempt {attempt}] Starting find_and_reply_to_new_posts for {username}")

        # Get ideal_num_posts for this user
        user_settings = read_user_settings(username)
        if not user_settings:
            notify(f"⚠️ [Job 1] Cannot proceed: No user settings found")
            return {"tweets_scraped": 0, "tweets_filtered": 0, "replies_generating": 0, "errors": ["No user settings"]}

        ideal_num_posts = user_settings.get("ideal_num_posts", 30)
        min_target = ideal_num_posts - 10

        # Run the job
        results = await find_and_reply_to_new_posts(username, triggered_by)

        tweets_found = results.get("tweets_scraped", 0)
        notify(f"📊 [Job 1 Attempt {attempt}] Found {tweets_found} tweets (target: at least {min_target})")

        # Check if we have enough tweets (no maximum - more is better!)
        if tweets_found >= min_target:
            notify(f"✅ [Job 1] Success: Found {tweets_found} tweets (target: at least {min_target})")
            return results

        # Too few tweets - need to retry with reduced filter
        current_filter = user_settings.get("min_impressions_filter", 2000)

        # Check if we can reduce the filter further
        if current_filter <= MIN_FILTER_THRESHOLD:
            notify(f"⚠️ [Job 1] Cannot retry: Impressions filter already at minimum ({current_filter} <= {MIN_FILTER_THRESHOLD})")
            notify(f"📊 [Job 1] Final result: {tweets_found} tweets found (target: at least {min_target})")
            return results

        # Prepare for retry: clear seen tweets and reduce filter
        new_filter = max(current_filter // 2, MIN_FILTER_THRESHOLD)
        notify(f"🔄 [Job 1] Retrying: Reducing impressions filter from {current_filter} to {new_filter}")

        # Log to user's log file
        log_filter_adjustment(username, current_filter, new_filter, tweets_found)

        # Clear seen tweets
        notify(f"🧹 [Job 1] Clearing seen_tweets for {username}")
        user_info = read_user_info(username)
        if user_info:
            user_info["seen_tweets"] = {}
            from backend.utlils.utils import write_user_info
            write_user_info(user_info)

        # Update the impressions filter
        write_user_settings(username, min_impressions_filter=new_filter)
        notify(f"✅ [Job 1] Updated min_impressions_filter to {new_filter}")

        attempt += 1

        # Small delay before retry to avoid rate limits
        await asyncio.sleep(2)

    notify(f"⚠️ [Job 1] Max attempts ({max_attempts}) reached")
    return results


# =============================================================================
# Job 2: Find User Activity
# =============================================================================

async def find_user_activity(username: str, max_tweets: int = 50, triggered_by: str = "manual") -> dict:
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
    initiated_time = datetime.now(UTC)
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

        # Build structured logging results
        from backend.twitter.logging import UserActivityResults

        recently_posted = results["discover_recently_posted"]
        resurrected = results["discover_resurrected"]

        structured_results = UserActivityResults(
            total_discovered=results["total_discovered"],
            recently_posted=recently_posted.get("discovered_tweets", 0),
            resurrected=resurrected.get("resurrected_tweets", 0),
            original_posts=recently_posted.get("original_posts", 0),
            replies=recently_posted.get("replies", 0),
            comment_backs=recently_posted.get("comment_backs", 0),
            new_comments=results["total_comments"],
            new_quote_tweets=results["total_quote_tweets"]
        )

        _update_job_status(
            username, "find_user_activity", "complete", "complete",
            results=results
        )

        # Print completion log
        summary = f"{results['total_discovered']} discovered, {results['total_comments']} comments"
        print_job_complete("find_user_activity", username, triggered_by, summary, duration)
        log_job_complete(username, "find_user_activity", triggered_by, initiated_time, structured_results)
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
        duration = int(time.time() - start_time)

        # Build empty structured results for error case
        from backend.twitter.logging import UserActivityResults

        empty_structured_results = UserActivityResults(
            total_discovered=0,
            recently_posted=0,
            resurrected=0,
            original_posts=0,
            replies=0,
            comment_backs=0,
            new_comments=0,
            new_quote_tweets=0
        )

        log_job_error(username, "find_user_activity", triggered_by, initiated_time, str(e), empty_structured_results)
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

        # If models not configured, use None to trigger Gemini
        models = user_info.get("models", [None]) if user_info.get("models") else [None]
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


async def find_and_reply_to_engagement(username: str, triggered_by: str = "manual") -> dict:
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

    from backend.browser_automation.twitter.api import deep_scrape_thread, shallow_scrape_thread
    from backend.data.twitter.comments_cache import get_comment, get_thread_context, process_scraped_quote_tweets, process_scraped_replies
    from backend.data.twitter.posted_tweets_cache import get_tweets_by_monitoring_state, read_posted_tweets_cache, write_posted_tweets_cache
    from backend.twitter.monitoring import _determine_monitoring_state, _should_promote_to_active

    start_time = time.time()
    initiated_time = datetime.now(UTC)
    print_job_start("find_and_reply_to_engagement", username, triggered_by)
    _update_job_status(username, "find_and_reply_to_engagement", "running", "starting", triggered_by=triggered_by)
    notify(f"🚀 [Job 3] Starting find_and_reply_to_engagement for {username}")

    user_info = read_user_info(username)
    if not user_info:
        raise HTTPException(status_code=404, detail="User not found")

    user_handle = user_info.get("handle", username)

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
                scrape_result = await shallow_scrape_thread(None, url, tweet_id)
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
                scrape_result = await deep_scrape_thread(None, url, tweet_id, user_handle)
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

        # Build structured logging results
        from backend.twitter.logging import EngagementDiscoveryResults

        structured_results = EngagementDiscoveryResults(
            active_tweets_scraped=results["active_scraped"],
            warm_tweets_scraped=results["warm_scraped"],
            tweets_promoted=results["promoted_to_active"],
            new_comments=results["new_comments"],
            new_quote_tweets=results["new_quote_tweets"],
            comment_backs_generated=results["replies_generating"]
        )

        _update_job_status(
            username, "find_and_reply_to_engagement", "complete", "complete",
            results=results
        )

        # Print completion log
        summary = f"{results['active_scraped']} deep, {results['warm_scraped']} shallow, {results['new_comments']} comments"
        print_job_complete("find_and_reply_to_engagement", username, triggered_by, summary, duration)
        log_job_complete(username, "find_and_reply_to_engagement", triggered_by, initiated_time, structured_results)
        notify(f"✅ [Job 3] Complete: {results['active_scraped']} deep, {results['warm_scraped']} shallow, {results['new_comments']} comments, {results['new_quote_tweets']} QTs, {results['replies_generating']} replies generating")

        # Reset to idle after delay
        asyncio.create_task(_reset_job_to_idle(username, "find_and_reply_to_engagement"))

    except Exception as e:
        duration = int(time.time() - start_time)

        # Build empty structured results for error case
        from backend.twitter.logging import EngagementDiscoveryResults

        empty_structured_results = EngagementDiscoveryResults(
            active_tweets_scraped=0,
            warm_tweets_scraped=0,
            tweets_promoted=0,
            new_comments=0,
            new_quote_tweets=0,
            comment_backs_generated=0
        )

        log_job_error(username, "find_and_reply_to_engagement", triggered_by, initiated_time, str(e), empty_structured_results)
        error(f"find_and_reply_to_engagement failed: {e}", status_code=500, function_name="find_and_reply_to_engagement", username=username, critical=False)
        results["errors"].append(str(e))
        _update_job_status(
            username, "find_and_reply_to_engagement", "error", "error",
            results=results, error_msg=str(e)
        )

    return results


# =============================================================================
# API Endpoints
# =============================================================================

@router.post("/{username}/find-and-reply-to-new-posts")
async def start_find_and_reply_to_new_posts(
    username: str,
    triggered_by: str = "manual"
) -> dict:
    """
    Start Job 1: Find and reply to new posts.

    Scrapes tweets from configured accounts/queries and generates AI replies
    in parallel as tweets are discovered.

    Uses retry logic: if < 7 tweets are found, clears seen_tweets and halves
    the impressions filter, then retries (min filter: 100).

    Uses asyncio.create_task() for true parallel execution with other background jobs.

    Args:
        triggered_by: "user" for manual trigger, "scheduler" for background scheduler
    """
    user_info = read_user_info(username)
    if not user_info:
        raise HTTPException(status_code=404, detail="User not found")

    asyncio.create_task(_run_job_with_error_handling(
        find_and_reply_to_new_posts_with_retry(username, triggered_by),
        "find_and_reply_to_new_posts", username
    ))

    return {
        "message": "Job started: find_and_reply_to_new_posts",
        "username": username,
        "status": "running",
        "triggered_by": triggered_by
    }


@router.post("/{username}/find-user-activity")
async def start_find_user_activity(
    username: str,
    max_tweets: int = 50,
    triggered_by: str = "manual"
) -> dict:
    """
    Start Job 2: Find user activity.

    Discovers user's external posts and resurrects cold tweets.
    Runs discover_recently_posted and discover_resurrected in parallel.

    Uses asyncio.create_task() for true parallel execution with other background jobs.

    Args:
        triggered_by: "user" for manual trigger, "scheduler" for background scheduler
    """
    user_info = read_user_info(username)
    if not user_info:
        raise HTTPException(status_code=404, detail="User not found")

    asyncio.create_task(_run_job_with_error_handling(
        find_user_activity(username, max_tweets, triggered_by),
        "find_user_activity", username
    ))

    return {
        "message": "Job started: find_user_activity",
        "username": username,
        "status": "running",
        "triggered_by": triggered_by
    }


@router.post("/{username}/find-and-reply-to-engagement")
async def start_find_and_reply_to_engagement(
    username: str,
    triggered_by: str = "manual"
) -> dict:
    """
    Start Job 3: Find and reply to engagement.

    Monitors engagement on posted tweets and generates comment replies
    in parallel as comments are discovered.

    Order: Shallow scrape warm first, then deep scrape active (including promoted).

    Uses asyncio.create_task() for true parallel execution with other background jobs.

    Args:
        triggered_by: "user" for manual trigger, "scheduler" for background scheduler
    """
    user_info = read_user_info(username)
    if not user_info:
        raise HTTPException(status_code=404, detail="User not found")

    asyncio.create_task(_run_job_with_error_handling(
        find_and_reply_to_engagement(username, triggered_by),
        "find_and_reply_to_engagement", username
    ))

    return {
        "message": "Job started: find_and_reply_to_engagement",
        "username": username,
        "status": "running",
        "triggered_by": triggered_by
    }


async def analyze(username: str, triggered_by: str = "manual") -> dict:
    """
    Job 4: Analyze user's posting history and preferences.

    Analyzes logs to determine:
    - Which model the user prefers (based on posted tweets)
    - Which prompt variant the user prefers
    - Lifetime metrics (follows, posts, scrolling time saved)

    Args:
        username: The user to run the job for
        triggered_by: "user" for manual trigger, "scheduler" for background scheduler

    Returns:
        Analysis dict with model/prompt preferences and metrics
    """
    import time
    from collections import Counter

    from backend.twitter.logging import TweetAction, read_user_log
    from backend.utlils.utils import write_user_info

    start_time = time.time()
    initiated_time = datetime.now(UTC)
    print_job_start("analyze", username, triggered_by)
    _update_job_status(username, "analyze", "running", "analyzing", triggered_by=triggered_by)
    notify(f"🚀 [Job 4] Starting analyze for {username}")

    user_info = read_user_info(username)
    if not user_info:
        _update_job_status(username, "analyze", "error", "user_not_found", triggered_by=triggered_by)
        return {"error": "User not found"}

    # Read all log entries
    all_logs = read_user_log(username)

    # Filter to only POSTED actions (both tweet replies and comment replies)
    posted_logs = [
        log for log in all_logs
        if log.get("action") in [TweetAction.POSTED.value, TweetAction.COMMENT_REPLY_POSTED.value]
    ]

    # Count model and prompt variant usage
    model_counter: Counter = Counter()
    prompt_counter: Counter = Counter()

    for log in posted_logs:
        metadata = log.get("metadata", {})
        model = metadata.get("model")
        prompt_variant = metadata.get("prompt_variant")

        if model and model != "unknown":
            model_counter[model] += 1
        if prompt_variant and prompt_variant != "unknown":
            prompt_counter[prompt_variant] += 1

    # Calculate percentages
    total_models = sum(model_counter.values())
    total_prompts = sum(prompt_counter.values())

    model_percentages = {}
    if total_models > 0:
        for model, count in model_counter.items():
            model_percentages[model] = round((count / total_models) * 100)

    prompt_percentages = {}
    if total_prompts > 0:
        for prompt, count in prompt_counter.items():
            prompt_percentages[prompt] = round((count / total_prompts) * 100)

    # Build analysis dict for user_info
    analysis = {
        "model": model_percentages,
        "prompt": prompt_percentages,
        "lifetime_new_follows": user_info.get("lifetime_new_follows", 0),
        "lifetime_posts": user_info.get("lifetime_posts", 0),
        "scrolling_time_saved": user_info.get("scrolling_time_saved", 0),
        "total_posted_analyzed": len(posted_logs),
        "last_analyzed": datetime.now(UTC).isoformat(),
    }

    # Store in user_info
    user_info["analysis"] = analysis
    write_user_info(user_info)

    # Build structured logging results
    from backend.twitter.logging import AnalysisResults

    structured_results = AnalysisResults(
        posts_analyzed=len(posted_logs),
        model_preferences=model_percentages,
        prompt_preferences=prompt_percentages,
        metrics_updated=["lifetime_posts", "lifetime_new_follows", "scrolling_time_saved"]
    )

    _update_job_status(username, "analyze", "complete", "done", triggered_by=triggered_by)
    duration = int(time.time() - start_time)
    summary = f"{len(posted_logs)} posts analyzed"
    print_job_complete("analyze", username, triggered_by, summary, duration)
    log_job_complete(username, "analyze", triggered_by, initiated_time, structured_results)
    notify(f"✅ [Job 4] Analysis complete for {username}: {len(posted_logs)} posts analyzed")

    return analysis


@router.post("/{username}/analyze")
async def start_analyze(
    username: str,
    triggered_by: str = "manual"
) -> dict:
    """
    Start Job 4: Analyze user preferences.

    Analyzes user's posting history to determine model and prompt preferences.

    Uses asyncio.create_task() for true parallel execution with other background jobs.

    Args:
        triggered_by: "user" for manual trigger, "scheduler" for background scheduler
    """
    user_info = read_user_info(username)
    if not user_info:
        raise HTTPException(status_code=404, detail="User not found")

    asyncio.create_task(_run_job_with_error_handling(
        analyze(username, triggered_by),
        "analyze", username
    ))

    return {
        "message": "Job started: analyze",
        "username": username,
        "status": "running",
        "triggered_by": triggered_by
    }


@router.post("/{username}/run-background-jobs")
async def run_all_background_jobs(
    username: str,
    triggered_by: str = "manual"
) -> dict:
    """
    Run all 4 background jobs for a user in parallel.

    Jobs triggered:
    1. find_and_reply_to_new_posts - Scrape tweets and generate replies
    2. find_user_activity - Discover external posts and resurrect cold tweets
    3. find_and_reply_to_engagement - Monitor engagement and generate comment replies
    4. analyze - Analyze user preferences and update metrics

    All jobs run in parallel using asyncio.create_task().

    Args:
        username: The user to run jobs for
        triggered_by: "user" for manual trigger, "scheduler" for background scheduler
    """
    user_info = read_user_info(username)
    if not user_info:
        raise HTTPException(status_code=404, detail="User not found")

    # Launch all 4 jobs in parallel
    asyncio.create_task(_run_job_with_error_handling(
        find_and_reply_to_new_posts_with_retry(username, triggered_by),
        "find_and_reply_to_new_posts", username
    ))
    asyncio.create_task(_run_job_with_error_handling(
        find_user_activity(username, triggered_by=triggered_by),
        "find_user_activity", username
    ))
    asyncio.create_task(_run_job_with_error_handling(
        find_and_reply_to_engagement(username, triggered_by),
        "find_and_reply_to_engagement", username
    ))
    asyncio.create_task(_run_job_with_error_handling(
        analyze(username, triggered_by),
        "analyze", username
    ))

    return {
        "message": "All background jobs started",
        "username": username,
        "jobs": [
            "find_and_reply_to_new_posts",
            "find_user_activity",
            "find_and_reply_to_engagement",
            "analyze"
        ],
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
    valid_jobs = ["find_and_reply_to_new_posts", "find_user_activity", "find_and_reply_to_engagement", "analyze"]
    if job_name not in valid_jobs:
        raise HTTPException(status_code=400, detail=f"Invalid job name. Must be one of: {valid_jobs}")

    return get_job_status(username, job_name)
