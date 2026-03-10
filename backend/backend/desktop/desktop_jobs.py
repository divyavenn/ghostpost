"""
Desktop Jobs API.

This queue is intentionally simple and in-memory for now:
- Web app queues work
- Desktop CLI polls and claims jobs
- CLI reports completion/failure

The API also includes token-based CLI association so one desktop worker can be
linked to one Ghostpost account handle.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import secrets
from typing import Any

try:
    from datetime import UTC
except ImportError:
    from datetime import timezone
    UTC = timezone.utc

import uuid
from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel

from backend.desktop.pairing import resolve_daemon_token
from backend.desktop.task_types import (
    DesktopTaskType,
    is_timeline_collection_task,
    normalize_task_type,
    supported_task_catalog,
)
from backend.utlils.supabase_client import (
    get_twitter_profile,
    get_twitter_profiles_for_user,
    get_user_by_id,
    update_user,
)
from backend.utlils.utils import notify, read_user_info, write_user_info

router = APIRouter(prefix="/desktop-jobs", tags=["desktop"])


@dataclass
class DesktopJob:
    id: str
    username: str
    job_type: str
    params: dict
    created_at: datetime
    status: str
    result: dict | None = None
    error: str | None = None
    completed_at: datetime | None = None
    worker_name: str | None = None


@dataclass
class DesktopToken:
    token_hash: str
    username: str
    client_name: str
    created_at: datetime
    expires_at: datetime
    revoked: bool = False
    last_seen_at: datetime | None = None


class DesktopTokenIssueRequest(BaseModel):
    client_name: str = "ghostpost-desktop"
    days_valid: int = 30


class DesktopTokenIssueResponse(BaseModel):
    token: str
    client_name: str
    username: str
    expires_at: str
    note: str


class JobResultRequest(BaseModel):
    result: dict[str, Any] = {}
    reported_twitter_handle: str | None = None


class JobFailRequest(BaseModel):
    error: str = "Unknown error"
    reported_twitter_handle: str | None = None


class JobStartRequest(BaseModel):
    worker_name: str | None = None
    reported_twitter_handle: str | None = None


class QueueDesktopTaskRequest(BaseModel):
    username: str
    task_type: str
    params: dict[str, Any] = {}


# In-memory queue/auth state (MVP).
desktop_jobs: dict[str, DesktopJob] = {}
desktop_auth_tokens: dict[str, DesktopToken] = {}


@dataclass
class DesktopIdentity:
    username: str
    user_id: str | None
    device_id: str | None
    auth_mode: str
    device_accounts: dict[str, Any]


def create_desktop_job(username: str, job_type: str, params: dict) -> str:
    """Queue a new desktop job."""
    normalized_task_type = normalize_task_type(job_type).value
    job_id = str(uuid.uuid4())
    job = DesktopJob(
        id=job_id,
        username=username,
        job_type=normalized_task_type,
        params=params,
        created_at=datetime.now(UTC),
        status="pending",
    )
    desktop_jobs[job_id] = job
    notify(f"📱 Queued desktop job {job_id} ({normalized_task_type}) for @{username}")
    return job_id


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _resolve_username_from_token(raw_token: str) -> str:
    token_hash = _hash_token(raw_token)
    token = desktop_auth_tokens.get(token_hash)
    now = datetime.now(UTC)

    if not token:
        raise HTTPException(status_code=401, detail="Invalid desktop token")
    if token.revoked:
        raise HTTPException(status_code=401, detail="Desktop token revoked")
    if token.expires_at < now:
        raise HTTPException(status_code=401, detail="Desktop token expired")

    token.last_seen_at = now
    return token.username


def _normalize_handle(handle: str | None) -> str | None:
    if not handle:
        return None
    clean = handle.strip().lower()
    if clean.startswith("@"):
        clean = clean[1:]
    if not clean:
        return None
    return clean


def _is_x_task_type(job_type: str) -> bool:
    return job_type in {
        DesktopTaskType.POST_X.value,
        DesktopTaskType.POST_ALL.value,
        DesktopTaskType.REPLY_X.value,
        DesktopTaskType.SEARCH_X.value,
        DesktopTaskType.GET_THREAD_X.value,
        DesktopTaskType.FETCH_HOME_TIMELINE_X.value,
        DesktopTaskType.FETCH_USER_TIMELINE_X.value,
        DesktopTaskType.DEEP_SCRAPE_THREAD_X.value,
        DesktopTaskType.SHALLOW_SCRAPE_THREAD_X.value,
        DesktopTaskType.SCRAPE_TWEETS_X.value,
    }


def _resolve_identity(raw_token: str) -> DesktopIdentity:
    # Backwards-compatible path: legacy issued desktop token
    try:
        username = _resolve_username_from_token(raw_token)
        return DesktopIdentity(
            username=username,
            user_id=None,
            device_id=None,
            auth_mode="legacy_token",
            device_accounts={},
        )
    except HTTPException:
        pass

    # Preferred path: daemon pairing token
    resolved = resolve_daemon_token(raw_token)
    user_id = resolved.get("user_id")
    profiles = get_twitter_profiles_for_user(user_id) if user_id else []
    if not profiles:
        raise HTTPException(status_code=403, detail="No linked X profile for paired daemon user")
    username = profiles[0]["handle"]
    device = resolved.get("device") or {}
    return DesktopIdentity(
        username=username,
        user_id=user_id,
        device_id=resolved.get("device_id"),
        auth_mode="paired_daemon",
        device_accounts=device.get("accounts") or {},
    )


def _assert_x_account_match(
    identity: DesktopIdentity,
    job_type: str,
    reported_handle: str | None = None,
    expected_handle: str | None = None,
) -> None:
    if not _is_x_task_type(job_type):
        return

    expected = _normalize_handle(expected_handle or identity.username)
    if not expected:
        return

    from_device = None
    twitter_state = identity.device_accounts.get("twitter") if identity.device_accounts else None
    if isinstance(twitter_state, dict):
        from_device = twitter_state.get("account")

    actual = _normalize_handle(reported_handle or from_device)
    if not actual:
        if identity.auth_mode == "paired_daemon":
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "ACCOUNT_LOGIN_REQUIRED",
                    "expected_twitter_handle": f"@{expected}",
                    "reported_twitter_handle": None,
                },
            )
        return

    if actual != expected:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "ACCOUNT_MISMATCH",
                "expected_twitter_handle": f"@{expected}",
                "reported_twitter_handle": f"@{actual}",
            },
        )


def _record_desktop_auth_alert(
    username: str,
    code: str,
    expected_handle: str,
    reported_handle: str | None = None,
) -> None:
    try:
        profile = get_twitter_profile(username)
        if not profile:
            return
        user_id = profile.get("user_id")
        if not user_id:
            return
        user = get_user_by_id(user_id)
        if not user:
            return

        survey_data = user.get("survey_data") or {}
        if code == "ACCOUNT_MISMATCH":
            message = (
                "Desktop daemon X account does not match your Ghostpost-linked account. "
                "Log in to the correct X account on this machine, then retry."
            )
        else:
            message = (
                "Desktop daemon could not verify the expected X account. "
                "Please log in to X on this machine and retry."
            )

        survey_data["desktop_auth_alert"] = {
            "code": code,
            "message": message,
            "expected_twitter_handle": expected_handle,
            "reported_twitter_handle": reported_handle,
            "created_at": datetime.now(UTC).isoformat(),
        }
        update_user(user_id, {"survey_data": survey_data})
    except Exception as exc:
        notify(f"⚠️ Failed to persist desktop auth alert for @{username}: {exc}")


def _auth_alert_state_changed(
    job: DesktopJob,
    code: str,
    expected_handle: str,
    reported_handle: str | None = None,
) -> bool:
    previous = job.params.get("_auth_block")
    current = {
        "code": code,
        "expected_twitter_handle": expected_handle,
        "reported_twitter_handle": reported_handle,
    }
    if previous == current:
        return False
    job.params["_auth_block"] = current
    return True


def _claim_pending_jobs(identity: DesktopIdentity, worker_name: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    pending: list[dict[str, Any]] = []
    claimed = 0
    username = identity.username
    for job in sorted(desktop_jobs.values(), key=lambda j: j.created_at):
        if job.username != username or job.status != "pending":
            continue
        expected_handle = str(job.params.get("expected_twitter_handle") or username)
        try:
            _assert_x_account_match(identity, job.job_type, expected_handle=expected_handle)
            if job.params.get("_auth_block"):
                job.params.pop("_auth_block", None)
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, dict) else {}
            code = str(detail.get("code", "ACCOUNT_LOGIN_REQUIRED"))
            if code in {"ACCOUNT_MISMATCH", "ACCOUNT_LOGIN_REQUIRED"}:
                expected = str(detail.get("expected_twitter_handle", f"@{expected_handle}"))
                reported = detail.get("reported_twitter_handle")
                if _auth_alert_state_changed(job, code=code, expected_handle=expected, reported_handle=reported):
                    _record_desktop_auth_alert(
                        username=username,
                        code=code,
                        expected_handle=expected,
                        reported_handle=reported,
                    )
                continue
            raise
        pending.append({
            "id": job.id,
            "job_type": job.job_type,
            "params": job.params,
            "created_at": job.created_at.isoformat(),
            "claimed_by_device_id": identity.device_id,
            "claimed_by_auth_mode": identity.auth_mode,
        })
        job.status = "running"
        device_suffix = f" [{identity.device_id}]" if identity.device_id else ""
        job.worker_name = f"{worker_name or 'token-auth'}{device_suffix}"

        if job.job_type in {DesktopTaskType.POST_X.value, DesktopTaskType.POST_ALL.value}:
            draft_id = str(job.params.get("draft_id") or "")
            if draft_id:
                _update_post_queue_item_status(username, draft_id, "running")
        elif job.job_type == DesktopTaskType.SCRAPE_TWEETS_X.value:
            from backend.twitter.twitter_jobs import _update_job_status
            _update_job_status(
                username,
                "find_and_reply_to_new_posts",
                "running",
                "scraping",
                progress={"current": 25, "total": 100},
                details="Desktop worker is scraping",
            )

        claimed += 1
        if claimed >= limit:
            break

    if pending:
        notify(f"📤 Claimed {len(pending)} desktop job(s) for @{username}")
    return pending


def _load_post_queue(username: str) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    user_info = read_user_info(username)
    if not user_info:
        return None, []
    return user_info, list(user_info.get("post_queue", []))


def _save_post_queue(user_info: dict[str, Any], queue: list[dict[str, Any]]) -> None:
    user_info["post_queue"] = queue
    write_user_info(user_info)


def _find_post_queue_item(username: str, draft_id: str) -> dict[str, Any] | None:
    _user_info, queue = _load_post_queue(username)
    for item in queue:
        if item.get("draft_id") == draft_id:
            return item
    return None


def _update_post_queue_item_status(
    username: str,
    draft_id: str,
    status: str,
    *,
    error: str | None = None,
    result: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    user_info, queue = _load_post_queue(username)
    if not user_info:
        return None

    updated_item = None
    now_iso = datetime.now(UTC).isoformat()
    for item in queue:
        if item.get("draft_id") == draft_id:
            item["status"] = status
            item["updated_at"] = now_iso
            if error:
                item["last_error"] = error
            if result:
                item["result"] = result
                posted_tweet_id = result.get("posted_tweet_id") or result.get("tweet_id")
                if posted_tweet_id:
                    item["posted_tweet_id"] = posted_tweet_id
            if status == "completed":
                item["completed_at"] = now_iso
            updated_item = item
            break

    if updated_item:
        _save_post_queue(user_info, queue)
    return updated_item


async def _complete_job_internal(
    job_id: str,
    result: dict[str, Any],
    expected_username: str | None = None,
    identity: DesktopIdentity | None = None,
    reported_twitter_handle: str | None = None,
) -> dict[str, Any]:
    if job_id not in desktop_jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = desktop_jobs[job_id]
    if expected_username and job.username != expected_username:
        raise HTTPException(status_code=403, detail="Job does not belong to this desktop session")
    if identity:
        expected_handle = str(job.params.get("expected_twitter_handle") or job.username)
        _assert_x_account_match(identity, job.job_type, reported_twitter_handle, expected_handle)

    job.status = "completed"
    job.result = result
    job.completed_at = datetime.now(UTC)
    notify(f"✅ Desktop job {job_id} completed for @{job.username}")

    await process_job_result(job)
    return {"status": "success", "job_id": job_id}


async def _start_job_internal(
    job_id: str,
    expected_username: str | None = None,
    worker_name: str | None = None,
    identity: DesktopIdentity | None = None,
    reported_twitter_handle: str | None = None,
) -> dict[str, Any]:
    if job_id not in desktop_jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = desktop_jobs[job_id]
    if expected_username and job.username != expected_username:
        raise HTTPException(status_code=403, detail="Job does not belong to this desktop session")
    if identity:
        expected_handle = str(job.params.get("expected_twitter_handle") or job.username)
        _assert_x_account_match(identity, job.job_type, reported_twitter_handle, expected_handle)

    if job.status in {"completed", "failed"}:
        return {"status": job.status, "job_id": job_id}

    job.status = "running"
    if worker_name:
        job.worker_name = worker_name

    if job.job_type in {DesktopTaskType.POST_X.value, DesktopTaskType.POST_ALL.value}:
        draft_id = str(job.params.get("draft_id") or "")
        if draft_id:
            _update_post_queue_item_status(job.username, draft_id, "running")
    elif job.job_type == DesktopTaskType.SCRAPE_TWEETS_X.value:
        from backend.twitter.twitter_jobs import _update_job_status
        _update_job_status(
            job.username,
            "find_and_reply_to_new_posts",
            "running",
            "scraping",
            progress={"current": 20, "total": 100},
            details="Desktop execution started",
        )

    notify(f"▶️ Desktop job {job_id} marked running for @{job.username}")
    return {"status": "running", "job_id": job_id}


async def _fail_job_internal(
    job_id: str,
    error_message: str,
    expected_username: str | None = None,
    identity: DesktopIdentity | None = None,
    reported_twitter_handle: str | None = None,
) -> dict[str, Any]:
    if job_id not in desktop_jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = desktop_jobs[job_id]
    if expected_username and job.username != expected_username:
        raise HTTPException(status_code=403, detail="Job does not belong to this desktop session")
    if identity:
        expected_handle = str(job.params.get("expected_twitter_handle") or job.username)
        _assert_x_account_match(identity, job.job_type, reported_twitter_handle, expected_handle)

    job.status = "failed"
    job.error = error_message
    job.completed_at = datetime.now(UTC)
    notify(f"❌ Desktop job {job_id} failed for @{job.username}: {error_message}")

    if job.job_type in {DesktopTaskType.POST_X.value, DesktopTaskType.POST_ALL.value}:
        draft_id = str(job.params.get("draft_id") or "")
        if draft_id:
            _update_post_queue_item_status(job.username, draft_id, "failed", error=error_message)
    elif job.job_type == DesktopTaskType.SCRAPE_TWEETS_X.value:
        from backend.twitter.twitter_jobs import _update_job_status
        _update_job_status(
            job.username,
            "find_and_reply_to_new_posts",
            "error",
            "error",
            progress={"current": 0, "total": 100},
            details="Desktop scrape failed",
            error_msg=error_message,
        )

    return {"status": "acknowledged", "job_id": job_id}


@router.post("/auth/issue", response_model=DesktopTokenIssueResponse)
async def issue_desktop_token(
    username: str = Query(..., description="Ghostpost handle to bind this desktop client to"),
    payload: DesktopTokenIssueRequest | None = None,
) -> DesktopTokenIssueResponse:
    """Issue a desktop token to associate a CLI worker with one Ghostpost account."""
    user_info = read_user_info(username)
    if not user_info:
        raise HTTPException(status_code=404, detail="User not found")

    req = payload or DesktopTokenIssueRequest()
    now = datetime.now(UTC)
    expires_at = now + timedelta(days=max(1, min(req.days_valid, 90)))
    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw_token)

    desktop_auth_tokens[token_hash] = DesktopToken(
        token_hash=token_hash,
        username=username,
        client_name=req.client_name,
        created_at=now,
        expires_at=expires_at,
    )
    notify(f"🔐 Issued desktop token for @{username} ({req.client_name})")

    return DesktopTokenIssueResponse(
        token=raw_token,
        client_name=req.client_name,
        username=username,
        expires_at=expires_at.isoformat(),
        note="Store this token securely in the desktop CLI. It will not be shown again.",
    )


@router.get("/auth/verify")
async def verify_desktop_token(x_desktop_token: str = Header(...)) -> dict[str, Any]:
    identity = _resolve_identity(x_desktop_token)
    return {
        "ok": True,
        "username": identity.username,
        "user_id": identity.user_id,
        "device_id": identity.device_id,
        "auth_mode": identity.auth_mode,
    }


@router.get("/task-types")
async def get_supported_task_types() -> dict[str, Any]:
    catalog = supported_task_catalog()
    return {"task_types": catalog, "count": len(catalog)}


@router.post("/tasks")
async def queue_desktop_task(payload: QueueDesktopTaskRequest) -> dict[str, Any]:
    user_info = read_user_info(payload.username)
    if not user_info:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        normalized = normalize_task_type(payload.task_type)
        params = dict(payload.params or {})
        if _is_x_task_type(normalized.value):
            params.setdefault("expected_twitter_handle", payload.username)
        job_id = create_desktop_job(payload.username, normalized.value, params)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "status": "queued",
        "job_id": job_id,
        "username": payload.username,
        "task_type": normalized.value,
    }


@router.get("/tasks/pending")
async def get_pending_jobs_for_token(
    x_desktop_token: str = Header(...),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[dict[str, Any]]:
    identity = _resolve_identity(x_desktop_token)
    return _claim_pending_jobs(identity, worker_name="token-auth", limit=limit)


@router.post("/tasks/{job_id}/complete")
async def complete_job_for_token(
    job_id: str,
    payload: JobResultRequest,
    x_desktop_token: str = Header(...),
) -> dict[str, Any]:
    identity = _resolve_identity(x_desktop_token)
    try:
        return await _complete_job_internal(
            job_id,
            payload.result,
            expected_username=identity.username,
            identity=identity,
            reported_twitter_handle=payload.reported_twitter_handle,
        )
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        code = str(detail.get("code", ""))
        if code in {"ACCOUNT_MISMATCH", "ACCOUNT_LOGIN_REQUIRED"}:
            _record_desktop_auth_alert(
                username=identity.username,
                code=code,
                expected_handle=str(detail.get("expected_twitter_handle", f"@{identity.username}")),
                reported_handle=detail.get("reported_twitter_handle"),
            )
        raise


@router.post("/tasks/{job_id}/start")
async def start_job_for_token(
    job_id: str,
    payload: JobStartRequest | None = None,
    x_desktop_token: str = Header(...),
) -> dict[str, Any]:
    identity = _resolve_identity(x_desktop_token)
    req = payload or JobStartRequest()
    try:
        return await _start_job_internal(
            job_id,
            expected_username=identity.username,
            worker_name=req.worker_name,
            identity=identity,
            reported_twitter_handle=req.reported_twitter_handle,
        )
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        code = str(detail.get("code", ""))
        if code in {"ACCOUNT_MISMATCH", "ACCOUNT_LOGIN_REQUIRED"}:
            _record_desktop_auth_alert(
                username=identity.username,
                code=code,
                expected_handle=str(detail.get("expected_twitter_handle", f"@{identity.username}")),
                reported_handle=detail.get("reported_twitter_handle"),
            )
        raise


@router.post("/tasks/{job_id}/fail")
async def fail_job_for_token(
    job_id: str,
    payload: JobFailRequest,
    x_desktop_token: str = Header(...),
) -> dict[str, Any]:
    identity = _resolve_identity(x_desktop_token)
    try:
        return await _fail_job_internal(
            job_id,
            payload.error,
            expected_username=identity.username,
            identity=identity,
            reported_twitter_handle=payload.reported_twitter_handle,
        )
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        code = str(detail.get("code", ""))
        if code in {"ACCOUNT_MISMATCH", "ACCOUNT_LOGIN_REQUIRED"}:
            _record_desktop_auth_alert(
                username=identity.username,
                code=code,
                expected_handle=str(detail.get("expected_twitter_handle", f"@{identity.username}")),
                reported_handle=detail.get("reported_twitter_handle"),
            )
        raise


@router.get("/{username}/pending")
async def get_pending_jobs(username: str) -> list[dict[str, Any]]:
    """Legacy poll endpoint (username-only)."""
    identity = DesktopIdentity(
        username=username,
        user_id=None,
        device_id=None,
        auth_mode="legacy_unauthenticated",
        device_accounts={},
    )
    return _claim_pending_jobs(identity)


@router.post("/{job_id}/complete")
async def complete_job(job_id: str, result: dict[str, Any]) -> dict[str, Any]:
    """Legacy completion endpoint."""
    return await _complete_job_internal(job_id, result)


@router.post("/{job_id}/start")
async def start_job(job_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Legacy start/running endpoint."""
    worker_name = None
    if payload:
        worker_name = payload.get("worker_name")
    return await _start_job_internal(job_id, worker_name=worker_name)


@router.post("/{job_id}/fail")
async def fail_job(job_id: str, error_data: dict[str, Any]) -> dict[str, Any]:
    """Legacy fail endpoint."""
    return await _fail_job_internal(job_id, str(error_data.get("error", "Unknown error")))


@router.get("/{username}/status")
async def get_job_status(username: str) -> dict[str, Any]:
    user_jobs = [job for job in desktop_jobs.values() if job.username == username]
    return {
        "total": len(user_jobs),
        "pending": sum(1 for j in user_jobs if j.status == "pending"),
        "running": sum(1 for j in user_jobs if j.status == "running"),
        "completed": sum(1 for j in user_jobs if j.status == "completed"),
        "failed": sum(1 for j in user_jobs if j.status == "failed"),
        "jobs": [
            {
                "id": j.id,
                "job_type": j.job_type,
                "status": j.status,
                "created_at": j.created_at.isoformat(),
                "completed_at": j.completed_at.isoformat() if j.completed_at else None,
                "worker_name": j.worker_name,
            }
            for j in sorted(user_jobs, key=lambda x: x.created_at, reverse=True)[:50]
        ],
    }


@router.delete("/{job_id}")
async def delete_job(job_id: str) -> dict[str, Any]:
    if job_id not in desktop_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    del desktop_jobs[job_id]
    return {"status": "deleted", "job_id": job_id}


async def process_job_result(job: DesktopJob):
    """
    Process completed job results.
    """
    if is_timeline_collection_task(job.job_type):
        from backend.data.twitter.edit_cache import write_to_cache
        from backend.twitter.twitter_jobs import _reset_job_to_idle, _update_job_status

        tweets = (job.result or {}).get("tweets", [])
        if tweets:
            await write_to_cache(tweets, f"Desktop {job.job_type}", username=job.username)
            notify(f"💾 Wrote {len(tweets)} tweet(s) to cache for @{job.username}")

        # Keep existing loading overlay flow alive for frontend by marking the scrape job complete.
        if job.job_type == DesktopTaskType.SCRAPE_TWEETS_X.value:
            reply_count = 0
            user_info = read_user_info(job.username) or {}
            account_type = user_info.get("account_type", "trial")

            if account_type == "premium":
                _update_job_status(
                    job.username,
                    "find_and_reply_to_new_posts",
                    "running",
                    "generating",
                    progress={"current": 75, "total": 100},
                    details="Generating replies",
                )
                try:
                    from backend.twitter.generate_replies import generate_replies
                    generated = await generate_replies(username=job.username, overwrite=False)
                    reply_count = sum(1 for t in generated if t.get("generated_replies"))
                except Exception as generation_error:
                    notify(f"⚠️ Reply generation after desktop scrape failed: {generation_error}")

            _update_job_status(
                job.username,
                "find_and_reply_to_new_posts",
                "complete",
                "complete",
                progress={"current": 100, "total": 100},
                details=f"Desktop scrape complete ({len(tweets)} tweets)",
                results={"tweets_scraped": len(tweets), "replies_generated": reply_count},
            )
            import asyncio
            asyncio.create_task(_reset_job_to_idle(job.username, "find_and_reply_to_new_posts"))

    elif job.job_type == DesktopTaskType.POST_X.value:
        from backend.data.twitter.comments_cache import delete_comment
        from backend.data.twitter.edit_cache import delete_tweet
        from backend.data.twitter.posted_tweets_cache import add_posted_tweet

        draft_id = str(job.params.get("draft_id") or "")
        if not draft_id:
            return

        item = _update_post_queue_item_status(job.username, draft_id, "completed", result=job.result or {})
        if not item:
            return

        posted_tweet_id = (job.result or {}).get("posted_tweet_id") or (job.result or {}).get("tweet_id")
        if posted_tweet_id:
            # Persist in posted_tweets cache so the "Posted" tab can show it with metrics.
            add_posted_tweet(
                username=job.username,
                posted_tweet_id=str(posted_tweet_id),
                text=item.get("reply", ""),
                original_tweet_url=item.get("original_tweet_url", ""),
                responding_to_handle=item.get("responding_to", ""),
                replying_to_pfp=item.get("replying_to_pfp", ""),
                response_to_thread=item.get("response_to_thread", []) or [],
                in_reply_to_id=item.get("tweet_id_to_reply"),
                post_type="comment_reply" if item.get("type") == "comment_reply" else "reply",
            )

        # Remove source item from discovered/comments caches once successfully posted.
        if item.get("type") == "comment_reply":
            delete_comment(job.username, item.get("response_to", ""))
        else:
            await delete_tweet(job.username, item.get("response_to", ""), log_deletion=False)

    elif job.job_type == DesktopTaskType.POST_ALL.value:
        draft_id = str(job.params.get("draft_id") or "")
        if not draft_id:
            return
        _update_post_queue_item_status(job.username, draft_id, "completed", result=job.result or {})


def cleanup_old_jobs(max_age_hours: int = 24):
    """Clean up old completed/failed jobs."""
    now = datetime.now(UTC)
    to_delete: list[str] = []
    for job_id, job in desktop_jobs.items():
        if job.status not in {"completed", "failed"} or not job.completed_at:
            continue
        age_hours = (now - job.completed_at).total_seconds() / 3600
        if age_hours > max_age_hours:
            to_delete.append(job_id)
    for job_id in to_delete:
        del desktop_jobs[job_id]
    if to_delete:
        notify(f"🧹 Cleaned up {len(to_delete)} old desktop job(s)")

    return len(to_delete)
