"""
Background scheduler for automatic tweet scraping and reply generation.

This module sets up scheduled tasks to:
- Scrape tweets from configured accounts/queries for all active users
- Generate AI replies for newly scraped tweets
- Clean up tweets older than 3 days
- Run at configurable intervals (default: every 24 hours)
"""

import json

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import APIRouter

from backend.generate_replies import generate_replies
from backend.log_interactions import log_scrape_action
from backend.read_tweets import read_tweets
from backend.tweets_cache import cleanup_old_tweets
from backend.utils import BROWSER_STATE_FILE, cookie_still_valid, notify

# Global scheduler instance
scheduler = AsyncIOScheduler()
# API Router

router = APIRouter(prefix="/scheduler", tags=["scheduler"])


def get_users_with_valid_sessions() -> list[str]:
    """
    Get list of users who have valid browser sessions.
    Only users with valid browser states will have tweets scraped.

    Returns:
        list[str]: List of usernames with valid browser sessions
    """
    if not BROWSER_STATE_FILE.exists():
        notify("⚠️ No browser state file found")
        return []

    try:
        with open(BROWSER_STATE_FILE) as f:
            browser_states = json.load(f)

        if not isinstance(browser_states, dict):
            notify("⚠️ Invalid browser state format")
            return []

        # Filter users with valid sessions
        valid_users = []
        for username, state in browser_states.items():
            if cookie_still_valid(state):
                valid_users.append(username)
            else:
                notify(f"⚠️ Browser session expired for {username}")

        return valid_users

    except Exception as e:
        from backend.utils import error
        error(f"Error reading browser states", status_code=500, exception_text=str(e), function_name="get_users_with_valid_sessions")
        notify(f"❌ Error reading browser states: {e}")
        return []


async def auto_scrape_for_user(username: str):
    """
    Automatically scrape tweets, generate replies, and clean up old tweets for a single user.

    Args:
        username: Twitter handle of the user
    """
    import time
    from backend.utils import read_user_info, write_user_info

    start_time = time.time()

    try:
        notify(f"🤖 [Auto-scrape] Starting for user: {username}")

        # Step 1: Clean up tweets older than 3 days (72 hours)
        notify(f"🧹 [Auto-scrape] Cleaning up old tweets for {username}...")
        removed_count = await cleanup_old_tweets(username, hours=72)
        if removed_count > 0:
            notify(f"✅ [Auto-scrape] Cleaned up {removed_count} tweet(s) older than 3 days for {username}")
        else:
            notify(f"✅ [Auto-scrape] No old tweets to clean up for {username}")

        # Step 2: Scrape new tweets
        notify(f"🔍 [Auto-scrape] Scraping tweets for {username}...")
        tweets = await read_tweets(username=username)
        notify(f"✅ [Auto-scrape] Scraped {len(tweets)} tweets for {username}")

        # Step 3: Generate replies for new tweets
        notify(f"💬 [Auto-scrape] Generating replies for {username}...")
        result = await generate_replies(username=username, overwrite=False)
        reply_count = sum(1 for t in result if t.get('reply'))
        notify(f"✅ [Auto-scrape] Generated {reply_count} new replies for {username}")

        # Log the scraping action (auto-initiated)
        log_scrape_action(username, len(tweets), initiated_by="auto")

        notify(f"🎉 [Auto-scrape] Completed for {username}")

    except Exception as e:
        from backend.utils import error
        error(f"Auto-scrape failed for {username}", status_code=500, exception_text=str(e), function_name="auto_scrape_for_user", username=username)
        notify(f"❌ [Auto-scrape] Failed for {username}: {e}")

    finally:
        # Update scrolling_time_saved regardless of success/failure
        elapsed_seconds = int(time.time() - start_time)
        try:
            user_info = read_user_info(username)
            if user_info:
                current_time_saved = user_info.get("scrolling_time_saved", 0)
                user_info["scrolling_time_saved"] = current_time_saved + elapsed_seconds
                write_user_info(user_info)
                notify(f"⏱️ Added {elapsed_seconds}s to scrolling time for @{username} (total: {user_info['scrolling_time_saved']}s)")
        except Exception as e:
            from backend.utils import error
            error(f"Failed to update scrolling time", status_code=500, exception_text=str(e), function_name="auto_scrape_for_user", username=username)
            notify(f"⚠️ Failed to update scrolling time for {username}: {e}")


async def auto_scrape_all_users():
    """
    Run automatic scraping for all users with valid browser sessions.
    This is the main job function called by the scheduler.
    """
    notify("🚀 [Auto-scrape] Starting scheduled scraping for all users...")

    try:
        # Get only users with valid browser sessions
        users = get_users_with_valid_sessions()

        if not users:
            notify("⚠️ [Auto-scrape] No users with valid browser sessions found")
            return

        notify(f"👥 [Auto-scrape] Found {len(users)} user(s) with valid sessions: {', '.join(users)}")

        # Process each user
        for username in users:
            try:
                await auto_scrape_for_user(username)
            except Exception as e:
                from backend.utils import error
                error(f"Error processing auto-scrape", status_code=500, exception_text=str(e), function_name="auto_scrape_all_users", username=username)
                notify(f"❌ [Auto-scrape] Error processing {username}: {e}")
                continue

        notify(f"✅ [Auto-scrape] Completed batch scraping for {len(users)} user(s)")

    except Exception as e:
        from backend.utils import error
        error(f"Fatal error in batch scraping", status_code=500, exception_text=str(e), function_name="auto_scrape_all_users")
        notify(f"❌ [Auto-scrape] Fatal error in batch scraping: {e}")


def start_scheduler(interval_hours: int = 24):
    """
    Start the background scheduler with specified interval.

    Args:
        interval_hours: Hours between automatic scraping runs (default: 24)
    """
    if scheduler.running:
        notify("⚠️ Scheduler is already running")
        return

    # Add the auto-scrape job
    scheduler.add_job(
        auto_scrape_all_users,
        trigger=IntervalTrigger(hours=interval_hours),
        id='auto_scrape_all_users',
        name=f'Auto-scrape tweets every {interval_hours} hours',
        replace_existing=True,
        max_instances=1  # Prevent overlapping runs
    )

    scheduler.start()
    notify(f"✅ Background scheduler started (interval: {interval_hours} hours)")
    notify(f"📅 Next auto-scrape: {scheduler.get_jobs()[0].next_run_time}")


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


def trigger_manual_scrape():
    """
    Manually trigger a scrape for all users (doesn't wait for scheduled time).
    Returns immediately, runs in background.
    """
    if not scheduler.running:
        notify("⚠️ Scheduler is not running, cannot trigger manual scrape")
        return False

    # Schedule the job to run immediately
    scheduler.add_job(auto_scrape_all_users, id='manual_scrape', replace_existing=True)

    notify("🔄 Manual scrape triggered")
    return True


@router.get("/status")
async def get_status_endpoint():
    """Get the current status of the background scheduler."""
    return get_scheduler_status()


@router.post("/trigger")
async def trigger_manual_scrape_endpoint():
    """Manually trigger a scrape for all users immediately."""
    success = trigger_manual_scrape()
    if success:
        return {"message": "Manual scrape triggered successfully"}
    else:
        return {"message": "Failed to trigger manual scrape", "error": "Scheduler not running"}
