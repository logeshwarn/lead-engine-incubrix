# Changelog

Dated list of notable changes. Newest first.

## 2026-10-27: Phase 0 setup

- Added the repo layout: `engine/`, `tests/`, `docs/records/`.
- Added `run.py` with `--input`, `--out`, `--config` and `--refresh`. `--help` works. No stages run yet.
- Added `engine/common.py`: loads `config.yaml` and `.env`, checks required config sections, and writes one log file per run.
- Added `config.yaml` with every threshold from the brief (countries, activity, evidence age, Priority A, retries).
- Added `.env.example`, `.gitignore`, `pyproject.toml` (ruff, pytest) and pinned `requirements.txt`.
- Added docs: README, TECH_BUILD, TECH_RUNTIME, WORKFLOW, PHASES, DECISIONS, CHANGELOG, and the two records files.
- Added `tests/test_setup.py`.
