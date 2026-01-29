"""
Bread Account Management

Bread accounts are burner Twitter accounts used for automated scraping operations.
This avoids consuming user API quotas and risking user account TOS violations.
"""

# List of bread accounts: [username, password]
BREAD_ACCOUNTS = [
    ["matilda80085", "xme4pbf!FMW6gtc8uzf"],
    ["proudlurker", "JXJ-pfd3bdv*myu0whb"]
]


async def run_with_bread_account(job_func, username: str, **kwargs):
    """
    Wrapper to run a background job function with bread account browser context.

    Creates a persistent browser session for the entire job lifecycle using a
    randomly selected bread account. The browser context is passed to the job
    function for all scraping operations.

    Args:
        job_func: The background job function to run (must accept ctx parameter)
        username: The user's username (for data routing, NOT authentication)
        **kwargs: Additional arguments to pass to job_func

    Returns:
        Result from job_func

    Example:
        await run_with_bread_account(
            find_and_reply_to_new_posts,
            "testuser",
            triggered_by="scheduled"
        )

    Flow:
        1. Acquire an available bread account (per-account locking)
        2. Launches headless browser with allocated account
        3. Job runs with bread account context for authentication
        4. All results written to user's cache files (NOT bread account's)
        5. Browser cleanup on job completion
        6. Release bread account for next job

    Jobs can run in parallel if they use different bread accounts.
    """
    from backend.twitter.bread_context import BreadAccountContext
    from backend.twitter.bread_account_manager import acquire_bread_account, release_bread_account

    # Generate job identifier
    job_name = job_func.__name__
    job_id = f"{username}:{job_name}"

    # Acquire an available account (will wait if all are busy)
    bread_username, bread_password = await acquire_bread_account(job_id)

    try:
        # Create browser context with allocated account
        async with BreadAccountContext(
            username,
            force_account=(bread_username, bread_password)
        ) as bread_ctx:
            result = await job_func(
                username=username,
                ctx=bread_ctx.context,  # Playwright browser context for scraping
                **kwargs
            )
        return result
    finally:
        # Always release, even on error
        release_bread_account(bread_username, job_id)
