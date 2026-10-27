# Phases

Status is one of: not started, in progress, done. Update this file at the end of each phase.

| Phase | Name | Status |
|---|---|---|
| 0 | Setup | done (2026-10-27) |
| 1 | Discover and enrich | in progress (discover built 2026-10-27) |
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

Moved to a later phase:
- LLM provider choice and access check. The owner deferred it; it is needed by Phase 4 at the latest.

Open questions resolved on 2026-10-27 (see DECISIONS.md): `leads.csv` holds qualified creators only; long-form means 20 minutes or more.

## Phase 1: Discover and enrich

Done when 200 candidates are enriched with no repeat API calls on rerun, and TECH_RUNTIME.md and WORKFLOW.md are updated.

| Module | Status |
|---|---|
| `engine/discover.py` | done (2026-10-27) |
| `engine/enrich.py` | not started |

Discover finished (2026-10-27):
- YouTube channel search, Podcast Index search and iTunes Search, all through the SQLite cache (`cached_get`), with 3 retries and failure logging
- `candidates` table with one row per `(platform, platform_id)`
- Small live run on 2 seed keywords: 90 unique candidates (50 YouTube, 40 podcast) in 29.5 s. The rerun made 0 live calls and took 0.1 s
- Hand check of the sample: discovery returns non-creators too, for example a podcast agency, a bank's podcast and a brand's show. Verify must exclude these (assignment section 2)
- Tests: `tests/test_cache.py`, `tests/test_discover.py`. All tests block the real network

Still open in Phase 1:
- Full discover pass over all 42 seeds (about 8,400 YouTube units, nearly a full day's quota). Run it only when enrich is ready, so the candidates are used at once
- `engine/enrich.py`

Open questions for later phases:
- Phase 3: scoring weights are not set yet.
