"""Shared helpers used by every stage: config, logging, the SQLite database and cached API calls."""

import hashlib
import json
import logging
import sqlite3
import time
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
    "segments",
    "countries",
    "language",
    "activity",
    "reachable",
    "evidence",
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
    conn = sqlite3.connect(out_dir / "engine.db")
    # api_cache: one stored response per request, so reruns cost no quota.
    conn.execute(
        "CREATE TABLE IF NOT EXISTS api_cache (cache_key TEXT PRIMARY KEY, source TEXT, response TEXT, fetched_at TEXT)"
    )
    # api_log: every request, cached or not, for the run report (calls, cache hits, errors).
    conn.execute("CREATE TABLE IF NOT EXISTS api_log (at TEXT, source TEXT, cached INTEGER, ok INTEGER, detail TEXT)")
    conn.commit()
    return conn


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


def cached_get(conn, source, url, params, http, max_age_days, headers_fn=None, secret_params=("key",)):
    """GET a JSON API through the SQLite cache.

    Returns (data, was_cached). Retries transient failures `http["retries"]` times with
    exponential backoff, then raises ApiError so the caller can log it and skip the row.
    headers_fn is called per attempt because some APIs (Podcast Index) sign the current time.
    """
    key = _cache_key(source, url, params, secret_params)
    row = conn.execute("SELECT response, fetched_at FROM api_cache WHERE cache_key = ?", (key,)).fetchone()
    if row and now_utc() - datetime.fromisoformat(row[1]) < timedelta(days=max_age_days):
        _log_call(conn, source, cached=1, ok=1)
        return json.loads(row[0]), True

    def attempt():
        try:
            r = requests.get(
                url, params=params, headers=headers_fn() if headers_fn else None, timeout=http["timeout_seconds"]
            )
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
        _log_call(conn, source, cached=0, ok=0, detail=str(e))
        raise ApiError(source, "n/a", f"gave up after {http['retries']} attempts ({e})") from None

    if r.status_code != 200:
        reason = _error_reason(r)
        _log_call(conn, source, cached=0, ok=0, detail=f"HTTP {r.status_code} {reason}")
        raise ApiError(source, r.status_code, reason)

    data = r.json()
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
