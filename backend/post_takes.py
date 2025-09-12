import os
import re
import requests
from typing import Dict
from main import ask_model
import pprint
from urllib.parse import unquote

# --- config ---
# OAuth 2.0 *user access token* with permission to create posts (tweets)
# Store securely (e.g., env/secret manager)

RAW_TOKEN = os.getenv("TWITTER_USER_BEARER") or os.getenv("TWITTER_BEARER", "")
BEARER = unquote(RAW_TOKEN)

API_URL = "https://api.twitter.com/2/tweets"  # ← fix host

USER_ACCESS = "1689356162716610560-pSgc0JQ3NQqatheVV4nKLSt9Gpcing"
ACCESS_TOKEN_SECRET = "dVGhm8yc2pnbAIdPjjv2uHBosVhDYbE0GYXj4ctVaqg5x"

SESSION = requests.Session()
SESSION.headers.update({
    "Authorization": f"Bearer {BEARER}",
    "Content-Type": "application/json",
    "Accept": "application/json",
})

# Sanity checks: warn if token looks URL-encoded or like an app-only token
if "%" in (RAW_TOKEN or ""):
    print("[warn] Your bearer token appears URL-encoded. Decoded automatically. If posting still 403s, ensure it's a *user* access token with tweet.write scope.")
if BEARER.startswith("AAAAAAAA"):  # typical app-only bearer prefix
    print("[warn] Token looks like an *app-only* bearer. Posting requires a *user-context* access token with tweet.write. Generate an OAuth 2.0 user token (PKCE) for your app and set TWITTER_USER_BEARER.")

def push(payload: Dict) -> Dict:
    r = SESSION.post(API_URL, json=payload, timeout=30)
    if r.status_code >= 400:
        try:
            print("[error body]", r.status_code, r.text)
        except Exception:
            pass
        r.raise_for_status()
    return r.json()

def post_take_as_reply(prompt: str, item: Dict) -> Dict:
    tweet_id = item["id"]
    # if item["thread"] is a list, join it:
    thread_text = "\n\n".join(item.get("thread", [])) if isinstance(item.get("thread"), list) else str(item.get("thread", ""))
    text = ask_model(f"{prompt}\n\nContext:\n{thread_text}")

    payload = {
        "text": text,
        "reply": {"in_reply_to_tweet_id": tweet_id},
    }
    pprint.pp(payload)
    return push(payload)  # ← actually post

def post_take_as_quote(prompt: str, item: Dict) -> Dict:
    tweet_id = item["id"]
    thread_text = "\n\n".join(item.get("thread", [])) if isinstance(item.get("thread"), list) else str(item.get("thread", ""))
    text = ask_model(f"{prompt}\n\nContext:\n{thread_text}")

    payload = {
        "text": text,
        "quote_tweet_id": tweet_id,   # if 400s, re-check doc for field name in your tier
    }
    pprint.pp(payload)
    return push(payload)  # ← actually post

def post_take(take: str) -> Dict:
    payload = {"text": take}
    pprint.pp(payload)
    return push(payload)

def post_take_with_token(take: str, access_token: str) -> Dict:
    """Post a tweet using user access token"""
    url = "https://api.x.com/2/tweets"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    payload = {"text": take}
    pprint.pp(payload)
    
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    
    if response.status_code >= 400:
        print(f"❌ HTTP Error {response.status_code}: {response.text}")
        response.raise_for_status()
    
    return response.json()

def post_take_as_reply_with_token(prompt: str, item: Dict, access_token: str) -> Dict:
    """Post a reply using user access token"""
    from main import ask_model
    
    tweet_id = item["id"]
    thread_text = "\n\n".join(item.get("thread", [])) if isinstance(item.get("thread"), list) else str(item.get("thread", ""))
    text = ask_model(f"{prompt}\n\nContext:\n{thread_text}")

    url = "https://api.x.com/2/tweets"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "text": text,
        "reply": {"in_reply_to_tweet_id": tweet_id},
    }
    pprint.pp(payload)
    
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    
    if response.status_code >= 400:
        print(f"[error] {response.status_code} {response.text}")
        response.raise_for_status()
    
    return response.json()

# --- example usage ---
if __name__ == "__main__":
    # quick auth probe: who am I?
    try:
        who = requests.get(
            "https://api.twitter.com/2/users/me",
            headers={"Authorization": f"Bearer {BEARER}"},
            timeout=10,
        )
        print("/users/me:", who.status_code, who.text[:200])
    except Exception as e:
        print("[warn] /users/me probe failed:", e)
    # attempt a post
    post_take("hello world!")
