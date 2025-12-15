"""
Progress bar display for background jobs.

Provides dynamic terminal progress bars that update in place for live viewing,
while preserving completed states in log history.
"""

from datetime import datetime

try:
    from datetime import UTC
except ImportError:
    from datetime import timezone
    UTC = timezone.utc


# Track last printed phase to know when to finalize a line
_last_phase: dict[str, str] = {}

# Human-readable display names for jobs
JOB_DISPLAY_NAMES = {
    "find_and_reply_to_new_posts": "Finding new posts",
    "find_user_activity": "Finding user activity",
    "find_and_reply_to_engagement": "Monitoring engagement",
    "analyze": "Analyzing activity, making models smarter",
}


def get_job_display_name(job_name: str) -> str:
    """Get a human-readable display name for a job."""
    return JOB_DISPLAY_NAMES.get(job_name, job_name)


def get_trigger_icon(triggered_by: str) -> str:
    """Get the icon for the trigger source."""
    return "⏰" if triggered_by == "scheduler" else "👤"


def print_job_start(job_name: str, username: str, triggered_by: str = "user") -> None:
    """Print a job start message."""
    trigger_icon = get_trigger_icon(triggered_by)
    timestamp = datetime.now(UTC).strftime("%H:%M:%S")
    display_name = get_job_display_name(job_name)
    print(f"[{timestamp}] {trigger_icon} [{display_name}] @{username} | STARTED", flush=True)


def print_job_complete(
    job_name: str,
    username: str,
    triggered_by: str,
    summary: str,
    duration_seconds: int
) -> None:
    """Print a job completion message."""
    trigger_icon = get_trigger_icon(triggered_by)
    timestamp = datetime.now(UTC).strftime("%H:%M:%S")
    display_name = get_job_display_name(job_name)
    print(f"[{timestamp}] {trigger_icon} [{display_name}] @{username} | COMPLETE: {summary} ({duration_seconds}s)", flush=True)


def print_job_error(job_name: str, username: str, triggered_by: str, error_msg: str) -> None:
    """Print a job error message."""
    trigger_icon = get_trigger_icon(triggered_by)
    timestamp = datetime.now(UTC).strftime("%H:%M:%S")
    display_name = get_job_display_name(job_name)
    print(f"\n[{timestamp}] {trigger_icon} [{display_name}] @{username} | ERROR: {error_msg}", flush=True)


def print_progress_bar(
    job_name: str,
    phase: str,
    current: int,
    total: int,
    username: str,
    triggered_by: str = "unknown"
) -> None:
    """
    Print a dynamic progress bar that updates in place.

    Uses \\r to overwrite the current line for live updates.
    Prints a newline when phase completes or changes (for history).

    Args:
        job_name: Internal job name (e.g., "find_and_reply_to_new_posts")
        phase: Current phase (e.g., "scraping_account:elonmusk")
        current: Current progress count
        total: Total items to process
        username: User the job is running for
        triggered_by: "user" or "scheduler"
    """
    if total <= 0:
        return

    percentage = min(100, int((current / total) * 100))
    bar_length = 30
    filled = int(bar_length * current / total)
    bar = "█" * filled + "░" * (bar_length - filled)

    display_name = get_job_display_name(job_name)
    trigger_icon = get_trigger_icon(triggered_by)
    timestamp = datetime.now(UTC).strftime("%H:%M:%S")

    # Format phase for readability
    phase_display = phase.replace("_", " ")
    if ":" in phase_display:
        action, target = phase_display.split(":", 1)
        phase_display = f"{action} → {target}"

    # Create the progress line (pad to overwrite previous content)
    line = f"[{timestamp}] {trigger_icon} [{display_name}] @{username} | {phase_display} [{bar}] {percentage}% ({current}/{total})"
    padded_line = line.ljust(120)  # Pad to ensure we overwrite old content

    # Check if phase changed - if so, finalize the previous line first
    cache_key = f"{username}:{job_name}"
    last_phase = _last_phase.get(cache_key)
    if last_phase and last_phase != phase:
        print()  # Newline to preserve the previous phase's final state

    _last_phase[cache_key] = phase

    # If complete, print with newline (finalizes this phase in history)
    if current >= total:
        print(f"\r{padded_line}", flush=True)
        _last_phase.pop(cache_key, None)  # Clear phase tracking
    else:
        # Live update: overwrite current line
        print(f"\r{padded_line}", end="", flush=True)


def clear_phase_tracking(username: str, job_name: str) -> None:
    """Clear phase tracking for a job (call on job completion/error)."""
    cache_key = f"{username}:{job_name}"
    _last_phase.pop(cache_key, None)
