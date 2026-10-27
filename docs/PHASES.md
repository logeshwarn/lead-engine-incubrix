# Phases

Status is one of: not started, in progress, done. Update this file at the end of each phase.

| Phase | Name | Status |
|---|---|---|
| 0 | Setup | in progress |
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

Still open, waiting on the owner:
- [ ] Confirm API access for YouTube, Podcast Index and the LLM (keys go in `.env`)
- [ ] Choose the LLM provider (deferred until Phase 4 at the latest)
- [ ] Lock the `leads.csv` columns to the Submission Workbook (owner will add the workbook to `docs/`)

Open questions for later phases:
- Phase 2: the brief does not define "long-form" for the activity rule (minimum length in minutes).
- Phase 3: scoring weights are not in the brief yet.
