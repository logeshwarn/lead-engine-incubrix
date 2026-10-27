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

## Pending (not done yet)

These are not entries. Each one moves to the log once it is done.

- Choose the LLM provider and create its key
- Review the corrected `data/seeds.csv` and confirm it
