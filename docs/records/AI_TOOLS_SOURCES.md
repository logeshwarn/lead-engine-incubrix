# AI tools and sources

Every AI tool and outside source used to build the project, as it happens. Dated, factual, and never back-filled or estimated.

## AI tools

| Date | Tool | Model or version | Used by | Used for |
|---|---|---|---|---|
| 2026-10-27 | Claude Code (Claude desktop app, Code tab) | Claude Opus 5.5 | engine build | Phase 0: read the brief, created the repo layout, `run.py`, `engine/common.py`, config files, tests and all docs |
| 2026-10-27 | Claude web (claude.ai) | not recorded (owner to fill in) | owner | drafted the 42-row seed list, now `data/seeds_original.csv` |
| 2026-10-27 | Claude Code (Claude desktop app, Code tab) | Claude Opus 5.5 | engine build | reviewed and corrected the seed list (`data/seeds.csv`), read the Submission Workbook's columns and dropdowns, aligned `config.yaml`, added `tests/test_seeds.py` |
| 2026-10-27 | Claude Code (Claude desktop app, Code tab) | Claude Opus 5.5 | engine build | locked `leads.csv` columns to the workbook, wrote `check_apis.py` and its tests, ran the live API check |
| 2026-10-27 | Claude Code (Claude desktop app, Code tab) | Claude Opus 5.5 | engine build | analysed the qualification rules and wrote the plan; chose the four delegated decisions; built `engine/discover.py`, `cached_get` and their tests; ran the small live discover and the iTunes store comparison |

## Sources

| Date | Source | Used for |
|---|---|---|
| 2026-10-27 | `docs/BRIEF.pdf` (supplied by the owner) | requirements, thresholds, tech stack, phases |
| 2026-10-27 | PyPI (via `pip install`) | installed the approved libraries; versions pinned in `requirements.txt` |
| 2026-10-27 | YouTube Data API v3 (`videoCategories.list`, 1 call, 1 quota unit) | access check only; no creator data collected |
| 2026-10-27 | Podcast Index API (`search/byterm`, 1 call) | access check only; no creator data collected |
| 2026-10-27 | `docs/Submission_Workbook.xlsx` (supplied by the owner) | `leads.csv` columns; allowed values for segment, country (ISO, `GB`), channels and priority |
| 2026-10-27 | `docs/IncuBrix_2027_Growth_Engineer_Option_1_Lead_Generation_and_Outreach.pdf` (supplied by the owner) | qualification rules, exclusions (agencies, brands and others), platform-rule and sender rules, audit targets |
| 2026-10-27 | YouTube `search.list` (1 live call, 100 quota units), Podcast Index `search/byterm` (1 call), iTunes Search (7 calls, one per approved store) | small live discover on "video podcast business interviews" and "founder interviews podcast": 90 unique candidates. The rerun was all cache hits |
| 2026-10-27 | YouTube, Podcast Index and iTunes (1 accidental call each, with dummy keys `yt` / `pk`) | a test bug ran discover once before the fake HTTP layer was installed. The owner's keys and quota were not used; results went to a temporary test database only. Fixed, and all tests now block the network |
