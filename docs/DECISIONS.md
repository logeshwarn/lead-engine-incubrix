# Decisions

A short log of non-obvious choices, thresholds and trade-offs. Newest first.

| Date | Decision | Reason |
|---|---|---|
| 2026-10-27 | iTunes is searched in the US store only (`discover.itunes_stores`), not all 7 approved-country stores. | Live test on "founder interviews podcast": all 7 stores returned the same 38 shows (0 new outside US). Searching each store would add about 174 calls and 9 minutes per full run for nothing. The setting stays configurable. |
| 2026-10-27 | Discovery searches are cached for 7 days (`cache.search_max_age_days`). | A rerun within the week costs no quota (Phase 1 rule), and a weekly rerun still finds new creators. |
| 2026-10-27 | The database and logs live in the `--out` folder (`<out>/engine.db`, `<out>/logs/`), not at fixed paths in config. | Running with a different `--out`, for example IncuBrix's own test input in the live review, cannot mix with the main run. |
| 2026-10-27 | API keys are stripped from cache keys and are never logged. Network errors are logged by type only. | The database and logs can then be shared for evidence without leaking secrets. A new key also reuses old cached results. |
| 2026-10-27 | Only network errors, 429 and 5xx are retried. 4xx errors fail at once, and YouTube `quotaExceeded` stops YouTube for the rest of the run. | Retrying a bad request or an empty quota cannot succeed and only wastes time. |
| 2026-10-27 | When discover finds a creator twice, the first hit in seed-file order wins. The `candidates` table is rebuilt from the cache each run. | Deterministic and rerunnable. Cross-platform duplicates (same creator on YouTube and as a podcast) are handled by the dedupe stage. |
| 2026-10-27 | Discover keeps every result, including agencies and brands. Filtering happens in verify. | One stage, one job. Verify has the enriched data and records the rejection reason. |
| 2026-10-27 | Every test blocks the real network (autouse fixture in `tests/conftest.py`). | Tests must never spend quota or depend on live data. |
| 2026-10-27 | **Need evidence:** both an observed gap with a link (for example no captions, long episodes with no Shorts, upload gaps) and the creator's own words count. Own words score higher. | Own words alone would yield too few leads for 1,000. Observed gaps are still real, checkable public evidence. Owner delegated the choice. |
| 2026-10-27 | **Long-form** means 20 minutes or more (`activity.long_form_min_minutes`). | Neither the brief nor the assignment defines it. 20 minutes clearly excludes Shorts and clips while including typical podcast and tutorial lengths. Owner delegated the choice. |
| 2026-10-27 | **`leads.csv` holds qualified creators only.** Rejected creators go to `rejected.csv` with a reason. | The assignment says "all required workbook fields are complete" and counts "unique qualified creators (full leads.csv)". Rejected rows would break both. Owner delegated the choice. |
| 2026-10-27 | Rules come from the brief plus the assignment PDF. Where they differ, the stricter rule wins (for example our own audit is 40 leads at 90%, while IncuBrix samples 20 at 85%). | Passing the stricter bar passes both. |
| 2026-10-27 | `leads.csv` columns and allowed values live as constants in `engine/common.py`; segments and countries stay in `config.yaml`. | The columns are a fixed contract with the workbook, not a setting. Segments and countries are also used by the caps rules. |
| 2026-10-27 | The schema test reads the `.xlsx` as zipped XML with the standard library. | Avoids adding `openpyxl` just for a test (no new dependency without approval). |
| 2026-10-27 | API access is checked by a separate `check_apis.py`, using the cheapest calls (YouTube `videoCategories.list` = 1 unit; one Podcast Index search). It prints pass/fail only. | Proves the keys without spending search quota or ever printing secrets. It sits outside `engine/` because it is not a pipeline stage. |
| 2026-10-27 | Country codes are ISO (`GB`, not the brief's `UK`). | The Submission Workbook's country dropdown uses `US, CA, GB, IE, AU, NZ, SG, Other`. |
| 2026-10-27 | Segment names are the workbook's exact labels: `Podcaster/Video Podcaster`, `YouTuber/Video-First Creator`, `Expert-Led Creator`. Video podcasters belong to the podcaster segment. | Values are copied straight into `leads.csv`, so there is no translation step to get wrong. |
| 2026-10-27 | Seeds may only use `youtube` or `podcast`. The 8 LinkedIn and Instagram seeds (S025-27, S029-31, S034, S039) were moved to YouTube, and their need signals were rewritten as signals visible on YouTube. | The brief provides no LinkedIn or Instagram discovery API, and scraping them breaks their terms. LinkedIn and Instagram can still be a *contact* channel when a creator links them publicly. |
| 2026-10-27 | Size band split into numeric `size_min` and `size_max`. Blank for podcast seeds. | Podcast Index and iTunes publish no audience count. A blank band means "not enforced", rather than a guessed size. |
| 2026-10-27 | `need_signal_to_check` is a hint for what verify should look for, never evidence. | Evidence has to be a quote and a URL from the creator's own public content (brief, no invented data). |
| 2026-10-27 | The owner's original seed draft is kept as `data/seeds_original.csv`. | It shows what the owner wrote and what the engine changed, for the manual-work disclosure. |
| 2026-10-27 | Seeds have a `status` column (`active` or `paused`). | Lets the owner switch a niche off without deleting it. Discover will read only `active` rows. |
| 2026-10-27 | The brief is kept as `docs/BRIEF.pdf`, not converted to `BRIEF.md`. | The owner supplied a PDF. One source of truth avoids two copies drifting apart. |
| 2026-10-27 | `leads.csv` columns stay unlocked until the owner adds the Submission Workbook. | The columns must match the workbook exactly, and guessing them would mean redoing the export. |
| 2026-10-27 | LLM provider choice is deferred (`LLM_API_KEY` placeholder). | The owner's decision. It is needed by Phase 4 (drafting) at the latest. |
| 2026-10-27 | All libraries named in the brief were approved at once and pinned in `requirements.txt`. | Owner approval. It avoids asking again at each phase. Any library outside the brief still needs approval. |
| 2026-10-27 | Only direct dependencies are pinned, one `requirements.txt` for app and dev tools. | The brief asks for a single pinned file. Direct pins stay readable for the live review. |
| 2026-10-27 | `output/` and `*.db` are ignored by git. | They are generated each run and may hold contact data. If the final `leads.csv` must be committed for submission, add it explicitly then. |
| 2026-10-27 | Shared helpers go in `engine/common.py`; every other `engine/` file is exactly one stage. | Keeps "one stage, one file" while not repeating config and logging code in each stage. |
| 2026-10-27 | `config.yaml` is checked for required sections at start-up. | A broken config should fail before any API quota is spent. |
