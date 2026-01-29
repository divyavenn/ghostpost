"""
Desktop Jobs API - Endpoints for desktop app to poll and report job results
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

try:
    from datetime import UTC
except ImportError:
    from datetime import timezone
    UTC = timezone.utc

import uuid
from fastapi import APIRouter, HTTPException

from backend.utlils.utils import notify

router = APIRouter(prefix="/desktop-jobs", tags=["desktop"])


@dataclass
class DesktopJob:
    """Desktop job data structure"""
    id: str
    username: str
    job_type: Literal["search_tweets", "fetch_home_timeline", "fetch_user_timeline", "deep_scrape_thread"]
    params: dict
    created_at: datetime
    status: Literal["pending", "running", "completed", "failed"]
    result: dict | None = None
    error: str | None = None
    completed_at: datetime | None = None


# In-memory job queue (could be replaced with Redis/database)
desktop_jobs: dict[str, DesktopJob] = {}


def create_desktop_job(username: str, job_type: str, params: dict) -> str:
    """
    Create a new desktop job.
    Called by scheduler or API to queue work for desktop app.

    Args:
        username: User the job is for
        job_type: Type of job (search_tweets, fetch_home_timeline, etc.)
        params: Job parameters

    Returns:
        Job ID
    """
    job_id = str(uuid.uuid4())
    job = DesktopJob(
        id=job_id,
        username=username,
        job_type=job_type,
        params=params,
        created_at=datetime.now(UTC),
        status="pending"
    )

    desktop_jobs[job_id] = job
    notify(f"📱 Created desktop job {job_id} ({job_type}) for {username}")

    return job_id


@router.get("/{username}/pending")
async def get_pending_jobs(username: str) -> list[dict]:
    """
    Get all pending jobs for a user.
    Desktop app polls this endpoint.

    When desktop app fetches jobs, they are marked as "running".
    """
    pending = []

    for job in desktop_jobs.values():
        if job.username == username and job.status == "pending":
            pending.append({
                "id": job.id,
                "job_type": job.job_type,
                "params": job.params,
                "created_at": job.created_at.isoformat()
            })

            # Mark as running when desktop app picks it up
            job.status = "running"

    if pending:
        notify(f"📤 Sent {len(pending)} pending job(s) to desktop app for {username}")

    return pending


@router.post("/{job_id}/complete")
async def complete_job(job_id: str, result: dict) -> dict:
    """
    Mark job as completed with results.
    Desktop app POSTs here after successfully executing job.
    """
    if job_id not in desktop_jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = desktop_jobs[job_id]
    job.status = "completed"
    job.result = result
    job.completed_at = datetime.now(UTC)

    notify(f"✅ Desktop job {job_id} completed for {job.username}")

    # Process the result (e.g., write to cache, trigger next steps)
    await process_job_result(job)

    return {"status": "success", "job_id": job_id}


@router.post("/{job_id}/fail")
async def fail_job(job_id: str, error_data: dict) -> dict:
    """
    Mark job as failed with error.
    Desktop app POSTs here if job execution fails.
    """
    if job_id not in desktop_jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = desktop_jobs[job_id]
    job.status = "failed"
    job.error = error_data.get("error", "Unknown error")
    job.completed_at = datetime.now(UTC)

    notify(f"❌ Desktop job {job_id} failed for {job.username}: {job.error}")

    return {"status": "acknowledged", "job_id": job_id}


@router.get("/{username}/status")
async def get_job_status(username: str) -> dict:
    """
    Get status of all jobs for a user.
    """
    user_jobs = [job for job in desktop_jobs.values() if job.username == username]

    return {
        "total": len(user_jobs),
        "pending": sum(1 for j in user_jobs if j.status == "pending"),
        "running": sum(1 for j in user_jobs if j.status == "running"),
        "completed": sum(1 for j in user_jobs if j.status == "completed"),
        "failed": sum(1 for j in user_jobs if j.status == "failed"),
        "jobs": [
            {
                "id": j.id,
                "job_type": j.job_type,
                "status": j.status,
                "created_at": j.created_at.isoformat(),
                "completed_at": j.completed_at.isoformat() if j.completed_at else None
            }
            for j in sorted(user_jobs, key=lambda x: x.created_at, reverse=True)[:20]
        ]
    }


@router.delete("/{job_id}")
async def delete_job(job_id: str) -> dict:
    """Delete a job (cleanup)"""
    if job_id not in desktop_jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    del desktop_jobs[job_id]
    return {"status": "deleted", "job_id": job_id}


async def process_job_result(job: DesktopJob):
    """
    Process completed job results.
    This is where you'd write to cache, update database, etc.
    """
    # TODO: Implement result processing based on job type

    if job.job_type == "fetch_home_timeline":
        # Write tweets to cache
        from backend.data.twitter.edit_cache import write_to_cache
        tweets = job.result.get("tweets", [])
        if tweets:
            await write_to_cache(tweets, f"Desktop job {job.id}", username=job.username)
            notify(f"💾 Wrote {len(tweets)} tweets to cache for {job.username}")

    elif job.job_type == "search_tweets":
        # Write search results to cache
        from backend.data.twitter.edit_cache import write_to_cache
        tweets = job.result.get("tweets", [])
        if tweets:
            await write_to_cache(tweets, f"Desktop search: {job.params.get('query')}", username=job.username)
            notify(f"💾 Wrote {len(tweets)} search results to cache for {job.username}")

    # Add more job type handlers as needed


def cleanup_old_jobs(max_age_hours: int = 24):
    """
    Clean up completed/failed jobs older than max_age_hours.
    Should be called periodically.
    """
    now = datetime.now(UTC)
    to_delete = []

    for job_id, job in desktop_jobs.items():
        if job.status in ["completed", "failed"] and job.completed_at:
            age_hours = (now - job.completed_at).total_seconds() / 3600
            if age_hours > max_age_hours:
                to_delete.append(job_id)

    for job_id in to_delete:
        del desktop_jobs[job_id]

    if to_delete:
        notify(f"🧹 Cleaned up {len(to_delete)} old desktop jobs")

    return len(to_delete)
