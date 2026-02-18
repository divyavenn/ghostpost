"""
Modal deployment configuration for FloodMe backend.

Deploy with:
    modal deploy modal_app.py

Run locally with Modal:
    modal serve modal_app.py

Set up secrets first:
    modal secret create floodme-secrets \
        SUPABASE_URL=... \
        SUPABASE_API_KEY=... \
        SUPABASE_JWT_KEY=... \
        CLAUDE_API_KEY=... \
        DIVYA_API_KEY=... \
        DIVYA_MODEL_NAME=... \
        TWITTER_CLIENT_ID=... \
        TWITTER_CLIENT_SECRET=... \
        TWITTER_BEARER_TOKEN=... \
        STRIPE_SECRET_KEY=... \
        STRIPE_PUBLISHABLE_KEY=... \
        STRIPE_WEBHOOK_SECRET=... \
        STRIPE_PAID_PRICE_ID=... \
        DEV_EMAIL=... \
        SMTP_HOST=... \
        SMTP_PORT=... \
        SMTP_USER=... \
        SMTP_PASSWORD=... \
        BROWSERBASE_API_KEY=... \
        BROWSERBASE_PROJECT_ID=...
"""

import modal

# Create the Modal app
app = modal.App("floodme-backend")

# Define the container image with all dependencies
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "fastapi>=0.104.0",
        "uvicorn[standard]>=0.24.0",
        "python-multipart>=0.0.6",
        "requests>=2.31.0",
        "python-jose[cryptography]>=3.3.0",
        "passlib[bcrypt]>=1.7.4",
        "python-dotenv>=1.0.0",
        "supabase>=2.0.0",
        "postgrest>=0.13.0",
        "playwright>=1.40.0",
        "browserbase>=0.3.0",
        "websockets>=12.0",
        "pydantic>=2.5.0",
        "apscheduler>=3.10.0",
        "httpx>=0.28.1",
        "stripe>=7.0.0",
    )
    .run_commands("playwright install chromium && playwright install-deps")
)

# Mount the backend code
backend_mount = modal.Mount.from_local_dir(
    "backend",
    remote_path="/root/backend",
)


@app.function(
    image=image,
    mounts=[backend_mount],
    secrets=[modal.Secret.from_name("floodme-secrets")],
    timeout=600,  # 10 minute timeout for long requests
    container_idle_timeout=300,  # Keep warm for 5 minutes
    allow_concurrent_inputs=10,
)
@modal.asgi_app()
def fastapi_app():
    """Serve the FastAPI application."""
    import sys
    sys.path.insert(0, "/root")

    # Import the FastAPI app (without starting the scheduler - we'll use Modal's scheduler)
    from backend.main import app as _app

    # Disable the built-in scheduler since Modal handles cron jobs
    # The scheduler is started in the lifespan context, so we need to create a new app
    # or modify the lifespan. For simplicity, we'll just return the app and let
    # the scheduler run (it will work but Modal's cron is more reliable for serverless)

    return _app


@app.function(
    image=image,
    mounts=[backend_mount],
    secrets=[modal.Secret.from_name("floodme-secrets")],
    timeout=1800,  # 30 minute timeout for background jobs
    schedule=modal.Cron("0 */6 * * *"),  # Run every 6 hours
)
async def scheduled_jobs():
    """
    Run all background jobs on a schedule.

    This replaces the APScheduler-based scheduler with Modal's native cron.
    Runs every 6 hours: scraping, engagement monitoring, reply generation.
    """
    import sys
    sys.path.insert(0, "/root")

    from backend.utlils.scheduler import run_all_jobs_all_users
    from backend.utlils.utils import notify

    notify("🚀 Starting scheduled background jobs via Modal cron...")
    await run_all_jobs_all_users()
    notify("✅ Scheduled jobs completed")


@app.function(
    image=image,
    mounts=[backend_mount],
    secrets=[modal.Secret.from_name("floodme-secrets")],
    timeout=300,  # 5 minute timeout
    schedule=modal.Cron("0 * * * *"),  # Run every hour
)
async def cleanup_sessions():
    """
    Clean up expired browser sessions.

    Runs every hour to prevent zombie processes.
    """
    import sys
    sys.path.insert(0, "/root")

    from backend.utlils.scheduler import cleanup_expired_browser_sessions
    from backend.utlils.utils import notify

    notify("🧹 Running browser session cleanup via Modal cron...")
    await cleanup_expired_browser_sessions()
    notify("✅ Session cleanup completed")


# Optional: Manual trigger endpoint for testing
@app.function(
    image=image,
    mounts=[backend_mount],
    secrets=[modal.Secret.from_name("floodme-secrets")],
    timeout=1800,
)
async def trigger_jobs_manually():
    """Manually trigger all background jobs (for testing)."""
    import sys
    sys.path.insert(0, "/root")

    from backend.utlils.scheduler import run_all_jobs_all_users
    from backend.utlils.utils import notify

    notify("🚀 Manually triggering all background jobs...")
    await run_all_jobs_all_users()
    notify("✅ Manual job run completed")
    return {"status": "completed"}


# Local entrypoint for testing
@app.local_entrypoint()
def main():
    """Test the deployment locally."""
    print("FloodMe Backend - Modal Deployment")
    print("===================================")
    print("")
    print("Commands:")
    print("  modal serve modal_app.py    # Run locally with hot reload")
    print("  modal deploy modal_app.py   # Deploy to Modal cloud")
    print("")
    print("After deployment, your API will be available at:")
    print("  https://[your-username]--floodme-backend-fastapi-app.modal.run")
    print("")
    print("To trigger jobs manually:")
    print("  modal run modal_app.py::trigger_jobs_manually")
