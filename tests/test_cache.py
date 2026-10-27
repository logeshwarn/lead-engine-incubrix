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
