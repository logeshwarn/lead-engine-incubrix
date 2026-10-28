# Tech used inside the app

Update this file when a library, API or data store changes. "Used by" lists only files that exist; planned files are marked *(planned)*.

## Libraries

| Purpose | Library | Version | Used by |
|---|---|---|---|
| Config | PyYAML | 6.0.3 | `engine/common.py` |
| Secrets | python-dotenv | 1.2.4 | `engine/common.py`, `check_apis.py` |
| Logging | Python `logging` | stdlib | `engine/common.py`, `run.py`, `engine/discover.py`: one log file per run |
| Data handling | pandas | 3.1.0 | `engine/discover.py`, `engine/enrich.py`; later stages *(planned)*. Note: pandas 3 `iterrows()` turns `None` into `NaN`, so stages loop over `to_dict("records")` |
| Storage and cache | SQLite (`sqlite3`) | stdlib | `engine/common.py` (`api_cache`, `api_log`), `engine/discover.py` (`candidates`) |
| HTTP | requests | 2.34.2 | `engine/common.py` (`cached_get`), `check_apis.py` |
| Parallel fetching | `concurrent.futures.ThreadPoolExecutor`, `threading` | stdlib | `engine/common.py` (`parallel_map`), used by `engine/enrich.py` for feeds and websites (8 workers) |
| Retries | tenacity | 9.2.1 | `engine/common.py` (`cached_get`): 3 attempts, exponential backoff, only for network errors, 429 and 5xx |
| Podcast Index auth | `hashlib` (SHA-1) | stdlib | `engine/common.py` (`podcastindex_headers`) |
| RSS parsing | feedparser | 6.0.14 | `engine/enrich.py`: podcast feeds (episodes, durations, owner email, transcript tag) |
| Website reading | beautifulsoup4 (`html.parser`, built in) | 4.15.0 | `engine/enrich.py`: page text, links, `mailto:`; also strips HTML from show notes. Public pages only |
| robots.txt | `urllib.robotparser` | stdlib | `engine/enrich.py`: every website page is checked before fetching |
| Language detection | langdetect | 1.0.9 | `engine/verify.py`: share of recent items detected as English (fixed seed, so reruns match) |
| Domain normalisation | tldextract | 5.4.0 | `engine/verify.py`: email domain vs website domain, country domains; dedupe *(planned)*. Uses the bundled suffix list (`suffix_list_urls=()`), so no network call |
| Email seed test | `smtplib`, `imaplib` | stdlib | seed test *(planned)*: test accounts only |

## APIs

Access to all three keyed APIs was confirmed on 2026-10-27 with `python check_apis.py`: YouTube and Podcast Index at 22:28 IST, Gemini at 23:25 IST, all HTTP 200. The check costs 1 YouTube unit, 1 Podcast Index call and 0 Gemini tokens.

| API | Endpoint used | Purpose | Quota or cost | Key in `.env` | Used by |
|---|---|---|---|---|---|
| YouTube Data API v3 | `channels.list` (50 IDs per call), `playlistItems.list`, `videos.list` | enrich: profile, uploads, durations, caption flags | 1 unit per call: about 2-3 units per channel, 0 for skipped channels | `YOUTUBE_API_KEY` | `engine/enrich.py` |
| YouTube Data API v3 | `channels.list` (`forHandle`, `id` or `forUsername`) | verify: size of a podcast from the creator's linked YouTube channel | 1 unit per otherwise-qualified podcast with a channel link, cached 7 days | `YOUTUBE_API_KEY` | `engine/verify.py` |
| YouTube Data API v3 | `search.list` (`type=channel`) | find channels per keyword | 10,000 units/day by default (Google's documented default; check your project). `search.list` costs **100 units**, so one call per keyword, cached 7 days. Prefer `channels.list` and `playlistItems.list` (1 unit) for enrichment | `YOUTUBE_API_KEY` | `engine/discover.py`, `check_apis.py`; enrich *(planned)* |
| Podcast Index API | `podcasts/trending`, `recent/feeds` (`cat`, `lang=en`, `max=1000`) | discover: active English shows per category | free; 2 calls per category seed, cached 7 days | `PODCASTINDEX_API_KEY`, `PODCASTINDEX_API_SECRET` | `engine/discover.py` |
| Podcast Index API | `search/byterm` | find podcasts per keyword | free tier | `PODCASTINDEX_API_KEY`, `PODCASTINDEX_API_SECRET` | `engine/discover.py`, `check_apis.py` |
| Podcast RSS feeds | the show's own feed URL | enrich: episodes and the owner email | free; one GET per feed, cached 7 days | none | `engine/enrich.py` |
| Creator websites | homepage + contact + about page | enrich: page text, emails, links | free; up to 3 pages + `robots.txt` per site, cached 7 days. User-Agent `IncuBrixLeadEngine/0.1` | none | `engine/enrich.py` |
| iTunes Search API | `/search?media=podcast` | find podcasts per keyword | free, no key. Apple allows roughly 20 calls a minute, so there is a 3 s pause after each uncached call | none | `engine/discover.py` |
| Google Gemini API (AI Studio key), model `gemini-3.5-flash-lite` (`llm.model`) | `models` list (access check); `generateContent` with a JSON schema | verify: creator vs organisation, quote-checked; drafting *(planned)* | **free tier.** Measured 2026-10-28: 9 calls, 13,818 tokens (about 1,500 per creator), $0. Each uncached call is followed by a 4 s pause (about 15 a minute). Answers cached 30 days. Key sent in the `x-goog-api-key` header, never in the URL. A stronger model would classify better (see DECISIONS.md) | `LLM_API_KEY` | `engine/common.py` (`gemini_json`), `engine/verify.py`, `check_apis.py` |

One uncached discover pass over the current `data/seeds.csv`:
- 84 YouTube `search.list` calls, about 8,400 of the 10,000 daily units
- 29 Podcast Index calls
- 29 iTunes calls

## Data stores

All data is inside the `--out` folder (default `output/`, ignored by git). The database runs in SQLite WAL mode so parallel fetch threads can write the cache at the same time.

| Store | Where | Holds |
|---|---|---|
| SQLite table `api_cache` | `<out>/engine.db` | one stored JSON response per request (keys stripped; Gemini answers are keyed by the full prompt), with the time it was fetched. Remembered failures are stored as `{"_failed": {"status", "reason"}}`. Parsed feeds are stored under the versioned source `rss.v2` |
| SQLite table `api_log` | `<out>/engine.db` | every request: time, source, cached or live, ok or failed, error detail. Used for the run report's API call and error counts |
| SQLite table `candidates` | `<out>/engine.db` | discover output, one row per creator per platform |
| SQLite table `profiles` | `<out>/engine.db` | enrich output, one row per candidate: profile facts, emails, links and pages (JSON), enrich_status |
| SQLite table `content_items` | `<out>/engine.db` | enrich output: uploads and episodes from the last 60 days |
| SQLite table `verified` | `<out>/engine.db` | verify output: one row per profile with each check, its evidence quote and URL, contacts (JSON), Qualified or Rejected and the reasons |
| Log files | `<out>/logs/run_YYYYMMDD_HHMMSS.log` | one file per run |
