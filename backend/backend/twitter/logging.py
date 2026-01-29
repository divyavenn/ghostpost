import json
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Literal

try:  # Python 3.11+
    from datetime import UTC  # type: ignore[attr-defined]
except ImportError:  # Python <3.11
    from datetime import timezone
    UTC = timezone.utc
from fastapi import APIRouter
from pydantic import BaseModel

from backend.utlils.utils import _cache_key


# ============================================================================
# Details Models (one per action type)
# ============================================================================

class ErrorLog(BaseModel):
    message: str
    status_code: int
    calling_function: str
    timestamp: datetime
    user_id: str | None
    platform: Literal["Twitter", "Reddit"]
    raw_exception: str
        
class SkippedTweetDetails(BaseModel):
    """Details for when a discovered tweet is skipped/removed from queue."""
    tweet_id: str
    author: str
    thread_content: list[str]  # Thread text that was being replied to

class TwitterPostedReplyDetails(BaseModel):
    """Details for when a reply is successfully posted to Twitter."""
    generations: list[str]  # All generated reply options
    chosen_generation_index: int  # Which generation was selected
    chosen_model: str  # Model that generated the chosen reply
    chosen_prompt: str  # Prompt variant used
    final_text: str  # Final edited text that was posted (may differ from generation)
    posted_tweet_id: str  # ID of the posted tweet from Twitter
    original_tweet_id: str  # ID of tweet being replied to
    

class SearchResults(BaseModel):
    source_type: str  # "query", "account", "home_timeline"
    source_value: str  # Query text, @handle, or "following"
    tweets_found: int  # Total tweets fetched from search API
    tweets_discovered: int  # Tweets that passed initial checks
    discovery_tweets_selected: int  # Tweets selected after filtering
    filtered_old: int  # Filtered due to age
    filtered_impressions: int  # Filtered due to low impressions
    filtered_intent: int  # Filtered due to intent mismatch
    filtered_seen: int  # Already seen/replied to
    filtered_replies: int  # Filtered because reply
    filtered_retweets: int  # Filtered because retweet
    threads_fetched: int  # Full thread contexts fetched
    replies_generated: int  # Replies generated for selected tweets
    

class NewPostDiscoveryResults(BaseModel):
    """Metrics for find_and_reply_to_new_posts job."""
    total_tweets_found: int  # Total tweets fetched
    per_search_results : list[SearchResults]
    tweets_skipped_already_seen: int = 0  # Tweets filtered during Phase 4 because already in seen_tweets

class UserActivityResults(BaseModel):
    """Metrics for find_user_activity job."""
    total_discovered: int  # Total tweets discovered (recently posted + resurrected)
    recently_posted: int  # Tweets posted externally by user
    resurrected: int  # Cold tweets with new activity
    original_posts: int  # User's original posts found
    replies: int  # User's replies found
    comment_backs: int  # User's comment-backs found
    new_comments: int  # New comments on user's posts
    new_quote_tweets: int  # New quote tweets of user's posts

class EngagementDiscoveryResults(BaseModel):
    """Metrics for find_and_reply_to_engagement job."""
    active_tweets_scraped: int  # Active tweets checked (deep scrape)
    warm_tweets_scraped: int  # Warm tweets checked (shallow scrape)
    tweets_promoted: int  # Tweets promoted to active state
    new_comments: int  # New comments discovered
    new_quote_tweets: int  # New quote tweets discovered
    comment_backs_generated: int  # Replies generated for new engagement

class AnalysisResults(BaseModel):
    """Metrics for analyze job."""
    posts_analyzed: int  # Total posted tweets analyzed
    model_preferences: dict[str, float]  # Model usage percentages
    prompt_preferences: dict[str, float]  # Prompt variant usage percentages
    metrics_updated: list[str]  # Which user metrics were updated (e.g., ["lifetime_posts", "lifetime_new_follows"])
    
class TwitterAction(str, Enum):
    # details include tweet_id, author, and thread content of removed post
    DISCOVERED_POST_SKIPPED = "skipped"

    # details include a list of all the generations
    # which one was chosen (index, model and prompt that created it),
    # the final, edited version that was actually posted
    # the tweet_id of the post
    REPLY_POSTED = "reply_posted"
    COMMENT_BACK_POSTED = "comment_back_posted"

    # details should include metrics for jobs (how many total new posts found via search, how many filtered out at each stage of filtering, how many finally written to cache, # replies generated )
    NEW_POSTS_DISCOVERED = "new_post_discovery"
    #  (how many original posts, replies, comment_backs discovered)
    USER_POSTS_DISCOVERED = "user_post_discovery"
    #  (how many users posts for which enagement metrics were updated, how many comments were scraped)
    ENGAGEMENT_DISCOVERED = "engagement_discover"
   
    # (how many logs processed and what user metrics were updated as result)
    ANALYSIS = "analysis"

    # Legacy aliases for backward compatibility
    POSTED = "reply_posted"  # Alias for REPLY_POSTED
    DELETED = "skipped"  # Alias for DISCOVERED_POST_SKIPPED


# Backward compatibility alias
TweetAction = TwitterAction

class TweetLog(BaseModel):
    action: TwitterAction
    trigger: Literal['manual', 'scheduled']
    handle: str
    initiated: datetime
    completed: datetime
    success: Literal['complete', 'partial', 'error']
    details: TwitterPostedReplyDetails | SkippedTweetDetails | NewPostDiscoveryResults | UserActivityResults | EngagementDiscoveryResults | AnalysisResults
    message: dict[str, Any] | None 
    
    
    


def get_user_log_path(username: str) -> Path:
    from backend.utlils.utils import CACHE_DIR
    return CACHE_DIR / f"{_cache_key(username)}_log.jsonl"


# ============================================================================
# Deprecated/Legacy Logging Functions (kept for backward compatibility)
# ============================================================================

def log_scrape_action(username: str, tweet_count: int, initiated_by: str = "user") -> None:
    """[DEPRECATED] Legacy function - kept for backward compatibility."""
    pass


def log_filter_adjustment(username: str, old_filter: int, new_filter: int, tweets_found: int) -> None:
    """[DEPRECATED] Legacy function - kept for backward compatibility."""
    pass


def read_user_log(username: str, limit: int | None = None) -> list[dict[str, Any]]:
    log_path = get_user_log_path(username)

    if not log_path.exists():
        return []

    entries = []
    try:
        with open(log_path, encoding="utf-8") as f:
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


def log_job_complete(
    username: str,
    job_name: str,
    triggered_by: str,
    initiated: datetime,
    results: dict[str, Any],
    message: dict[str, Any] | None = None
) -> None:
    """Log when a background job completes (successfully or with partial success)."""
    log_path = get_user_log_path(username)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Map job_name to TwitterAction
    job_action_map = {
        "find_and_reply_to_new_posts": TwitterAction.NEW_POSTS_DISCOVERED,
        "find_user_activity": TwitterAction.USER_POSTS_DISCOVERED,
        "find_and_reply_to_engagement": TwitterAction.ENGAGEMENT_DISCOVERED,
        "analyze": TwitterAction.ANALYSIS,
    }

    # Determine success status based on message
    success = "partial" if message else "complete"

    log_entry = TweetLog(
        action=job_action_map[job_name],
        trigger=triggered_by,  # type: ignore
        handle=username,
        initiated=initiated,
        completed=datetime.now(UTC),
        success=success,  # type: ignore
        details=results,  # type: ignore - will be validated by Pydantic
        message=message,
    )

    # Append to JSONL file
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(log_entry.model_dump_json() + "\n")


def log_job_error(
    username: str,
    job_name: str,
    triggered_by: str,
    initiated: datetime,
    error_msg: str,
    partial_results: dict[str, Any] | None = None
) -> None:
    """Log when a background job encounters an error. Writes to both user log and error log."""
    from backend.utlils.utils import error

    log_path = get_user_log_path(username)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Map job_name to TwitterAction
    job_action_map = {
        "find_and_reply_to_new_posts": TwitterAction.NEW_POSTS_DISCOVERED,
        "find_user_activity": TwitterAction.USER_POSTS_DISCOVERED,
        "find_and_reply_to_engagement": TwitterAction.ENGAGEMENT_DISCOVERED,
        "analyze": TwitterAction.ANALYSIS,
    }

    # Create error message dict
    error_message = {"error": error_msg}

    # Use partial_results as details if provided, otherwise create empty results
    details = partial_results if partial_results else {}

    log_entry = TweetLog(
        action=job_action_map[job_name],
        trigger=triggered_by,  # type: ignore
        handle=username,
        initiated=initiated,
        completed=datetime.now(UTC),
        success="error",  # type: ignore
        details=details,  # type: ignore - will be validated by Pydantic
        message=error_message,
    )

    # Write to user log
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(log_entry.model_dump_json() + "\n")

    # Also write to error log
    error(
        f"Job {job_name} failed for @{username}: {error_msg}",
        critical=False,
        username=username,
    )




# API Router
router = APIRouter(prefix="/logs", tags=["logs"])


class LogQueryParams(BaseModel):
    limit: int | None = None



@router.get("/{username}")
def get_logs(username: str, limit: int = 10) -> dict[str, Any]:
    """Get the last N logs in chronological write order."""
    log_path = get_user_log_path(username)

    if not log_path.exists():
        return {"entries": []}

    entries = []
    try:
        with open(log_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except Exception:
        return {"entries": []}

    # Return most recent first
    return {"entries": entries[-limit:][::-1]}


@router.get("/grouped/{username}")
def get_grouped_logs(username: str, limit: int = 10) -> dict[str, Any]:
    """Get the last N logs for each action type, grouped by action."""
    log_path = get_user_log_path(username)

    if not log_path.exists():
        return {"grouped": {}}

    # Group entries by action type
    grouped: dict[str, list[dict[str, Any]]] = {}

    try:
        with open(log_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entry = json.loads(line)
                        action = entry.get("action", "unknown")

                        if action not in grouped:
                            grouped[action] = []
                        grouped[action].append(entry)
                    except json.JSONDecodeError:
                        continue
    except Exception:
        return {"grouped": {}}

    # Return last N entries for each action type, most recent first
    result = {}
    for action, entries in grouped.items():
        result[action] = entries[-limit:][::-1]

    return {"grouped": result}


@router.get("/errors/user/{username}")
def get_errors_by_user(username: str, limit: int = 50) -> dict[str, Any]:
    """Get error logs filtered by user_id."""
    from backend.utlils.utils import CACHE_DIR

    errors_log_path = CACHE_DIR / "errors.jsonl"

    if not errors_log_path.exists():
        return {"errors": []}

    matching_errors = []
    try:
        with open(errors_log_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entry = json.loads(line)
                        if entry.get("user_id") == username:
                            matching_errors.append(entry)
                    except json.JSONDecodeError:
                        continue
    except Exception:
        return {"errors": []}

    # Return most recent first
    return {"errors": matching_errors[-limit:][::-1]}


@router.get("/errors/function/{function_name}")
def get_errors_by_function(function_name: str, limit: int = 50) -> dict[str, Any]:
    """Get error logs filtered by calling_function."""
    from backend.utlils.utils import CACHE_DIR

    errors_log_path = CACHE_DIR / "errors.jsonl"

    if not errors_log_path.exists():
        return {"errors": []}

    matching_errors = []
    try:
        with open(errors_log_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entry = json.loads(line)
                        if entry.get("calling_function") == function_name:
                            matching_errors.append(entry)
                    except json.JSONDecodeError:
                        continue
    except Exception:
        return {"errors": []}

    # Return most recent first
    return {"errors": matching_errors[-limit:][::-1]}


@router.get("/errors/platform/{platform}")
def get_errors_by_platform(platform: str, limit: int = 50) -> dict[str, Any]:
    """Get error logs filtered by platform."""
    from backend.utlils.utils import CACHE_DIR

    errors_log_path = CACHE_DIR / "errors.jsonl"

    if not errors_log_path.exists():
        return {"errors": []}

    matching_errors = []
    try:
        with open(errors_log_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entry = json.loads(line)
                        if entry.get("platform") == platform:
                            matching_errors.append(entry)
                    except json.JSONDecodeError:
                        continue
    except Exception:
        return {"errors": []}

    # Return most recent first
    return {"errors": matching_errors[-limit:][::-1]}


@router.get("/errors/time-range")
def get_errors_by_time_range(
    start_time: str | None = None,
    end_time: str | None = None,
    limit: int = 50
) -> dict[str, Any]:
    """
    Get error logs filtered by time range.

    Args:
        start_time: ISO format datetime string (e.g., "2025-12-25T00:00:00Z")
        end_time: ISO format datetime string (e.g., "2025-12-25T23:59:59Z")
        limit: Maximum number of errors to return
    """
    from backend.utlils.utils import CACHE_DIR

    errors_log_path = CACHE_DIR / "errors.jsonl"

    if not errors_log_path.exists():
        return {"errors": []}

    # Parse time range
    start_dt = None
    end_dt = None

    if start_time:
        try:
            start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        except ValueError:
            return {"error": "Invalid start_time format. Use ISO format (e.g., 2025-12-25T00:00:00Z)"}

    if end_time:
        try:
            end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        except ValueError:
            return {"error": "Invalid end_time format. Use ISO format (e.g., 2025-12-25T23:59:59Z)"}

    matching_errors = []
    try:
        with open(errors_log_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entry = json.loads(line)
                        timestamp_str = entry.get("timestamp")
                        if timestamp_str:
                            entry_dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))

                            # Check if within time range
                            if start_dt and entry_dt < start_dt:
                                continue
                            if end_dt and entry_dt > end_dt:
                                continue

                            matching_errors.append(entry)
                    except (json.JSONDecodeError, ValueError):
                        continue
    except Exception:
        return {"errors": []}

    # Return most recent first
    return {"errors": matching_errors[-limit:][::-1]}


@router.get("/errors/all")
def get_all_errors(limit: int = 50) -> dict[str, Any]:
    """Get all error logs with optional limit."""
    from backend.utlils.utils import CACHE_DIR

    errors_log_path = CACHE_DIR / "errors.jsonl"

    if not errors_log_path.exists():
        return {"errors": []}

    all_errors = []
    try:
        with open(errors_log_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        all_errors.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except Exception:
        return {"errors": []}

    # Return most recent first
    return {"errors": all_errors[-limit:][::-1]}


@router.post("/{username}/append_log")
def log_tweet_action(username: str, action: TwitterAction, tweet_id: str, metadata: dict[str, Any] | None = None) -> None:
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

