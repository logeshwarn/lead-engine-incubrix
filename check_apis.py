"""Make one cheap live call to each API to prove the keys in .env work.

    python check_apis.py

Prints only pass/fail and counts, never keys or response bodies.
"""

import hashlib
import os
import sys
import time

import requests
from dotenv import load_dotenv

YOUTUBE_URL = "https://www.googleapis.com/youtube/v3/videoCategories"
PODCASTINDEX_URL = "https://api.podcastindex.org/api/1.0/search/byterm"
USER_AGENT = "IncuBrixLeadEngine/0.1"  # Podcast Index rejects requests without a User-Agent
TIMEOUT = 20


def podcastindex_headers(key, secret, now=None):
    """Podcast Index auth: sha1(key + secret + unix time), sent with the key and the time."""
    now = str(int(now if now is not None else time.time()))
    digest = hashlib.sha1((key + secret + now).encode("utf-8")).hexdigest()
    return {"X-Auth-Key": key, "X-Auth-Date": now, "Authorization": digest, "User-Agent": USER_AGENT}


def check_youtube(key):
    # videoCategories.list costs 1 quota unit (search.list would cost 100).
    if not key:
        return False, "YOUTUBE_API_KEY is empty in .env"
    try:
        r = requests.get(YOUTUBE_URL, params={"part": "snippet", "regionCode": "US", "key": key}, timeout=TIMEOUT)
    except requests.RequestException as e:
        # Only the error type: the message can contain the URL, which holds the key.
        return False, f"network error ({type(e).__name__})"
    if r.status_code != 200:
        reason = (
            r.json().get("error", {}).get("message", "")
            if r.headers.get("content-type", "").startswith("application/json")
            else ""
        )
        return False, f"HTTP {r.status_code} {reason}".strip()
    return True, f"HTTP 200, {len(r.json().get('items', []))} video categories returned (cost: 1 quota unit)"


def check_podcastindex(key, secret):
    if not key or not secret:
        return False, "PODCASTINDEX_API_KEY or PODCASTINDEX_API_SECRET is empty in .env"
    try:
        r = requests.get(
            PODCASTINDEX_URL,
            params={"q": "business podcast", "max": 1},
            headers=podcastindex_headers(key, secret),
            timeout=TIMEOUT,
        )
    except requests.RequestException as e:
        return False, f"network error ({type(e).__name__})"
    if r.status_code != 200:
        return False, f"HTTP {r.status_code}"
    body = r.json()
    return True, f"HTTP 200, status={body.get('status')}, {body.get('count', 0)} feed returned"


def main():
    load_dotenv()
    results = {
        "YouTube Data API v3": check_youtube(os.getenv("YOUTUBE_API_KEY", "")),
        "Podcast Index API": check_podcastindex(
            os.getenv("PODCASTINDEX_API_KEY", ""), os.getenv("PODCASTINDEX_API_SECRET", "")
        ),
    }
    for name, (ok, detail) in results.items():
        print(f"{'PASS' if ok else 'FAIL'}  {name}: {detail}")
    return 0 if all(ok for ok, _ in results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
