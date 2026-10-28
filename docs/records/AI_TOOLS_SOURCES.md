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
