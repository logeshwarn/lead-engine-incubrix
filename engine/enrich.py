"""Stage 2, enrich: candidates -> profiles + recent content items.

Reads the `candidates` table and writes two tables:
- `profiles`: one row per candidate with profile facts, public emails and links (each with the
  URL it was found on), website page text, and an enrich_status saying what worked.
- `content_items`: recent uploads or episodes (last `enrich.recent_days`) with date, duration,
  caption/transcript flag and description, so verify can count activity and quote evidence.

Only public data is read: the YouTube Data API, the creator's own RSS feed, and pages on the
creator's own website that robots.txt allows. Nothing is guessed: a value we cannot find stays blank.
"""

import json
import logging
import os
import re
from calendar import timegm
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import feedparser
import pandas as pd
from bs4 import BeautifulSoup

from engine.common import USER_AGENT, ApiError, cached_get, now_utc

log = logging.getLogger("enrich")

YT_CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"
YT_PLAYLIST_URL = "https://www.googleapis.com/youtube/v3/playlistItems"
YT_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
# Cache name for parsed feeds. Bump the version when parse_feed output changes, so results parsed
# by older code are not reused (v2: episode dates read as UTC, not local time).
FEED_CACHE = "rss.v2"

PROFILE_COLUMNS = [
    "platform",
    "platform_id",
    "name",
    "profile_url",
    "handle",
    "description",
    "country",  # only as the platform states it; blank when not stated
    "language",
    "subscribers",  # YouTube only; blank when hidden or for podcasts
    "total_items",
    "created_at",
    "last_content_at",
    "website",
    "emails",  # JSON list of {"value", "source_url"}: only addresses published by the creator
    "links",  # JSON list of {"url", "source_url"}
    "pages",  # JSON list of {"url", "title", "text"} from the creator's own website
    "feed_url",
    "segment",
    "niche",
    "seed_id",
    "query",
    "source",
    "itunes_store_country",
    "enrich_status",  # ok | partial: ... | skipped: ... | failed: ...
    "enriched_at",
]
ITEM_COLUMNS = [
    "platform",
    "platform_id",
    "item_id",
    "title",
    "url",
    "published_at",
    "duration_seconds",
    "has_captions",  # YouTube caption flag, or podcast transcript tag; blank when unknown
    "description",
]

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
URL_RE = re.compile(r"https?://[^\s<>\"')\]]+")
NOT_EMAIL_ENDINGS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")  # e.g. logo@2x.png in page source


# ---------- small parsers (pure functions, unit tested) ----------


def iso_duration_seconds(value):
    """YouTube ISO 8601 duration, e.g. PT1H2M3S -> 3723. Returns None when absent."""
    m = re.fullmatch(r"P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?", value or "")
    if not m or not value or value == "P":
        return None
    d, h, mi, s = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s


def itunes_duration_seconds(value):
    """iTunes duration: '1:02:03', '62:03' or '3723'. Returns None when absent or unreadable."""
    value = (value or "").strip()
    if not value:
        return None
    try:
        parts = [float(p) for p in value.split(":")]
    except ValueError:
        return None
    seconds = 0
    for p in parts:
        seconds = seconds * 60 + p
    return int(seconds)


def find_emails(text, source_url):
    """Addresses written in public text, tagged with where they were seen. Filtering is in clean_emails."""
    return [{"value": e, "source_url": source_url} for e in EMAIL_RE.findall(text or "")]


def clean_emails(emails):
    """Lower-case, drop anything that is not a real-looking address, keep the first source per address."""
    kept = []
    for e in emails:
        value = (e["value"] or "").strip().lower().rstrip(".")
        if EMAIL_RE.fullmatch(value) and not value.endswith(NOT_EMAIL_ENDINGS) and not value.endswith("@example.com"):
            kept.append({"value": value, "source_url": e["source_url"]})
    return unique_by(kept, "value")


def find_links(text, source_url):
    return [{"url": u.rstrip(".,;"), "source_url": source_url} for u in URL_RE.findall(text or "")]


def unique_by(items, key, limit=None):
    seen, out = set(), []
    for item in items:
        if item[key] not in seen:
            seen.add(item[key])
            out.append(item)
    return out[:limit] if limit else out


def host(url):
    netloc = urlparse(url or "").netloc.lower()
    return netloc[4:] if netloc.startswith("www.") else netloc


def is_skipped_domain(url, skip_domains):
    h = host(url)
    return any(h == d or h.endswith("." + d) for d in skip_domains)


def parse_iso(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


# ---------- YouTube ----------


def _yt_get(conn, config, source, url, params, api_key):
    data, _ = cached_get(
        conn, source, url, {**params, "key": api_key}, config["http"], config["cache"]["enrich_max_age_days"]
    )
    return data


def size_problem(subscribers, size_min, size_max):
    """Why a channel is outside its seed's subscriber band, or None. Unknown size is never a reason."""
    if subscribers is None:
        return None
    lo, hi = pd.to_numeric(size_min, errors="coerce"), pd.to_numeric(size_max, errors="coerce")
    if pd.notna(lo) and subscribers < lo:
        return f"size {subscribers} below {int(lo)}"
    if pd.notna(hi) and subscribers > hi:
        return f"size {subscribers} above {int(hi)}"
    return None


def enrich_youtube(conn, config, candidates, api_key):
    """Profiles and recent items for YouTube candidates. Costs about 2-3 quota units per channel."""
    profiles, items = [], []
    cutoff = now_utc() - timedelta(days=config["enrich"]["recent_days"])
    approved = set(config["countries"]["approved"])
    ids = sorted(candidates["platform_id"])  # sorted so batches (and their cache keys) are stable between runs
    channels, quota_hit = {}, False
    for i in range(0, len(ids), 50):  # channels.list takes up to 50 IDs for 1 unit
        batch = ids[i : i + 50]
        try:
            data = _yt_get(
                conn,
                config,
                "youtube.channels",
                YT_CHANNELS_URL,
                {"part": "snippet,statistics,contentDetails", "id": ",".join(batch), "maxResults": 50},
                api_key,
            )
            channels.update({c["id"]: c for c in data.get("items", [])})
        except ApiError as e:
            log.error("youtube channels batch %d: %s", i // 50, e)
            quota_hit = quota_hit or e.reason == "quotaExceeded"

    for cand in candidates.to_dict("records"):
        row = base_profile(cand)
        ch = channels.get(cand["platform_id"])
        if ch is None:
            row["enrich_status"] = "failed: quota used up" if quota_hit else "failed: channel not returned by API"
            profiles.append(row)
            continue
        sn, st = ch.get("snippet", {}), ch.get("statistics", {})
        subs = None if st.get("hiddenSubscriberCount") else int(st.get("subscriberCount", 0))
        handle = sn.get("customUrl")
        row.update(
            name=sn.get("title"),
            handle=handle,
            profile_url=f"https://www.youtube.com/{handle}" if handle else row["profile_url"],
            description=sn.get("description"),
            country=sn.get("country"),
            language=sn.get("defaultLanguage"),
            subscribers=subs,
            total_items=int(st.get("videoCount", 0)),
            created_at=sn.get("publishedAt"),
        )
        emails = find_emails(sn.get("description"), row["profile_url"])
        links = find_links(sn.get("description"), row["profile_url"])

        # Skip the per-channel calls when the channel cannot qualify anyway: saves quota for the rest.
        skip = size_problem(subs, cand.get("size_min"), cand.get("size_max"))
        if not skip and row["country"] and row["country"] not in approved:
            skip = f"country {row['country']} not approved"
        if not skip and row["total_items"] == 0:
            skip = "no uploads"
        if skip or quota_hit:
            row["enrich_status"] = f"skipped: {skip}" if skip else "failed: quota used up"
            row.update(emails=emails, links=links)
            profiles.append(row)
            continue

        status = []
        try:
            uploads = ch["contentDetails"]["relatedPlaylists"]["uploads"]
            pl = _yt_get(
                conn,
                config,
                "youtube.playlistItems",
                YT_PLAYLIST_URL,
                {"part": "contentDetails", "playlistId": uploads, "maxResults": config["enrich"]["youtube_uploads"]},
                api_key,
            )
            uploads = [
                (it["contentDetails"]["videoId"], it["contentDetails"].get("videoPublishedAt"))
                for it in pl.get("items", [])
            ]
            dates = [parse_iso(d) for _, d in uploads if d]
            row["last_content_at"] = max(dates).isoformat() if dates else None
            recent = [vid for vid, d in uploads if d and parse_iso(d) >= cutoff]
            if recent:
                vids = _yt_get(
                    conn,
                    config,
                    "youtube.videos",
                    YT_VIDEOS_URL,
                    {"part": "snippet,contentDetails", "id": ",".join(recent[:50]), "maxResults": 50},
                    api_key,
                )
                for v in vids.get("items", []):
                    vurl = f"https://www.youtube.com/watch?v={v['id']}"
                    desc = v["snippet"].get("description", "")
                    items.append(
                        {
                            "platform": "youtube",
                            "platform_id": cand["platform_id"],
                            "item_id": v["id"],
                            "title": v["snippet"].get("title"),
                            "url": vurl,
                            "published_at": v["snippet"].get("publishedAt"),
                            "duration_seconds": iso_duration_seconds(v["contentDetails"].get("duration")),
                            "has_captions": v["contentDetails"].get("caption") == "true",
                            "description": desc[: config["enrich"]["item_text_chars"]],
                        }
                    )
                    # Video descriptions often hold the sponsor links and "business inquiries" address.
                    emails += find_emails(desc, vurl)
                    links += find_links(desc, vurl)
                    row["language"] = row["language"] or v["snippet"].get("defaultAudioLanguage")
        except ApiError as e:
            status.append(f"uploads ({e.reason or e.status})")
            log.error("youtube %s uploads: %s", cand["platform_id"], e)
            if e.reason == "quotaExceeded":
                quota_hit = True
        row.update(emails=emails, links=links)
        row["enrich_status"] = "partial: " + ", ".join(status) if status else "ok"
        row["website"] = next(
            (u["url"] for u in links if not is_skipped_domain(u["url"], config["enrich"]["skip_domains"])), None
        )
        profiles.append(row)
    return profiles, items


# ---------- podcasts (RSS) ----------


def entry_date(entry):
    """Episode date as UTC, or None when missing or impossible (e.g. year 99999 in a broken feed)."""
    parsed = entry.get("published_parsed")
    if not parsed:
        return None
    try:
        # feedparser gives UTC; timegm reads it as UTC (time.mktime would wrongly apply the local zone).
        return datetime.fromtimestamp(timegm(parsed), timezone.utc)
    except (OverflowError, ValueError, OSError):
        return None  # one bad date drops that date only, not the whole feed


def parse_feed(r, max_episodes, text_chars):
    """RSS bytes -> the few fields we use. Raises when the feed has no readable channel."""
    f = feedparser.parse(r.content)
    if not f.feed and not f.entries:
        raise ValueError("unreadable feed")
    owner = f.feed.get("publisher_detail") or {}
    episodes = []
    for e in f.entries:
        published = entry_date(e)
        episodes.append(
            {
                "id": e.get("id") or e.get("link") or e.get("title"),
                "title": e.get("title"),
                "url": e.get("link"),
                "published_at": published.isoformat() if published else None,
                "duration_seconds": itunes_duration_seconds(e.get("itunes_duration")),
                "has_transcript": bool(e.get("podcast_transcript")),
                "description": BeautifulSoup(e.get("summary", ""), "html.parser").get_text(" ", strip=True)[
                    :text_chars
                ],
            }
        )
    episodes.sort(key=lambda ep: ep["published_at"] or "", reverse=True)
    return {
        "title": f.feed.get("title"),
        "link": f.feed.get("link"),
        "language": f.feed.get("language"),
        "author": f.feed.get("author"),
        "owner_email": owner.get("email"),
        "description": BeautifulSoup(f.feed.get("summary", ""), "html.parser").get_text(" ", strip=True)[:text_chars],
        "episode_count": len(f.entries),
        "episodes": episodes[:max_episodes],
    }


def enrich_podcasts(conn, config, candidates):
    profiles, items = [], []
    cfg = config["enrich"]
    cutoff = now_utc() - timedelta(days=cfg["recent_days"])
    for cand in candidates.to_dict("records"):
        row = base_profile(cand)
        if not cand.get("feed_url"):
            row["enrich_status"] = "failed: no feed URL"
            profiles.append(row)
            continue
        try:
            feed, _ = cached_get(
                conn,
                FEED_CACHE,
                cand["feed_url"],
                {},
                config["http"],
                config["cache"]["enrich_max_age_days"],
                failure_max_age_days=config["cache"]["failure_max_age_days"],
                headers_fn=lambda: {"User-Agent": USER_AGENT},
                parse=lambda r: parse_feed(r, cfg["rss_episodes"], cfg["item_text_chars"]),
            )
        except ApiError as e:
            row["enrich_status"] = f"failed: feed ({e.reason or e.status})"
            log.error("rss %s: %s", cand["platform_id"], e)
            profiles.append(row)
            continue
        feed_url = cand["feed_url"]
        emails = [{"value": feed["owner_email"].lower(), "source_url": feed_url}] if feed.get("owner_email") else []
        emails += find_emails(feed.get("description"), feed_url)
        links = find_links(feed.get("description"), feed_url)
        dates = [ep["published_at"] for ep in feed["episodes"] if ep["published_at"]]
        row.update(
            name=feed.get("title") or row["name"],
            description=feed.get("description"),
            language=feed.get("language") or row["language"],
            total_items=feed.get("episode_count"),
            last_content_at=max(dates) if dates else None,
            website=feed.get("link") or row["website"],
            handle=feed.get("author"),
        )
        for ep in feed["episodes"]:
            if not ep["published_at"] or parse_iso(ep["published_at"]) < cutoff:
                continue
            items.append(
                {
                    "platform": "podcast",
                    "platform_id": cand["platform_id"],
                    "item_id": ep["id"],
                    "title": ep["title"],
                    "url": ep["url"],
                    "published_at": ep["published_at"],
                    "duration_seconds": ep["duration_seconds"],
                    "has_captions": ep["has_transcript"],
                    "description": ep["description"],
                }
            )
            source = ep["url"] or feed_url
            emails += find_emails(ep["description"], source)
            links += find_links(ep["description"], source)
        row.update(emails=emails, links=links, enrich_status="ok")
        profiles.append(row)
    return profiles, items


# ---------- creator website ----------


def parse_page(r, text_chars):
    """HTML -> title, visible text, links (with anchor text) and emails. 4xx pages parse as empty."""
    if r.status_code != 200 or "html" not in r.headers.get("content-type", ""):
        return {"status": r.status_code, "url": r.url, "title": None, "text": "", "links": [], "emails": []}
    soup = BeautifulSoup(r.text, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    links, emails = [], []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.lower().startswith("mailto:"):
            emails.append(href[7:].split("?")[0])
        elif not href.startswith(("#", "javascript:", "tel:")):
            links.append({"url": urljoin(r.url, href), "text": a.get_text(" ", strip=True)[:80]})
    text = soup.get_text(" ", strip=True)
    return {
        "status": 200,
        "url": r.url,
        "title": soup.title.get_text(strip=True) if soup.title else None,
        "text": text[:text_chars],
        "links": links,
        "emails": emails + EMAIL_RE.findall(text),
    }


def robots_allows(conn, config, url):
    """True when robots.txt lets us fetch url. Missing robots.txt (4xx) means allowed; no answer means not."""
    parts = urlparse(url)
    robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
    try:
        lines, _ = cached_get(
            conn,
            "robots",
            robots_url,
            {},
            config["http"],
            config["cache"]["enrich_max_age_days"],
            failure_max_age_days=config["cache"]["failure_max_age_days"],
            headers_fn=lambda: {"User-Agent": USER_AGENT},
            parse=lambda r: r.text.splitlines() if r.status_code == 200 else [],
            ok_statuses=tuple(range(200, 500)),
        )
    except ApiError:
        return False  # cannot read the site's rules, so do not fetch it
    rp = RobotFileParser()
    rp.parse(lines)
    return rp.can_fetch(USER_AGENT, url)


def fetch_page(conn, config, url):
    if not robots_allows(conn, config, url):
        return None
    page, _ = cached_get(
        conn,
        "website",
        url,
        {},
        config["http"],
        config["cache"]["enrich_max_age_days"],
        failure_max_age_days=config["cache"]["failure_max_age_days"],
        headers_fn=lambda: {"User-Agent": USER_AGENT},
        parse=lambda r: parse_page(r, config["enrich"]["website_text_chars"]),
        ok_statuses=tuple(range(200, 500)),
    )
    return page


def enrich_website(conn, config, row):
    """Homepage plus the first same-site contact/about pages. Adds pages, emails and links to row."""
    cfg = config["enrich"]
    url = row.get("website")
    if not url or not url.startswith("http") or is_skipped_domain(url, cfg["skip_domains"]):
        return None
    try:
        home = fetch_page(conn, config, url)
        if home is None:
            return "website (robots.txt disallows)"
        pages = [home]
        for word in cfg["website_pages"]:
            link = next(
                (
                    lk["url"]
                    for lk in home["links"]
                    if host(lk["url"]) == host(url) and (word in lk["url"].lower() or word in lk["text"].lower())
                ),
                None,
            )
            if link and link not in [p["url"] for p in pages]:
                page = fetch_page(conn, config, link)
                if page:
                    pages.append(page)
    except ApiError as e:
        log.error("website %s: %s", url, e)
        return f"website ({e.reason or e.status})"
    for p in pages:
        row["emails"] += [{"value": e, "source_url": p["url"]} for e in p["emails"]]
        row["links"] += [
            {"url": lk["url"], "source_url": p["url"]} for lk in p["links"] if host(lk["url"]) != host(url)
        ]
    row["pages"] = [{"url": p["url"], "title": p["title"], "text": p["text"]} for p in pages if p["status"] == 200]
    return None if row["pages"] else f"website (HTTP {home['status']})"


# ---------- stage ----------


def base_profile(cand):
    row = {c: None for c in PROFILE_COLUMNS}
    for c in ["platform", "platform_id", "name", "description", "language", "feed_url", "website", "segment", "niche",
              "seed_id", "query", "source", "itunes_store_country"]:  # fmt: skip
        value = cand.get(c)
        row[c] = None if pd.isna(value) else value
    row["profile_url"] = cand.get("url")
    row.update(emails=[], links=[], pages=[], enriched_at=now_utc().date().isoformat())
    return row


def run(conn, config):
    candidates = pd.read_sql("SELECT * FROM candidates", conn)
    # NaN is truthy, so a missing feed URL would look present: turn every missing value into None,
    # and loop over plain dicts below (pandas iterrows turns None back into NaN).
    candidates = candidates.astype(object).where(candidates.notna(), None)
    yt = candidates[candidates["platform"] == "youtube"]
    pods = candidates[candidates["platform"] == "podcast"]

    api_key = os.getenv("YOUTUBE_API_KEY", "")
    if api_key:
        yt_profiles, yt_items = enrich_youtube(conn, config, yt, api_key)
    else:
        log.error("YOUTUBE_API_KEY is empty: YouTube candidates not enriched")
        yt_profiles = [{**base_profile(c), "enrich_status": "failed: no YouTube key"} for c in yt.to_dict("records")]
        yt_items = []
    pod_profiles, pod_items = enrich_podcasts(conn, config, pods)

    profiles = yt_profiles + pod_profiles
    for row in profiles:
        if not row["enrich_status"].startswith(("failed", "skipped")):
            problem = enrich_website(conn, config, row)
            if problem:
                row["enrich_status"] = (
                    "partial: " if row["enrich_status"] == "ok" else row["enrich_status"] + ", "
                ) + problem
        row["emails"] = clean_emails(row["emails"])
        row["links"] = unique_by(row["links"], "url", config["enrich"]["max_links"])
        for col in ["emails", "links", "pages"]:
            row[col] = json.dumps(row[col])

    profiles = pd.DataFrame(profiles, columns=PROFILE_COLUMNS)
    items = pd.DataFrame(yt_items + pod_items, columns=ITEM_COLUMNS)
    # Rebuilt from the cache every run, so replacing the tables keeps the stage rerunnable.
    profiles.to_sql("profiles", conn, if_exists="replace", index=False)
    items.to_sql("content_items", conn, if_exists="replace", index=False)
    log.info(
        "%d profiles (%s), %d recent items",
        len(profiles),
        profiles["enrich_status"].str.split(":").str[0].value_counts().to_dict(),
        len(items),
    )
    return profiles, items
