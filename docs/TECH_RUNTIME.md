# Tech used inside the app

Update this file when a library, API or data store changes. "Used by" lists only files that exist; planned files are marked *(planned)*.

## Libraries

| Purpose | Library | Version | Used by |
|---|---|---|---|
| Config | PyYAML | 6.0.3 | `engine/common.py` |
| Secrets | python-dotenv | 1.2.4 | `engine/common.py` |
| Logging | Python `logging` | stdlib | `engine/common.py`, `run.py`: one log file per run |
| Data handling | pandas | 3.1.0 | all stages *(planned)* |
| Storage and cache | SQLite (`sqlite3`) | stdlib | candidates, API cache, run state *(planned)* |
| HTTP and retries | requests, tenacity | 2.34.2, 9.2.1 | `check_apis.py` (requests); discover, enrich *(planned)*: 3 attempts with backoff |
| RSS parsing | feedparser | 6.0.14 | podcast discovery *(planned)* |
| Website reading | beautifulsoup4 | 4.15.0 | enrich *(planned)*: public pages only, respect robots.txt and site terms |
| Language detection | langdetect | 1.0.9 | verify *(planned)*: English content check |
| Domain normalisation | tldextract | 5.4.0 | dedupe *(planned)*: dedupe key |
| Email seed test | `smtplib`, `imaplib` | stdlib | seed test *(planned)*: test accounts only |

## APIs

YouTube and Podcast Index access was confirmed on 2026-10-27 with `python check_apis.py` (both HTTP 200). That check costs 1 YouTube unit and 1 Podcast Index call. The LLM is not chosen yet. One uncached pass over the current `data/seeds.csv` makes 84 YouTube `search.list` calls, about 8,400 of the 10,000 daily units.

| API | Purpose | Quota or cost | Key in `.env` | Used by |
|---|---|---|---|---|
| YouTube Data API v3 | YouTube discovery and enrichment | 10,000 units/day by default (Google's documented default; check your project). `search.list` costs 100 units per call, so use it sparingly and prefer `channels.list` and `playlistItems.list` | `YOUTUBE_API_KEY` | `check_apis.py`; discover, enrich *(planned)* |
| Podcast Index API | podcast discovery | free tier | `PODCASTINDEX_API_KEY`, `PODCASTINDEX_API_SECRET` | `check_apis.py`; discover *(planned)* |
| iTunes Search API | podcast discovery | free, no key | none | discover *(planned)* |
| LLM (provider not chosen) | classification and drafting, JSON output only; may only quote supplied text and must return an evidence quote and URL | to be recorded once chosen | `LLM_API_KEY` | verify, draft *(planned)* |

## Data stores

| Store | Where | Holds |
|---|---|---|
| SQLite | `output/engine.db` (`paths.db` in config) | candidates, API cache, run state *(planned)* |
| Log files | `output/logs/` (`paths.logs` in config) | one file per run |
