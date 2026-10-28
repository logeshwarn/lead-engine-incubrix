"""cached_get: reruns cost no API calls, failures retry 3 times then skip, keys never stored."""

import pytest
import requests
from conftest import FakeResponse

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
