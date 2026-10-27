"""enrich: profiles and recent items from YouTube, RSS and websites; nothing guessed, reruns free."""

import json
from datetime import timedelta

import pandas as pd
import pytest
from conftest import FakeResponse

from engine import enrich
from engine.common import now_utc

RECENT = (now_utc() - timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
OLD = (now_utc() - timedelta(days=200)).strftime("%Y-%m-%dT%H:%M:%SZ")
RECENT_RSS = (now_utc() - timedelta(days=3)).strftime("%a, %d %b %Y %H:%M:%S GMT")
OLD_RSS = (now_utc() - timedelta(days=300)).strftime("%a, %d %b %Y %H:%M:%S GMT")


def channel(
    cid, subs=5000, country="US", hidden=False, videos=10, desc="Business: hi@chan.example https://chan.example"
):
    return {
        "id": cid,
        "snippet": {
            "title": cid,
            "description": desc,
            "customUrl": f"@{cid}",
            "country": country,
            "publishedAt": "2020-01-01T00:00:00Z",
        },  # fmt: skip
        "statistics": {"subscriberCount": str(subs), "hiddenSubscriberCount": hidden, "videoCount": str(videos)},
        "contentDetails": {"relatedPlaylists": {"uploads": f"UU{cid}"}},
    }


CHANNELS = {
    "UC_OK": channel("UC_OK"),
    "UC_BIG": channel("UC_BIG", subs=9_000_000),
    "UC_IN": channel("UC_IN", country="IN"),
}
PLAYLIST = {"items": [
    {"contentDetails": {"videoId": "v1", "videoPublishedAt": RECENT}},
    {"contentDetails": {"videoId": "v2", "videoPublishedAt": OLD}},
]}  # fmt: skip
VIDEOS = {"items": [{"id": "v1", "snippet": {"title": "Ep one", "publishedAt": RECENT,
          "description": "Sponsored by Acme https://acme.example"},
          "contentDetails": {"duration": "PT45M10S", "caption": "false"}}]}  # fmt: skip

RSS = f"""<?xml version="1.0"?><rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
 xmlns:podcast="https://podcastindex.org/namespace/1.0"><channel><title>Show X</title><link>https://showx.example</link>
<language>en-us</language><itunes:owner><itunes:email>Host@ShowX.example</itunes:email></itunes:owner>
<item><title>New ep</title><link>https://showx.example/2</link><guid>g2</guid><pubDate>{RECENT_RSS}</pubDate>
<itunes:duration>1:02:03</itunes:duration><description>Use code SAVE for our course</description>
<podcast:transcript url="https://showx.example/2.vtt" type="text/vtt"/></item>
<item><title>Old ep</title><guid>g1</guid><pubDate>{OLD_RSS}</pubDate><itunes:duration>300</itunes:duration></item>
</channel></rss>"""

HOME = """<html><head><title>Show X</title></head><body><p>Based in Austin, Texas.</p>
<a href="/contact-us">Contact</a><a href="/about">About us</a><a href="https://www.instagram.com/showx">IG</a>
<img src="logo@2x.png"></body></html>"""
CONTACT = '<html><body><a href="mailto:bookings@showx.example?subject=hi">Email us</a></body></html>'


def respond(url, params):
    if "youtube/v3/channels" in url:
        ids = params["id"].split(",")
        return FakeResponse(200, {"items": [CHANNELS[i] for i in ids if i in CHANNELS]})
    if "playlistItems" in url:
        return FakeResponse(200, PLAYLIST)
    if "youtube/v3/videos" in url:
        return FakeResponse(200, VIDEOS)
    if url == "https://feed/x":
        return FakeResponse(200, text=RSS, content_type="application/rss+xml")
    if url.endswith("/robots.txt"):
        return FakeResponse(404, text="")
    if url.rstrip("/") == "https://showx.example":
        return FakeResponse(200, text=HOME)
    if url == "https://showx.example/contact-us":
        return FakeResponse(200, text=CONTACT)
    if url == "https://showx.example/about":
        return FakeResponse(404, text="not found")
    if "chan.example" in url:
        return FakeResponse(200, text="<html><title>Chan</title><body>hello</body></html>")
    raise AssertionError(f"unexpected URL {url}")


@pytest.fixture
def candidates(conn):
    rows = [
        {"platform": "youtube", "platform_id": "UC_OK", "url": "https://www.youtube.com/channel/UC_OK",
         "size_min": "1000",
         "size_max": "250000", "seed_id": "S1", "segment": "YouTuber/Video-First Creator"},
        {"platform": "youtube", "platform_id": "UC_BIG", "url": "u", "size_min": "1000", "size_max": "250000"},
        {"platform": "youtube", "platform_id": "UC_IN", "url": "u", "size_min": "1000", "size_max": "250000"},
        {"platform": "youtube", "platform_id": "UC_GONE", "url": "u"},
        {"platform": "podcast", "platform_id": "itunes:1", "name": "Show X", "url": "https://apple/x",
         "feed_url": "https://feed/x", "seed_id": "S2"},
        {"platform": "podcast", "platform_id": "itunes:2", "name": "No feed", "url": "https://apple/y"},
    ]  # fmt: skip
    pd.DataFrame(rows).to_sql("candidates", conn, index=False)


@pytest.fixture(autouse=True)
def key(monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "yt")


def profiles_by_id(conn):
    return pd.read_sql("SELECT * FROM profiles", conn).set_index("platform_id")


# ---- pure parsers ----


@pytest.mark.parametrize(
    "value,seconds", [("PT45M10S", 2710), ("PT1H", 3600), ("P1DT2S", 86402), ("PT0S", 0), ("P0D", 0), ("", None)]
)
def test_iso_duration(value, seconds):
    assert enrich.iso_duration_seconds(value) == seconds


@pytest.mark.parametrize(
    "value,seconds", [("1:02:03", 3723), ("62:03", 3723), ("3723", 3723), ("", None), ("n/a", None)]
)
def test_itunes_duration(value, seconds):
    assert enrich.itunes_duration_seconds(value) == seconds


def test_clean_emails_drops_non_addresses_and_keeps_first_source():
    raw = enrich.find_emails("Mail Hi@X.example. or logo@2x.png or a@example.com", "s1")
    raw += [{"value": "hi@x.example", "source_url": "s2"}]
    assert enrich.clean_emails(raw) == [{"value": "hi@x.example", "source_url": "s1"}]


def test_skip_domains():
    skip = ["instagram.com", "youtube.com"]
    assert enrich.is_skipped_domain("https://www.instagram.com/a", skip)
    assert enrich.is_skipped_domain("https://m.youtube.com/a", skip)
    assert not enrich.is_skipped_domain("https://notyoutube.com/a", skip)


def test_size_problem():
    assert enrich.size_problem(500, "1000", "250000") == "size 500 below 1000"
    assert enrich.size_problem(None, "1000", "250000") is None  # hidden count is never a reason
    assert enrich.size_problem(5000, None, None) is None  # podcasts have no band


# ---- stage ----


def test_youtube_profile_and_items(conn, config, fake_http, candidates):
    fake_http(respond)
    enrich.run(conn, config)
    p = profiles_by_id(conn).loc["UC_OK"]
    assert p.enrich_status == "ok"
    assert p.handle == "@UC_OK" and p.profile_url == "https://www.youtube.com/@UC_OK"
    assert p.subscribers == 5000 and p.country == "US"
    assert p.last_content_at.startswith(RECENT[:10])
    assert p.website == "https://chan.example"
    emails = json.loads(p.emails)
    assert emails == [{"value": "hi@chan.example", "source_url": "https://www.youtube.com/@UC_OK"}]
    assert any(lk["url"] == "https://acme.example" for lk in json.loads(p.links))
    items = pd.read_sql("SELECT * FROM content_items WHERE platform_id = 'UC_OK'", conn)
    assert list(items.item_id) == ["v1"]  # v2 is older than the 60-day window
    assert items.iloc[0].duration_seconds == 2710 and items.iloc[0].has_captions == 0


def test_out_of_scope_channels_skip_upload_calls(conn, config, fake_http, candidates):
    fake = fake_http(respond)
    enrich.run(conn, config)
    p = profiles_by_id(conn)
    assert p.loc["UC_BIG", "enrich_status"] == "skipped: size 9000000 above 250000"
    assert p.loc["UC_IN", "enrich_status"] == "skipped: country IN not approved"
    assert p.loc["UC_GONE", "enrich_status"] == "failed: channel not returned by API"
    playlist_calls = [c for c in fake.calls if "playlistItems" in c["url"]]
    assert [c["params"]["playlistId"] for c in playlist_calls] == ["UUUC_OK"]


def test_podcast_profile_from_rss(conn, config, fake_http, candidates):
    fake_http(respond)
    enrich.run(conn, config)
    p = profiles_by_id(conn).loc["itunes:1"]
    assert p.language == "en-us" and p.total_items == 2 and p.website == "https://showx.example"
    emails = {e["value"]: e["source_url"] for e in json.loads(p.emails)}
    assert emails["host@showx.example"] == "https://feed/x"  # the feed's listed owner email
    assert emails["bookings@showx.example"] == "https://showx.example/contact-us"  # from the contact page
    items = pd.read_sql("SELECT * FROM content_items WHERE platform_id = 'itunes:1'", conn)
    assert list(items.title) == ["New ep"]
    assert items.iloc[0].duration_seconds == 3723 and items.iloc[0].has_captions == 1


def test_website_pages_and_social_links(conn, config, fake_http, candidates):
    fake = fake_http(respond)
    enrich.run(conn, config)
    p = profiles_by_id(conn).loc["itunes:1"]
    pages = json.loads(p.pages)
    assert [pg["url"] for pg in pages] == ["https://showx.example", "https://showx.example/contact-us"]  # about = 404
    assert "Austin, Texas" in pages[0]["text"]
    assert any("instagram.com/showx" in lk["url"] for lk in json.loads(p.links))
    assert not any("instagram.com" in c["url"] for c in fake.calls)  # recorded, never fetched
    assert "logo@2x.png" not in p.emails


def test_missing_feed_is_failed_not_guessed(conn, config, fake_http, candidates):
    fake_http(respond)
    enrich.run(conn, config)
    p = profiles_by_id(conn).loc["itunes:2"]
    assert p.enrich_status == "failed: no feed URL"
    assert json.loads(p.emails) == [] and pd.isna(p.website)


def test_robots_disallow_blocks_fetch(conn, config, fake_http, candidates):
    def strict(url, params):
        if url.endswith("/robots.txt"):
            return FakeResponse(200, text="User-agent: *\nDisallow: /")
        return respond(url, params)

    fake = fake_http(strict)
    enrich.run(conn, config)
    p = profiles_by_id(conn).loc["itunes:1"]
    assert p.enrich_status == "partial: website (robots.txt disallows)"
    assert not any(c["url"].rstrip("/") == "https://showx.example" for c in fake.calls)


def test_broken_feed_logged_and_row_kept(conn, config, fake_http, candidates):
    fake_http(lambda url, params: FakeResponse(500) if url == "https://feed/x" else respond(url, params))
    enrich.run(conn, config)
    assert profiles_by_id(conn).loc["itunes:1", "enrich_status"].startswith("failed: feed")


def test_youtube_quota_marks_rows_failed(conn, config, fake_http, candidates):
    quota = FakeResponse(403, {"error": {"errors": [{"reason": "quotaExceeded"}]}})
    fake_http(lambda url, params: quota if "googleapis" in url else respond(url, params))
    enrich.run(conn, config)
    p = profiles_by_id(conn)
    assert (p[p.platform == "youtube"].enrich_status == "failed: quota used up").all()
    assert p.loc["itunes:1", "enrich_status"] == "ok"  # podcasts unaffected


def test_rerun_makes_no_calls(conn, config, fake_http, candidates):
    fake = fake_http(respond)
    enrich.run(conn, config)
    first = len(fake.calls)
    before = pd.read_sql("SELECT * FROM profiles", conn)
    enrich.run(conn, config)
    assert len(fake.calls) == first  # Phase 1 rule: no repeat calls on rerun (404 pages included)
    pd.testing.assert_frame_equal(before, pd.read_sql("SELECT * FROM profiles", conn))


def test_entry_date_is_utc_and_survives_bad_dates():
    import time

    good = {"published_parsed": time.struct_time((2026, 10, 20, 10, 0, 0, 0, 293, 0))}
    assert enrich.entry_date(good).isoformat() == "2026-10-20T10:00:00+00:00"  # not shifted by the local zone
    bad = {"published_parsed": time.struct_time((99999, 1, 1, 0, 0, 0, 0, 1, 0))}
    assert enrich.entry_date(bad) is None
    assert enrich.entry_date({}) is None
