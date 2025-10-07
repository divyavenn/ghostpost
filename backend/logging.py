
import json
from datetime import datetime, timezone, UTC
from enum import Enum
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel
from backend.utils import _cache_key


class TweetAction(str, Enum):
    WRITTEN = "written"
    EDITED = "edited"
    DELETED = "deleted"
    POSTED = "posted"



def get_user_log_path(username: str) -> Path:
    from backend.utils import CACHE_DIR
    return CACHE_DIR / f"{_cache_key(username)}_log.jsonl"



def read_user_log(username: str, limit: int | None = None) -> list[dict[str, Any]]:
    log_path = get_user_log_path(username)

    if not log_path.exists():
        return []

    entries = []
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except Exception:
        return []

    # Return most recent first if limit specified
    if limit is not None:
        return entries[-limit:][::-1]

    return entries


def get_log_stats(username: str) -> dict[str, int]:
    entries = read_user_log(username)

    stats = {
        "total": len(entries),
        TweetAction.WRITTEN.value: 0,
        TweetAction.EDITED.value: 0,
        TweetAction.DELETED.value: 0,
        TweetAction.POSTED.value: 0,
    }

    for entry in entries:
        action = entry.get("action")
        if action in stats:
            stats[action] += 1

    return stats


# API Router
router = APIRouter(prefix="/logs", tags=["logs"])


class LogQueryParams(BaseModel):
    limit: int | None = None


@router.get("/{username}/logs")
async def get_logs(username: str, limit: int | None = None) -> dict[str, Any]:
    """Get log entries for a user."""
    entries = read_user_log(username, limit=limit)
    return {
        "username": username,
        "count": len(entries),
        "entries": entries
    }


@router.get("/{username}/stats")
async def get_log_statistics(username: str) -> dict[str, Any]:
    """Get statistics about a user's log."""
    stats = get_log_stats(username)
    return {
        "username": username,
        "stats": stats
    }

@router.post("/{username}/append_log")
def log_tweet_action(username: str, action: TweetAction,tweet_id: str, metadata: dict[str, Any] | None = None
) -> None:
    log_path = get_user_log_path(username)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "action": action.value,
        "tweet_id": tweet_id,
        "username": username,
    }

    if metadata:
        entry["metadata"] = metadata

    # Append to JSONL file (each line is a JSON object)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")