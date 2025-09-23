from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any, Dict, Optional
import os

from utils import notify


TOKEN_STORAGE_DIR = Path(
    os.getenv("TWITTER_TOKEN_DIR", str(Path(__file__).parent / "oauth_tokens"))
)
TOKEN_FILE_NAME = "tokens.json"
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
SUPABASE_TOKEN_TABLE = os.getenv("SUPABASE_TOKEN_TABLE", "twitter_tokens")


def load_token_cache(directory: Path = TOKEN_STORAGE_DIR) -> Dict[str, Any]:
    """Return the existing token map from disk (empty dict if missing/invalid)."""
    token_path = directory / TOKEN_FILE_NAME
    if not token_path.exists():
        return {}
    try:
        data = json.loads(token_path.read_text())
        if isinstance(data, dict):
            return data
    except Exception:
        notify("⚠️ could not parse existing token file")
    return {}


def persist_token_to_file(
    user_key: str,
    refresh_token: str,
    directory: Path = TOKEN_STORAGE_DIR,
) -> Path:
    """Persist the refresh token to a shared JSON map keyed by user identifier."""
    directory.mkdir(parents=True, exist_ok=True)
    token_path = directory / TOKEN_FILE_NAME
    tokens = load_token_cache(directory)

    tokens[user_key] = refresh_token

    tmp_path = token_path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(tokens, indent=2))
    tmp_path.replace(token_path)
    return token_path


def persist_token_to_supabase(
    user_id: str,
    token_response: Dict[str, Any],
    table: Optional[str] = None,
) -> Any:
    """Upsert OAuth token payload into a Supabase table."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set to persist tokens."
        )

    try:
        from supabase import Client, create_client
    except ImportError as exc:
        raise RuntimeError(
            "Supabase client not installed. Install 'supabase' to persist tokens."
        ) from exc

    client: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

    expires_in = token_response.get("expires_in")
    expires_at: Optional[str] = None
    if expires_in:
        try:
            expires_at_dt = datetime.now(timezone.utc) + timedelta(
                seconds=int(expires_in)
            )
            expires_at = expires_at_dt.isoformat()
        except Exception:
            expires_at = None

    record = {
        "user_id": user_id,
        "access_token": token_response.get("access_token"),
        "refresh_token": token_response.get("refresh_token"),
        "token_type": token_response.get("token_type"),
        "scope": token_response.get("scope"),
        "expires_at": expires_at,
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "raw_response": json.dumps(token_response),
    }

    table_name = table or SUPABASE_TOKEN_TABLE
    result = client.table(table_name).upsert(record, on_conflict="user_id").execute()
    return getattr(result, "data", result)
  
  
