"""Desktop daemon pairing and account sync APIs."""

from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import secrets
import threading
from typing import Any, Literal
import uuid

try:
    from datetime import UTC
except ImportError:
    from datetime import timezone
    UTC = timezone.utc

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from backend.config import CACHE_DIR
from backend.auth.supabase_routes import verify_supabase_token
from backend.utlils.supabase_client import get_twitter_profiles_for_user, get_user_by_id, update_user
from backend.utlils.utils import notify

router = APIRouter(prefix="/desktop", tags=["desktop-pairing"])

PAIRING_STATE_FILE = CACHE_DIR / "desktop_pairing_state.json"
_STATE_LOCK = threading.Lock()

PLATFORMS = ("twitter", "substack", "linkedin", "reddit")


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _load_state() -> dict[str, Any]:
    if not PAIRING_STATE_FILE.exists():
        return {"pairing_codes": {}, "devices": {}, "daemon_tokens": {}}
    try:
        import json

        data = json.loads(PAIRING_STATE_FILE.read_text())
        if not isinstance(data, dict):
            return {"pairing_codes": {}, "devices": {}, "daemon_tokens": {}}
        data.setdefault("pairing_codes", {})
        data.setdefault("devices", {})
        data.setdefault("daemon_tokens", {})
        return data
    except Exception:
        return {"pairing_codes": {}, "devices": {}, "daemon_tokens": {}}


def _save_state(state: dict[str, Any]) -> None:
    import json

    PAIRING_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = PAIRING_STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2))
    tmp.replace(PAIRING_STATE_FILE)


def _normalize_platforms(platforms: list[str] | None) -> list[str]:
    if not platforms:
        return ["twitter"]
    normalized: list[str] = []
    for value in platforms:
        key = value.strip().lower()
        if key in PLATFORMS and key not in normalized:
            normalized.append(key)
    return normalized or ["twitter"]


def _get_user_profile_summary(user_id: str, email_fallback: str | None = None) -> dict[str, Any]:
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    profiles = get_twitter_profiles_for_user(user_id)
    twitter_handle = profiles[0]["handle"] if profiles else None
    twitter_username = profiles[0].get("username") if profiles else None
    survey_data = user.get("survey_data") or {}
    platforms = _normalize_platforms(survey_data.get("interested_socials"))

    return {
        "user_id": user_id,
        "email": user.get("email") or email_fallback,
        "account_type": user.get("account_type", "trial"),
        "twitter_handle": twitter_handle,
        "twitter_username": twitter_username,
        "platform_preferences": platforms,
        "survey_data": survey_data,
    }


def _authenticate_daemon_token(state: dict[str, Any], raw_token: str) -> tuple[dict[str, Any], dict[str, Any]]:
    token_hash = _hash_token(raw_token)
    token_record = state["daemon_tokens"].get(token_hash)
    now = datetime.now(UTC)

    if not token_record:
        raise HTTPException(status_code=401, detail="Invalid daemon token")
    if token_record.get("revoked"):
        raise HTTPException(status_code=401, detail="Daemon token revoked")

    expires_at_raw = token_record.get("expires_at")
    if expires_at_raw:
        expires_at = datetime.fromisoformat(expires_at_raw)
        if expires_at < now:
            raise HTTPException(status_code=401, detail="Daemon token expired")

    device_id = token_record.get("device_id")
    device = state["devices"].get(device_id)
    if not device or device.get("revoked"):
        raise HTTPException(status_code=401, detail="Daemon device revoked")

    token_record["last_seen_at"] = _now_iso()
    device["last_seen_at"] = _now_iso()
    return token_record, device


def resolve_daemon_token(raw_token: str) -> dict[str, Any]:
    """Resolve daemon token into identity metadata and refresh heartbeat timestamps."""
    with _STATE_LOCK:
        state = _load_state()
        token_record, device = _authenticate_daemon_token(state, raw_token)
        _save_state(state)
    return {
        "user_id": token_record["user_id"],
        "device_id": device["id"],
        "device": device,
        "token_record": token_record,
    }


class DownloadLinksResponse(BaseModel):
    macos: str
    windows: str
    linux: str
    docs: str


class PairingStartResponse(BaseModel):
    pair_code: str
    expires_at: str
    expires_in_seconds: int
    user_info: dict[str, Any]


class PairingStartRequest(BaseModel):
    expires_minutes: int = Field(default=10, ge=2, le=30)


class PairingCompleteRequest(BaseModel):
    pair_code: str
    device: dict[str, Any]


class PairingCompleteResponse(BaseModel):
    daemon_token: str
    token_type: Literal["Bearer"] = "Bearer"
    expires_at: str
    device: dict[str, Any]
    user_info: dict[str, Any]
    platform_preferences: list[str]


class PlatformPreferencesRequest(BaseModel):
    platforms: list[str]


class AccountState(BaseModel):
    status: Literal["logged_in", "logged_out", "unknown"] = "unknown"
    account: str | None = None


class AccountsSyncRequest(BaseModel):
    accounts: dict[str, AccountState]


@router.get("/download-links", response_model=DownloadLinksResponse)
async def get_download_links() -> DownloadLinksResponse:
    return DownloadLinksResponse(
        macos="https://github.com/ghostpost/daemon/releases/latest/download/ghostpost-daemon-macos.dmg",
        windows="https://github.com/ghostpost/daemon/releases/latest/download/ghostpost-daemon-windows.exe",
        linux="https://github.com/ghostpost/daemon/releases/latest/download/ghostpost-daemon-linux.AppImage",
        docs="https://github.com/ghostpost/daemon#readme",
    )


@router.post("/pairing/start", response_model=PairingStartResponse)
async def start_pairing(
    payload: PairingStartRequest,
    user_data: dict[str, Any] = Depends(verify_supabase_token),
) -> PairingStartResponse:
    user_id = user_data.get("sub")
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid user token")

    code = secrets.token_hex(3).upper()
    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=payload.expires_minutes)

    with _STATE_LOCK:
        state = _load_state()
        state["pairing_codes"][code] = {
            "code": code,
            "user_id": user_id,
            "email": user_data.get("email"),
            "created_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "used_at": None,
        }
        _save_state(state)

    user_info = _get_user_profile_summary(user_id, user_data.get("email"))
    notify(f"🔗 Created daemon pairing code for user {user_id}")
    return PairingStartResponse(
        pair_code=code,
        expires_at=expires_at.isoformat(),
        expires_in_seconds=payload.expires_minutes * 60,
        user_info=user_info,
    )


@router.post("/pairing/complete", response_model=PairingCompleteResponse)
async def complete_pairing(payload: PairingCompleteRequest) -> PairingCompleteResponse:
    code = payload.pair_code.strip().upper()
    if not code:
        raise HTTPException(status_code=400, detail="pair_code is required")

    with _STATE_LOCK:
        state = _load_state()
        code_record = state["pairing_codes"].get(code)
        if not code_record:
            raise HTTPException(status_code=404, detail="Invalid pairing code")
        if code_record.get("used_at"):
            raise HTTPException(status_code=409, detail="Pairing code already used")

        expires_at = datetime.fromisoformat(code_record["expires_at"])
        if expires_at < datetime.now(UTC):
            raise HTTPException(status_code=410, detail="Pairing code expired")

        user_id = code_record["user_id"]
        user_info = _get_user_profile_summary(user_id, code_record.get("email"))
        platforms = user_info["platform_preferences"]

        device_id = str(uuid.uuid4())
        raw_token = secrets.token_urlsafe(32)
        token_hash = _hash_token(raw_token)
        token_expires_at = datetime.now(UTC) + timedelta(days=30)

        device_payload = payload.device or {}
        device = {
            "id": device_id,
            "user_id": user_id,
            "device_name": str(device_payload.get("name") or "Ghostpost Desktop"),
            "os": str(device_payload.get("os") or "unknown"),
            "daemon_version": str(device_payload.get("daemon_version") or "unknown"),
            "machine_id": str(device_payload.get("machine_id") or ""),
            "platform_preferences": platforms,
            "accounts": {},
            "paired_at": _now_iso(),
            "last_seen_at": _now_iso(),
            "revoked": False,
            "token_hash": token_hash,
        }

        state["devices"][device_id] = device
        state["daemon_tokens"][token_hash] = {
            "token_hash": token_hash,
            "device_id": device_id,
            "user_id": user_id,
            "created_at": _now_iso(),
            "expires_at": token_expires_at.isoformat(),
            "last_seen_at": _now_iso(),
            "revoked": False,
        }
        code_record["used_at"] = _now_iso()
        _save_state(state)

    notify(f"✅ Daemon paired for user {user_id} device={device_id}")
    return PairingCompleteResponse(
        daemon_token=raw_token,
        expires_at=token_expires_at.isoformat(),
        device=device,
        user_info=user_info,
        platform_preferences=platforms,
    )


@router.get("/devices")
async def get_user_devices(user_data: dict[str, Any] = Depends(verify_supabase_token)) -> dict[str, Any]:
    user_id = user_data.get("sub")
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid user token")

    user_info = _get_user_profile_summary(user_id, user_data.get("email"))
    with _STATE_LOCK:
        state = _load_state()
        devices = [
            device
            for device in state["devices"].values()
            if device.get("user_id") == user_id
        ]
    devices.sort(key=lambda d: d.get("paired_at", ""), reverse=True)
    return {
        "devices": devices,
        "platform_preferences": user_info["platform_preferences"],
        "user_info": user_info,
    }


@router.post("/devices/{device_id}/revoke")
async def revoke_device(device_id: str, user_data: dict[str, Any] = Depends(verify_supabase_token)) -> dict[str, Any]:
    user_id = user_data.get("sub")
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid user token")

    with _STATE_LOCK:
        state = _load_state()
        device = state["devices"].get(device_id)
        if not device or device.get("user_id") != user_id:
            raise HTTPException(status_code=404, detail="Device not found")
        device["revoked"] = True
        token_hash = device.get("token_hash")
        if token_hash and token_hash in state["daemon_tokens"]:
            state["daemon_tokens"][token_hash]["revoked"] = True
        _save_state(state)

    return {"status": "revoked", "device_id": device_id}


@router.patch("/platform-preferences")
async def update_platform_preferences(
    payload: PlatformPreferencesRequest,
    user_data: dict[str, Any] = Depends(verify_supabase_token),
) -> dict[str, Any]:
    user_id = user_data.get("sub")
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid user token")
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    platforms = _normalize_platforms(payload.platforms)
    survey_data = user.get("survey_data") or {}
    survey_data["interested_socials"] = platforms
    update_user(user_id, {"survey_data": survey_data})

    with _STATE_LOCK:
        state = _load_state()
        for device in state["devices"].values():
            if device.get("user_id") == user_id and not device.get("revoked"):
                device["platform_preferences"] = platforms
        _save_state(state)

    return {"platform_preferences": platforms}


@router.get("/config")
async def get_daemon_config(x_daemon_token: str = Header(...)) -> dict[str, Any]:
    with _STATE_LOCK:
        state = _load_state()
        token_record, device = _authenticate_daemon_token(state, x_daemon_token)
        _save_state(state)
    user_info = _get_user_profile_summary(token_record["user_id"])
    return {
        "device": device,
        "user_info": user_info,
        "platform_preferences": device.get("platform_preferences", user_info["platform_preferences"]),
    }


@router.post("/accounts/sync")
async def sync_accounts(payload: AccountsSyncRequest, x_daemon_token: str = Header(...)) -> dict[str, Any]:
    with _STATE_LOCK:
        state = _load_state()
        token_record, device = _authenticate_daemon_token(state, x_daemon_token)
        allowed_platforms = set(device.get("platform_preferences") or [])
        allowed_platforms.update(PLATFORMS)

        accounts: dict[str, Any] = device.get("accounts") or {}
        now_iso = _now_iso()
        for platform, account_data in payload.accounts.items():
            key = platform.strip().lower()
            if key not in allowed_platforms:
                continue
            accounts[key] = {
                "status": account_data.status,
                "account": account_data.account,
                "updated_at": now_iso,
            }

        device["accounts"] = accounts
        device["last_seen_at"] = now_iso
        token_record["last_seen_at"] = now_iso
        _save_state(state)

    return {
        "status": "ok",
        "device_id": device["id"],
        "accounts": device["accounts"],
    }
