# Changelog

Dated list of notable changes. Newest first.

## 2026-10-28: Verify fixes from the volume hand check

- `engine/verify.py`:
  - shows whose website or contact email is on a broadcaster or network domain are organisations (`verify.media_domains`)
  - the LLM prompt names broadcasters, stations, networks, churches and ministries as organisations
  - a country quote that is a sentence or address is put to the LLM, which must answer that it is about the host (or the host's own business). New column `country_quote_about`
  - podcast size from the creator's linked YouTube channel (`check_podcast_size`, 1 unit per row, before the LLM); above 500,000 is rejected. New column `size_evidence`
  - the log's token count now leaves out cached answers
- `config.yaml`: `verify.podcast_max_youtube_subscribers` (500,000, pending owner review), `verify.media_domains`.
- Tests: 19 new (domains, YouTube link forms, size, country-quote answers). 168 tests in total.
- Verify rerun on the 3,299 profiles: 54 qualified (was 71); 11 of the 12 doubtful rows now rejected.
- Docs: WORKFLOW, TECH_RUNTIME, DECISIONS, PHASES, and both records files.

## 2026-10-28: Volume step

- `engine/discover.py`: `podcast_category` seeds read Podcast Index category lists (trending and recently updated, up to 1,000 English shows each). New column `newest_item_at`; podcasts whose newest episode is older than 60 days are dropped before enrich (`drop_inactive`).
- `engine/common.py`: `parallel_map` (thread pool, one SQLite connection per thread); the database now runs in WAL mode with a 60 s lock timeout.
- `engine/enrich.py`: feeds and websites are fetched 8 at a time (`enrich.workers`); results keep input order.
- `config.yaml`: `discover.category_max_results`, `discover.category_lists`, `enrich.workers`, `podcast_category` platform.
- `data/seeds.csv`: 16 category seeds added (S043-S058), pending owner review. The owner's 42 seeds are unchanged.
- Tests: category, inactive-drop and `parallel_map` tests; 149 tests in total.
- Live run on 2 categories: 3,299 candidates, 71 qualified (2.2%), 1 h 56 min, 252,461 Gemini tokens ($0). Hand check found about 12 doubtful rows; listed in PHASES.md.
- Docs: WORKFLOW, TECH_RUNTIME, DECISIONS, PHASES, README, and both records files.

## 2026-10-28: Verify done: LLM creator check

- `engine/verify.py`: creator-vs-organisation check with Gemini (`check_creator`, `apply_creator_check`), run only on rows that pass everything else. The model's quote must be found word for word in the creator's own text; organisation, unclear, unverified and failed answers are rejections with reasons. New columns: `creator_kind`, `creator_evidence`, `creator_evidence_url`.
- `engine/common.py`: `gemini_json` (cached by prompt, JSON schema, key in header, pause after uncached calls); `cached_get` can POST a JSON body and take its own timeout.
- `config.yaml`: `llm.model: gemini-3.5-flash-lite` plus timeout, pause, cache days and input size. The model choice and test results are in DECISIONS.md.
- Tests: the fake HTTP now covers POST, and every test blocks real GET and POST. 8 new creator-check tests; 145 tests in total.
- Live sample: 9 LLM answers (13,818 tokens, $0); 2 of 343 candidates qualify.
- Docs: WORKFLOW, TECH_RUNTIME, DECISIONS (model trade-off), PHASES (results, yield risk), README, and both records files.

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
