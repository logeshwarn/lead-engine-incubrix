# Phases

Status is one of: not started, in progress, done. Update this file at the end of each phase.

| Phase | Name | Status |
|---|---|---|
| 0 | Setup | done (2026-10-27) |
| 1 | Discover and enrich | done (2026-10-28) |
| 2 | Verify, dedupe, caps | not started |
| 3 | Score and route | not started |
| 4 | Outreach drafting | not started |
| 5 | Scale, export, refresh | not started |
| 6 | Seed test | not started |
| 7 | Hardening and handover | not started |

## Phase 0: Setup

Done when `python run.py --help` works and the docs exist.

Finished (2026-10-27):
- Repo layout: `engine/`, `tests/`, `docs/`, `docs/records/`
- `.venv` (Python 3.11.9), pinned `requirements.txt`, `.env.example`, `config.yaml`, `.gitignore`, `pyproject.toml`
- `run.py` with `--input`, `--out`, `--config`, `--refresh`; `--help` works
- `engine/common.py`: config loading with required-section check, one log file per run
- All docs from brief section 3 plus the two records files
- Tests in `tests/test_setup.py`

Also finished (2026-10-27):
- Owner added YouTube and Podcast Index keys to `.env`
- Owner added `docs/Submission_Workbook.xlsx`; `config.yaml` now uses its segment labels and ISO country codes
- Owner's seed list reviewed and corrected into `data/seeds.csv`, checked by `tests/test_seeds.py`

- `leads.csv` columns locked to the 30 columns in workbook tab `02_LEADS` (`LEADS_COLUMNS` in `engine/common.py`), with allowed channel, priority and status values. `tests/test_leads_schema.py` re-reads the workbook.
- API access confirmed on 2026-10-27 22:28 IST with `python check_apis.py`: YouTube Data API v3 PASS (HTTP 200, 1 quota unit), Podcast Index PASS (HTTP 200).

Later added (2026-10-27): the LLM provider is Google Gemini, and access was confirmed at 23:25 IST with `python check_apis.py` (HTTP 200, 0 tokens).

Open questions resolved on 2026-10-27 (see DECISIONS.md): `leads.csv` holds qualified creators only; long-form means 20 minutes or more.

## Phase 1: Discover and enrich

Done when 200 candidates are enriched with no repeat API calls on rerun, and TECH_RUNTIME.md and WORKFLOW.md are updated.

| Module | Status |
|---|---|
| `engine/discover.py` | done (2026-10-27) |
| `engine/enrich.py` | done (2026-10-28) |

Discover finished (2026-10-27):
- YouTube channel search, Podcast Index search and iTunes Search, all through the SQLite cache (`cached_get`), with 3 retries and failure logging
- `candidates` table with one row per `(platform, platform_id)`
- Small live run on 2 seed keywords: 90 unique candidates (50 YouTube, 40 podcast) in 29.5 s. The rerun made 0 live calls and took 0.1 s
- Hand check of the sample: discovery returns non-creators too, for example a podcast agency, a bank's podcast and a brand's show. Verify must exclude these (assignment section 2)
- Tests: `tests/test_cache.py`, `tests/test_discover.py`. All tests block the real network

Enrich finished (2026-10-28):
- YouTube profiles, uploads, durations and caption flags; podcast RSS feeds (episodes, owner email, transcripts); the creator's own website (homepage, contact and about pages, robots.txt respected). Every email and link keeps the URL it was found on
- `profiles` and `content_items` tables; `enrich_status` on every row
- Tests: `tests/test_enrich.py`, plus remembered-failure tests in `tests/test_cache.py`

**Phase 1 check (done-when met), on 5 seed keywords (S001, S002, S004, S011, S015):**

| Run | Result | Live calls | Time |
|---|---|---|---|
| First full run (fixed code) | 343 candidates enriched: 236 ok, 30 partial, 75 skipped, 2 failed; 1,644 recent items | all | 30.9 min |
| Rerun A (retried 18 earlier failures, now remembered) | same | 18 | 12.4 min |
| **Rerun B** | **same** | **0 of 1,100** | **3.3 s** |

YouTube quota used by all live runs to date: 247 units (+2 for `check_apis.py`).

**Hand inspection of the 266 usable profiles (ok + partial):**
- **Public email found:** 200 of 266. Some are not the creator's business address, for example a site-builder address from a website footer (godaddy.com) or a promo-service address. The source URL is kept, so verify/route can accept only addresses on the creator's own domain or labelled for business contact.
- **Country is the biggest gap:** only 11 of 266 state a country on the platform. Verify must find the country in public text (website location, address) or reject. This is the main risk to reaching 1,000.
- **Activity:** 81 have 8+ items in the last 60 days and 114 have 2+ long-form items. The 30-day rule is checked in verify.
- **Captions:** only 4% of recent YouTube videos have creator-uploaded captions (the API flag ignores auto-captions), and 18% of podcast episodes have a transcript. "No captions" will be common, so it must be worded precisely and not over-weighted in scoring.
- **Language:** mostly English, but some German, Spanish, Hindi and Urdu shows. The language check in verify is needed.
- **Non-creators** (agencies, brands, a bank) are still present, as expected. Verify excludes them.

Carried to Phase 5 (scale):
- Fetching feeds and websites one at a time takes about 5 s per candidate on a first run (343 took 31 min). 5,000+ candidates need parallel fetching. Python's built-in thread pool does this with no new dependency.
- The full discover pass over all 42 seeds takes about 8,400 YouTube units, then about 2-3 units per in-scope channel to enrich, so 2-3 days of quota for the first full run.

Open questions for later phases:
- Phase 3: scoring weights are not set yet.
