"""Shared helpers used by every stage: config, logging, the SQLite database and cached API calls."""

import hashlib
import json
import logging
import os
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
import yaml
from dotenv import load_dotenv
from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_exponential

USER_AGENT = "IncuBrixLeadEngine/0.1"  # Podcast Index rejects requests without a User-Agent

# Sections the stages rely on; checking them up front fails fast on a broken config
# instead of crashing halfway through a run.
REQUIRED_SECTIONS = [
    "http",
    "cache",
    "discover",
    "enrich",
    "verify",
    "dedupe",
    "llm",
    "segments",
    "countries",
    "language",
    "activity",
    "reachable",
    "evidence",
    "score",
    "draft",
    "priority_a",
    "targets",
]


# leads.csv columns, locked to Submission Workbook tab 02_LEADS (row 4, columns A-AD).
# Order matters: the workbook rows are pasted straight from leads.csv.
# tests/test_leads_schema.py re-reads the workbook so any drift fails a test.
LEADS_COLUMNS = [
    "lead_id",
    "creator_name",
    "creator_segment",
    "country_iso2",
    "primary_language",
    "primary_platform",
    "profile_url",
    "stable_creator_id",
    "followers_or_subscribers",
    "last_content_date",
    "recent_content_url",
    "content_count_30d",
    "longform_count_60d",
    "monetization_signal",
    "monetization_evidence_url",
    "incubrix_need",
    "need_evidence_url",
    "best_channel",
    "channel_handle_or_url",
    "channel_evidence_url",
    "backup_channel",
    "personalization_hook",
    "first_message",
    "checked_date",
    "priority",
    "lead_score",
    "candidate_status",
    "rejection_reason",
    "duplicate_check",
    "completeness_check",
]

# Allowed values from the workbook's 02_LEADS dropdowns. Segment and country lists
# live in config.yaml because the caps stage also uses them.
CHANNELS = [
    "Email",
    "LinkedIn",
    "Instagram",
    "X",
    "YouTube",
    "TikTok",
    "Community",
    "Podcast guest pitch",
    "Contact form",
    "Partner referral",
    "Other",
]  # best_channel and backup_channel
PRIORITIES = ["A", "B", "C"]
CANDIDATE_STATUSES = ["Qualified", "Rejected"]


def load_config(path="config.yaml"):
    """Read config.yaml and load secrets from .env into the environment."""
    # .env is optional here so --help and tests work without keys;
    # each stage checks for the keys it needs.
    load_dotenv()
    with open(path, encoding="utf-8") as f:
        config = yaml.safe_load(f)
    missing = [s for s in REQUIRED_SECTIONS if s not in (config or {})]
    if missing:
        raise ValueError(f"config.yaml is missing sections: {', '.join(missing)}")
    return config


def setup_logging(log_dir):
    """Log to the console and to one new file per run."""
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"run_{datetime.now():%Y%m%d_%H%M%S}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(log_file, encoding="utf-8"), logging.StreamHandler()],
        force=True,  # replace any earlier handlers so each run gets its own file
    )
    return log_file


def now_utc():
    return datetime.now(timezone.utc)


def connect_db(out_dir):
    """Open (or create) <out>/engine.db with the shared tables every stage can rely on."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(out_dir / "engine.db", timeout=60)
    # WAL lets parallel fetch threads write the cache while others read it (see parallel_map).
    conn.execute("PRAGMA journal_mode=WAL")
    # api_cache: one stored response per request, so reruns cost no quota.
    conn.execute(
        "CREATE TABLE IF NOT EXISTS api_cache (cache_key TEXT PRIMARY KEY, source TEXT, response TEXT, fetched_at TEXT)"
    )
    # api_log: every request, cached or not, for the run report (calls, cache hits, errors).
    conn.execute("CREATE TABLE IF NOT EXISTS api_log (at TEXT, source TEXT, cached INTEGER, ok INTEGER, detail TEXT)")
    conn.commit()
    return conn


def merge_cache(conn, other_db):
    """Copy another run's cached responses and call log into this database. Returns rows merged.

    Two runs fetching at the same time must use separate folders, because every stage replaces its
    table. Merging their caches afterwards lets one final run reuse both without fetching twice.
    For a request both runs made, the newer response wins.
    """
    conn.execute("ATTACH DATABASE ? AS other", (str(other_db),))
    try:
        before = conn.execute("SELECT COUNT(*) FROM api_cache").fetchone()[0]
        conn.execute(
            "INSERT INTO api_cache SELECT * FROM other.api_cache WHERE true ON CONFLICT(cache_key) DO UPDATE SET "
            "source = excluded.source, response = excluded.response, fetched_at = excluded.fetched_at "
            "WHERE excluded.fetched_at > api_cache.fetched_at"
        )
        # Rows both logs share (from the copy each run started from) are not counted twice.
        conn.execute("INSERT INTO api_log SELECT * FROM other.api_log EXCEPT SELECT * FROM api_log")
        conn.commit()
        return conn.execute("SELECT COUNT(*) FROM api_cache").fetchone()[0] - before
    finally:
        conn.execute("DETACH DATABASE other")


class ApiError(Exception):
    """A request that failed for good. `reason` is safe to log: it never contains keys."""

    def __init__(self, source, status, reason=""):
        self.source, self.status, self.reason = source, status, reason
        super().__init__(f"{source}: HTTP {status} {reason}".strip())


class _Transient(Exception):
    """Worth retrying: network error, rate limit (429) or server error (5xx)."""


def _cache_key(source, url, params, secret_params):
    # Secrets are left out so the database never stores a key, and a new key reuses old results.
    public = {k: v for k, v in sorted(params.items()) if k not in secret_params}
    return json.dumps([source, url, public], sort_keys=True)


def _log_call(conn, source, cached, ok, detail=""):
    conn.execute("INSERT INTO api_log VALUES (?, ?, ?, ?, ?)", (now_utc().isoformat(), source, cached, ok, detail))
    conn.commit()


def cached_get(
    conn,
    source,
    url,
    params,
    http,
    max_age_days,
    headers_fn=None,
    secret_params=("key",),
    parse=None,
    ok_statuses=(200,),
    failure_max_age_days=None,
    json_body=None,
    timeout=None,
):
    """GET a URL (or POST json_body, for the LLM) through the SQLite cache.

    Returns (data, was_cached). Retries transient failures `http["retries"]` times with
    exponential backoff, then raises ApiError so the caller can log it and skip the row.
    headers_fn is called per attempt because some APIs (Podcast Index) sign the current time.
    parse turns the response into JSON-able data (default: r.json()). RSS feeds and web pages
    pass a parser so only the extracted fields are cached, not megabytes of raw page.
    ok_statuses: web pages and robots.txt also accept 4xx (parsed as "nothing there"), so a
    missing page is cached like any answer and a rerun does not ask again.
    failure_max_age_days: when set, a final failure is remembered for that long and re-raised
    without a request, so a rerun does not wait through the same timeouts again. Left unset for
    APIs, where a remembered quota error would block calls after the quota resets.
    json_body is part of the cache key, so the same prompt is never sent twice.
    """
    key = _cache_key(source, url, {**params, "_body": json_body} if json_body else params, secret_params)
    row = conn.execute("SELECT response, fetched_at FROM api_cache WHERE cache_key = ?", (key,)).fetchone()
    if row:
        age = now_utc() - datetime.fromisoformat(row[1])
        data = json.loads(row[0])
        failed = data.get("_failed") if isinstance(data, dict) else None
        if failed and failure_max_age_days is not None and age < timedelta(days=failure_max_age_days):
            _log_call(conn, source, cached=1, ok=0, detail=failed["reason"])
            raise ApiError(source, failed["status"], failed["reason"])
        if not failed and age < timedelta(days=max_age_days):
            _log_call(conn, source, cached=1, ok=1)
            return data, True

    def fail(status, reason):
        _log_call(conn, source, cached=0, ok=0, detail=f"HTTP {status} {reason}".strip())
        if failure_max_age_days is not None:
            failed = {"_failed": {"status": status, "reason": reason}}
            conn.execute(
                "INSERT OR REPLACE INTO api_cache VALUES (?, ?, ?, ?)",
                (key, source, json.dumps(failed), now_utc().isoformat()),
            )
            conn.commit()
        raise ApiError(source, status, reason)

    def attempt():
        headers = headers_fn() if headers_fn else None
        wait = timeout or http["timeout_seconds"]
        try:
            if json_body is None:
                r = requests.get(url, params=params, headers=headers, timeout=wait)
            else:
                r = requests.post(url, params=params, headers=headers, json=json_body, timeout=wait)
        except requests.RequestException as e:
            # Only the error type: the message can contain the URL, which may hold a key.
            raise _Transient(type(e).__name__) from None
        if r.status_code == 429 or r.status_code >= 500:
            raise _Transient(f"HTTP {r.status_code}")
        return r

    try:
        r = Retrying(
            stop=stop_after_attempt(http["retries"]),
            wait=wait_exponential(multiplier=http["backoff_seconds"]),
            retry=retry_if_exception_type(_Transient),
            reraise=True,
        )(attempt)
    except _Transient as e:
        fail("n/a", f"gave up after {http['retries']} attempts ({e})")

    if r.status_code not in ok_statuses:
        fail(r.status_code, _error_reason(r))

    try:
        data = parse(r) if parse else r.json()
    except Exception as e:  # a broken feed or page must skip this row, not crash the run
        fail(200, f"parse error ({type(e).__name__})")
    conn.execute(
        "INSERT OR REPLACE INTO api_cache VALUES (?, ?, ?, ?)", (key, source, json.dumps(data), now_utc().isoformat())
    )
    _log_call(conn, source, cached=0, ok=1)
    return data, False


def _error_reason(r):
    """Short machine reason from an error body, e.g. YouTube's 'quotaExceeded'."""
    try:
        err = r.json().get("error", {})
    except ValueError:
        return ""
    if isinstance(err, dict):
        errors = err.get("errors") or [{}]
        return errors[0].get("reason") or err.get("message", "")
    return str(err)


def podcastindex_headers(key, secret, now=None):
    """Podcast Index auth: sha1(key + secret + unix time), sent with the key and the time."""
    now = str(int(now if now is not None else time.time()))
    digest = hashlib.sha1((key + secret + now).encode("utf-8")).hexdigest()
    return {"X-Auth-Key": key, "X-Auth-Date": now, "Authorization": digest, "User-Agent": USER_AGENT}


GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def _gemini_parse(r):
    """Keep the response only if the model's text is valid JSON, so a broken answer is never cached."""
    data = r.json()
    json.loads(data["candidates"][0]["content"]["parts"][0]["text"])
    return data


def gemini_json(conn, config, system, prompt, schema):
    """Ask Gemini for JSON that matches `schema`. Returns (answer, tokens_used, was_cached).

    Cached by prompt, so reruns cost nothing. The key travels in a header, never the URL.
    Raises ApiError (logged by the caller) when the key is missing or the call fails.
    """
    llm = config["llm"]
    api_key = os.getenv("LLM_API_KEY", "")
    if not api_key:
        raise ApiError("gemini", "n/a", "LLM_API_KEY is empty")
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0,  # the same text should always get the same answer
            "responseMimeType": "application/json",
            "responseSchema": schema,
        },
    }
    data, was_cached = cached_get(
        conn,
        "gemini",
        GEMINI_URL.format(model=llm["model"]),
        {},
        config["http"],
        llm["cache_days"],
        headers_fn=lambda: {"x-goog-api-key": api_key},
        parse=_gemini_parse,
        json_body=body,
        timeout=llm["timeout_seconds"],
    )
    if not was_cached:
        time.sleep(llm["pause_seconds"])  # stay inside the free tier's requests-per-minute limit
    answer = json.loads(data["candidates"][0]["content"]["parts"][0]["text"])
    tokens = data.get("usageMetadata", {}).get("totalTokenCount", 0)
    return answer, tokens, was_cached


def parallel_map(conn, workers, fn, items):
    """Run fn(conn, item) for every item on `workers` threads; results come back in input order.

    Each thread opens its own connection to the same database file, because a SQLite connection
    must not be shared between threads. Used for feeds and websites, which are slow to answer
    but different hosts, so fetching several at once cuts the run time without hammering a site.
    """
    path = conn.execute("PRAGMA database_list").fetchone()[2]
    conn.commit()  # threads must see everything written so far
    local, opened, lock = threading.local(), [], threading.Lock()

    def call(item):
        if not hasattr(local, "conn"):
            local.conn = sqlite3.connect(path, timeout=60, check_same_thread=False)
            with lock:
                opened.append(local.conn)
        return fn(local.conn, item)

    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            return list(pool.map(call, items))
    finally:
        for c in opened:
            c.close()
