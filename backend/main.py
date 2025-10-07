from fastapi import FastAPI

from backend.logging import router as logging_router
from backend.post_takes import router as post_router
from backend.read_tweets import router as read_router
from backend.tweets_cache import router as tweets_router

app = FastAPI(title="FloodMe API")

app.include_router(tweets_router)
app.include_router(post_router)
app.include_router(read_router)
app.include_router(logging_router)


