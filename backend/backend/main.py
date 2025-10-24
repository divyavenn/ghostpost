from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.account_routes import router as account_router
from backend.auth_routes import router as auth_router
from backend.browser_auth_routes import router as browser_auth_router
from backend.generate_replies import router as generate_router
from backend.log_interactions import router as logging_router
from backend.performance_check import router as performance_router
from backend.post_takes import router as post_router
from backend.posted_tweets import router as posted_router
from backend.read_tweets import router as read_router
from backend.scheduler import router as scheduler_router
from backend.scheduler import start_scheduler, stop_scheduler
from backend.tweets_cache import router as tweets_router
from backend.user import router as user_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events for the FastAPI app."""
    # Startup: Start the background scheduler
    start_scheduler(interval_hours=24)  # Run auto-scrape every 24 hours
    yield
    # Shutdown: Stop the scheduler
    stop_scheduler()


app = FastAPI(title="FloodMe API", lifespan=lifespan)

# Add CORS middleware to allow frontend to make requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Local dev (Vite)
        "http://localhost:3000",  # Local dev
        "http://localhost",  # Docker frontend (port 80)
        "http://192.168.8.57:3000",  # Production server
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(account_router)
app.include_router(auth_router)
app.include_router(browser_auth_router)
app.include_router(tweets_router)
app.include_router(post_router)
app.include_router(posted_router)
app.include_router(performance_router)
app.include_router(read_router)
app.include_router(generate_router)
app.include_router(logging_router)
app.include_router(user_router)
app.include_router(scheduler_router)


@app.get("/health")
async def health_check():
    """Basic health check endpoint for Docker healthcheck."""
    return {"status": "healthy"}


@app.get("/health/vnc")
async def vnc_health_check():
    """Check if VNC services are ready for OAuth."""
    import os
    import socket

    checks = {
        "display": False,
        "x11vnc": False,
        "novnc": False,
    }

    # Check DISPLAY environment variable
    checks["display"] = os.getenv("DISPLAY") == ":99"

    # Check if x11vnc is listening on port 5900
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('localhost', 5900))
        checks["x11vnc"] = result == 0
        sock.close()
    except Exception:
        checks["x11vnc"] = False

    # Check if noVNC is listening on port 6080
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('localhost', 6080))
        checks["novnc"] = result == 0
        sock.close()
    except Exception:
        checks["novnc"] = False

    all_ready = all(checks.values())

    return {
        "ready": all_ready,
        "checks": checks,
        "message": "VNC services ready for OAuth" if all_ready else "VNC services not ready yet"
    }
