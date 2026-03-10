"""Canonical desktop task type definitions for the web->desktop queue."""

from __future__ import annotations

from enum import Enum
from typing import Any


class DesktopTaskType(str, Enum):
    POST_ALL = "POST_ALL"
    POST_X = "POST_X"
    POST_LINKEDIN = "POST_LINKEDIN"
    POST_SUBSTACK = "POST_SUBSTACK"
    REPLY_X = "REPLY_X"
    SEARCH_X = "SEARCH_X"
    GET_THREAD_X = "GET_THREAD_X"
    FETCH_HOME_TIMELINE_X = "FETCH_HOME_TIMELINE_X"
    FETCH_USER_TIMELINE_X = "FETCH_USER_TIMELINE_X"
    DEEP_SCRAPE_THREAD_X = "DEEP_SCRAPE_THREAD_X"
    SHALLOW_SCRAPE_THREAD_X = "SHALLOW_SCRAPE_THREAD_X"
    SCRAPE_TWEETS_X = "SCRAPE_TWEETS_X"


_ALIASES: dict[str, DesktopTaskType] = {
    # Posting
    "POST_ALL": DesktopTaskType.POST_ALL,
    "post_all": DesktopTaskType.POST_ALL,
    "POST_X": DesktopTaskType.POST_X,
    "POST_TWITTER": DesktopTaskType.POST_X,
    "post_x": DesktopTaskType.POST_X,
    "post_twitter": DesktopTaskType.POST_X,
    "post_tweet": DesktopTaskType.POST_X,
    "POST_LINKEDIN": DesktopTaskType.POST_LINKEDIN,
    "post_linkedin": DesktopTaskType.POST_LINKEDIN,
    "POST_SUBSTACK": DesktopTaskType.POST_SUBSTACK,
    "post_substack": DesktopTaskType.POST_SUBSTACK,
    "post_substack_note": DesktopTaskType.POST_SUBSTACK,
    # Replying/searching/threads
    "REPLY_X": DesktopTaskType.REPLY_X,
    "reply_x": DesktopTaskType.REPLY_X,
    "reply_tweet": DesktopTaskType.REPLY_X,
    "SEARCH_X": DesktopTaskType.SEARCH_X,
    "search_x": DesktopTaskType.SEARCH_X,
    "search_tweets": DesktopTaskType.SEARCH_X,
    "GET_THREAD_X": DesktopTaskType.GET_THREAD_X,
    "get_thread_x": DesktopTaskType.GET_THREAD_X,
    "get_thread": DesktopTaskType.GET_THREAD_X,
    "FETCH_HOME_TIMELINE_X": DesktopTaskType.FETCH_HOME_TIMELINE_X,
    "fetch_home_timeline_x": DesktopTaskType.FETCH_HOME_TIMELINE_X,
    "fetch_home_timeline": DesktopTaskType.FETCH_HOME_TIMELINE_X,
    "FETCH_USER_TIMELINE_X": DesktopTaskType.FETCH_USER_TIMELINE_X,
    "fetch_user_timeline_x": DesktopTaskType.FETCH_USER_TIMELINE_X,
    "fetch_user_timeline": DesktopTaskType.FETCH_USER_TIMELINE_X,
    "DEEP_SCRAPE_THREAD_X": DesktopTaskType.DEEP_SCRAPE_THREAD_X,
    "deep_scrape_thread_x": DesktopTaskType.DEEP_SCRAPE_THREAD_X,
    "deep_scrape_thread": DesktopTaskType.DEEP_SCRAPE_THREAD_X,
    "SHALLOW_SCRAPE_THREAD_X": DesktopTaskType.SHALLOW_SCRAPE_THREAD_X,
    "shallow_scrape_thread_x": DesktopTaskType.SHALLOW_SCRAPE_THREAD_X,
    "shallow_scrape_thread": DesktopTaskType.SHALLOW_SCRAPE_THREAD_X,
    # Existing aggregate scrape endpoint
    "SCRAPE_TWEETS_X": DesktopTaskType.SCRAPE_TWEETS_X,
    "scrape_tweets_x": DesktopTaskType.SCRAPE_TWEETS_X,
    "scrape_tweets": DesktopTaskType.SCRAPE_TWEETS_X,
}


def normalize_task_type(task_type: str | DesktopTaskType) -> DesktopTaskType:
    if isinstance(task_type, DesktopTaskType):
        return task_type
    normalized = _ALIASES.get(task_type)
    if normalized:
        return normalized
    raise ValueError(f"Unsupported desktop task type: {task_type}")


def is_timeline_collection_task(task_type: str | DesktopTaskType) -> bool:
    normalized = normalize_task_type(task_type)
    return normalized in {
        DesktopTaskType.FETCH_HOME_TIMELINE_X,
        DesktopTaskType.SEARCH_X,
        DesktopTaskType.FETCH_USER_TIMELINE_X,
        DesktopTaskType.SCRAPE_TWEETS_X,
    }


def supported_task_catalog() -> list[dict[str, Any]]:
    return [
        {
            "task_type": DesktopTaskType.POST_ALL.value,
            "description": "Post to all enabled channels",
            "aliases": ["post_all"],
            "implemented": True,
        },
        {
            "task_type": DesktopTaskType.POST_X.value,
            "description": "Post tweet on X",
            "aliases": ["post_tweet", "post_twitter", "POST_TWITTER", "post_x"],
            "implemented": True,
        },
        {
            "task_type": DesktopTaskType.POST_LINKEDIN.value,
            "description": "Post update on LinkedIn",
            "aliases": ["post_linkedin"],
            "implemented": True,
        },
        {
            "task_type": DesktopTaskType.POST_SUBSTACK.value,
            "description": "Post Substack note",
            "aliases": ["post_substack_note", "post_substack"],
            "implemented": True,
        },
        {
            "task_type": DesktopTaskType.REPLY_X.value,
            "description": "Reply to a tweet on X",
            "aliases": ["reply_x", "reply_tweet"],
            "implemented": False,
        },
        {
            "task_type": DesktopTaskType.SEARCH_X.value,
            "description": "Search tweets on X",
            "aliases": ["search_tweets", "search_x"],
            "implemented": False,
        },
        {
            "task_type": DesktopTaskType.GET_THREAD_X.value,
            "description": "Fetch thread context and top replies",
            "aliases": ["get_thread", "get_thread_x"],
            "implemented": False,
        },
        {
            "task_type": DesktopTaskType.FETCH_HOME_TIMELINE_X.value,
            "description": "Fetch home timeline from X",
            "aliases": ["fetch_home_timeline", "fetch_home_timeline_x"],
            "implemented": False,
        },
        {
            "task_type": DesktopTaskType.FETCH_USER_TIMELINE_X.value,
            "description": "Fetch specific user's timeline from X",
            "aliases": ["fetch_user_timeline", "fetch_user_timeline_x"],
            "implemented": False,
        },
        {
            "task_type": DesktopTaskType.DEEP_SCRAPE_THREAD_X.value,
            "description": "Deep scrape thread replies/metrics",
            "aliases": ["deep_scrape_thread", "deep_scrape_thread_x"],
            "implemented": False,
        },
        {
            "task_type": DesktopTaskType.SHALLOW_SCRAPE_THREAD_X.value,
            "description": "Shallow scrape thread metrics",
            "aliases": ["shallow_scrape_thread", "shallow_scrape_thread_x"],
            "implemented": False,
        },
        {
            "task_type": DesktopTaskType.SCRAPE_TWEETS_X.value,
            "description": "Run discovery scrape (accounts + queries)",
            "aliases": ["scrape_tweets", "scrape_tweets_x"],
            "implemented": False,
        },
    ]
