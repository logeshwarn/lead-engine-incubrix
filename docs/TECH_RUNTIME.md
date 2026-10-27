# Tech used inside the app

Update this file when a library, API or data store changes. "Used by" lists only files that exist; planned files are marked *(planned)*.

## Libraries

| Purpose | Library | Version | Used by |
|---|---|---|---|
| Config | PyYAML | 6.0.3 | `engine/common.py` |
| Secrets | python-dotenv | 1.2.4 | `engine/common.py`, `check_apis.py` |
| Logging | Python `logging` | stdlib | `engine/common.py`, `run.py`, `engine/discover.py`: one log file per run |
| Data handling | pandas | 3.1.0 | `engine/discover.py`; later stages *(planned)* |
| Storage and cache | SQLite (`sqlite3`) | stdlib | `engine/common.py` (`api_cache`, `api_log`), `engine/discover.py` (`candidates`) |
| HTTP | requests | 2.34.2 | `engine/common.py` (`cached_get`), `check_apis.py` |
| Retries | tenacity | 9.2.1 | `engine/common.py` (`cached_get`): 3 attempts, exponential backoff, only for network errors, 429 and 5xx |
| Podcast Index auth | `hashlib` (SHA-1) | stdlib | `engine/common.py` (`podcastindex_headers`) |
| RSS parsing | feedparser | 6.0.14 | enrich *(planned)* |
| Website reading | beautifulsoup4 | 4.15.0 | enrich *(planned)*: public pages only, respect robots.txt and site terms |
| Language detection | langdetect | 1.0.9 | verify *(planned)*: English content check |
| Domain normalisation | tldextract | 5.4.0 | dedupe *(planned)*: dedupe key |
| Email seed test | `smtplib`, `imaplib` | stdlib | seed test *(planned)*: test accounts only |

## APIs

YouTube and Podcast Index access was confirmed on 2026-10-27 with `python check_apis.py` (both HTTP 200). That check costs 1 YouTube unit and 1 Podcast Index call. The LLM is not chosen yet.

| API | Endpoint used | Purpose | Quota or cost | Key in `.env` | Used by |
|---|---|---|---|---|---|
| YouTube Data API v3 | `search.list` (`type=channel`) | find channels per keyword | 10,000 units/day by default (Google's documented default; check your project). `search.list` costs **100 units**, so one call per keyword, cached 7 days. Prefer `channels.list` and `playlistItems.list` (1 unit) for enrichment | `YOUTUBE_API_KEY` | `engine/discover.py`, `check_apis.py`; enrich *(planned)* |
| Podcast Index API | `search/byterm` | find podcasts per keyword | free tier | `PODCASTINDEX_API_KEY`, `PODCASTINDEX_API_SECRET` | `engine/discover.py`, `check_apis.py` |
| iTunes Search API | `/search?media=podcast` | find podcasts per keyword | free, no key. Apple allows roughly 20 calls a minute, so there is a 3 s pause after each uncached call | none | `engine/discover.py` |
| LLM (provider not chosen) | n/a | drafting, and possibly unclear classification cases; JSON output only; may only quote supplied text and must return an evidence quote and URL | to be recorded once chosen | `LLM_API_KEY` | draft *(planned)* |

One uncached discover pass over the current `data/seeds.csv`:
- 84 YouTube `search.list` calls, about 8,400 of the 10,000 daily units
- 29 Podcast Index calls
- 29 iTunes calls

## Data stores

All data is inside the `--out` folder (default `output/`, ignored by git).

| Store | Where | Holds |
|---|---|---|
| SQLite table `api_cache` | `<out>/engine.db` | one stored JSON response per request (keys stripped), with the time it was fetched |
| SQLite table `api_log` | `<out>/engine.db` | every request: time, source, cached or live, ok or failed, error detail. Used for the run report's API call and error counts |
| SQLite table `candidates` | `<out>/engine.db` | discover output, one row per creator per platform |
| Log files | `<out>/logs/run_YYYYMMDD_HHMMSS.log` | one file per run |
