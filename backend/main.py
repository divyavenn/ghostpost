from fastapi import FastAPI

from backend.post_takes import router as post_router
from backend.tweets_cache import router as tweets_router

app = FastAPI(title="FloodMe API")

app.include_router(tweets_router)
app.include_router(post_router)


