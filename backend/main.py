from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.auth_routes import router as auth_router
from backend.generate_replies import router as generate_router
from backend.log_interactions import router as logging_router
from backend.post_takes import router as post_router
from backend.read_tweets import router as read_router
from backend.tweets_cache import router as tweets_router
from backend.user import router as user_router

app = FastAPI(title="FloodMe API")

# Add CORS middleware to allow frontend to make requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",      # Local dev (Vite)
        "http://localhost:3000",      # Local dev
        "http://192.168.8.57:3000",   # Production server
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(tweets_router)
app.include_router(post_router)
app.include_router(read_router)
app.include_router(generate_router)
app.include_router(logging_router)
app.include_router(user_router)


