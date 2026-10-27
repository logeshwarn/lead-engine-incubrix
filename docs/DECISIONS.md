# Decisions

A short log of non-obvious choices, thresholds and trade-offs. Newest first.

| Date | Decision | Reason |
|---|---|---|
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
