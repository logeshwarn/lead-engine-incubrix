# Decisions

A short log of non-obvious choices, thresholds and trade-offs. Newest first.

| Date | Decision | Reason |
|---|---|---|
| 2026-10-27 | The brief is kept as `docs/BRIEF.pdf`, not converted to `BRIEF.md`. | The owner supplied a PDF. One source of truth avoids two copies drifting apart. |
| 2026-10-27 | `leads.csv` columns stay unlocked until the owner adds the Submission Workbook. | The columns must match the workbook exactly, and guessing them would mean redoing the export. |
| 2026-10-27 | LLM provider choice is deferred (`LLM_API_KEY` placeholder). | The owner's decision. It is needed by Phase 4 (drafting) at the latest. |
| 2026-10-27 | All libraries named in the brief were approved at once and pinned in `requirements.txt`. | Owner approval. It avoids asking again at each phase. Any library outside the brief still needs approval. |
| 2026-10-27 | Only direct dependencies are pinned, one `requirements.txt` for app and dev tools. | The brief asks for a single pinned file. Direct pins stay readable for the live review. |
| 2026-10-27 | `output/` and `*.db` are ignored by git. | They are generated each run and may hold contact data. If the final `leads.csv` must be committed for submission, add it explicitly then. |
| 2026-10-27 | Shared helpers go in `engine/common.py`; every other `engine/` file is exactly one stage. | Keeps "one stage, one file" while not repeating config and logging code in each stage. |
| 2026-10-27 | `config.yaml` is checked for required sections at start-up. | A broken config should fail before any API quota is spent. |
