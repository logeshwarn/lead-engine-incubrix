# IncuBrix Lead Engine

A small Python engine that finds content creators (podcasters, YouTubers, expert-led creators), verifies each one with public evidence, picks the best contact channel, drafts personalised outreach, and exports a CRM-ready `leads.csv`. It is meant to be rerun every week with one command.

The full brief is in [docs/BRIEF.pdf](docs/BRIEF.pdf).

The assignment it answers is in [docs/IncuBrix_2027_Growth_Engineer_Option_1_Lead_Generation_and_Outreach.pdf](docs/IncuBrix_2027_Growth_Engineer_Option_1_Lead_Generation_and_Outreach.pdf).

**Status:** all 9 stages are built and the engine meets the 1,000-lead target. The final run (29 Oct 2026, `data/seeds.csv`) gave **1,083 qualified leads** (25 Priority A with full sequences), with 0 duplicates and every hard rule passing. Repeat, refresh and stop-and-resume runs are proven too. The seed test and the owner's audit are still open; see [docs/PHASES.md](docs/PHASES.md).

The stages: **discover → enrich → verify → dedupe → caps → score → route → draft → export.** Each one reads a table in `engine.db` and writes the next one, so a stopped run continues from the cache. The details are in [docs/WORKFLOW.md](docs/WORKFLOW.md).

## Setup (Windows, Python 3.11+)

```bash
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Then open `.env` and fill in your API keys: YouTube, Podcast Index (key and secret) and Gemini (`LLM_API_KEY`). `GROQ_API_KEY` is optional: Groq takes over when Gemini's free daily quota runs out. All of them have free tiers. `.env` is ignored by git, so never commit it.

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
| `--refresh` | off | re-fetch everything cached more than 1 day ago, so all evidence is re-checked; keep what was fetched today |
| `--merge-cache` | off | first copy another output folder's cached fetches into this one (for two runs fetched in parallel) |
| `--fetch-shard K/N` | off | only fill the cache for part K of N of the creators a running full run discovered, in the same `--out` folder; writes no tables. Start N of them next to a slow first run (feed parsing uses one CPU core per process) |
| `--workers N` | `enrich.workers` | fetch threads for this run |

`python run.py --help` lists the same flags.

**Quota warning:** an uncached run over the full `data/seeds.csv` makes 84 YouTube searches, about 8,400 of the 10,000 free daily units, and enrich adds about 2-3 units per YouTube channel. A full first run therefore takes 2-3 days of quota. The free LLM quotas allow roughly 1,000-1,500 creator checks a day across the Gemini and Groq models (`llm` in `config.yaml`). A creator that could not be checked is rejected with `creator check not run`, and the next run after the quota resets checks only those creators. How the 1,083 leads were built up over several reruns: [docs/CACHE_AND_RERUNS.md](docs/CACHE_AND_RERUNS.md). Each run stops YouTube calls cleanly when the quota runs out, and the next day's run continues from the cache. A rerun within 7 days is served from the cache and costs nothing. **If a run stops** (Ctrl+C, crash, power or network loss), run the same command again: it continues from the cache. To try the engine cheaply, copy a few rows of `data/seeds.csv` into a new file and pass it with `--input`.

## Config

- `data/seeds.csv`: the niches and search terms to discover from. Each row is a niche, not a lead. A row with `primary_platform` = `podcast_category` names a Podcast Index category (e.g. `Fitness`) and brings up to 2,000 active shows; `apple_chart` names an Apple genre (e.g. `Health & Fitness`) and brings Apple's top-200 chart in each non-US store. The columns are explained in [docs/WORKFLOW.md](docs/WORKFLOW.md). Set `status` to `paused` to skip a row.
- `config.yaml`: thresholds, country and segment caps, scoring weights (`score`), message wording (`draft`, `sender`), activity rules, evidence age, the cache window (`cache`) and search sizes (`discover`). Values come from the brief, and segment and country names come from the Submission Workbook. Changes and their reasons go in [docs/DECISIONS.md](docs/DECISIONS.md).
- `.env`: API keys only. `.env.example` lists the keys you need.

## Outputs

- `output/leads.csv`: the qualified leads, 30 columns locked to the Submission Workbook, with the first message for every lead
- `output/outreach/`: `sequences.csv` (every message with its day, channel and send mode), one file per lead in `A/`, `B/`, `C/`, and `templates.md`
- `output/run_report.md`: result, counts, mix, hard rules, top rejection reasons, runtime, API calls, tokens, cost and errors (generated, do not edit)
- `output/rejected.csv`: every rejected creator, with all its reasons (the first is the main one), its profile, website, country evidence URL and, for a merged duplicate, `duplicate_of`
- `output/engine.db`: SQLite database. It holds:
  - the API cache and the API call log
  - `candidates` (discover)
  - `profiles` and `content_items` (enrich)
  - `verified` (verify): look at `candidate_status` and `rejection_reason`
  - `deduped` (dedupe): the same rows, one Qualified row per creator; `duplicate_of` names the row a duplicate was merged into
  - `capped` and `cap_checks` (caps): the final country mix, and each hard rule with its value and pass/fail
  - `scored` (score): each lead's 5 score parts, `lead_score` and `priority` (A, B or C)
  - `routed` (route): the best and backup channel per lead, each with its handle or URL and evidence URL
  - `drafted` (draft): every message and its checks
  
  Delete it to start from scratch, which spends the quota again. Any SQLite viewer (for example "DB Browser for SQLite") can open it to inspect the rows by hand.
- `output/logs/run_YYYYMMDD_HHMMSS.log`: one log file per run

## Seed test (your own test accounts only)

Fill the `SEED_*` lines in `.env` (a sending Gmail with an App Password, and your second test email, LinkedIn and Instagram accounts), then:

```bash
python seedtest.py plan --out output/ --leads 3
```

```bash
python seedtest.py clicks --out output/
```

```bash
python seedtest.py send --out output/
```

```bash
python seedtest.py report --out output/
```

`clicks` runs in its own terminal. Run `send` again after 8 and 18 minutes for the follow-ups, send the printed LinkedIn and Instagram messages by hand, log them with `python seedtest.py mark --out output/ S004 sent`, and collect email replies with `python seedtest.py replies --out output/`. Steps and screenshots: [docs/WORKFLOW.md](docs/WORKFLOW.md#seed-test-seedtestpy-phase-6).

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
- **`creator check failed` or `creator check not run (LLM unavailable)`** in `rejection_reason`: no model in the LLM chain could answer, because every Gemini and Groq model hit its free quota or was busy. Run the same command again after the quotas reset (Gemini at midnight Pacific; Groq 24 hours after its first calls). Answers already given are cached, so only the unchecked creators are asked. The models and their order are `llm.model`, `llm.fallback_models` and `llm.groq_models` in `config.yaml`. The log says `out of quota` when a model is dropped.
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
| [docs/LAUNCH_KIT.md](docs/LAUNCH_KIT.md) | 30-day launch plan for IncuBrix: channels, daily volume, owners, tools, budget, targets, risks |
| [docs/WORKBOOK_TEXT.md](docs/WORKBOOK_TEXT.md) | draft text for the Submission Workbook tabs |
| [docs/CACHE_AND_RERUNS.md](docs/CACHE_AND_RERUNS.md) | how the cache and reruns work, why, and the milestones from 7 to 1,083 leads |
| [CHANGELOG.md](CHANGELOG.md) | dated changes |
| [docs/records/AI_TOOLS_SOURCES.md](docs/records/AI_TOOLS_SOURCES.md) | AI tools and sources used |
| [docs/records/MANUAL_WORK.md](docs/records/MANUAL_WORK.md) | manual work done by the owner |
