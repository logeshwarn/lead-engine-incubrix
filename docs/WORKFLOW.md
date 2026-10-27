# App workflow

Update this file when a stage or one of its rules changes.

Each stage is one file in `engine/`. It reads a table and writes a table, so it can be run on its own. Stage tables live in SQLite, so a crashed run resumes from the last finished stage.

| # | Stage | File | Input | Output | Status |
|---|---|---|---|---|---|
| 1 | discover | `engine/discover.py` | `data/seeds.csv` | candidate creators (platform ID, URL, source, query) | not built |
| 2 | enrich | `engine/enrich.py` | candidates | profile, recent uploads, links, public contact info (cached) | not built |
| 3 | verify | `engine/verify.py` | enriched candidates | 7 checks with an evidence quote and URL each; failures go to `rejected.csv` | not built |
| 4 | dedupe | `engine/dedupe.py` | verified | one row per creator (platform ID, domain, email) | not built |
| 5 | caps | `engine/caps.py` | deduped | country and segment rules enforced | not built |
| 6 | score | `engine/score.py` | capped | score from 0 to 100; top 25 flagged Priority A | not built |
| 7 | route | `engine/route.py` | scored | best channel and backup channel | not built |
| 8 | draft | `engine/draft.py` | routed | first message (+ 2 follow-ups for Priority A), opt-out included | not built |
| 9 | export | `engine/export.py` | drafted | `leads.csv`, `outreach/`, `rejected.csv`, `run_report.md` | not built |

## Seeds (`data/seeds.csv`)

Each row is a niche to search, not a lead. `tests/test_seeds.py` checks the file.

| Column | Meaning |
|---|---|
| `seed_id` | unique ID, for example `S001` |
| `segment` | one of the three workbook segment labels in `config.yaml` |
| `niche` | short label, used for segment and country mix reporting |
| `primary_platform` | `youtube` or `podcast` (the only discovery sources) |
| `discovery_keywords` | search terms separated by `;`. Each YouTube term costs one `search.list` call (100 units). No term may repeat |
| `need_signal_to_check` | hint for verify about which need to look for. Never used as evidence |
| `size_min`, `size_max` | subscriber range for YouTube seeds. Blank for podcasts (no public audience count) |
| `status` | `active` (searched) or `paused` (skipped) |

The current file has 42 seeds: 84 YouTube terms (about 8,400 quota units for one uncached pass) and 29 podcast terms.

Shared helpers live in `engine/common.py` (config loading, per-run logging). `run.py` runs the stages in order.

## Output format (`leads.csv`)

The 30 columns are locked to Submission Workbook tab `02_LEADS`, in workbook order, as `LEADS_COLUMNS` in `engine/common.py`. Allowed values:

- `creator_segment`: the 3 segments in `config.yaml`
- `country_iso2`: the approved list in `config.yaml`, or `Other`
- `best_channel` and `backup_channel`: `CHANNELS`
- `priority`: `A`, `B` or `C`
- `candidate_status`: `Qualified` or `Rejected`

`tests/test_leads_schema.py` fails if any of these drift from the workbook.

## Commands

- `python run.py --input data/seeds.csv --out output/`: full run
- `python run.py --refresh`: re-check evidence older than 30 days, keep unchanged cached results
- `python check_apis.py`: one cheap live call per API to prove the `.env` keys work

## Qualification checks (all must pass, each with a working public link)

1. **Real and relevant**: real creator, approved segment and country, official profile, stable platform ID.
2. **Active**: 8+ items in 30 days, or 2+ long-form items in 60 days.
3. **Commercial**: public sponsorship, product, service, course, membership or affiliate evidence.
4. **Needs IncuBrix**: public sign of a content creation, editing, captions, repurposing, publishing, consistency, backlog or team workflow need.
5. **Reachable**: real public business channel, active in the last 60 days, never guessed.
6. **Personalised and compliant**: cites a specific recent piece of content, names the sender, includes an opt-out.
7. **Complete and unique**: all fields filled, evidence checked within 30 days, no duplicates.

## Hard constraints (run fails loudly if broken)

- At least 80% of leads from US, CA, UK, IE, AU, NZ, SG
- At least 3 countries
- No country above 60%
- Mainly English content

All values are in `config.yaml`.

## Failure handling

- HTTP calls: retry 3 times with backoff, then log the error and skip the row. No row is ever filled with guessed data.
- Config: `run.py` stops at start-up if `config.yaml` is missing a required section.
- Each run writes its own log file to `output/logs/`.
