"""
Background scheduler for automatic tweet scraping and reply generation.

This module sets up scheduled tasks to:
- Scrape tweets from configured accounts/queries for all active users
- Generate AI replies for newly scraped tweets
- Clean up tweets older than 3 days
- Run engagement monitoring to discover comments on posted tweets
- Run at configurable intervals (default: every 24 hours for scraping, every 6 hours for engagement)
"""

import json

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import APIRouter

from backend.utlils.utils import BROWSER_STATE_FILE, cookie_still_valid, notify

# Default intervals
DEFAULT_SCRAPE_INTERVAL_HOURS = 24
DEFAULT_ENGAGEMENT_INTERVAL_HOURS = 6

# Global scheduler instance
scheduler = AsyncIOScheduler()
# API Router

router = APIRouter(prefix="/scheduler", tags=["scheduler"])


async def cleanup_expired_browser_sessions():
    """
    Cleanup expired browser sessions to prevent zombie processes.
    This helps prevent resource leaks from browser sessions that weren't properly closed.
    """
    try:
        from backend.browser_management.sessions import cleanup_expired_sessions
        await cleanup_expired_sessions()
        notify("🧹 Cleaned up expired browser sessions")
    except Exception as e:
        from backend.utlils.utils import error
        error("Failed to cleanup browser sessions", status_code=500, exception_text=str(e), function_name="cleanup_expired_browser_sessions")
        notify(f"⚠️ Failed to cleanup browser sessions: {e}")


def get_users_with_valid_sessions() -> list[str]:
    """
    Get list of users who have valid OAuth tokens.

    Browser sessions are optional and checked separately when needed for scraping.
    This function checks OAuth tokens as the primary authentication mechanism.

    Returns:
        list[str]: List of usernames with valid OAuth tokens
    """
    from backend.utlils.utils import read_tokens

    try:
        tokens = read_tokens()

        if not tokens:
            notify("⚠️ No OAuth tokens found")
            return []

        # Return all users who have OAuth tokens
        # Token refresh/validation happens when jobs actually run
        valid_users = list(tokens.keys())
        return valid_users

    except Exception as e:
        from backend.utlils.utils import error
        error("Error reading OAuth tokens", status_code=500, exception_text=str(e), function_name="get_users_with_valid_sessions")
        notify(f"❌ Error reading OAuth tokens: {e}")
        return []


def get_users_with_valid_browser_sessions() -> list[str]:
    """
    Get list of users who have valid browser sessions (for scraping).

    This is separate from OAuth - browser sessions are only needed for
    Playwright-based scraping, not for API calls.

    Returns:
        list[str]: List of usernames with valid browser sessions
    """
    if not BROWSER_STATE_FILE.exists():
        return []

    try:
        with open(BROWSER_STATE_FILE) as f:
            browser_states = json.load(f)

        if not isinstance(browser_states, dict):
            return []

        valid_users = []
        for username, state in browser_states.items():
            if cookie_still_valid(state):
                valid_users.append(username)

        return valid_users

    except Exception:
        return []


async def run_all_jobs_for_user(username: str):
    """
    Run all background jobs for a single user (called by scheduler).

    Jobs run in sequence:
    1. find_and_reply_to_new_posts - Discover new posts and generate replies
    2. find_user_activity - Discover user's external posts and resurrect cold tweets
    3. find_and_reply_to_engagement - Monitor engagement and generate comment replies
    4. analyze - Analyze posting history and update preferences

    Args:
        username: Twitter handle of the user
    """
    from backend.twitter.twitter_jobs import (
        find_and_reply_to_new_posts,
        find_user_activity,
        find_and_reply_to_engagement,
        analyze
    )

    try:
        notify(f"🤖 [Scheduler] Starting all jobs for user: {username}")

        # Step 0: Cleanup expired browser sessions to prevent resource leaks
        await cleanup_expired_browser_sessions()

        # Job 1: Find and reply to new posts
        try:
            await find_and_reply_to_new_posts(username, triggered_by="scheduled")
        except Exception as e:
            from backend.utlils.utils import error
            error(f"Job 1 failed for {username}", status_code=500, exception_text=str(e), function_name="run_all_jobs_for_user", username=username)
            notify(f"❌ [Scheduler] Job 1 (find_and_reply_to_new_posts) failed for {username}: {e}")

        # Job 2: Find user activity
        try:
            await find_user_activity(username, triggered_by="scheduled")
        except Exception as e:
            from backend.utlils.utils import error
            error(f"Job 2 failed for {username}", status_code=500, exception_text=str(e), function_name="run_all_jobs_for_user", username=username)
            notify(f"❌ [Scheduler] Job 2 (find_user_activity) failed for {username}: {e}")

        # Job 3: Find and reply to engagement
        try:
            await find_and_reply_to_engagement(username, triggered_by="scheduled")
        except Exception as e:
            from backend.utlils.utils import error
            error(f"Job 3 failed for {username}", status_code=500, exception_text=str(e), function_name="run_all_jobs_for_user", username=username)
            notify(f"❌ [Scheduler] Job 3 (find_and_reply_to_engagement) failed for {username}: {e}")

        # Job 4: Analyze
        try:
            await analyze(username, triggered_by="scheduled")
        except Exception as e:
            from backend.utlils.utils import error
            error(f"Job 4 failed for {username}", status_code=500, exception_text=str(e), function_name="run_all_jobs_for_user", username=username)
            notify(f"❌ [Scheduler] Job 4 (analyze) failed for {username}: {e}")

        notify(f"🎉 [Scheduler] Completed all jobs for {username}")

    except Exception as e:
        from backend.utlils.utils import error
        error(f"Scheduler jobs failed for {username}", status_code=500, exception_text=str(e), function_name="run_all_jobs_for_user", username=username)
        notify(f"❌ [Scheduler] Failed for {username}: {e}")


async def run_all_jobs_all_users():
    """
    Run all background jobs for all users with valid OAuth sessions.
    This is the main job function called by the scheduler.

    Runs all 4 jobs in sequence for each user:
    1. find_and_reply_to_new_posts
    2. find_user_activity
    3. find_and_reply_to_engagement
    4. analyze

    Auth exceptions (OAuthTokenExpired, BrowserSessionExpired) are caught per-user
    to gracefully stop processing for that user without affecting others.
    """
    from backend.utlils.utils import AuthenticationError

    notify("🚀 [Scheduler] Starting all background jobs for all users...")

    try:
        # Get only users with valid OAuth sessions
        users = get_users_with_valid_sessions()

        if not users:
            notify("⚠️ [Scheduler] No users with valid OAuth sessions found")
            return

        notify(f"👥 [Scheduler] Found {len(users)} user(s) with valid sessions: {', '.join(users)}")

        # Process each user
        for username in users:
            try:
                await run_all_jobs_for_user(username)
            except AuthenticationError as auth_err:
                # Auth failed mid-job - stop processing this user, continue with others
                notify(f"🔐 [Scheduler] Auth expired for {username}, stopping job: {auth_err}")
                continue
            except Exception as e:
                from backend.utlils.utils import error
                error("Error processing scheduled jobs", status_code=500, exception_text=str(e), function_name="run_all_jobs_all_users", username=username)
                notify(f"❌ [Scheduler] Error processing {username}: {e}")
                continue

        notify(f"✅ [Scheduler] Completed all jobs for {len(users)} user(s)")

    except Exception as e:
        from backend.utlils.utils import error
        error("Fatal error in scheduled jobs", status_code=500, exception_text=str(e), function_name="run_all_jobs_all_users")
        notify(f"❌ [Scheduler] Fatal error in scheduled jobs: {e}")


def start_scheduler(
    scrape_interval_hours: int = DEFAULT_SCRAPE_INTERVAL_HOURS,
    engagement_interval_hours: int = DEFAULT_ENGAGEMENT_INTERVAL_HOURS
):
    """
    Start the background scheduler with specified intervals.

    All 4 jobs now run together as a single scheduled task:
    - find_and_reply_to_new_posts
    - find_user_activity
    - find_and_reply_to_engagement
    - analyze

    Args:
        scrape_interval_hours: Hours between background job runs (default: 24)
        engagement_interval_hours: [DEPRECATED] Kept for backward compatibility, not used
    """
    if scheduler.running:
        notify("⚠️ Scheduler is already running")
        return

    # Add the main job that runs all 4 centralized jobs
    scheduler.add_job(
        run_all_jobs_all_users,
        trigger=IntervalTrigger(hours=scrape_interval_hours),
        id='run_all_jobs_all_users',
        name=f'Run all background jobs every {scrape_interval_hours} hours',
        replace_existing=True,
        max_instances=1  # Prevent overlapping runs
    )

    # Add browser session cleanup job (runs every hour to prevent zombie processes)
    scheduler.add_job(
        cleanup_expired_browser_sessions,
        trigger=IntervalTrigger(hours=1),
        id='cleanup_browser_sessions',
        name='Cleanup expired browser sessions every hour',
        replace_existing=True,
        max_instances=1
    )

    scheduler.start()
    notify(f"✅ Background scheduler started (all jobs run every {scrape_interval_hours}h)")
    notify("🧹 Browser session cleanup scheduled every hour")

    jobs = scheduler.get_jobs()
    for job in jobs:
        notify(f"📅 {job.name}: next run at {job.next_run_time}")


def stop_scheduler():
    """Stop the background scheduler."""
    if scheduler.running:
        scheduler.shutdown()
        notify("🛑 Background scheduler stopped")
    else:
        notify("⚠️ Scheduler is not running")


def get_scheduler_status():
    """
    Get current status of the scheduler.

    Returns:
        dict: Status information including running state, jobs, and next run time
    """
    if not scheduler.running:
        return {"running": False, "jobs": []}

    jobs = scheduler.get_jobs()
    job_info = []

    for job in jobs:
        job_info.append({"id": job.id, "name": job.name, "next_run": str(job.next_run_time) if job.next_run_time else None, "trigger": str(job.trigger)})

    return {"running": True, "jobs": job_info}


def trigger_manual_jobs():
    """
    Manually trigger all background jobs for all users (doesn't wait for scheduled time).
    Returns immediately, runs in background.
    """
    if not scheduler.running:
        notify("⚠️ Scheduler is not running, cannot trigger manual jobs")
        return False

    # Schedule the job to run immediately
    scheduler.add_job(run_all_jobs_all_users, id='manual_jobs', replace_existing=True)

    notify("🔄 Manual background jobs triggered")
    return True


@router.get("/status")
async def get_status_endpoint():
    """Get the current status of the background scheduler."""
    return get_scheduler_status()


@router.post("/trigger")
async def trigger_manual_jobs_endpoint():
    """
    Manually trigger all background jobs for all users immediately.

    Runs all 4 jobs in sequence:
    - find_and_reply_to_new_posts
    - find_user_activity
    - find_and_reply_to_engagement
    - analyze
    """
    success = trigger_manual_jobs()
    if success:
        return {"message": "Manual background jobs triggered successfully"}
    else:
        return {"message": "Failed to trigger manual jobs", "error": "Scheduler not running"}
