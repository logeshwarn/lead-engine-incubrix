# Changelog

Dated list of notable changes. Newest first.

## 2026-10-28: Stage 3, verify

- Added `engine/verify.py`: the qualification checks, each with a verbatim quote and URL, writing the `verified` table (Qualified or Rejected, all reasons kept). It covers country (6 evidence sources), language (langdetect), organisations, activity, offers, needs (own words, then observed gaps), contacts (published business channels only) and evidence age.
- `config.yaml`: added `verify` thresholds; `run.py` now runs verify after enrich.
- `engine/enrich.py`:
  - show description combines `<itunes:summary>` and `<description>`
  - reads `<podcast:location>` (new `location` column); feed cache is now `rss.v3`
  - the YouTube website must match the creator's name
- Fixes from the 20-row hand check: no country or contacts from show notes; the right-most place wins; street addresses only on contact/about pages; profile-shaped social links only; more hosting-platform email domains blocked; guest-pitch testimonials ignored; topic words no longer exclude creators.
- Tests: `tests/test_verify.py` and new enrich tests. 137 tests in total.
- Docs: WORKFLOW (stage 3, evidence rules), TECH_RUNTIME, DECISIONS, PHASES (hand check, yield), README, and both records files.

## 2026-10-28: Stage 2, enrich (Phase 1 done)

- Added `engine/enrich.py`: YouTube channel, upload and video details (size/country gate before the per-channel calls); podcast RSS (episodes, durations, owner email, transcript tag); the creator's own website (homepage, contact and about pages, robots.txt checked, big platforms never fetched). Writes the `profiles` and `content_items` tables.
- `engine/common.py`, `cached_get` gained three options:
  - `parse`: caches extracted fields instead of raw pages
  - `ok_statuses`: caches 4xx pages as "nothing there"
  - `failure_max_age_days`: remembers failed feeds and sites for 1 day
- `engine/discover.py`: candidates now carry the seed's `size_min` and `size_max`.
- `run.py` runs discover then enrich.
- `config.yaml`: added `enrich` (windows, page limits, skip domains) and `cache.enrich_max_age_days` / `cache.failure_max_age_days`.
- Fixes found in the live run:
  - episode dates were shifted by the local timezone (`mktime` changed to `timegm`)
  - one impossible date dropped a whole feed
  - pandas 3 `iterrows()` turned `None` into `NaN`
  - the parsed-feed cache is now versioned (`rss.v2`)
- Tests: `tests/test_enrich.py`; failure-cache tests in `tests/test_cache.py`; `FakeResponse` supports text responses. 69 tests in total.
- Live check: 343 candidates enriched; the rerun made 0 live calls out of 1,100 and took 3.3 s.
- Docs: WORKFLOW, TECH_RUNTIME, DECISIONS, PHASES (Phase 1 done, inspection findings), README, and both records files.

## 2026-10-27: LLM provider and sender set

- `check_apis.py` now also checks the Gemini key by listing models (0 tokens, key sent in a header). All three APIs pass.
- `config.yaml`: added `sender` (name, description, postal-address placeholder) and `llm` (provider: gemini).
- `.env.example`: `LLM_API_KEY` is now described as the Gemini key.
- Tests: Gemini check fails cleanly without a key and never puts the key in the URL.
- Docs: DECISIONS, TECH_RUNTIME, PHASES, README, and both records files.

## 2026-10-27: Stage 1, discover

- Added `engine/discover.py`: searches YouTube (channels), Podcast Index and iTunes for every active seed keyword, and writes the `candidates` table, one row per creator per platform.
- `engine/common.py`:
  - added `connect_db` (`<out>/engine.db` with the `api_cache` and `api_log` tables)
  - added `cached_get` (SQLite cache, 3 retries with backoff, keys never stored or logged)
  - added `ApiError`
  - moved `podcastindex_headers` here from `check_apis.py`
- `run.py` now runs discover. The database and logs are written inside `--out`, and a missing input file stops the run.
- `config.yaml`:
  - removed `paths`
  - added `cache` (7-day search cache) and `discover` (search sizes, iTunes store list = US)
  - set `activity.long_form_min_minutes: 20`
- Added `tests/conftest.py` (fake HTTP, network blocked in all tests), `tests/test_cache.py` and `tests/test_discover.py`.
- Recorded the decisions: need evidence, long-form = 20 minutes, `leads.csv` qualified-only, and the assignment PDF as a rules source.
- Docs: WORKFLOW (discover stage, merged assignment rules), TECH_RUNTIME, DECISIONS, PHASES, README, and both records files.

## 2026-10-27: Phase 0 done: leads.csv columns locked, API access confirmed

- `engine/common.py`: `LEADS_COLUMNS` (the 30 workbook columns, in order), plus `CHANNELS`, `PRIORITIES` and `CANDIDATE_STATUSES` from the workbook dropdowns.
- Added `check_apis.py`: one cheap live call each to YouTube and Podcast Index, printing PASS/FAIL only. Both passed on 2026-10-27.
- Added `tests/test_leads_schema.py` (re-reads the workbook) and `tests/test_check_apis.py`.
- Docs: PHASES (Phase 0 done), WORKFLOW (output format), TECH_RUNTIME, DECISIONS, README, and both records files.

## 2026-10-27: Seeds reviewed, config aligned to the Submission Workbook

- `data/seeds.csv`: corrected the owner's 42-row draft. The original is kept as `data/seeds_original.csv`.
  - Segments now use the workbook labels; `video_podcaster` is merged into `Podcaster/Video Podcaster`.
  - Platform `podcast_apple_spotify` is now `podcast`. The 8 LinkedIn and Instagram rows moved to `youtube`, and their need signals were rewritten.
  - `size_band_target` is split into `size_min` and `size_max`, blank for podcasts.
  - Need signals that could not be checked publicly (S008 "manual editing", S018 "sponsor-led") were replaced.
  - Removed "(non-clinical)" from an S034 search term.
  - Status `draft` is now `active`.
- `config.yaml`: country `UK` is now `GB`; segments use the workbook labels; added `discovery_platforms`.
- Added `tests/test_seeds.py` and updated `tests/test_setup.py`.
- Docs: WORKFLOW (seed columns, quota cost), DECISIONS, PHASES, README, and both records files.

## 2026-10-27: Phase 0 setup

- Added the repo layout: `engine/`, `tests/`, `docs/records/`.
- Added `run.py` with `--input`, `--out`, `--config` and `--refresh`. `--help` works. No stages run yet.
- Added `engine/common.py`: loads `config.yaml` and `.env`, checks required config sections, and writes one log file per run.
- Added `config.yaml` with every threshold from the brief (countries, activity, evidence age, Priority A, retries).
- Added `.env.example`, `.gitignore`, `pyproject.toml` (ruff, pytest) and pinned `requirements.txt`.
- Added docs: README, TECH_BUILD, TECH_RUNTIME, WORKFLOW, PHASES, DECISIONS, CHANGELOG, and the two records files.
- Added `tests/test_setup.py`.
