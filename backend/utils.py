
import json
import time
from pathlib import Path

AUTH_COOKIE = "auth_token"

def notify(msg: str):
    print(msg)
    
def error(msg: str):
    raise RuntimeError(f"❌ {msg}")

def cookie_still_valid(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        state = json.loads(path.read_text())
    except Exception:
        return False
    for c in state.get("cookies", []):
        if c.get("name") == AUTH_COOKIE:
            return c.get("expires", 0) == 0 or c["expires"] > time.time() + 60
    return False