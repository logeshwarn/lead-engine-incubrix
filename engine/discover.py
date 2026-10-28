"""Stage 1, discover: seed keywords -> candidate creators.

Reads data/seeds.csv (active rows) and writes the `candidates` table: one row per
creator per platform with its platform ID, URL, source and the query that found it.
Every API call goes through the cache.

Quality is judged in verify. The one exception: podcasts whose newest episode is older than
the activity window are dropped here, because they can never pass "active" and fetching their
feeds is most of enrich's time (2026-10-28: 57-61% of search results were inactive).
"""

import logging
import os
import time
from datetime import datetime, timedelta, timezone

import pandas as pd

from engine.common import ApiError, cached_get, now_utc, podcastindex_headers

log = logging.getLogger("discover")

YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
PODCASTINDEX_SEARCH_URL = "https://api.podcastindex.org/api/1.0/search/byterm"
ITUNES_SEARCH_URL = "https://itunes.apple.com/search"
# Apple's top-200 chart per genre and store, and the lookup that turns chart IDs into feeds.
# A store's chart leans towards that country's listeners, so non-US stores find more non-US creators.
# The store is never country evidence: verify still needs the creator's own statement.
APPLE_CHART_URL = "https://itunes.apple.com/{store}/rss/toppodcasts/limit=200/genre={genre}/json"
ITUNES_LOOKUP_URL = "https://itunes.apple.com/lookup"
# Category lists of active shows, up to 1000 per call (keyword search stops at 60 results).
PODCASTINDEX_CATEGORY_URLS = {
    "trending": "https://api.podcastindex.org/api/1.0/podcasts/trending",
    "recent": "https://api.podcastindex.org/api/1.0/recent/feeds",
}

CANDIDATE_COLUMNS = [
    "platform",  # youtube | podcast
    "platform_id",  # YouTube channel ID, or itunes:<id> / podcastindex:<id> for podcasts
    "name",
    "url",
    "description",
    "website",
    "feed_url",
    "language",
    "itunes_store_country",  # the Apple store that listed it: a hint only, not the creator's country
    "source",  # youtube | podcastindex | itunes
    "query",
    "seed_id",
    "segment",
    "niche",
    "size_min",  # the seed's subscriber band, carried so enrich can skip out-of-band channels
    "size_max",
    "newest_item_at",  # newest episode date as the directory reports it (podcasts); blank when unknown
    "discovered_at",
]


def load_seeds(path):
    seeds = pd.read_csv(path, dtype=str)
    return seeds[seeds["status"] == "active"]


def keywords(seed):
    return [k.strip() for k in seed["discovery_keywords"].split(";") if k.strip()]


def podcast_id(itunes_id, podcastindex_id):
    # The iTunes ID is shared by both directories, so the same show found in either gets one ID.
    return f"itunes:{itunes_id}" if itunes_id else f"podcastindex:{podcastindex_id}"


def youtube_rows(data):
    rows = []
    for item in data.get("items", []):
        channel_id = item.get("id", {}).get("channelId") or item.get("snippet", {}).get("channelId")
        if not channel_id:
            continue  # without a stable ID the row cannot be verified, so skip it
        snippet = item.get("snippet", {})
        rows.append(
            {
                "platform": "youtube",
                "platform_id": channel_id,
                "name": snippet.get("channelTitle") or snippet.get("title"),
                "url": f"https://www.youtube.com/channel/{channel_id}",
                "description": snippet.get("description"),
                "source": "youtube",
            }
        )
    return rows


def from_unix(seconds):
    return datetime.fromtimestamp(seconds, timezone.utc).isoformat() if seconds else None


def podcastindex_rows(data):
    rows = []
    for feed in data.get("feeds", []):
        if not feed.get("id"):
            continue
        # Search results call it newestItemPubdate; the category lists call it newestItemPublishTime.
        newest = feed.get("newestItemPubdate") or feed.get("newestItemPublishTime")
        rows.append(
            {
                "platform": "podcast",
                "platform_id": podcast_id(feed.get("itunesId"), feed["id"]),
                "name": feed.get("title"),
                "url": f"https://podcastindex.org/podcast/{feed['id']}",
                "description": feed.get("description"),
                "website": feed.get("link"),
                "feed_url": feed.get("url"),
                "language": feed.get("language"),
                "newest_item_at": from_unix(newest),
                "source": "podcastindex",
            }
        )
    return rows


def itunes_rows(data, store_country):
    rows = []
    for show in data.get("results", []):
        if not show.get("collectionId"):
            continue
        rows.append(
            {
                "platform": "podcast",
                "platform_id": podcast_id(show["collectionId"], None),
                "name": show.get("collectionName"),
                "url": show.get("collectionViewUrl"),
                "feed_url": show.get("feedUrl"),
                "itunes_store_country": store_country,
                "newest_item_at": show.get("releaseDate"),  # Apple's date of the latest episode
                "source": "itunes",
            }
        )
    return rows


def search_youtube(conn, config, keyword, api_key):
    params = {
        "part": "snippet",
        "q": keyword,
        "type": "channel",
        "maxResults": config["discover"]["youtube_max_results"],
        "relevanceLanguage": config["language"]["required"],
        "key": api_key,
    }
    data, _ = cached_get(
        conn, "youtube.search", YOUTUBE_SEARCH_URL, params, config["http"], config["cache"]["search_max_age_days"]
    )
    return youtube_rows(data)


def search_podcastindex(conn, config, keyword, api_key, api_secret):
    params = {"q": keyword, "max": config["discover"]["podcastindex_max_results"]}
    data, _ = cached_get(
        conn,
        "podcastindex.search",
        PODCASTINDEX_SEARCH_URL,
        params,
        config["http"],
        config["cache"]["search_max_age_days"],
        headers_fn=lambda: podcastindex_headers(api_key, api_secret),
    )
    return podcastindex_rows(data)


def search_podcast_category(conn, config, category, list_name, api_key, api_secret):
    """One Podcast Index category list ("trending" or "recent"): active English shows."""
    params = {"cat": category, "lang": "en", "max": config["discover"]["category_max_results"]}
    data, _ = cached_get(
        conn,
        f"podcastindex.{list_name}",
        PODCASTINDEX_CATEGORY_URLS[list_name],
        params,
        config["http"],
        config["cache"]["search_max_age_days"],
        headers_fn=lambda: podcastindex_headers(api_key, api_secret),
    )
    return podcastindex_rows(data)


def drop_inactive(candidates, days):
    """Remove podcasts whose newest episode is known and older than `days`. Unknown dates stay."""
    newest = pd.to_datetime(candidates["newest_item_at"], utc=True, errors="coerce", format="ISO8601")
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    inactive = (candidates["platform"] == "podcast") & newest.notna() & (newest < cutoff)
    return candidates[~inactive], int(inactive.sum())


def search_itunes(conn, config, keyword, country):
    params = {
        "term": keyword,
        "media": "podcast",
        "entity": "podcast",
        "country": country.lower(),
        "limit": config["discover"]["itunes_limit"],
    }
    data, was_cached = cached_get(
        conn, "itunes.search", ITUNES_SEARCH_URL, params, config["http"], config["cache"]["search_max_age_days"]
    )
    if not was_cached:
        time.sleep(config["discover"]["itunes_pause_seconds"])  # stay under Apple's rate limit
    return itunes_rows(data, country)


def apple_pause(config, was_cached):
    if not was_cached:
        time.sleep(config["discover"]["itunes_pause_seconds"])  # stay under Apple's rate limit


def search_apple_chart(conn, config, genre_name, store):
    """Shows on Apple's top-200 chart for one genre in one store, as candidate rows."""
    genre = config["discover"]["apple_genres"][genre_name]
    url = APPLE_CHART_URL.format(store=store.lower(), genre=genre)
    data, was_cached = cached_get(conn, "apple.chart", url, {}, config["http"], config["cache"]["search_max_age_days"])
    apple_pause(config, was_cached)
    entries = data.get("feed", {}).get("entry", [])
    entries = [entries] if isinstance(entries, dict) else entries  # one entry comes back as a dict
    ids = [e["id"]["attributes"]["im:id"] for e in entries if e.get("id", {}).get("attributes", {}).get("im:id")]
    rows = []
    for i in range(0, len(ids), 100):  # the lookup takes many IDs per call; 100 keeps the URL short
        params = {"id": ",".join(ids[i : i + 100]), "entity": "podcast"}
        found, was_cached = cached_get(
            conn, "itunes.lookup", ITUNES_LOOKUP_URL, params, config["http"], config["cache"]["search_max_age_days"]
        )
        apple_pause(config, was_cached)
        rows += itunes_rows(found, store)
    for row in rows:
        row["source"] = "apple_chart"
    return rows


def run(conn, config, seeds_path):
    """Search every active seed keyword and write the `candidates` table."""
    seeds = load_seeds(seeds_path)
    yt_key = os.getenv("YOUTUBE_API_KEY", "")
    pi_key, pi_secret = os.getenv("PODCASTINDEX_API_KEY", ""), os.getenv("PODCASTINDEX_API_SECRET", "")
    youtube_on, podcastindex_on = bool(yt_key), bool(pi_key and pi_secret)
    if not youtube_on:
        log.error("YOUTUBE_API_KEY is empty: skipping YouTube discovery")
    if not podcastindex_on:
        log.error("Podcast Index key or secret is empty: skipping Podcast Index discovery (iTunes still runs)")

    rows, failures = [], 0
    for _, seed in seeds.iterrows():
        for keyword in keywords(seed):
            found = []
            if seed["primary_platform"] == "youtube" and youtube_on:
                try:
                    found += search_youtube(conn, config, keyword, yt_key)
                except ApiError as e:
                    failures += 1
                    log.error("seed %s %r: %s", seed["seed_id"], keyword, e)
                    if e.reason == "quotaExceeded":
                        # More calls today would all fail; the next run resumes from the cache.
                        log.error("YouTube daily quota used up: skipping remaining YouTube searches")
                        youtube_on = False
            elif seed["primary_platform"] == "podcast":
                # Podcast Index first, then each iTunes store in config (one is enough: stores overlap fully).
                searches = []
                if podcastindex_on:
                    searches.append(("podcastindex", search_podcastindex, (conn, config, keyword, pi_key, pi_secret)))
                for country in config["discover"]["itunes_stores"]:
                    searches.append((f"itunes {country}", search_itunes, (conn, config, keyword, country)))
                for name, search, search_args in searches:
                    try:
                        found += search(*search_args)
                    except ApiError as e:
                        failures += 1
                        log.error("seed %s %r %s: %s", seed["seed_id"], keyword, name, e)
            elif seed["primary_platform"] == "podcast_category" and podcastindex_on:
                # The keyword is a Podcast Index category name; both lists add different shows.
                for list_name in config["discover"]["category_lists"]:
                    try:
                        found += search_podcast_category(conn, config, keyword, list_name, pi_key, pi_secret)
                    except ApiError as e:
                        failures += 1
                        log.error("seed %s category %r %s: %s", seed["seed_id"], keyword, list_name, e)
            elif seed["primary_platform"] == "apple_chart":
                # The keyword is an Apple genre name (discover.apple_genres); one chart per non-US store.
                for store in config["discover"]["chart_stores"]:
                    try:
                        found += search_apple_chart(conn, config, keyword, store)
                    except ApiError as e:
                        failures += 1
                        log.error("seed %s chart %r %s: %s", seed["seed_id"], keyword, store, e)
            for row in found:
                row.update(
                    query=keyword,
                    seed_id=seed["seed_id"],
                    segment=seed["segment"],
                    niche=seed["niche"],
                    size_min=seed["size_min"],
                    size_max=seed["size_max"],
                    discovered_at=now_utc().date().isoformat(),
                )
            rows += found

    candidates = pd.DataFrame(rows, columns=CANDIDATE_COLUMNS)
    found_total = len(candidates)
    # Same creator from several keywords or sources: keep the first hit (seed order is the owner's priority).
    candidates = candidates.drop_duplicates(["platform", "platform_id"], keep="first")
    candidates, inactive = drop_inactive(candidates, config["activity"]["long_form_days"])
    # Rebuilt from the cache every run, so replacing the table is safe and keeps the stage rerunnable.
    candidates.to_sql("candidates", conn, if_exists="replace", index=False)
    log.info(
        "%d seeds, %d hits, %d unique candidates (%s), %d inactive podcasts dropped, %d failed searches",
        len(seeds),
        found_total,
        len(candidates),
        candidates["platform"].value_counts().to_dict(),
        inactive,
        failures,
    )
    return candidates
