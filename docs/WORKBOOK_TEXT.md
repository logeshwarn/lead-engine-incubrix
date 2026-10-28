# Submission Workbook text (draft)

Text to paste into `docs/Submission_Workbook.xlsx`, tab by tab. It is a draft: the owner checks every line before pasting.

- **[final run]**: a number from the final `run_report.md`, filled in when that run finishes.
- **[owner]**: only the owner can fill this in (personal details, videos, product use, time spent).
- Evidence paths are relative to the repository, or to the output folder for `leads.csv`, `outreach/`, `rejected.csv` and `run_report.md`.

## 00_START

| Field | Text |
|---|---|
| Candidate ID, full name, email, college and degree, assessment start, submission time | [owner] |
| Main output folder URL | [owner: shared folder holding `leads.csv`, `outreach/`, `rejected.csv`, `run_report.md`, `seed_test/`] |
| Repository or workflow URL | [owner: private repository link] |
| Launch kit URL | [owner: link to `docs/LAUNCH_KIT.md` in the repository] |
| Product walkthrough video URL, Technical demo video URL | [owner] |
| AI tools, data sources and services used | Claude Code (Claude Opus 5.5) built the engine and docs. Claude web drafted the first seed list. Google Gemini `gemini-3.5-flash-lite` (free tier) does the creator-vs-organisation check and the country-quote check inside the engine. Data: Podcast Index API, Apple iTunes Search, Lookup and top-chart feeds, YouTube Data API v3, and creators' public RSS feeds and websites. Full dated list: `docs/records/AI_TOOLS_SOURCES.md`. |
| Total money spent (if any) and on what | $0: every API was used on its free tier or free quota **[final run: confirm in `run_report.md`]** |
| Manual work disclosed (what and how much) | See `docs/records/MANUAL_WORK.md`: seed list review, decisions on the open questions, hand checks of leads, the seed test (LinkedIn and Instagram sent by hand). [owner: time spent per row] |

## 03_ENGINE_LAUNCH

### A. Engine proof

| Requirement | Done? | Evidence path / URL | Notes |
|---|---|---|---|
| One clear run command in the README | Yes | `README.md`, section "Run" | `python run.py --input data/seeds.csv --out output/` |
| Works on a fresh machine or account | [owner: test on a fresh clone] | `README.md`, section "Setup" | Python 3.11+, `pip install -r requirements.txt`, 3 keys in `.env` |
| Removes duplicates | Yes | `engine/dedupe.py`, `tests/test_dedupe.py`; `duplicate_check` column in `leads.csv` | One creator per platform ID, website domain or email (union-find). An email listed on 3 or more shows is treated as a network's, not the creator's. The export stops on a duplicate `lead_id`. |
| Quality checks before export | Yes | `engine/verify.py`, `engine/caps.py`, `engine/draft.py`; `run_report.md` "Hard rules"; `rejected.csv` | Each of the brief's qualification rules is checked with an evidence URL; the country caps are checked; every message is checked (episode reference, sender, opt-out, length, no employee claim). The run exits with code 2 if a hard rule fails. |
| Clean export in the official format | Yes | `leads.csv`; `tests/test_leads_schema.py` | The 30 columns of tab 02_LEADS, in order, with the workbook's allowed values. The test re-reads the workbook. |
| Refresh updates existing items without duplicates | Yes | `run.py --refresh`; `tests/test_setup.py::test_refresh_shortens_the_cache_window`; `tests/test_dedupe.py::test_run_writes_table_and_rerun_is_identical` | `lead_id` is the stable platform ID, so a refreshed creator keeps its row. |
| Logs errors and recovers from a simple failure | Yes | `output/logs/`; `engine/common.py` (`cached_get`); `tests/test_cache.py` | Retries transient errors 3 times, logs and skips a failed source, and resumes from the cache when rerun after a crash. |
| Tests included | Yes | `tests/` (245 tests); `python -m pytest` | |
| No secrets in the repository | Yes | `.gitignore`, `.env.example`; `tests/test_setup.py` | Keys only in `.env`, which git ignores. `.env.example` has names only (tested). |

### B. Run summary

Fill from each run's `run_report.md` and log file. Runs to do:

| Run | How | Input size | Items produced | Items rejected | Duplicates removed | Runtime (min) | Direct cost | Evidence / log |
|---|---|---|---|---|---|---|---|---|
| Normal run | `python run.py --input data/seeds.csv --out output/full/` | [final run: seeds, candidates] | [final run] | [final run] | [final run] | [final run] | $0 | `output/full/run_report.md`, `output/full/logs/` |
| Repeat run (same input) | the same command again | same | same leads, same IDs | same | same | [owner run] | $0 | the second report: identical counts, from the cache |
| Refresh (new input) | `python run.py --refresh --input <new seeds> --out output/full/` | [owner run] | [owner run] | | | | $0 | its report and log |
| Failure and recovery | stop the run partway (Ctrl+C), then run the same command again | | | | | | $0 | log: resumes from the cache with no duplicate rows |

### C. Launch kit summary

From `docs/LAUNCH_KIT.md`:

| Field | Text |
|---|---|
| Who exactly we target first | Independent English-language podcasters and video podcasters in the US, GB, CA, AU, NZ, IE and SG. They post weekly (or 2+ long episodes in 60 days), show a public sign of income, and have a measured gap: most have no transcripts on recent episodes. Start with the 25 Priority A leads, then B, then C. |
| Channels / platforms and why | Email first: the creator's own published business address, the best channel for 37 of the first 40 leads, and trackable. Backups, all sent by hand: the creator's own contact form, Instagram DM, LinkedIn note, or the show's guest-pitch page. **[final run: full mix]** |
| Week 1 actions (owner, tool, volume) | Growth owner reviews and sends the 25 A sequences by hand from `outreach/A/` (Mon-Tue), then B emails at 20 a day per mailbox (2 mailboxes), and logs everything in a Google Sheets or HubSpot free CRM. Ops sets up the separate domain, SPF/DKIM/DMARC and Postmaster Tools before Monday. Founder takes calls. |
| Weeks 2-4 actions | A follow-up 2 on the backup channel (day 9). B and C sends rising to 30, then 40 a day per mailbox. Engineer runs `--refresh` every Monday (30 min) and loads only new IDs. Weekly review moves volume to the channels that get replies. |
| Tools and monthly cost | Engine on free APIs ($0); domain (about $1); 2 Google Workspace mailboxes (about $14-17); free CRM and Postmaster Tools. Total about $15-18 a month. |
| Targets after 30 days (numbers) | All 25 A and **[final run]** B/C contacted. Bounces under 2%, spam complaints under 0.1%. Assumed replies: 15% for A, 3% for B/C, with 1 meeting per 3 replies (**[final run]** meetings). Measured rates per channel replace these by day 30. |
| Biggest risk and how to handle it | Cold email hurting deliverability or breaking consent rules. Handled with a separate domain, low volume that rises slowly, own-published addresses only, and stopping at 3% bounces. Legal confirms the rules per country; UK and Irish sole traders are contacted by contact form until PECR consent is confirmed. |
| What IncuBrix must provide (accounts, access, budget) | Outreach domain and 2 mailboxes; postal address; sender name and role; approval of the product line; legal sign-off; one team member's Instagram and LinkedIn; a founder's booking link and about 2 hours a week; about 1.5 hours a day of growth time; API keys; about $15-18 a month. |

## 04_SELF_CHECK

### A. Minimum results

| Minimum | Your value | Evidence path / URL |
|---|---|---|
| Unique qualified creators (full leads.csv) | [final run] | `leads.csv`; `run_report.md` "Counts" |
| Countries: 80% approved, 3+ countries, none above 60% | [final run: Yes/No] | `run_report.md` "Hard rules" and "Mix" |
| Final duplicates | 0 | `leads.csv` `duplicate_check`; the export stops on a duplicate `lead_id` |
| Outreach channels with ready sequences | [final run: count of channels used in `outreach/sequences.csv`; at least Email, Contact form, Instagram, LinkedIn] | `outreach/templates.md`, `outreach/sequences.csv` |
| Priority A leads with first message + 2 follow-ups | 25 | `outreach/A/`, `outreach/sequences.csv` |
| Seed test on own accounts passed on 3 channels | [owner: after the seed test] | `seed_test/seed_report.md` and screenshots |
| Engine reruns from README | Yes | `README.md`; the repeat run in tab 03 B |

### B. Exceptional requirements

| Requirement | Achieved? | Notes |
|---|---|---|
| 5,000 unique creators | [final run] | Unlikely to be met: the strict country, activity and income rules leave about 1-2% of candidates. |
| 250 Priority A leads with full sequences | No | The brief asks for 25 A. Drafting is automated, so raising `priority_a.count` in `config.yaml` would produce more. |
| Refresh 5,000 rows with 0% duplicates | [final run] | |
| Channel-mix recommendation from response evidence | No (planned) | The launch kit measures replies per channel in week 1; the seed test proves only the mechanics. |

### C. Self-score

[owner: score each area and give the reasons; reviewers compare it with their own]
