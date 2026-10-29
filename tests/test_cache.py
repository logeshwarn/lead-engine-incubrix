"""cached_get: reruns cost no API calls, failures retry 3 times then skip, keys never stored."""

import sqlite3

import pytest
import requests
from conftest import FakeResponse

from engine import common
from engine.common import ApiError, cached_get

URL = "https://api.example.test/search"


def get(conn, config, params=None, max_age_days=7):
    return cached_get(conn, "test", URL, params or {"q": "x", "key": "SECRET"}, config["http"], max_age_days)


def test_second_call_is_served_from_cache(conn, config, fake_http):
    fake = fake_http(lambda url, params: FakeResponse(200, {"items": [1]}))
    assert get(conn, config) == ({"items": [1]}, False)
    assert get(conn, config) == ({"items": [1]}, True)
    assert len(fake.calls) == 1  # Phase 1 rule: no repeat API calls on rerun


def test_expired_cache_is_fetched_again(conn, config, fake_http):
    fake = fake_http(lambda url, params: FakeResponse(200, {}))
    get(conn, config)
    get(conn, config, max_age_days=0)
    assert len(fake.calls) == 2


def test_key_is_not_stored(conn, config, fake_http):
    fake_http(lambda url, params: FakeResponse(200, {}))
    get(conn, config)
    stored = " ".join(str(v) for row in conn.execute("SELECT * FROM api_cache") for v in row)
    assert "SECRET" not in stored


def test_new_key_reuses_cache(conn, config, fake_http):
    fake = fake_http(lambda url, params: FakeResponse(200, {}))
    get(conn, config, {"q": "x", "key": "OLD"})
    get(conn, config, {"q": "x", "key": "NEW"})
    assert len(fake.calls) == 1


def test_transient_error_retried_then_succeeds(conn, config, fake_http):
    replies = [requests.ConnectionError("down"), FakeResponse(503), FakeResponse(200, {"ok": 1})]
    fake = fake_http(lambda url, params: replies.pop(0))
    assert get(conn, config)[0] == {"ok": 1}
    assert len(fake.calls) == 3


def test_gives_up_after_three_attempts_and_logs(conn, config, fake_http):
    fake = fake_http(lambda url, params: FakeResponse(500))
    with pytest.raises(ApiError):
        get(conn, config)
    assert len(fake.calls) == 3
    assert conn.execute("SELECT ok FROM api_log").fetchall() == [(0,)]
    assert conn.execute("SELECT COUNT(*) FROM api_cache").fetchone()[0] == 0  # failures are never cached


def test_client_error_not_retried_and_reason_kept(conn, config, fake_http):
    body = {"error": {"errors": [{"reason": "quotaExceeded"}], "message": "quota"}}
    fake = fake_http(lambda url, params: FakeResponse(403, body))
    with pytest.raises(ApiError) as e:
        get(conn, config)
    assert e.value.reason == "quotaExceeded"
    assert len(fake.calls) == 1  # retrying a 403 would only waste time


def test_network_error_message_hides_key(conn, config, fake_http):
    fake_http(lambda url, params: requests.ConnectionError(f"{URL}?key=SECRET"))
    with pytest.raises(ApiError) as e:
        get(conn, config)
    assert "SECRET" not in str(e.value)
    assert "SECRET" not in str(conn.execute("SELECT detail FROM api_log").fetchall())


def test_remembered_failure_skips_the_request(conn, config, fake_http):
    fake = fake_http(lambda url, params: FakeResponse(500))
    for _ in range(2):
        with pytest.raises(ApiError):
            cached_get(conn, "website", URL, {}, config["http"], 7, failure_max_age_days=1)
    assert len(fake.calls) == 3  # 3 attempts on the first run, none on the rerun
    assert conn.execute("SELECT cached, ok FROM api_log").fetchall() == [(0, 0), (1, 0)]


def test_remembered_failure_expires(conn, config, fake_http):
    replies = [FakeResponse(500)] * 3 + [FakeResponse(200, {"ok": 1})]
    fake = fake_http(lambda url, params: replies.pop(0))
    with pytest.raises(ApiError):
        cached_get(conn, "website", URL, {}, config["http"], 7, failure_max_age_days=1)
    data, cached = cached_get(conn, "website", URL, {}, config["http"], 7, failure_max_age_days=0)
    assert data == {"ok": 1} and cached is False
    assert len(fake.calls) == 4


def test_api_failures_are_not_remembered(conn, config, fake_http):
    # APIs leave failure_max_age_days unset: a quota error must not block calls after the quota resets.
    fake = fake_http(lambda url, params: FakeResponse(500))
    for _ in range(2):
        with pytest.raises(ApiError):
            get(conn, config)
    assert len(fake.calls) == 6


def test_parallel_map_keeps_order_and_uses_own_connections(conn):
    from engine.common import parallel_map

    seen = []

    def work(c, n):
        seen.append(c)
        c.execute("SELECT 1")  # each thread's own connection works
        return n * 2

    assert parallel_map(conn, 4, work, list(range(20))) == [n * 2 for n in range(20)]
    assert conn not in seen  # the main connection is never shared with a thread


def test_merge_cache_copies_new_and_newer_responses(tmp_path):
    from engine.common import connect_db, merge_cache

    main, other = connect_db(tmp_path / "main"), connect_db(tmp_path / "other")
    main.execute("INSERT INTO api_cache VALUES ('k1', 's', '\"old\"', '2026-10-01T00:00:00')")
    main.execute("INSERT INTO api_cache VALUES ('k2', 's', '\"keep\"', '2026-10-05T00:00:00')")
    other.execute("INSERT INTO api_cache VALUES ('k1', 's', '\"new\"', '2026-10-02T00:00:00')")
    other.execute("INSERT INTO api_cache VALUES ('k2', 's', '\"stale\"', '2026-10-03T00:00:00')")
    other.execute("INSERT INTO api_cache VALUES ('k3', 's', '\"only other\"', '2026-10-02T00:00:00')")
    for db in (main, other):  # a shared log row from the common copy, and one row only the other run has
        db.execute("INSERT INTO api_log VALUES ('2026-10-01', 's', 0, 1, '')")
    other.execute("INSERT INTO api_log VALUES ('2026-10-02', 's', 0, 1, '')")
    other.commit()
    main.commit()
    assert merge_cache(main, tmp_path / "other" / "engine.db") == 1
    got = dict(main.execute("SELECT cache_key, response FROM api_cache").fetchall())
    assert got == {"k1": '"new"', "k2": '"keep"', "k3": '"only other"'}
    assert main.execute("SELECT COUNT(*) FROM api_log").fetchone()[0] == 2


def test_locked_database_write_is_retried_not_fatal(conn, monkeypatch):
    """Many fetch shards write one cache; a write that finds the database locked waits and retries."""
    calls = {"n": 0}

    class Flaky:
        def execute(self, sql, args):
            calls["n"] += 1
            if calls["n"] <= 2:
                raise sqlite3.OperationalError("database is locked")
            return conn.execute(sql, args)

        def commit(self):
            conn.commit()

        def rollback(self):
            conn.rollback()

    monkeypatch.setattr(common.time, "sleep", lambda s: None)
    common.write_with_retry(Flaky(), [("INSERT INTO api_log VALUES (?, ?, ?, ?, ?)", ("t", "src", 0, 1, ""))])
    assert calls["n"] == 3 and conn.execute("SELECT COUNT(*) FROM api_log").fetchone()[0] == 1


def test_other_database_errors_are_not_retried(conn):
    with pytest.raises(sqlite3.OperationalError, match="no such table"):
        common.write_with_retry(conn, [("INSERT INTO nope VALUES (?)", (1,))])


def test_malformed_url_fails_the_row_without_retry(conn, config, fake_http):
    """Wave 1 crashed on a host like '.libsyn.com': urllib3 raises a ValueError, not a RequestException."""
    import urllib3

    fake = fake_http(lambda url, params: urllib3.exceptions.LocationParseError(".libsyn.com"))
    with pytest.raises(ApiError) as e:
        get(conn, config)
    assert e.value.reason == "invalid URL" and len(fake.calls) == 1


def test_gemini_falls_back_when_the_model_is_out_of_quota(conn, config, fake_http, monkeypatch):
    """Each Gemini model has its own free daily quota; the full run used up Flash-Lite's on 2026-10-29."""
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setattr(common, "OUT_OF_QUOTA", set())
    monkeypatch.setattr(common.time, "sleep", lambda s: None)
    config["llm"].update(model="lite", fallback_models=["flash"], pause_seconds=0)
    config["http"]["backoff_seconds"] = 0
    answer = {
        "candidates": [{"content": {"parts": [{"text": '{"kind": "creator"}'}]}}],
        "usageMetadata": {"totalTokenCount": 9},
    }

    def respond(url, params):
        return FakeResponse(429) if "/lite:" in url else FakeResponse(200, answer)

    fake = fake_http(respond)
    assert common.llm_json(conn, config, "sys", "prompt 1", {})[0] == {"kind": "creator"}
    assert common.llm_json(conn, config, "sys", "prompt 2", {})[0] == {"kind": "creator"}
    lite_calls = [c for c in fake.calls if "/lite:" in c["url"]]
    assert len(lite_calls) == 2 * config["http"]["retries"]  # first prompt only, plus one try after the wait
    assert common.OUT_OF_QUOTA == {"lite"}


def gemini_answer(text='{"kind": "creator"}'):
    return {"candidates": [{"content": {"parts": [{"text": text}]}}], "usageMetadata": {"totalTokenCount": 9}}


def groq_answer(text='{"kind": "creator"}'):
    return {"choices": [{"message": {"content": text}}], "usage": {"total_tokens": 7}}


def test_groq_answers_when_every_gemini_model_is_out_of_quota(conn, config, fake_http, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("GROQ_API_KEY", "g")
    monkeypatch.setattr(common, "OUT_OF_QUOTA", set())
    monkeypatch.setattr(common.time, "sleep", lambda s: None)
    config["llm"].update(model="lite", fallback_models=["flash"], groq_models=["openai/gpt-oss-120b"])
    config["http"]["backoff_seconds"] = 0

    def respond(url, params):
        return FakeResponse(200, groq_answer()) if "groq.com" in url else FakeResponse(429)

    fake = fake_http(respond)
    answer, tokens, cached, model = common.llm_json(conn, config, "sys", "prompt", {"type": "OBJECT"})
    assert answer == {"kind": "creator"} and tokens == 7 and not cached and model == "openai/gpt-oss-120b"
    body = next(c["json"] for c in fake.calls if "groq.com" in c["url"])
    assert body["response_format"]["json_schema"]["schema"] == {"type": "object", "additionalProperties": False}
    assert body["reasoning_effort"] == "low"
    assert next(c["headers"] for c in fake.calls if "groq.com" in c["url"]) == {"Authorization": "Bearer g"}


def test_a_per_minute_429_waits_and_retries_instead_of_dropping_the_model(conn, config, fake_http, monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "g")
    monkeypatch.setattr(common, "OUT_OF_QUOTA", set())
    waits = []
    monkeypatch.setattr(common.time, "sleep", waits.append)
    config["llm"].update(groq_models=["openai/gpt-oss-120b"], rate_limit_wait_seconds=60)
    config["http"]["backoff_seconds"] = 0
    retries = config["http"]["retries"]

    def respond(url, params):
        busy = len(fake.calls) <= retries  # every first-round attempt hits the minute limit
        return FakeResponse(429) if busy else FakeResponse(200, groq_answer())

    fake = fake_http(respond)
    answer, _, _, model = common.llm_json(conn, config, "sys", "prompt", {})
    assert answer == {"kind": "creator"} and model == "openai/gpt-oss-120b"
    assert 60 in waits and common.OUT_OF_QUOTA == set()


def test_a_busy_model_passes_the_prompt_on_but_stays_in_the_chain(conn, config, fake_http, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setattr(common, "OUT_OF_QUOTA", set())
    monkeypatch.setattr(common.time, "sleep", lambda s: None)
    config["llm"].update(model="busy", fallback_models=["flash"], groq_models=[])
    config["http"]["backoff_seconds"] = 0

    def respond(url, params):
        return FakeResponse(503) if "/busy:" in url else FakeResponse(200, gemini_answer())

    fake_http(respond)
    answer, _, _, model = common.llm_json(conn, config, "sys", "prompt", {})
    assert answer == {"kind": "creator"} and model == "flash" and common.OUT_OF_QUOTA == set()


def test_a_cached_answer_from_any_model_is_used_before_asking_again(conn, config, fake_http, monkeypatch):
    """A creator judged by Groq yesterday is not re-judged by Gemini today, after Gemini's quota resets."""
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("GROQ_API_KEY", "g")
    monkeypatch.setattr(common, "OUT_OF_QUOTA", {"lite"})
    monkeypatch.setattr(common.time, "sleep", lambda s: None)
    config["llm"].update(model="lite", fallback_models=[], groq_models=["openai/gpt-oss-120b"])
    fake = fake_http(lambda url, params: FakeResponse(200, groq_answer()))
    common.llm_json(conn, config, "sys", "prompt", {})
    monkeypatch.setattr(common, "OUT_OF_QUOTA", set())  # the next day: Gemini has quota again
    answer, _, cached, model = common.llm_json(conn, config, "sys", "prompt", {})
    assert cached and model == "openai/gpt-oss-120b" and len(fake.calls) == 1
