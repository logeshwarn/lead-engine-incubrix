# IncuBrix Lead Engine

A small Python engine that finds content creators (podcasters, YouTubers, expert-led creators), verifies each one with public evidence, picks the best contact channel, drafts personalised outreach, and exports a CRM-ready `leads.csv`. It is meant to be rerun every week with one command.

The full brief is in [docs/BRIEF.pdf](docs/BRIEF.pdf).

**Status:** Phase 0 (setup) is done, and API access for YouTube and Podcast Index is confirmed. The pipeline stages are not built yet, so a run only loads the config, writes a log and lists the planned stages. See [docs/PHASES.md](docs/PHASES.md).

## Setup (Windows, Python 3.11+)

```bash
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Then open `.env` and fill in your API keys. `.env` is ignored by git, so never commit it.

Check that the keys work. This costs 1 YouTube quota unit and prints only PASS or FAIL:

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

## Config

- `data/seeds.csv`: the niches and search terms to discover from. Each row is a niche, not a lead. The columns are explained in [docs/WORKFLOW.md](docs/WORKFLOW.md). Set `status` to `paused` to skip a row.
- `config.yaml`: thresholds, country and segment caps, activity rules and evidence age. Values come from the brief, and segment and country names come from the Submission Workbook. Changes and their reasons go in [docs/DECISIONS.md](docs/DECISIONS.md).
- `.env`: API keys only. `.env.example` lists the keys you need.

## Outputs

These are planned and will exist once the export stage is built (Phase 5):

- `output/leads.csv`: qualified leads, with columns locked to the Submission Workbook
- `output/rejected.csv`: rejected candidates and the reason for each
- `output/outreach/`: drafted messages
- `output/run_report.md`: counts, mix, runtime, API calls, cost and errors (generated, do not edit)

Already produced today:

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
