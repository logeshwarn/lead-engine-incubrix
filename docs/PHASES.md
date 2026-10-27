# Phases

Status is one of: not started, in progress, done. Update this file at the end of each phase.

| Phase | Name | Status |
|---|---|---|
| 0 | Setup | done (2026-10-27) |
| 1 | Discover and enrich | not started |
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

Open questions for later phases:
- Phase 2 or 5: the workbook's `leads.csv` has `candidate_status` (Qualified/Rejected) and `rejection_reason`, while the brief puts rejects in a separate `rejected.csv`. Which file should rejected rows go in?
- Phase 2: the brief does not define "long-form" for the activity rule (minimum length in minutes).
- Phase 3: scoring weights are not in the brief yet.
