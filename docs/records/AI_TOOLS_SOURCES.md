# AI tools and sources

Every AI tool and outside source used to build the project, as it happens. Dated, factual, and never back-filled or estimated.

## AI tools

| Date | Tool | Model or version | Used by | Used for |
|---|---|---|---|---|
| 2026-10-27 | Claude Code (Claude desktop app, Code tab) | Claude Opus 5.5 | engine build | Phase 0: read the brief, created the repo layout, `run.py`, `engine/common.py`, config files, tests and all docs |
| 2026-10-27 | Claude web (claude.ai) | not recorded (owner to fill in) | owner | drafted the 42-row seed list, now `data/seeds_original.csv` |
| 2026-10-27 | Claude Code (Claude desktop app, Code tab) | Claude Opus 5.5 | engine build | reviewed and corrected the seed list (`data/seeds.csv`), read the Submission Workbook's columns and dropdowns, aligned `config.yaml`, added `tests/test_seeds.py` |
| 2026-10-27 | Claude Code (Claude desktop app, Code tab) | Claude Opus 5.5 | engine build | locked `leads.csv` columns to the workbook, wrote `check_apis.py` and its tests, ran the live API check |

## Sources

| Date | Source | Used for |
|---|---|---|
| 2026-10-27 | `docs/BRIEF.pdf` (supplied by the owner) | requirements, thresholds, tech stack, phases |
| 2026-10-27 | PyPI (via `pip install`) | installed the approved libraries; versions pinned in `requirements.txt` |
| 2026-10-27 | YouTube Data API v3 (`videoCategories.list`, 1 call, 1 quota unit) | access check only; no creator data collected |
| 2026-10-27 | Podcast Index API (`search/byterm`, 1 call) | access check only; no creator data collected |
| 2026-10-27 | `docs/Submission_Workbook.xlsx` (supplied by the owner) | `leads.csv` columns; allowed values for segment, country (ISO, `GB`), channels and priority |
