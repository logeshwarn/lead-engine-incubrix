# IncuBrix Lead Engine

A small Python engine that finds content creators (podcasters, YouTubers, expert-led creators), verifies each one with public evidence, picks the best contact channel, drafts personalised outreach, and exports a CRM-ready `leads.csv`. It is built to be rerun every week with one command.

**Status (30 Oct 2026):** all 9 stages are built. The full run on `data/seeds.csv` (198 seeds) gave **1,260 qualified leads**, with 25 Priority A leads that each have full sequences, 0 duplicates and every hard rule passing. Repeat, refresh and stop-and-resume runs are proven ([docs/WORKBOOK_TEXT.md](docs/WORKBOOK_TEXT.md), tab 03). The seed test and the owner's audit are still open ([docs/PHASES.md](docs/PHASES.md)).

The brief and the assignment come from IncuBrix and are not in the repository. The rules they set are written out in [docs/WORKFLOW.md](docs/WORKFLOW.md): the qualification checks, the hard constraints and the `leads.csv` columns.

```
seeds.csv → discover → enrich → verify → dedupe → caps → score → route → draft → export
                                                         leads.csv, outreach/, rejected.csv, run_report.md
```

---

## 1. Set up (once, about 10 minutes)

You need **Python 3.11 or newer** and **git**. Every command below runs from the project folder.

**1. Get the code**

```bash
git clone <repository URL>
cd <project folder>
```

**2. Create a virtual environment and install the pinned packages**

Windows (PowerShell or Command Prompt):

```bash
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Activate the virtual environment again in every new terminal before running anything.

**3. Put your API keys in `.env`.** All of them are free. `.env` is ignored by git, so never commit it.

| Line in `.env` | Where to get it | Needed for |
|---|---|---|
| `YOUTUBE_API_KEY` | [Google Cloud console](https://console.cloud.google.com/): create a project, enable **YouTube Data API v3**, then Credentials → Create credentials → API key | YouTube discovery and channel details (10,000 free units a day) |
| `PODCASTINDEX_API_KEY` and `PODCASTINDEX_API_SECRET` | [api.podcastindex.org](https://api.podcastindex.org/): sign up, and the key and secret are shown to you | podcast discovery |
| `LLM_API_KEY` | [Google AI Studio](https://aistudio.google.com/): Get API key | the creator-vs-organisation check (Gemini, free tier) |
| `GROQ_API_KEY` *(optional)* | [console.groq.com](https://console.groq.com/): API Keys | takes over when Gemini's free daily quota runs out |

The `SEED_*` lines are only for the seed test (section 6). Leave them blank for normal runs.

**4. Check that the keys work.** This costs 1 YouTube quota unit and 0 LLM tokens, and prints only PASS or FAIL per API, never a key:

```bash
python check_apis.py
```

**5. Check that the code works.** This runs offline, because the tests never call a real API:

```bash
python -m pytest
```

---

## 2. Try it on a small input first (about 15 minutes)

[data/sample_seeds.csv](data/sample_seeds.csv) holds 11 country seeds: business, health and lifestyle podcasts in Australia, the UK, Canada, New Zealand, Ireland and Singapore. They use only free podcast searches, so they spend no YouTube search quota. Measured from an empty folder on 31 Oct 2026: 13.4 minutes, 297 candidates, **11 leads from 5 countries**, all hard rules passing.

```bash
python run.py --input data/sample_seeds.csv --out output/sample/
```

When it finishes, open `output/sample/run_report.md` for the counts, and `output/sample/leads.csv` for the leads. The last log line says `run finished`. The exit code is 0 when every hard rule passes, and 2 when the final set breaks one. An input of only 2 or 3 seeds often ends with leads from fewer than 3 countries, and then the run says so loudly: that is the rule working, not a crash.

### Your own input

A seed file is a CSV with these columns, one row per niche to search (not per lead):

```csv
seed_id,segment,niche,primary_platform,discovery_keywords,need_signal_to_check,size_min,size_max,status
T001,Podcaster/Video Podcaster,uk_fitness,podcast,uk fitness podcast; british personal trainer podcast,no transcripts,,,active
T002,YouTuber/Video-First Creator,cooking,youtube,home cooking channel,no captions,1000,250000,active
T003,Podcaster/Video Podcaster,cat_marketing,podcast_category,Marketing,no transcripts,,,active
```

- `segment`: `Podcaster/Video Podcaster`, `YouTuber/Video-First Creator` or `Expert-Led Creator`.
- `primary_platform`:
  - `podcast`: keyword search on Podcast Index and iTunes, free
  - `youtube`: channel search, **100 quota units per keyword**
  - `podcast_category`: a Podcast Index category name such as `Fitness`, which brings up to 2,000 active shows
  - `apple_chart`: an Apple genre name listed under `discover.apple_genres` in `config.yaml`
- `discovery_keywords`: search terms separated by `;`.
- `size_min`, `size_max`: the subscriber range for YouTube seeds. Leave them blank for podcasts.
- `status`: `active` or `paused`.

Full column notes are in [docs/WORKFLOW.md](docs/WORKFLOW.md#seeds-dataseedscsv). Then run:

```bash
python run.py --input path/to/your_seeds.csv --out output/my_run/
```

Use a new `--out` folder for each separate input, because each folder has its own database and cache.

---

## 3. Full run and refresh

**Full run** (the one command):

```bash
python run.py --input data/seeds.csv --out output/
```

**Refresh**, which re-checks all evidence, keeps every lead's ID and never adds duplicates:

```bash
python run.py --refresh --input data/seeds.csv --out output/
```

**Stopped or crashed?** Run the same command again. Every API answer is cached in `<out>/engine.db`, so the run continues where it stopped and nothing is fetched twice. How the cache works, and how the 1,260 leads were built up over several runs: [docs/CACHE_AND_RERUNS.md](docs/CACHE_AND_RERUNS.md).

**How long a full run takes from an empty folder.** The free quotas set the pace, not the code:

| Limit | What it means |
|---|---|
| YouTube: 10,000 units a day | the 84 YouTube search terms in `data/seeds.csv` cost about 8,400 units; channel details cost about 2-3 units per channel |
| LLM: roughly 1,000-1,500 creator checks a day | the Gemini and Groq free tiers (`llm` in `config.yaml`); creators not yet checked are rejected with `creator check not run`, and the next run after the quota resets checks only those |
| Fetching about 50,000 podcast feeds and websites | measured 28 Oct at about 1.75 s per new show with 8 parallel fetches (now 24, `enrich.workers`); a slow site is skipped after 3 × 20 s |

So a first full run takes **2-3 days of quota**. Run the same command once a day until the log shows no `creator check not run`. A rerun within 7 days comes from the cache and costs nothing. To speed up the first fetch, start extra fetch processes next to a running full run, in the same `--out` folder:

```bash
python run.py --input data/seeds.csv --out output/ --fetch-shard 1/4 --workers 8
```

Repeat that with `2/4`, `3/4` and `4/4` in separate terminals. Each shard only fills the cache. When they finish, rerun the normal command.

**All flags** (`python run.py --help` prints the same list):

| Flag | Default | What it does |
|---|---|---|
| `--input` | `data/seeds.csv` | seed CSV |
| `--out` | `output/` | output folder: database, cache, logs and results |
| `--config` | `config.yaml` | settings file |
| `--refresh` | off | re-fetch everything cached more than 1 day ago, so all evidence is re-checked |
| `--merge-cache OTHER_OUT` | off | first copy another output folder's cached answers into this one |
| `--fetch-shard K/N` | off | only fill the cache for part K of N of the creators (see above); writes no tables |
| `--workers N` | `enrich.workers` | parallel fetch threads |

---

## 4. Outputs (in the `--out` folder)

| File | What it is |
|---|---|
| `leads.csv` | the qualified leads, in the 30 columns of the Submission Workbook (tab 02_LEADS), each with its evidence URLs, best and backup channel, score, priority and first message |
| `outreach/` | `sequences.csv` (every message with its day, channel and send mode), one Markdown file per lead in `A/`, `B/` and `C/`, and `templates.md` |
| `rejected.csv` | every rejected creator with all its reasons (the first is the main one) |
| `run_report.md` | generated each run, do not edit: the result, counts, country, segment, priority and channel mix, the hard rules, top rejection reasons, runtime, API calls, tokens, cost and errors |
| `engine.db` | SQLite: the API cache and call log, plus one table per stage (`candidates`, `profiles`, `verified`, `deduped`, `capped`, `scored`, `routed`, `drafted`). Any SQLite viewer opens it. Delete it to start from scratch, which spends the quota again |
| `logs/run_YYYYMMDD_HHMMSS.log` | one log file per run |

---

## 5. Settings

- **`config.yaml`** holds every threshold, with a comment on each:
  - the activity rules, evidence age, country and segment caps
  - the scoring weights (`score`) and Priority A count
  - the message wording and sender (`draft`, `sender`)
  - the LLM models (`llm`), the cache windows (`cache`) and search sizes (`discover`)

  The reason for each value is in [docs/DECISIONS.md](docs/DECISIONS.md).
- **`data/seeds.csv`** is the niches to search: 198 seeds (32 YouTube, 44 podcast keyword, 50 Podcast Index category, 72 Apple chart).
- **`.env`** holds the API keys only. `.env.example` lists the names.

---

## 6. Seed test (your own test accounts only)

This proves scheduling, tracked links and reply logging on 3 channels (email, LinkedIn, Instagram) without contacting any creator. The script refuses any recipient that is not in your `.env`.

**Before you start:** fill the `SEED_*` lines in `.env`:
- a sending Gmail with 2-step verification and an [App Password](https://myaccount.google.com/apppasswords)
- your second Gmail
- your second LinkedIn profile link
- your second Instagram handle

The network must allow outgoing mail (port 587). Some college or office networks block it, so a phone hotspot works.

```bash
python seedtest.py plan --out output/ --leads 3
```

```bash
python seedtest.py clicks --out output/
```

```bash
python seedtest.py send --out output/
```

Then:
1. Keep `clicks` running in its own terminal.
2. Run `send` again after 8 and after 18 minutes for the follow-ups.
3. Send the printed LinkedIn and Instagram messages by hand, and log each one with `python seedtest.py mark --out output/ S004 sent`.
4. Reply from your test accounts. Collect email replies with `python seedtest.py replies --out output/`, and log social replies with `mark ... reply`.
5. Write the report:

```bash
python seedtest.py report --out output/
```

The steps and screenshots are listed in [docs/WORKFLOW.md](docs/WORKFLOW.md#seed-test-seedtestpy-phase-6).

---

## 7. Tests and lint

```bash
python -m pytest
```

```bash
python -m ruff check .
```

---

## 8. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `ModuleNotFoundError` | The virtual environment is not active, or `pip install -r requirements.txt` was skipped. |
| `check_apis.py`: YouTube FAIL, HTTP 400 or 403 | The key is wrong, YouTube Data API v3 is not enabled in the Google Cloud project, or today's quota is used up. |
| `check_apis.py`: Podcast Index FAIL, HTTP 401 | The key or secret is wrong, or your PC clock is off (the auth uses the current time). |
| `check_apis.py`: Gemini FAIL, HTTP 400 or 403 | The key is wrong or restricted. Create a new one in Google AI Studio. |
| `creator check not run (LLM unavailable)` in `rejected.csv` | Every Gemini and Groq model hit its free quota, was busy, or the network dropped. Run the same command again later: only unchecked creators are asked. Gemini resets at midnight Pacific time; Groq 24 hours after its first calls. The log says `out of quota` when a model is dropped. |
| Log says `YouTube daily quota used up` | The remaining YouTube calls were skipped. Run again after midnight Pacific time; finished searches are cached. |
| `RUN FAILED: the lead set breaks ... hard rule(s)`, exit code 2 | The final leads break a country or language rule (see `cap_checks` in `engine.db`). A country above 60% is trimmed automatically, so this usually means fewer than 3 countries: add seeds for other countries. |
| `config.yaml is missing sections: ...` | A required section was deleted. Restore it from git. |
| `input file not found` | Check the `--input` path. |
| The first run is slow | It fetches every feed and website once; reruns come from the cache. Use `--fetch-shard` (section 3). |
| `partial: website (robots.txt disallows)` in `profiles` | The site asks bots not to read it, so the engine doesn't. Expected, not an error. |
| Seed test: `SMTP ... TimeoutError` | The network blocks outgoing mail. Switch networks, for example to a phone hotspot. |

---

## 9. Project layout

| Path | What it is |
|---|---|
| `run.py` | the one command: runs the 9 stages in order |
| `engine/` | one file per stage (`discover.py` … `export.py`) and `common.py` (config, cache, retries, LLM chain, `leads.csv` schema) |
| `check_apis.py` | one cheap live call per API to prove the keys work |
| `seedtest.py` | the seed test |
| `config.yaml` | every threshold, weight and model |
| `data/seeds.csv` | the full seed list; `data/sample_seeds.csv`: 11 seeds for a quick try; `data/proof/`: the refresh-proof inputs; `data/seeds_original.csv`: the owner's first list |
| `tests/` | pytest tests, one file per stage, all offline |
| `docs/` | documentation (below) |
| `output/` | created by runs, ignored by git |

## 10. Documentation

| File | What it holds |
|---|---|
| [docs/WORKFLOW.md](docs/WORKFLOW.md) | the stages, their inputs and outputs, every qualification rule, and failure handling |
| [docs/TECH_RUNTIME.md](docs/TECH_RUNTIME.md) | the libraries, APIs and data stores used inside the app, with quotas and costs |
| [docs/TECH_BUILD.md](docs/TECH_BUILD.md) | the tools used to build the app |
| [docs/DECISIONS.md](docs/DECISIONS.md) | the decision log: each threshold and trade-off, with its reason |
| [docs/PHASES.md](docs/PHASES.md) | phase status and results |
| [docs/CACHE_AND_RERUNS.md](docs/CACHE_AND_RERUNS.md) | how the cache and reruns work, and the milestones from 7 to 1,260 leads |
| [docs/LAUNCH_KIT.md](docs/LAUNCH_KIT.md) | the 30-day launch plan for IncuBrix |
| [docs/WORKBOOK_TEXT.md](docs/WORKBOOK_TEXT.md) | text for the Submission Workbook tabs |
| [CHANGELOG.md](CHANGELOG.md) | dated changes |
| [docs/records/AI_TOOLS_SOURCES.md](docs/records/AI_TOOLS_SOURCES.md) | every AI tool and data source used |
| [docs/records/MANUAL_WORK.md](docs/records/MANUAL_WORK.md) | the manual work done by the owner |
