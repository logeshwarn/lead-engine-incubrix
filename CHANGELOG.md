# Changelog

Dated list of notable changes. Newest first.

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
