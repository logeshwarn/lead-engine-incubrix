# IncuBrix Lead Engine

A small Python engine that finds content creators (podcasters, YouTubers, expert-led creators), verifies each one with public evidence, picks the best contact channel, drafts personalised outreach, and exports a CRM-ready `leads.csv`. It is meant to be rerun every week with one command.

The full brief is in [docs/BRIEF.pdf](docs/BRIEF.pdf).

The assignment it answers is in [docs/IncuBrix_2027_Growth_Engineer_Option_1_Lead_Generation_and_Outreach.pdf](docs/IncuBrix_2027_Growth_Engineer_Option_1_Lead_Generation_and_Outreach.pdf).

**Status:** Phase 1 (discover and enrich) is done, and Phase 2 is in progress: verify is built.
- **Discover** searches YouTube, Podcast Index and iTunes for every active seed.
- **Enrich** adds each candidate's profile, recent uploads or episodes, and published contact details from YouTube, the show's RSS feed and the creator's own website (robots.txt respected).
- **Verify** runs the qualification checks. Each pass carries a quote and its URL, and each rejection lists its reasons (table `verified`).

The later stages are not built yet, and the run log lists them. See [docs/PHASES.md](docs/PHASES.md).

## Setup (Windows, Python 3.11+)

```bash
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Then open `.env` and fill in your API keys. `.env` is ignored by git, so never commit it.

Check that the keys work (YouTube, Podcast Index, Gemini). This costs 1 YouTube quota unit and 0 Gemini tokens, and prints only PASS or FAIL:

```bash
python check_apis.py
```

## Run

```bash
python run.py --input data/seeds.csv --out output/
```

```bash
python run.py --refresh
```

| Flag | Default | What it does |
|---|---|---|
| `--input` | `data/seeds.csv` | seed queries CSV |
| `--out` | `output/` | output folder |
| `--config` | `config.yaml` | settings file |
| `--refresh` | off | re-check evidence older than 30 days, keep unchanged cached results |

`python run.py --help` lists the same flags.

**Quota warning:** an uncached run over the full `data/seeds.csv` makes 84 YouTube searches, about 8,400 of the 10,000 free daily units, and enrich adds about 2-3 units per YouTube channel. A full first run therefore takes 2-3 days of quota. Each run stops YouTube calls cleanly when the quota runs out, and the next day's run continues from the cache. A rerun within 7 days is served from the cache and costs nothing. To try the engine cheaply, copy a few rows of `data/seeds.csv` into a new file and pass it with `--input`.

## Config

- `data/seeds.csv`: the niches and search terms to discover from. Each row is a niche, not a lead. A row with `primary_platform` = `podcast_category` names a Podcast Index category (e.g. `Fitness`) and brings up to 2,000 active shows. The columns are explained in [docs/WORKFLOW.md](docs/WORKFLOW.md). Set `status` to `paused` to skip a row.
- `config.yaml`: thresholds, country and segment caps, activity rules, evidence age, the cache window (`cache`) and search sizes (`discover`). Values come from the brief, and segment and country names come from the Submission Workbook. Changes and their reasons go in [docs/DECISIONS.md](docs/DECISIONS.md).
- `.env`: API keys only. `.env.example` lists the keys you need.

## Outputs

These are planned and will exist once the export stage is built (Phase 5):

- `output/leads.csv`: qualified leads, with columns locked to the Submission Workbook
- `output/rejected.csv`: rejected candidates and the reason for each
- `output/outreach/`: drafted messages
- `output/run_report.md`: counts, mix, runtime, API calls, cost and errors (generated, do not edit)

Already produced today:

- `output/engine.db`: SQLite database. It holds:
  - the API cache and the API call log
  - `candidates` (discover)
  - `profiles` and `content_items` (enrich)
  - `verified` (verify): look at `candidate_status` and `rejection_reason`
  - `deduped` (dedupe): the same rows, one Qualified row per creator; `duplicate_of` names the row a duplicate was merged into
  - `capped` and `cap_checks` (caps): the final country mix, and each hard rule with its value and pass/fail
  
  Delete it to start from scratch, which spends the quota again. Any SQLite viewer (for example "DB Browser for SQLite") can open it to inspect the rows by hand.
- `output/logs/run_YYYYMMDD_HHMMSS.log`: one log file per run

## Tests and lint

```bash
python -m pytest
```

```bash
python -m ruff check .
```

## Troubleshooting

- **`ModuleNotFoundError`**: the venv is not active, or `pip install -r requirements.txt` was skipped.
- **`config.yaml is missing sections: ...`**: a required section was deleted from `config.yaml`. Restore it from git.
- **`check_apis.py` says FAIL with HTTP 400 or 403 for YouTube**: the key is wrong, the YouTube Data API v3 is not enabled in the Google Cloud project, or the daily quota is used up.
- **`check_apis.py` says FAIL with HTTP 401 for Podcast Index**: the key or secret is wrong, or your PC clock is off. The auth uses the current time.
- **`check_apis.py` says FAIL with HTTP 400 or 403 for Gemini**: the key is wrong or restricted. Create a new one at https://aistudio.google.com (Get API key).
- **`creator check failed` or `creator check not run (LLM unavailable)`** in `rejection_reason`: Gemini did not answer (free-tier load or quota). Run again later; answers already given are cached. To try another model, change `llm.model` in `config.yaml`.
- **Log says `YouTube daily quota used up`**: the remaining YouTube searches were skipped. Run again after the quota resets (midnight Pacific time). Finished searches are cached, so the run continues where it stopped.
- **`input file not found`**: check the `--input` path.
- **The first run is slow** (about 1.75 s per new podcast with 8 parallel fetches; 96 minutes for 3,299 shows on 2026-10-28): a slow site can take up to 3 × 20 s before it is skipped. Reruns are served from the cache (about 6 minutes for the same 3,299 shows). Failed sites are retried after 1 day.
- **`RUN FAILED: the lead set breaks ... hard rule(s)`** and exit code 2: the final leads break a country or language rule (see `cap_checks` in `output/engine.db`). A country above 60% is trimmed automatically, so this usually means fewer than 3 countries. Add seeds for other countries or niches and run again.
- **`partial: website (robots.txt disallows)`** in `profiles`: the site asks bots not to read it, so we don't. That's expected behaviour, not an error.

## Docs

| File | Holds |
|---|---|
| [docs/TECH_BUILD.md](docs/TECH_BUILD.md) | tools used to build the app |
| [docs/TECH_RUNTIME.md](docs/TECH_RUNTIME.md) | libraries, APIs and data stores used inside the app |
| [docs/WORKFLOW.md](docs/WORKFLOW.md) | pipeline stages, inputs, outputs, failure handling |
| [docs/PHASES.md](docs/PHASES.md) | phase status |
| [docs/DECISIONS.md](docs/DECISIONS.md) | decision log |
| [CHANGELOG.md](CHANGELOG.md) | dated changes |
| [docs/records/AI_TOOLS_SOURCES.md](docs/records/AI_TOOLS_SOURCES.md) | AI tools and sources used |
| [docs/records/MANUAL_WORK.md](docs/records/MANUAL_WORK.md) | manual work done by the owner |
