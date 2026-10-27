# Manual work

Work done by hand by the owner, as it happens: decisions, account setup, hand checks and audits. Dated and factual, and never estimated or back-filled. The Submission Workbook asks for "what and how much", so fill in **Time spent** yourself. It stays "not recorded" until you do.

## Log

| Date | Who | What | Result | Time spent |
|---|---|---|---|---|
| 2026-10-27 | Owner | Answered Phase 0 setup questions | Approved the brief's library list; deferred the LLM choice; agreed to add the Submission Workbook | not recorded |
| 2026-10-27 | Owner | Created a YouTube Data API v3 key and a Podcast Index key and secret, and put them in `.env` | All three keys are set in `.env` (values not read). Access has not been tested by the engine yet | not recorded |
| 2026-10-27 | Owner | Asked for Phase 0 to be finished: lock the columns and run the live API check | `check_apis.py` run at 22:28 IST: YouTube PASS, Podcast Index PASS | not recorded |
| 2026-10-27 | Owner | Initialised git and made the first commit (`b193818`, Phase 0 files) | `.env` is not in the commit | not recorded |
| 2026-10-27 | Owner | Added `docs/Submission_Workbook.xlsx` (file dated 2026-10-25) | Gives the 30 `leads.csv` columns and the allowed segment, country, channel and priority values | not recorded |
| 2026-10-27 | Owner | Drafted the seed list with Claude web (claude.ai) and moved it to `data/seeds.csv` | 42 rows. The original is kept as `data/seeds_original.csv`; Claude Code corrected it (see CHANGELOG) | not recorded |
| 2026-10-27 | Owner | Shared a screenshot of the qualification rules and asked for an analysis and plan | Plan written; the rules were merged into `docs/WORKFLOW.md` | not recorded |
| 2026-10-27 | Owner | Added the assignment `docs/IncuBrix_2027_Growth_Engineer_Option_1_Lead_Generation_and_Outreach.pdf` | Used as a rules source alongside the brief | not recorded |
| 2026-10-27 | Owner | Committed and pushed Phase 0 (`1a50bc1 phase 0`) | In sync with `origin/main`; `.env` not tracked | not recorded |
| 2026-10-27 | Owner | Delegated four open decisions to Claude Code ("choose the best") | Need evidence = observed gap or own words; long-form = 20 min; `leads.csv` qualified-only; assignment PDF as rules source (DECISIONS.md) | not recorded |

| 2026-10-27 | Owner | Created a Google Gemini API key (AI Studio) and put it in `.env` as `LLM_API_KEY` | `check_apis.py` at 23:25 IST: Gemini PASS (HTTP 200, 0 tokens) | not recorded |
| 2026-10-27 | Owner | Gave the sender identity for outreach: "Logeshwaran, final year IT student at TCE" | Saved in `config.yaml` (`sender`) | not recorded |

## Pending (not done yet)

These are not entries. Each one moves to the log once it is done.

- Review the corrected `data/seeds.csv` and confirm it
