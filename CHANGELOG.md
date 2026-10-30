# Changelog

Dated list of notable changes. Newest first.

## 2026-10-31: seed test done

- Seed test on the owner's own accounts, 3 channels: Email 9 of 9 sent automatically on schedule (first messages, then +8 and +18 min, each within a minute of plan), 1 click, 1 reply found in Gmail by IMAP; Instagram and LinkedIn 1 message each sent by hand, each with 1 click and 1 reply. Proof in `output/full/seed_test/`.
- `seedtest.py`: `mark --out <folder> S004 sent` (the order in the README) now parses (`parse_intermixed_args`). Test added; 267 in total.
- README: the network must allow SMTP (port 587), with a troubleshooting row. Docs: PHASES (Phase 6 done), WORKBOOK_TEXT, MANUAL_WORK.

## 2026-10-30 (night): docs cleanup

- README rewritten as a run guide for evaluators: setup on Windows and macOS/Linux, where to get each API key, a quick try on `data/sample_seeds.csv`, how to write a seed file, full run and refresh with honest time and quota, outputs, settings, seed test, troubleshooting, project layout and docs index.
- Added `data/sample_seeds.csv` (S102-S112). From an empty folder: 13.4 min, 297 candidates, 11 leads in 5 countries, all hard rules pass. A 3-seed sample was tried first, but its leads came from only 1-2 countries, so the run failed the 3-country rule.
- TECH_RUNTIME: removed the stale *(planned)* marks, listed every stage table, current discover call counts and the LLM chain order. WORKFLOW: current seed counts. TECH_BUILD: OS note.

## 2026-10-30 (night): own-words need fix

- `engine/verify.py`: `NEED_WORDS` phrases must be about the show; `quote(..., whole_words=True)` for need quotes. 17 of 21 own-words needs were false matches (DECISIONS.md). Tests: 9 new; 265 in total.
- Rerun from the cache (23:04-23:56) to re-pick needs and Priority A: **1,260 leads** (US 756 = 60.0%), all hard rules pass; 5 real own-words needs remain. Docs use 1,260.

## 2026-10-30: waves 4-7, 1,262 leads

- Waves 5-7: S144-S164 (21 country and city keyword seeds), S165-S198 (34 Podcast Index categories). Results per run: 1,110, 1,125, 1,222, **1,262 leads** (US 60.0%), all hard rules pass. `output/full/` holds 1,262; backups of 1,083 and 1,222 in `output/backup_*`.
- Docs: README, LAUNCH_KIT, WORKBOOK_TEXT, PHASES and CACHE_AND_RERUNS use the 1,262 numbers.
- `tests/test_seeds.py`: a keyword may repeat on a different platform (an Apple genre and a Podcast Index category share names like "Business"); repeats within one platform still fail.

- `data/seeds.csv`: S113 and S114 (Australian and UK money and property podcasts, from the refresh proof) and S115-S143: 29 Apple subgenre charts (sports, comedy, science, leisure, TV and film, philosophy and others). `config.yaml` `discover.apple_genres` has their IDs.
- The proof runs' cache is merged into `output/full/`. The 1,083-lead outputs are backed up in `output/backup_1083/`.

## 2026-10-29 (evening): proof runs for tab 03

- Repeat run, refresh run and stop-and-resume run, all on copies (`output/proof/`, `output/proof_refresh/`); `output/full/` unchanged. Results in `docs/WORKBOOK_TEXT.md` tab 03 B and PHASES.
- `data/proof/seeds_base.csv` (S102-S112) and `data/proof/seeds_new.csv` (plus new seeds S113, S114) for the refresh proof.
- `docs/WORKBOOK_TEXT.md`: test count 256; the refresh requirement cites the refresh run.
- `docs/CACHE_AND_RERUNS.md`: proof-run section.
- README: current status (all stages built, 1,083 leads), the optional `GROQ_API_KEY`, the LLM quota per day, and the troubleshooting entry for the whole Gemini and Groq chain.
- DECISIONS: the owner keeps 1,083 leads as the submitted result.

## 2026-10-29: final run (1,083 leads), more LLM models

- Added `docs/CACHE_AND_RERUNS.md`: how the cache and reruns work, why they were needed, and the milestones (7, 82, 211, 493, 1,083 leads). README docs table lists it. `docs/WORKBOOK_TEXT.md` tab 00 now names every Gemini and Groq model used.
- `fallback_models` adds `gemini-3.1-flash-lite` first (its own 500 a day).
- Gemini briefly ran on the owner's billed key (`llm.pause_seconds` 4 -> 1); its credit ran out before any paid check, so the original free key and the 4 s pause are back.
- Rerun 06:22-06:51 IST from the cache: 211 leads (A 25, B 186), all non-US (GB 92, AU 52, CA 46, NZ 10, SG 6, IE 5); 1,997 creators unchecked.
- `common.llm_json`: a model that is busy (5xx after retries) passes the prompt to the next model without being dropped. `fallback_models` adds `gemini-3.8-flash`. Test added; 256 in total.
- Final run (12:32-15:47 IST, after the Gemini reset): **1,083 leads**, US 58.9%, all hard rules pass. `docs/LAUNCH_KIT.md`, `docs/WORKBOOK_TEXT.md` and PHASES filled with the final numbers; `run_report.md` names Groq among the free tiers.
- Merged run (wave 3 cache, 03:52-04:50 IST): 32,589 candidates, 82 leads (A 25, B 57), all non-US. Groq `gpt-oss-120b` hit its 200,000-token daily cap after 125 checks; 2,263 creators unchecked.
- `config.yaml`: `groq_models` adds `openai/gpt-oss-20b` and `qwen/qwen3.8-27b`.
- `common.llm_json`: after a 429, waits `llm.rate_limit_wait_seconds` (60) and tries once more before treating the model as out of quota, so a per-minute limit no longer drops a model for the whole run. Test added; 255 in total.

## 2026-10-29 (night): Groq as third LLM

- `common.llm_json` (was `gemini_json`): one chain of Gemini models then Groq models (`llm_chain`); cached answers from any model first (`cached_get(cache_only=True)`); out-of-quota models skipped. Returns the model; verify stores it in the new `creator_model` column.
- `config.yaml`: `llm.groq_models`, `groq_pause_seconds`, `groq_reasoning_effort`. `.env.example`: `GROQ_API_KEY`.
- Tests: Groq fallback, cache-first; 254 in total.

## 2026-10-29 (night): Gemini fallback, non-US first, wave 3 seeds

- First full run (01:14-02:00 IST): 23,943 candidates, 7 leads. Gemini Flash-Lite's free daily quota ran out after 47 creator checks, so 1,601 creators went unchecked (rejected "creator check not run").
- `common.gemini_json`: falls back to `llm.fallback_models` when a model is out of quota (`OUT_OF_QUOTA`). `config.yaml`: `fallback_models: [gemini-3.5-flash]`.
- `verify.apply_creator_check`: non-US rows are checked first.
- Seeds S073-S112 and 29 Apple subgenre IDs in `discover.apple_genres`.
- Tests: Gemini fallback; 252 in total.

## 2026-10-29: malformed URL fix

- Wave 1 stopped at 01:04 in the website phase on a link to `http://.libsyn.com`: urllib3 raises `LocationParseError` (a `ValueError`), which `cached_get` did not catch. Malformed or schemeless URLs now fail that one row as "invalid URL", without retries. Test added; 251 in total.
- All 20,012 podcast feeds were cached before the stop (19,923 readable). The final run will continue from the cache.

## 2026-10-28 (night): fetch shards

- `run.py --fetch-shard K/N` and `--workers N`; `enrich.in_shard`. 4 shards started next to wave 1 in `output/full/`.
- Tests: 3 new (shard split, shard run fills the cache only, argument check); 248 in total.
- Fix: the first 8 shards stopped on `database is locked` after all 20,012 feeds were cached (9 processes writing one cache). Cache and log writes now go through `common.write_with_retry`, which retries a locked write up to 10 times. Tests: 2 new; 250 in total. Shards restarted (6) for the website phase.
- Docs: README flags, WORKFLOW commands, DECISIONS.

## 2026-10-28 (night): launch kit and workbook text (drafts)

- Added `docs/LAUNCH_KIT.md`: 30-day plan with targets, channels, safe daily volume per channel, step-by-step owner actions, tools and cost, targets with labelled assumptions, risks, and what IncuBrix must provide.
- Added `docs/WORKBOOK_TEXT.md`: draft text for workbook tabs 00, 03 and 04, with evidence paths. Final-run numbers and owner-only fields are marked.
- README docs table lists both.

## 2026-10-28 (night): seed test tool

- Added `seedtest.py`: plan, send (SMTP), mark (hand-sent LinkedIn/Instagram), clicks (local tracker), replies (IMAP), report. Only the owner's `SEED_*` accounts can receive.
- `.env.example`: `SEED_*` names (blank). `config.yaml`: `seed_test.minutes_per_day`.
- Tests: `tests/test_seedtest.py` (5); 245 in total.
- Docs: WORKFLOW, README, TECH_RUNTIME, DECISIONS, PHASES.

## 2026-10-28 (night): deadline build, Phases 4 and 5

- Added `engine/draft.py` (stage 8): templated, fact-only messages for every lead and full Priority A sequences, each checked (content reference, sender, opt-out, length, no employee claim, no placeholder).
- `engine/export.py` (stage 9) now writes `leads.csv` (30 workbook columns), `outreach/` (sequences.csv, one file per lead, templates.md) and `run_report.md`, besides rejected.csv.
- `engine/verify.py`: a podcast failing only on country can take its linked YouTube channel's stated country; the size and country checks share one cached call. Need evidence falls back to the show page when an episode has no page of its own.
- `engine/discover.py`: `apple_chart` seeds (Apple's top-200 per genre in GB, AU, CA, IE, NZ, SG, then iTunes lookup).
- `engine/enrich.py`: YouTube channels are enriched in parallel (`enrich_channel`); `enrich.workers` 24.
- `run.py`: all 9 stages run; `--refresh` re-fetches anything cached more than 1 day ago; `--merge-cache` copies another run's cache; exit code 2 when a hard rule fails.
- `engine/common.py`: `merge_cache`.
- `data/seeds.csv`: 14 Apple chart seeds (S059-S072).
- Tests: draft, export, merge, refresh, linked country, Apple charts; 240 in total.
- Docs: WORKFLOW (stages 8 and 9, seeds, commands, resume), README, TECH_RUNTIME, DECISIONS, PHASES (Phase 4 done, Phase 5), and both records files.

## 2026-10-28: Stage 7, route (Phase 3 done)

- Added `engine/route.py`: `scored` -> `routed`. Best channel (email, contact form, guest-pitch page) and backup channel (another checkable channel, the creator's own social profile, a second email), each with its URL and evidence URL. Own-domain emails first, role mailboxes last, template placeholders never.
- `engine/verify.py`: "reachable" now needs a best and a backup channel (`route.choose`); a lead with one contact is rejected with "no backup channel". The unused `VERIFIABLE_CHANNELS` constant was removed.
- `run.py`: runs route after score.
- Tests: `tests/test_route.py` (12) and a verify test; 222 in total.
- Real data: 44 qualified, 40 final leads (US 24, GB 9, AU 3, CA 3, NZ 1), 25 A and 15 B.
- Docs: WORKFLOW (stage 7, reachable), DECISIONS (3 entries), PHASES (Phase 3 done), README, and both records files.

## 2026-10-28: Stage 6, score

- Added `engine/score.py`: `capped` -> `scored`. Five score parts kept as columns, `lead_score` 0-100, `priority` A (top 25), B (50+), C.
- `config.yaml`: new `score` section with the owner's weights ("Balanced"). `engine/caps.py` trims by the same score.
- `run.py`: runs score after caps.
- Tests: `tests/test_score.py` (9) and a caps test; 209 in total.
- Real data: 42 leads, 25 A and 17 B, scores 61 to 88.
- Docs: WORKFLOW (stage 6, caps ranking), DECISIONS (weights, priority, caps by score), PHASES (Phase 3), README, and both records files.

## 2026-10-28: rejected.csv and the 20-row check (Phase 2 done)

- Added `engine/export.py` with `write_rejected`: `<out>/rejected.csv` with every rejected creator and its reasons; a rejection without a reason fails the run. `run.py` writes it after caps.
- `engine/verify.py`, fixes from the hand check: a "brought to you by" self-mention is not sponsorship; commercial links only from the creator's own texts; hosting platforms' social accounts are not contacts.
- Tests: `tests/test_export.py` (2) and 9 new verify tests; 199 in total.
- Real data: 42 final leads (US 25, GB 9, AU 3, CA 3, NZ 1, IE 1), all rules pass; rejected.csv has 3,257 rows.
- Docs: WORKFLOW, DECISIONS, PHASES (Phase 2 done), README, and both records files.

## 2026-10-28: Stage 5, caps

- Added `engine/caps.py`: `deduped` -> `capped` and `cap_checks`. A country above 60% is trimmed to 60% (lowest-ranked leads rejected with "cap: ..."), then every hard rule is checked: approved share, 3+ countries, largest country, English, segment.
- `run.py`: runs caps after dedupe; a failed rule is logged loudly and the run exits with code 2 after the remaining stages.
- Tests: `tests/test_caps.py`, 9 tests; 188 in total.
- Real data: 51 -> 45 leads (US 33 -> 27); all rules pass.
- Docs: WORKFLOW (stage 5, hard constraints), DECISIONS, PHASES, README, and both records files.

## 2026-10-28: Stage 4, dedupe

- Added `engine/dedupe.py`: `verified` -> `deduped`. One qualified row per creator, matched by platform ID, website domain or email (chained); the kept row has the most recent content. Duplicates stay as Rejected with the matching key and `duplicate_of`.
- Rows whose contact email is listed on 3+ shows are rejected (networks and YouTube re-upload feeds).
- `config.yaml`: new `dedupe` section (`shared_domains`, `shared_email_min_shows`). `run.py` runs dedupe after verify.
- Tests: `tests/test_dedupe.py`, 11 tests; 179 in total.
- Real data: 52 qualified -> 51 unique creators (1 re-upload feed).
- Docs: WORKFLOW (stage 4), TECH_RUNTIME, DECISIONS, PHASES, README, and both records files.

## 2026-10-28: Podcast size limit 250,000

- `config.yaml`: `verify.podcast_max_youtube_subscribers` lowered from 500,000 to 250,000 (owner's choice). Verify rerun: 52 qualified (was 54).
- Docs: WORKFLOW, DECISIONS, PHASES, MANUAL_WORK.

## 2026-10-28: Verify fixes from the volume hand check

- `engine/verify.py`:
  - shows whose website or contact email is on a broadcaster or network domain are organisations (`verify.media_domains`)
  - the LLM prompt names broadcasters, stations, networks, churches and ministries as organisations
  - a country quote that is a sentence or address is put to the LLM, which must answer that it is about the host (or the host's own business). New column `country_quote_about`
  - podcast size from the creator's linked YouTube channel (`check_podcast_size`, 1 unit per row, before the LLM); above 500,000 is rejected. New column `size_evidence`
  - the log's token count now leaves out cached answers
- `config.yaml`: `verify.podcast_max_youtube_subscribers` (500,000, pending owner review), `verify.media_domains`.
- Tests: 19 new (domains, YouTube link forms, size, country-quote answers). 168 tests in total.
- Verify rerun on the 3,299 profiles: 54 qualified (was 71); 11 of the 12 doubtful rows now rejected.
- Docs: WORKFLOW, TECH_RUNTIME, DECISIONS, PHASES, and both records files.

## 2026-10-28: Volume step

- `engine/discover.py`: `podcast_category` seeds read Podcast Index category lists (trending and recently updated, up to 1,000 English shows each). New column `newest_item_at`; podcasts whose newest episode is older than 60 days are dropped before enrich (`drop_inactive`).
- `engine/common.py`: `parallel_map` (thread pool, one SQLite connection per thread); the database now runs in WAL mode with a 60 s lock timeout.
- `engine/enrich.py`: feeds and websites are fetched 8 at a time (`enrich.workers`); results keep input order.
- `config.yaml`: `discover.category_max_results`, `discover.category_lists`, `enrich.workers`, `podcast_category` platform.
- `data/seeds.csv`: 16 category seeds added (S043-S058), pending owner review. The owner's 42 seeds are unchanged.
- Tests: category, inactive-drop and `parallel_map` tests; 149 tests in total.
- Live run on 2 categories: 3,299 candidates, 71 qualified (2.2%), 1 h 56 min, 252,461 Gemini tokens ($0). Hand check found about 12 doubtful rows; listed in PHASES.md.
- Docs: WORKFLOW, TECH_RUNTIME, DECISIONS, PHASES, README, and both records files.

## 2026-10-28: Verify done: LLM creator check

- `engine/verify.py`: creator-vs-organisation check with Gemini (`check_creator`, `apply_creator_check`), run only on rows that pass everything else. The model's quote must be found word for word in the creator's own text; organisation, unclear, unverified and failed answers are rejections with reasons. New columns: `creator_kind`, `creator_evidence`, `creator_evidence_url`.
- `engine/common.py`: `gemini_json` (cached by prompt, JSON schema, key in header, pause after uncached calls); `cached_get` can POST a JSON body and take its own timeout.
- `config.yaml`: `llm.model: gemini-3.5-flash-lite` plus timeout, pause, cache days and input size. The model choice and test results are in DECISIONS.md.
- Tests: the fake HTTP now covers POST, and every test blocks real GET and POST. 8 new creator-check tests; 145 tests in total.
- Live sample: 9 LLM answers (13,818 tokens, $0); 2 of 343 candidates qualify.
- Docs: WORKFLOW, TECH_RUNTIME, DECISIONS (model trade-off), PHASES (results, yield risk), README, and both records files.

## 2026-10-28: Stage 3, verify

- Added `engine/verify.py`: the qualification checks, each with a verbatim quote and URL, writing the `verified` table (Qualified or Rejected, all reasons kept). It covers country (6 evidence sources), language (langdetect), organisations, activity, offers, needs (own words, then observed gaps), contacts (published business channels only) and evidence age.
- `config.yaml`: added `verify` thresholds; `run.py` now runs verify after enrich.
- `engine/enrich.py`:
  - show description combines `<itunes:summary>` and `<description>`
  - reads `<podcast:location>` (new `location` column); feed cache is now `rss.v3`
  - the YouTube website must match the creator's name
- Fixes from the 20-row hand check: no country or contacts from show notes; the right-most place wins; street addresses only on contact/about pages; profile-shaped social links only; more hosting-platform email domains blocked; guest-pitch testimonials ignored; topic words no longer exclude creators.
- Tests: `tests/test_verify.py` and new enrich tests. 137 tests in total.
- Docs: WORKFLOW (stage 3, evidence rules), TECH_RUNTIME, DECISIONS, PHASES (hand check, yield), README, and both records files.

## 2026-10-28: Stage 2, enrich (Phase 1 done)

- Added `engine/enrich.py`: YouTube channel, upload and video details (size/country gate before the per-channel calls); podcast RSS (episodes, durations, owner email, transcript tag); the creator's own website (homepage, contact and about pages, robots.txt checked, big platforms never fetched). Writes the `profiles` and `content_items` tables.
- `engine/common.py`, `cached_get` gained three options:
  - `parse`: caches extracted fields instead of raw pages
  - `ok_statuses`: caches 4xx pages as "nothing there"
  - `failure_max_age_days`: remembers failed feeds and sites for 1 day
- `engine/discover.py`: candidates now carry the seed's `size_min` and `size_max`.
- `run.py` runs discover then enrich.
- `config.yaml`: added `enrich` (windows, page limits, skip domains) and `cache.enrich_max_age_days` / `cache.failure_max_age_days`.
- Fixes found in the live run:
  - episode dates were shifted by the local timezone (`mktime` changed to `timegm`)
  - one impossible date dropped a whole feed
  - pandas 3 `iterrows()` turned `None` into `NaN`
  - the parsed-feed cache is now versioned (`rss.v2`)
- Tests: `tests/test_enrich.py`; failure-cache tests in `tests/test_cache.py`; `FakeResponse` supports text responses. 69 tests in total.
- Live check: 343 candidates enriched; the rerun made 0 live calls out of 1,100 and took 3.3 s.
- Docs: WORKFLOW, TECH_RUNTIME, DECISIONS, PHASES (Phase 1 done, inspection findings), README, and both records files.

## 2026-10-27: LLM provider and sender set

- `check_apis.py` now also checks the Gemini key by listing models (0 tokens, key sent in a header). All three APIs pass.
- `config.yaml`: added `sender` (name, description, postal-address placeholder) and `llm` (provider: gemini).
- `.env.example`: `LLM_API_KEY` is now described as the Gemini key.
- Tests: Gemini check fails cleanly without a key and never puts the key in the URL.
- Docs: DECISIONS, TECH_RUNTIME, PHASES, README, and both records files.

## 2026-10-27: Stage 1, discover

- Added `engine/discover.py`: searches YouTube (channels), Podcast Index and iTunes for every active seed keyword, and writes the `candidates` table, one row per creator per platform.
- `engine/common.py`:
  - added `connect_db` (`<out>/engine.db` with the `api_cache` and `api_log` tables)
  - added `cached_get` (SQLite cache, 3 retries with backoff, keys never stored or logged)
  - added `ApiError`
  - moved `podcastindex_headers` here from `check_apis.py`
- `run.py` now runs discover. The database and logs are written inside `--out`, and a missing input file stops the run.
- `config.yaml`:
  - removed `paths`
  - added `cache` (7-day search cache) and `discover` (search sizes, iTunes store list = US)
  - set `activity.long_form_min_minutes: 20`
- Added `tests/conftest.py` (fake HTTP, network blocked in all tests), `tests/test_cache.py` and `tests/test_discover.py`.
- Recorded the decisions: need evidence, long-form = 20 minutes, `leads.csv` qualified-only, and the assignment PDF as a rules source.
- Docs: WORKFLOW (discover stage, merged assignment rules), TECH_RUNTIME, DECISIONS, PHASES, README, and both records files.

## 2026-10-27: Phase 0 done: leads.csv columns locked, API access confirmed

- `engine/common.py`: `LEADS_COLUMNS` (the 30 workbook columns, in order), plus `CHANNELS`, `PRIORITIES` and `CANDIDATE_STATUSES` from the workbook dropdowns.
- Added `check_apis.py`: one cheap live call each to YouTube and Podcast Index, printing PASS/FAIL only. Both passed on 2026-10-27.
- Added `tests/test_leads_schema.py` (re-reads the workbook) and `tests/test_check_apis.py`.
- Docs: PHASES (Phase 0 done), WORKFLOW (output format), TECH_RUNTIME, DECISIONS, README, and both records files.

## 2026-10-27: Seeds reviewed, config aligned to the Submission Workbook

- `data/seeds.csv`: corrected the owner's 42-row draft. The original is kept as `data/seeds_original.csv`.
  - Segments now use the workbook labels; `video_podcaster` is merged into `Podcaster/Video Podcaster`.
  - Platform `podcast_apple_spotify` is now `podcast`. The 8 LinkedIn and Instagram rows moved to `youtube`, and their need signals were rewritten.
  - `size_band_target` is split into `size_min` and `size_max`, blank for podcasts.
  - Need signals that could not be checked publicly (S008 "manual editing", S018 "sponsor-led") were replaced.
  - Removed "(non-clinical)" from an S034 search term.
  - Status `draft` is now `active`.
- `config.yaml`: country `UK` is now `GB`; segments use the workbook labels; added `discovery_platforms`.
- Added `tests/test_seeds.py` and updated `tests/test_setup.py`.
- Docs: WORKFLOW (seed columns, quota cost), DECISIONS, PHASES, README, and both records files.

## 2026-10-27: Phase 0 setup

- Added the repo layout: `engine/`, `tests/`, `docs/records/`.
- Added `run.py` with `--input`, `--out`, `--config` and `--refresh`. `--help` works. No stages run yet.
- Added `engine/common.py`: loads `config.yaml` and `.env`, checks required config sections, and writes one log file per run.
- Added `config.yaml` with every threshold from the brief (countries, activity, evidence age, Priority A, retries).
- Added `.env.example`, `.gitignore`, `pyproject.toml` (ruff, pytest) and pinned `requirements.txt`.
- Added docs: README, TECH_BUILD, TECH_RUNTIME, WORKFLOW, PHASES, DECISIONS, CHANGELOG, and the two records files.
- Added `tests/test_setup.py`.
