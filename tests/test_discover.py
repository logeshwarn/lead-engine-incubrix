"""discover: seeds -> candidates, with one row per creator and no repeat calls on rerun."""

import pandas as pd
import pytest
from conftest import FakeResponse

from engine import discover

YT_BODY = {
    "items": [
        {"id": {"channelId": "UC_A"}, "snippet": {"channelTitle": "Chan A", "description": "a"}},
        {"id": {"channelId": "UC_B"}, "snippet": {"channelTitle": "Chan B", "description": "b"}},
        {"id": {}, "snippet": {"title": "no id"}},  # no stable ID: must be skipped
    ]
}
PI_BODY = {
    "feeds": [
        {
            "id": 11,
            "itunesId": 999,
            "title": "Show X",
            "url": "https://feed/x",
            "link": "https://x.com",
            "language": "en",
        },
        {"id": 12, "itunesId": None, "title": "Show Y", "url": "https://feed/y", "language": "en"},
    ]
}
ITUNES_BODY = {
    "results": [
        {
            "collectionId": 999,
            "collectionName": "Show X",
            "collectionViewUrl": "https://apple/x",
            "feedUrl": "https://feed/x",
        },
        {
            "collectionId": 555,
            "collectionName": "Show Z",
            "collectionViewUrl": "https://apple/z",
            "feedUrl": "https://feed/z",
        },
    ]
}


def respond(url, params):
    if "googleapis" in url:
        return FakeResponse(200, YT_BODY)
    if "podcastindex" in url:
        return FakeResponse(200, PI_BODY)
    return FakeResponse(200, ITUNES_BODY)


@pytest.fixture
def seeds_file(tmp_path):
    rows = [
        [
            "S1",
            "YouTuber/Video-First Creator",
            "tech",
            "youtube",
            "tech reviews; gadget channel",
            "x",
            1000,
            5000,
            "active",
        ],
        ["S2", "Podcaster/Video Podcaster", "biz", "podcast", "business podcast", "x", None, None, "active"],
        ["S3", "Expert-Led Creator", "coach", "youtube", "life coach", "x", 1000, 5000, "paused"],
    ]
    cols = ["seed_id", "segment", "niche", "primary_platform", "discovery_keywords", "need_signal_to_check",
            "size_min", "size_max", "status"]  # fmt: skip
    path = tmp_path / "seeds.csv"
    pd.DataFrame(rows, columns=cols).to_csv(path, index=False)
    return path


@pytest.fixture(autouse=True)
def keys(monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "yt")
    monkeypatch.setenv("PODCASTINDEX_API_KEY", "pk")
    monkeypatch.setenv("PODCASTINDEX_API_SECRET", "ps")


def test_candidates_found_and_deduped(conn, config, fake_http, seeds_file):
    fake_http(respond)
    c = discover.run(conn, config, seeds_file)
    # UC_A and UC_B appear under both YouTube keywords but are kept once each.
    assert sorted(c.loc[c.platform == "youtube", "platform_id"]) == ["UC_A", "UC_B"]
    # Show X is in Podcast Index and iTunes with the same iTunes ID: one row.
    assert sorted(c.loc[c.platform == "podcast", "platform_id"]) == ["itunes:555", "itunes:999", "podcastindex:12"]
    assert not c.duplicated(["platform", "platform_id"]).any()
    assert list(c.columns) == discover.CANDIDATE_COLUMNS


def test_first_hit_keeps_its_query_and_seed(conn, config, fake_http, seeds_file):
    fake_http(respond)
    c = discover.run(conn, config, seeds_file).set_index("platform_id")
    assert c.loc["UC_A", "query"] == "tech reviews"
    assert c.loc["UC_A", "seed_id"] == "S1"
    assert c.loc["itunes:999", "source"] == "podcastindex"  # Podcast Index is searched before iTunes


def test_paused_seed_skipped(conn, config, fake_http, seeds_file):
    fake = fake_http(respond)
    discover.run(conn, config, seeds_file)
    assert all(call["params"].get("q") != "life coach" for call in fake.calls)


def test_one_call_per_keyword_and_source(conn, config, fake_http, seeds_file):
    fake = fake_http(respond)
    discover.run(conn, config, seeds_file)
    stores = len(config["discover"]["itunes_stores"])
    # 2 YouTube keywords + 1 podcast keyword x (Podcast Index + one iTunes call per configured store)
    assert len(fake.calls) == 2 + 1 + stores


def test_rerun_makes_no_api_calls(conn, config, fake_http, seeds_file):
    fake = fake_http(respond)
    first = discover.run(conn, config, seeds_file)
    calls_first_run = len(fake.calls)
    second = discover.run(conn, config, seeds_file)
    assert len(fake.calls) == calls_first_run  # every call on the rerun came from the cache
    pd.testing.assert_frame_equal(first.reset_index(drop=True), second.reset_index(drop=True))


def test_table_written(conn, config, fake_http, seeds_file):
    fake_http(respond)
    discover.run(conn, config, seeds_file)
    assert pd.read_sql("SELECT * FROM candidates", conn).shape[0] == 5


def test_failed_search_logged_and_skipped(conn, config, fake_http, seeds_file):
    def flaky(url, params):
        return FakeResponse(500) if params.get("q") == "tech reviews" else respond(url, params)

    fake_http(flaky)
    c = discover.run(conn, config, seeds_file)
    # The failed keyword is skipped; the other YouTube keyword still finds both channels.
    assert sorted(c.loc[c.platform == "youtube", "query"].unique()) == ["gadget channel"]


def test_quota_exceeded_stops_youtube(conn, config, fake_http, seeds_file):
    quota = FakeResponse(403, {"error": {"errors": [{"reason": "quotaExceeded"}]}})
    fake = fake_http(lambda url, params: quota if "googleapis" in url else respond(url, params))
    c = discover.run(conn, config, seeds_file)
    assert sum("googleapis" in call["url"] for call in fake.calls) == 1  # no second YouTube call
    assert (c.platform == "podcast").all()  # podcasts still discovered


def test_missing_youtube_key_skips_youtube(conn, config, fake_http, seeds_file, monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "")
    fake = fake_http(respond)
    discover.run(conn, config, seeds_file)
    assert not any("googleapis" in call["url"] for call in fake.calls)


# ---------- volume step: category lists and inactive shows ----------

NOW_TS = int(pd.Timestamp.now(tz="UTC").timestamp())
CATEGORY_BODY = {
    "feeds": [
        {"id": 21, "itunesId": 2100, "title": "Active A", "url": "https://feed/a", "language": "en",
         "newestItemPublishTime": NOW_TS - 5 * 86400},
        {"id": 22, "itunesId": 2200, "title": "Old B", "url": "https://feed/b", "language": "en",
         "newestItemPublishTime": NOW_TS - 200 * 86400},
        {"id": 23, "itunesId": None, "title": "No date C", "url": "https://feed/c", "language": "en"},
    ]
}  # fmt: skip


@pytest.fixture
def category_seeds(tmp_path):
    cols = ["seed_id", "segment", "niche", "primary_platform", "discovery_keywords", "need_signal_to_check",
            "size_min", "size_max", "status"]  # fmt: skip
    path = tmp_path / "cat_seeds.csv"
    pd.DataFrame([["C1", "Podcaster/Video Podcaster", "fitness", "podcast_category", "Fitness", "x", None, None,
                   "active"]], columns=cols).to_csv(path, index=False)  # fmt: skip
    return path


def test_category_seed_calls_both_lists(conn, config, fake_http, category_seeds):
    fake = fake_http(lambda url, params: FakeResponse(200, CATEGORY_BODY))
    discover.run(conn, config, category_seeds)
    assert sorted(c["url"].rsplit("/", 2)[-2] + "/" + c["url"].rsplit("/", 1)[-1] for c in fake.calls) == [
        "podcasts/trending",
        "recent/feeds",
    ]
    assert all(c["params"] == {"cat": "Fitness", "lang": "en", "max": 1000} for c in fake.calls)


def test_inactive_podcasts_dropped_unknown_kept(conn, config, fake_http, category_seeds):
    fake_http(lambda url, params: FakeResponse(200, CATEGORY_BODY))
    c = discover.run(conn, config, category_seeds)
    assert sorted(c["name"]) == ["Active A", "No date C"]  # Old B's newest episode is 200 days old
    assert c.set_index("name").loc["Active A", "newest_item_at"].startswith(str(pd.Timestamp.now(tz="UTC").year))


def test_drop_inactive_never_touches_youtube():
    old = (pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=300)).isoformat()
    df = pd.DataFrame([{"platform": "youtube", "newest_item_at": old}, {"platform": "podcast", "newest_item_at": old}])
    kept, dropped = discover.drop_inactive(df, 60)
    assert list(kept["platform"]) == ["youtube"] and dropped == 1


# ---------- Apple charts per non-US store (2026-10-28) ----------

CHART_BODY = {"feed": {"entry": [{"id": {"attributes": {"im:id": "111"}}}, {"id": {"attributes": {"im:id": "222"}}}]}}
LOOKUP_BODY = {
    "results": [
        {"collectionId": 111, "collectionName": "UK Coach Show", "collectionViewUrl": "https://apple/111",
         "feedUrl": "https://feed/111", "releaseDate": pd.Timestamp.now(tz="UTC").isoformat()},
        {"collectionId": 222, "collectionName": "Old Show", "collectionViewUrl": "https://apple/222",
         "feedUrl": "https://feed/222", "releaseDate": "2020-01-01T00:00:00Z"},
    ]
}  # fmt: skip


@pytest.fixture
def chart_seeds(tmp_path):
    cols = ["seed_id", "segment", "niche", "primary_platform", "discovery_keywords", "need_signal_to_check",
            "size_min", "size_max", "status"]  # fmt: skip
    path = tmp_path / "chart_seeds.csv"
    pd.DataFrame([["A1", "Podcaster/Video Podcaster", "chart_health", "apple_chart", "Health & Fitness", "x", None,
                   None, "active"]], columns=cols).to_csv(path, index=False)  # fmt: skip
    return path


def test_apple_chart_seed_reads_each_store_and_drops_inactive(conn, config, fake_http, chart_seeds):
    config["discover"]["chart_stores"] = ["GB", "AU"]
    fake = fake_http(lambda url, params: FakeResponse(200, CHART_BODY if "toppodcasts" in url else LOOKUP_BODY))
    c = discover.run(conn, config, chart_seeds)
    charts = [call["url"] for call in fake.calls if "toppodcasts" in call["url"]]
    assert charts == [
        "https://itunes.apple.com/gb/rss/toppodcasts/limit=200/genre=1512/json",
        "https://itunes.apple.com/au/rss/toppodcasts/limit=200/genre=1512/json",
    ]
    assert c["platform_id"].tolist() == ["itunes:111"]  # one row though it charts in both stores; 222 is inactive
    assert c.iloc[0]["source"] == "apple_chart" and c.iloc[0]["itunes_store_country"] == "GB"
