from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.data.twitter.edit_cache import router as tweets_router
from backend.browser_automation.twitter.metrics import router as performance_router
from backend.browser_automation.twitter.timeline import router as read_router
from backend.twitter.auth_routes import router as auth_router
from backend.twitter.comment_replies import router as comment_replies_router
from backend.twitter.comments_routes import router as comments_router
from backend.twitter.generate_replies import router as generate_router
from backend.twitter.intent_to_queries import router as intent_router
from backend.twitter.logging import router as logging_router
from backend.twitter.posted_tweets import router as posted_router
from backend.twitter.posting import router as post_router
from backend.twitter.twitter_jobs import router as jobs_router
from backend.user.user import router as user_router
from backend.utlils.scheduler import router as scheduler_router
from backend.utlils.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events for the FastAPI app."""
    # Startup: Start the background scheduler
    start_scheduler(scrape_interval_hours=24, engagement_interval_hours=6)  # Scrape every 24h, engagement every 6h
    yield
    # Shutdown: Stop the scheduler
    stop_scheduler()


app = FastAPI(title="FloodMe API", version="1.0.0", openapi_version="3.1.0", lifespan=lifespan)

# Add CORS middleware to allow frontend to make requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Local dev (Vite)
        "http://localhost:5174",  # Local dev (Vite alternate port)
        "http://localhost:3000",  # Local dev
        "http://localhost",  # Docker frontend (port 80)
        "http://192.168.8.57:3000",  # Production server
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(tweets_router)
app.include_router(post_router)
app.include_router(posted_router)
app.include_router(performance_router)
app.include_router(read_router)
app.include_router(generate_router)
app.include_router(intent_router)
app.include_router(logging_router)
app.include_router(user_router)
app.include_router(scheduler_router)
app.include_router(comments_router)
app.include_router(comment_replies_router)
app.include_router(jobs_router)


@app.get("/health")
async def health_check():
    """Basic health check endpoint for Docker healthcheck."""
    return {"status": "healthy"}
