import os
import time
from functools import lru_cache

import requests

BEARER = os.getenv("TWITTER_BEARER_TOKEN", r"AAAAAAAAAAAAAAAAAAAAAJHRxQEAAAAAB%2F567wfymD1OQyW8C4MXhUX8t4c%3DZn9FSzsz31UhfpTQN10YRMHQHRuMqsGYjPFYFxUJXVezuuZuPi")
BASE = "https://api.twitter.com/2"

BEARER = os.getenv(
    "TWITTER_BEARER_TOKEN",
    r"AAAAAAAAAAAAAAAAAAAAAJHRxQEAAAAAB%2F567wfymD1OQyW8C4MXhUX8t4c%3DZn9FSzsz31UhfpTQN10YRMHQHRuMqsGYjPFYFxUJXVezuuZuPi",
)
BASE = "https://api.twitter.com/2"


def request_from_x(url, params=None):
    hdrs = {"Authorization": f"Bearer {BEARER}"}
    r = requests.get(url, headers=hdrs, params=params or {}, timeout=10)

    # handle rate-limit politely
    if r.status_code == 429:
        reset = int(r.headers.get("x-rate-limit-reset", "0"))
        sleep = max(reset - time.time(), 1)
        print(f"rate-limited → sleeping {sleep:.0f}s")
        time.sleep(sleep)
        return request_from_x(url, params)

    r.raise_for_status()
    return r.json()


@lru_cache(maxsize=128)
@lru_cache(maxsize=128)
def user_id(username: str) -> str:
    resp = request_from_x(f"{BASE}/users/by/username/{username}")
    return resp["data"]["id"]


def timeline(username: str, max_results=100):
    uid = user_id(username)
    resp = request_from_x(
        f"{BASE}/users/{uid}/tweets",
        params={
            "max_results": max_results,
            "tweet.fields": "public_metrics,created_at",
        },
    )
    return resp["data"]


if __name__ == "__main__":
    accounts = ["divya_venn", "witkowski_cam"]  # Twitter handles
    topics = ["building in public", "applied AI"]

    tweets = timeline("divya_venn", max_results=5)
    for t in tweets:
        print(t)
