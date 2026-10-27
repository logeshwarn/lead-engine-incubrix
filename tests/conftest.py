"""Shared test helpers: a fake HTTP layer so no test touches the network or spends quota."""

import pytest

from engine.common import connect_db, load_config


class FakeResponse:
    """JSON body by default; pass text= for RSS, HTML or robots.txt responses."""

    def __init__(self, status_code=200, body=None, text=None, content_type=None):
        self.status_code = status_code
        self._body = body if body is not None else {}
        self.text = text if text is not None else ""
        self.content = self.text.encode("utf-8")
        default_type = "application/json" if text is None else "text/html"
        self.headers = {"content-type": content_type or default_type}

    def json(self):
        if self.text and not self._body:
            raise ValueError("not JSON")
        return self._body


class FakeHttp:
    """Stands in for requests.get: returns queued responses (or one function of the URL) and counts calls."""

    def __init__(self, respond):
        self.respond = respond
        self.calls = []

    def __call__(self, url, params=None, headers=None, timeout=None):
        self.calls.append({"url": url, "params": params, "headers": headers})
        result = self.respond(url, params)
        if isinstance(result, Exception):
            raise result
        result.url = url  # like requests: the final URL, used to resolve relative links
        return result


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Any test that reaches the real requests.get fails: tests must never spend quota."""

    def blocked(*args, **kwargs):
        raise AssertionError("real network call in a test; use the fake_http fixture")

    monkeypatch.setattr("requests.get", blocked)
    monkeypatch.setattr("engine.common.requests.get", blocked)


@pytest.fixture
def config():
    cfg = load_config("config.yaml")
    cfg["http"]["backoff_seconds"] = 0  # no real waiting between retries in tests
    cfg["discover"]["itunes_pause_seconds"] = 0
    return cfg


@pytest.fixture
def conn(tmp_path):
    c = connect_db(tmp_path)
    yield c
    c.close()


@pytest.fixture
def fake_http(monkeypatch):
    """Call fake_http(respond_fn) to install a fake requests.get and get it back for call counting."""

    def install(respond):
        fake = FakeHttp(respond)
        monkeypatch.setattr("engine.common.requests.get", fake)
        return fake

    return install
