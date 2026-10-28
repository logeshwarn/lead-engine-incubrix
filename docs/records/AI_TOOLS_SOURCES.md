# AI tools and sources

Every AI tool and outside source used to build the project, as it happens. Dated, factual, and never back-filled or estimated.

## AI tools

| Date | Tool | Model or version | Used by | Used for |
|---|---|---|---|---|
| 2026-10-27 | Claude Code (Claude desktop app, Code tab) | Claude Opus 5.5 | engine build | Phase 0: read the brief, created the repo layout, `run.py`, `engine/common.py`, config files, tests and all docs |
| 2026-10-27 | Claude web (claude.ai) | not recorded (owner to fill in) | owner | drafted the 42-row seed list, now `data/seeds_original.csv` |
| 2026-10-27 | Claude Code (Claude desktop app, Code tab) | Claude Opus 5.5 | engine build | reviewed and corrected the seed list (`data/seeds.csv`), read the Submission Workbook's columns and dropdowns, aligned `config.yaml`, added `tests/test_seeds.py` |
| 2026-10-27 | Claude Code (Claude desktop app, Code tab) | Claude Opus 5.5 | engine build | locked `leads.csv` columns to the workbook, wrote `check_apis.py` and its tests, ran the live API check |
| 2026-10-27 | Claude Code (Claude desktop app, Code tab) | Claude Opus 5.5 | engine build | analysed the qualification rules and wrote the plan; chose the four delegated decisions; built `engine/discover.py`, `cached_get` and their tests; ran the small live discover and the iTunes store comparison |

| 2026-10-27 to 2026-10-28 | Claude Code (Claude desktop app, Code tab) | Claude Opus 5.5 | engine build | built `engine/enrich.py`, the cache extensions and their tests; ran the live Phase 1 check and the hand inspection; found and fixed the timezone, bad-date, NaN and repeat-failure bugs |
| 2026-10-28 | Claude Code (Claude desktop app, Code tab) | Claude Opus 5.5 | engine build | built `engine/verify.py` and its tests; ran verify on the 343-candidate sample; did the 20-row check of the engine's output and fixed the evidence rules it exposed; fixed the enrich feed-description and website bugs |
| 2026-10-28 | Claude Code (Claude desktop app, Code tab) | Claude Opus 5.5 | engine build | tested which free Gemini models answer; built the LLM creator check, `gemini_json` and their tests; checked the 9 LLM answers by hand |
| 2026-10-28 | Google Gemini API (runtime, inside the engine) | `gemini-3.5-flash-lite`, free tier | the engine | creator vs organisation in verify: 9 calls, 13,818 tokens, $0. Every answer's quote is checked against the creator's own text |
| 2026-10-28 | Claude Code (Claude desktop app, Code tab) | Claude Opus 5.5 | engine build | built the volume step (category discovery, inactive drop, parallel fetching) and its tests; measured the search limits; ran the 2-category live run and hand-checked all 71 qualified rows |
| 2026-10-28 | Google Gemini API (runtime, inside the engine) | `gemini-3.5-flash-lite`, free tier | the engine | creator vs organisation on the 2-category run: 164 uncached calls plus 2 from cache, 252,461 tokens, $0 |
| 2026-10-28 | Claude Code (Claude desktop app, Code tab) | Claude Opus 5.5 | engine build | built the verify fixes (broadcaster domains, country-quote check, podcast size) and their tests; reran verify 4 times; hand-checked the 71 and then the 54 qualified rows |
| 2026-10-28 | Claude Code (Claude desktop app, Code tab) | Claude Opus 5.5 | engine build | built `engine/dedupe.py` and its tests; ran it on the stored data and a stress check over all 3,299 profiles; found the re-upload feeds and the missing platform domains; no API calls |
| 2026-10-28 | Claude Code (Claude desktop app, Code tab) | Claude Opus 5.5 | engine build | built `engine/caps.py`, its tests and the run.py exit code; ran the full cached pipeline (no new API calls) |
| 2026-10-28 | Claude Code (Claude desktop app, Code tab) | Claude Opus 5.5 | engine build | built rejected.csv (`engine/export.py`) and its tests; did the 20-row hand check on stored evidence and fixed the 3 rule bugs it found; reran verify to export from cache (no new API calls) |
| 2026-10-28 | Claude Code (Claude desktop app, Code tab) | Claude Opus 5.5 | engine build | measured what separates the 42 leads; proposed 3 weight sets; built `engine/score.py`, caps-by-score and their tests; ran dedupe to score on stored data (no API calls) |
| 2026-10-28 | Claude Code (Claude desktop app, Code tab) | Claude Opus 5.5 | engine build | read the assignment's channel rules; built `engine/route.py`, the backup requirement in verify and their tests; hand-checked all 40 channel pairs; reran verify to route from cache (no new API calls) |
| 2026-10-28 | Claude Code (Claude desktop app, Code tab) | Claude Opus 5.5 | engine build | deadline night: built the linked-YouTube country check, Apple chart discovery, parallel YouTube enrich, `engine/draft.py`, the full `engine/export.py`, `--refresh`, `--merge-cache` and their tests; launched and monitored the full run |
| 2026-10-28 | Google Gemini API (runtime, inside the engine) | `gemini-3.5-flash-lite`, free tier | the engine | 4 verify reruns for the fixes: 290 uncached calls (2 more failed on a dropped connection), 200 from cache, $0. Tokens: 98,781, 238,406 and 6,530 on three of the reruns; the fourth was logged with cached answers included (236,183), a log bug fixed in the same module, so its own figure is not known exactly |
| 2026-10-28 | Claude Code (Claude desktop app, Code tab) | Claude Opus 5.5 | engine build | drafted `docs/LAUNCH_KIT.md` and `docs/WORKBOOK_TEXT.md` from the assignment PDF, the workbook tabs and the 40-lead run |

## Sources

| Date | Source | Used for |
|---|---|---|
| 2026-10-27 | `docs/BRIEF.pdf` (supplied by the owner) | requirements, thresholds, tech stack, phases |
| 2026-10-27 | PyPI (via `pip install`) | installed the approved libraries; versions pinned in `requirements.txt` |
| 2026-10-27 | YouTube Data API v3 (`videoCategories.list`, 1 call, 1 quota unit) | access check only; no creator data collected |
| 2026-10-27 | Podcast Index API (`search/byterm`, 1 call) | access check only; no creator data collected |
| 2026-10-27 | `docs/Submission_Workbook.xlsx` (supplied by the owner) | `leads.csv` columns; allowed values for segment, country (ISO, `GB`), channels and priority |
| 2026-10-27 | `docs/IncuBrix_2027_Growth_Engineer_Option_1_Lead_Generation_and_Outreach.pdf` (supplied by the owner) | qualification rules, exclusions (agencies, brands and others), platform-rule and sender rules, audit targets |
| 2026-10-27 | YouTube `search.list` (1 live call, 100 quota units), Podcast Index `search/byterm` (1 call), iTunes Search (7 calls, one per approved store) | small live discover on "video podcast business interviews" and "founder interviews podcast": 90 unique candidates. The rerun was all cache hits |
| 2026-10-27 | Google Gemini API (`models` list, 1 call, 0 tokens) | access check only; no content generated |
| 2026-10-27 | YouTube, Podcast Index and iTunes (1 accidental call each, with dummy keys `yt` / `pk`) | a test bug ran discover once before the fake HTTP layer was installed. The owner's keys and quota were not used; results went to a temporary test database only. Fixed, and all tests now block the network |
| 2026-10-27 to 2026-10-28 | Phase 1 live run on 5 seed keywords (S001, S002, S004, S011, S015). YouTube API: 1 more `search.list` (100 units), 2 `channels.list`, 25 `playlistItems.list`, 20 `videos.list` (47 units). Podcast Index: 2 more searches. iTunes: 2 more searches | 343 candidates discovered and enriched. YouTube quota used by all live runs to date: 247 units |
| 2026-10-27 to 2026-10-28 | Public podcast RSS feeds (243 shows; 474 live fetches, because the feeds were read again after the timezone fix) | episodes, durations, owner emails, transcript tags |
| 2026-10-27 to 2026-10-28 | Public creator websites: 249 robots.txt and 409 page fetches (homepage, contact, about), robots.txt respected | contact emails, links and page text, each kept with its source URL |
| 2026-10-28 | Public podcast RSS feeds (243 shows, read again for the `rss.v3` fix) and a few creator websites (new YouTube website choices) | show descriptions, `podcast:location` tags; no new API quota used |
| 2026-10-28 | Google Gemini API model tests (7 tiny requests of about 14-146 tokens to 6 models; several timed out or returned 503/404) | chose a model the free tier actually serves; results in DECISIONS.md |
| 2026-10-28 | Google Gemini API (1 accidental call from a test, a few hundred tokens, owner's free key) | before the fix, the test suite blocked GET but not POST, so one verify test reached Gemini. It used a temporary test database only. Fixed: every test now blocks real GET and POST |
| 2026-10-28 | Podcast Index API (`podcasts/trending` and `recent/feeds`, 4 calls, categories Fitness and Self-Improvement) | 3,299 candidates for the volume run. Earlier the same day: test calls to compare keyword search and category lists (counts in DECISIONS.md) |
| 2026-10-28 | Public podcast RSS feeds (3,293 fetched, 2 failed) and creator websites (4,224 pages and 1,989 robots.txt fetched, robots.txt respected; 8 page and 61 robots.txt failures) | episodes, descriptions, contacts and page text for the 3,299 volume-run candidates |
| 2026-10-28 | YouTube Data API v3 (`channels.list`, 88 calls, 88 units) | size of otherwise-qualified podcasts from the creator's linked YouTube channel |
| 2026-10-28 | YouTube Data API v3 (`channels.list`, 147 calls, 147 units) | planning for the Saturday deadline: the stated country of the YouTube channels linked by the 263 shows rejected only for missing country. 104 state an approved country (US 88, GB 9, CA 5, AU 1, NZ 1), 28 state none, 8 links did not resolve. Same request as verify's size check, so it is cached for the next run |
| 2026-10-28 | Apple podcast charts and iTunes Lookup API (1 test call to each chart endpoint; then wave 2 made 23 chart and 46 lookup calls before it was stopped as redundant) | testing the chart source and starting non-US discovery; wave 2's results are in `output/wave2/` and are repeated by the full run |
