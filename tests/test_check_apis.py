"""check_apis.py: auth header maths and no network call when a key is missing."""

import hashlib

import check_apis


def test_podcastindex_auth_header():
    headers = check_apis.podcastindex_headers("KEY", "SECRET", now=1700000000)
    assert headers["X-Auth-Date"] == "1700000000"
    assert headers["Authorization"] == hashlib.sha1(b"KEYSECRET1700000000").hexdigest()
    assert headers["User-Agent"]


def test_missing_keys_fail_without_calling(monkeypatch):
    def no_network(*args, **kwargs):
        raise AssertionError("must not call the API without a key")

    monkeypatch.setattr(check_apis.requests, "get", no_network)
    assert check_apis.check_youtube("")[0] is False
    assert check_apis.check_podcastindex("KEY", "")[0] is False


def test_network_error_hides_key(monkeypatch):
    def boom(*args, **kwargs):
        raise check_apis.requests.ConnectionError("https://example/?key=SECRETKEY123")

    monkeypatch.setattr(check_apis.requests, "get", boom)
    ok, detail = check_apis.check_youtube("SECRETKEY123")
    assert ok is False
    assert "SECRETKEY123" not in detail


def test_gemini_missing_key_fails_without_calling(monkeypatch):
    def no_network(*args, **kwargs):
        raise AssertionError("must not call the API without a key")

    monkeypatch.setattr(check_apis.requests, "get", no_network)
    assert check_apis.check_gemini("")[0] is False


def test_gemini_key_sent_in_header_not_url(monkeypatch):
    seen = {}

    class Ok:
        status_code = 200
        headers = {"content-type": "application/json"}

        def json(self):
            return {"models": [{"name": "m", "supportedGenerationMethods": ["generateContent"]}]}

    def fake_get(url, headers=None, timeout=None, params=None):
        seen.update(url=url, headers=headers, params=params)
        return Ok()

    monkeypatch.setattr(check_apis.requests, "get", fake_get)
    assert check_apis.check_gemini("SECRETKEY")[0] is True
    assert "SECRETKEY" not in seen["url"] and not seen["params"]
    assert seen["headers"]["x-goog-api-key"] == "SECRETKEY"
