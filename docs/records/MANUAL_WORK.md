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
| 2026-10-27 | Owner | Committed and pushed discover and the Gemini setup (`295980b phase 01`, `1cb765b gemini LLM`) | In sync with `origin/main` | not recorded |
| 2026-10-28 | Owner | Checked progress of the slow Phase 1 run and chose to let it finish rather than cap the sample | The full 343-candidate run completed; it showed the need for parallel fetching in Phase 5 | not recorded |
| 2026-10-28 | Owner | Started a full run on all 42 seeds in their own terminal (01:08), then stopped it during enrich | Discover finished: 6,268 candidates, 82 new YouTube searches (8,200 units). About 230 YouTube channels enriched and cached before the stop | not recorded |
| 2026-10-28 | Owner | Committed and pushed enrich (`dede66f`) | In sync with `origin/main` | not recorded |
| 2026-10-28 | Owner | Committed and pushed verify (`7a7125f`) | In sync with `origin/main` | not recorded |
| 2026-10-28 | Owner | Chose the Gemini creator check over stricter rules, and asked that the model-quality trade-off be documented | Recorded in DECISIONS.md and config.yaml | not recorded |
| 2026-10-28 | Owner | Chose "Volume first": raise discovery volume before building dedupe | Volume step built and measured; results in PHASES.md | not recorded |
| 2026-10-28 | Owner | Chose to fix the doubtful rows in verify before dedupe; asked to retry when the Gemini connection dropped mid-run | Verify fixes built; 54 qualified after the rerun | not recorded |
| 2026-10-28 | Owner | Committed the creator check, volume step and verify fixes (`c7bb6b5`) | In sync with git | not recorded |
| 2026-10-28 | Owner | Set the podcast size limit to 250,000 linked-YouTube subscribers, after reviewing the measured sizes | `config.yaml`, DECISIONS.md | not recorded |
| 2026-10-28 | Owner | Committed the size limit (`c17a748`) and asked to continue with dedupe | dedupe built | not recorded |
| 2026-10-28 | Owner | Committed dedupe (`255fe23`). Decided the caps behaviour: trim a country above 60%, then check; on a failed rule, finish the run but exit with an error | Recorded in DECISIONS.md; caps built | not recorded |
| 2026-10-28 | Owner | Committed caps (`20e34cb`) and asked to finish Phase 2 | rejected.csv and the 20-row check done | not recorded |
| 2026-10-28 | Owner | Committed Phase 2 (`796b3cb`). Chose the scoring weights ("Balanced", from 3 options) and the B/C rule (score 50+ is B) | Recorded in config.yaml and DECISIONS.md; score built | not recorded |
| 2026-10-28 | Owner | Committed score (`41e2bda`) and asked to continue with route | route built; Phase 3 done | not recorded |
| 2026-10-28 | Owner | Committed route (`98fe387`). Set the deadline: 1,000 leads by Saturday 31 Oct. Chose the compromises (honest count if short, templated messages for B leads, simpler seed test) and said "we will continue development and also fetching now! no stopping" | Full run started 21:35 in `output/full/`; development continued in parallel | not recorded |
| 2026-10-28 | Owner | Chose the seed-test accounts and channels: two Gmail accounts, LinkedIn and Instagram | `seedtest.py` built for them | not recorded |

## Pending (not done yet)

These are not entries. Each one moves to the log once it is done.

- Review the corrected `data/seeds.csv` and confirm it
- Review the 16 category seeds S043-S058 in `data/seeds.csv` (added by Claude Code)
- Commit the creator-check work, the volume step and the verify fixes
- Note: the 20-row check in PHASES.md was done by Claude Code on the engine's output. The 40-lead audit in Phase 7 is the owner's own manual work
