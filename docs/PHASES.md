# Phases

Status is one of: not started, in progress, done. Update this file at the end of each phase.

| Phase | Name | Status |
|---|---|---|
| 0 | Setup | done (2026-10-27) |
| 1 | Discover and enrich | done (2026-10-28) |
| 2 | Verify, dedupe, caps | done (2026-10-28) |
| 3 | Score and route | done (2026-10-28) |
| 4 | Outreach drafting | not started |
| 5 | Scale, export, refresh | not started |
| 6 | Seed test | not started |
| 7 | Hardening and handover | not started |

## Phase 0: Setup

Done when `python run.py --help` works and the docs exist.

Finished (2026-10-27):
- Repo layout: `engine/`, `tests/`, `docs/`, `docs/records/`
- `.venv` (Python 3.11.9), pinned `requirements.txt`, `.env.example`, `config.yaml`, `.gitignore`, `pyproject.toml`
- `run.py` with `--input`, `--out`, `--config`, `--refresh`; `--help` works
- `engine/common.py`: config loading with required-section check, one log file per run
- All docs from brief section 3 plus the two records files
- Tests in `tests/test_setup.py`

Also finished (2026-10-27):
- Owner added YouTube and Podcast Index keys to `.env`
- Owner added `docs/Submission_Workbook.xlsx`; `config.yaml` now uses its segment labels and ISO country codes
- Owner's seed list reviewed and corrected into `data/seeds.csv`, checked by `tests/test_seeds.py`

- `leads.csv` columns locked to the 30 columns in workbook tab `02_LEADS` (`LEADS_COLUMNS` in `engine/common.py`), with allowed channel, priority and status values. `tests/test_leads_schema.py` re-reads the workbook.
- API access confirmed on 2026-10-27 22:28 IST with `python check_apis.py`: YouTube Data API v3 PASS (HTTP 200, 1 quota unit), Podcast Index PASS (HTTP 200).

Later added (2026-10-27): the LLM provider is Google Gemini, and access was confirmed at 23:25 IST with `python check_apis.py` (HTTP 200, 0 tokens).

Open questions resolved on 2026-10-27 (see DECISIONS.md): `leads.csv` holds qualified creators only; long-form means 20 minutes or more.

## Phase 1: Discover and enrich

Done when 200 candidates are enriched with no repeat API calls on rerun, and TECH_RUNTIME.md and WORKFLOW.md are updated.

| Module | Status |
|---|---|
| `engine/discover.py` | done (2026-10-27) |
| `engine/enrich.py` | done (2026-10-28) |

Discover finished (2026-10-27):
- YouTube channel search, Podcast Index search and iTunes Search, all through the SQLite cache (`cached_get`), with 3 retries and failure logging
- `candidates` table with one row per `(platform, platform_id)`
- Small live run on 2 seed keywords: 90 unique candidates (50 YouTube, 40 podcast) in 29.5 s. The rerun made 0 live calls and took 0.1 s
- Hand check of the sample: discovery returns non-creators too, for example a podcast agency, a bank's podcast and a brand's show. Verify must exclude these (assignment section 2)
- Tests: `tests/test_cache.py`, `tests/test_discover.py`. All tests block the real network

Enrich finished (2026-10-28):
- YouTube profiles, uploads, durations and caption flags; podcast RSS feeds (episodes, owner email, transcripts); the creator's own website (homepage, contact and about pages, robots.txt respected). Every email and link keeps the URL it was found on
- `profiles` and `content_items` tables; `enrich_status` on every row
- Tests: `tests/test_enrich.py`, plus remembered-failure tests in `tests/test_cache.py`

**Phase 1 check (done-when met), on 5 seed keywords (S001, S002, S004, S011, S015):**

| Run | Result | Live calls | Time |
|---|---|---|---|
| First full run (fixed code) | 343 candidates enriched: 236 ok, 30 partial, 75 skipped, 2 failed; 1,644 recent items | all | 30.9 min |
| Rerun A (retried 18 earlier failures, now remembered) | same | 18 | 12.4 min |
| **Rerun B** | **same** | **0 of 1,100** | **3.3 s** |

YouTube quota used by all live runs to date: 247 units (+2 for `check_apis.py`).

**Hand inspection of the 266 usable profiles (ok + partial):**
- **Public email found:** 200 of 266. Some are not the creator's business address, for example a site-builder address from a website footer (godaddy.com) or a promo-service address. The source URL is kept, so verify/route can accept only addresses on the creator's own domain or labelled for business contact.
- **Country is the biggest gap:** only 11 of 266 state a country on the platform. Verify must find the country in public text (website location, address) or reject. This is the main risk to reaching 1,000.
- **Activity:** 81 have 8+ items in the last 60 days and 114 have 2+ long-form items. The 30-day rule is checked in verify.
- **Captions:** only 4% of recent YouTube videos have creator-uploaded captions (the API flag ignores auto-captions), and 18% of podcast episodes have a transcript. "No captions" will be common, so it must be worded precisely and not over-weighted in scoring.
- **Language:** mostly English, but some German, Spanish, Hindi and Urdu shows. The language check in verify is needed.
- **Non-creators** (agencies, brands, a bank) are still present, as expected. Verify excludes them.

Carried to Phase 5 (scale):
- Fetching feeds and websites one at a time takes about 5 s per candidate on a first run (343 took 31 min). 5,000+ candidates need parallel fetching. Python's built-in thread pool does this with no new dependency.
- The full discover pass over all 42 seeds takes about 8,400 YouTube units, then about 2-3 units per in-scope channel to enrich, so 2-3 days of quota for the first full run.

## Phase 2: Verify, dedupe, caps

Done when tests pass for the activity rule, dedupe, caps and missing evidence, and a hand check of 20 rows looks right.

| Module | Status |
|---|---|
| `engine/verify.py` | done (2026-10-28) |
| volume step (discover categories, parallel enrich) | done (2026-10-28) |
| verify fixes from the volume hand check | done (2026-10-28) |
| `engine/dedupe.py` | done (2026-10-28) |
| `engine/caps.py` | done (2026-10-28) |

Verify built (2026-10-28):
- All checks with a quote and URL; reasons kept for every rejection; `verified` table
- Tests: `tests/test_verify.py` covers the activity rule, missing evidence, country sources, language, organisations, offers, needs, contacts and the guest/sponsor cases
- Enrich fixes found while building verify:
  - podcast descriptions were empty for 26% of shows (feedparser stores `<description>` as `subtitle`)
  - `<podcast:location>` is now read
  - the YouTube "website" must match the creator's name, not just be the first link (it was a sponsor's)

**Hand check of 20 rows (2026-10-28), on the 343-candidate sample:**
- **First pass:** 13 qualified, but about half rested on wrong evidence:
  - a guest's company location used as the country (2)
  - "Birmingham, Alabama" read as GB
  - a sponsor's address used as the business email
  - a guest's email accepted
  - share links counted as social profiles
  - a hosting-platform email accepted
  
  All were fixed with rules and tests.
- **Second pass:** 9 qualified, and all 9 have correct country, offer, need and contact evidence. But **5 of the 9 are organisations rather than creators**: a trading-education company, two marketing agencies, a B2B publication and a training provider. Rules cannot separate these from creator-led businesses (Duct Tape Marketing, Authority Hacker), which use the same words ("our team", "case studies"). **Decision needed:** add the brief's LLM classification step (Gemini, quote-checked) for creator vs organisation, or accept stricter rules that also drop real creators.
- The 7 rejected rows checked by hand were all rejected for the right reasons.

**Yield on the sample:** 343 candidates → 266 usable → 119 active → 9 qualified (about 3% of usable, fewer once organisations are removed). The biggest filters are country evidence (most creators never state a location publicly) and activity (55% of shows posted nothing in 60 days). The full seed set (6,268 candidates) would give roughly 150-200 leads at this rate, so reaching 1,000 needs more volume. Options are listed for the owner in the module report.

**Creator check added (2026-10-28, owner chose the LLM option):** Gemini `gemini-3.5-flash-lite`, free tier, quote-checked. On the 9 rows that passed everything else:
- 2 answered creator: Duct Tape Marketing (John Jantsch), Fit Womens Weekly (Kindal Boyle)
- 7 answered organisation: Wealth Within, Authority Hacker, Exposure Ninja, Patient Care Marketing Pros, B2B Marketing, Trinity, Fitness Education Online

All 9 quotes were found word for word in the creator's own text. Hand check: 7 clearly right; Authority Hacker (founder-led brand) and Trinity (coaching company) are borderline and were judged strictly, which is the safe side for the audit. Cost: 13,818 tokens, $0.

**Yield after the creator check: 2 qualified of 343 candidates (0.6%).** At this rate the full 42-seed set (6,268 candidates) gives about 40 leads. The business and marketing podcast niches are dominated by company and agency shows. Reaching 1,000 needs much more volume and better-targeted seeds. That is the main project risk now.

**Volume step (2026-10-28, owner chose volume before dedupe):** Podcast Index category lists, dropping inactive shows in discover, and parallel feed/website fetching (8 workers). Measured run on 2 category seeds, S043 Fitness and S046 Self-Improvement:
- discover: 4 Podcast Index calls, 3,999 hits, **3,299 unique candidates**, 0 inactive (every show in these lists has a recent episode). 5 seconds.
- enrich: 3,299 feeds (2 failed), 4,224 website pages and 1,989 robots.txt files fetched. **96 minutes**, about 1.75 s per show with 8 workers (about 5 s per show before).
- verify: 166 Gemini answers, 252,461 tokens, $0. 20 minutes, most of it the 4 s pause between free-tier calls.
- Total run: 6,950 s (1 h 56 min). 10 fetch errors (SSL, timeouts, HTTP 5xx), all logged and the rows skipped.
- **71 qualified of 3,299 (2.2%, up from 0.6%).** Fitness 45, Self-Improvement 26. Countries: US 49, GB 12, AU 4, CA 4, NZ 1, IE 1. Needs: captions 61, repurposing 9, consistency 1.
- Top rejections: country not evidenced 2,628 (80%), no public commercial evidence 259, "News" in name 54, not active 52, no need evidence 29. The LLM answered organisation for 94 rows and unclear for 1.

**Hand check of all 71 qualified rows (Claude Code, on the engine's output):** about 59 look right. About 12 are doubtful:
- **Country quote about someone else** (5): the location phrase came from a team or company paragraph on the about page, not the host. Send Me To Sleep (the studio's headquarters), Finding Freedom (a co-founder), The Nourished Chat (a staff coach), Let's Talk Mental Health (a guest or partner), Storied: San Francisco (a contributing photographer). The country is probably still right in most cases, but the quote does not prove it.
- **Broadcasters or ministries that passed the creator check** (4): James O'Brien (Global radio), The Steve Sommers Overnight Drive (radio station), Point Taken (WTMJ Radio), Conversations with John & Lisa Bevere (Messenger International).
- **Probably above the size band** (3): Next Question with Katie Couric, The Human Upgrade (Dave Asprey), In the Booth with Babish. Podcasts have no public follower count, so the size band is never applied to them.
- Off-niche but real creators: the Self-Improvement lists include Sims, film, cricket and game-music shows. They pass because the brief does not require a niche match beyond "relevant creator".

**Verify fixes for the doubtful rows (2026-10-28, owner chose to fix verify before dedupe):** broadcaster/network domains, the LLM judging whom a country sentence or address is about, and podcast size from the linked YouTube channel. Verify rerun on the same 3,299 profiles (no new discovery or enrich):
- **54 qualified (1.6%)**, down from 71. Fitness 35, Self-Improvement 19. US 35, GB 10, CA 4, AU 3, NZ 1, IE 1.
- New rejections: 154 rows on a broadcaster or network domain (most were already rejected for other reasons; 42 Locked On shows), 9 above the size limit (Katie Couric 723,000, Brian Scott 921,000, Chris Van Vliet 866,000 and others), 10 country quotes about someone else or unclear.
- **All 12 doubtful rows from the hand check are now rejected except one:** Storied: San Francisco, where the LLM judged a quote about a contributing photographer to be about the host. The host does say "I moved to San Francisco", but the cited quote is the wrong one. Known miss.
- Also caught: "Moscow is a city located in northern Idaho" (a topic, not a location) on a true-crime show.
- Hand check of the final 54: the country, size and creator evidence of each row was read. Besides Storied, borderline: Oncology Today (Dr Neil Love; the address is his medical education company), The Human Upgrade (Dave Asprey, 328,000 YouTube subscribers, under the limit). Dr. John Campbell is very large on YouTube but only links to single videos, so his size is unknown and he passes.
- A first version of the country prompt counted the host's own business address as "someone else" and dropped 13 good rows (Pain Free Birth LLC, Fit Womens Weekly, The Mold Doctor and others). Fixed by naming the host's own business, practice or show as the host. Logged in DECISIONS.md.

**Size limit lowered to 250,000 (owner, 2026-10-28):** verify rerun from cache, no new API calls: **52 qualified** (US 33, GB 10, CA 4, AU 3, NZ 1, IE 1). Newly rejected for size: The Human Upgrade (328,000) and TestGuild (451,000). Eight Christian radio shows also link the same Moody Church Media channel (286,000), and TAKEN TV links one with 271,000; all 9 are now rejected for size before the LLM is asked; none of them had qualified.

**What this means for 1,000 leads:** After the verify fixes 1.6% of category candidates qualify, so about 62,000 candidates are needed, roughly 19 category seeds at about 1,650 candidates each. At 1.75 s per show that is about 22 hours of enrich (cached after the first time), and about 1,600 Gemini calls (about 2 hours with the pause; the free daily limit must be checked). Fixing the 12 doubtful patterns will lower the rate a little. Country evidence is still the biggest filter.

**Dedupe built (2026-10-28):** on the 52 qualified rows, 0 true duplicates and 1 re-upload feed rejected (Dr. John Campbell, contact email shared by 19 shows): **51 unique creators**. Stress check with all 3,299 profiles treated as qualified: 487 rows on an email shared by 3+ shows, 107 duplicates merged; the merges checked by hand are shows of one organisation. Tests: `tests/test_dedupe.py` (11 tests: each key, chains, shared platform domains, keep order, rejected rows ignored, shared emails, rerun identical).

**Caps built (2026-10-28):** on the 51 unique creators, US was 33 (65%); 6 US leads were trimmed, leaving **45 leads: US 27 (60%), GB 9, CA 4, AU 3, NZ 1, IE 1**. All 5 rules pass. The full cached run (all stages so far) took 375 s with no new API calls. Tests: `tests/test_caps.py` (9 tests: trim to 60%, trim order, untouched mix, too few countries, approved share, language and segment, rejected rows ignored, tables written).

**`rejected.csv` built (2026-10-28)** in `engine/export.py` (the export stage, started early because the brief lists it in Phase 2): every rejected creator with all its reasons. Tests: `tests/test_export.py`.

**20-row hand check of the final set (2026-10-28, Claude Code, on the engine's stored evidence; random sample, seed 20: 12 qualified, 8 rejected):**
- All 8 rejected rows were rejected for the right reasons (country not stated, "News" in name, no offer, no contact).
- Of the 12 qualified, 7 were right with correct evidence on every check (Dr. Jockers, Heart Led Wellness, Easy Double, Dave Smith Dharma, Empowered Relationship, Weightless, Wildly Strong).
- 3 rested on wrong evidence, all fixed with rules and tests:
  - OT Coaching Confidential and The Hypnotist: "Sponsorship" was "Brought to you by [the host's own business]". Now ignored; both still qualify on their real offers ("one-on-one mentoring", "Book a consultation").
  - Stassi J Unplugged: "Membership" was another creator's Patreon in an episode note, and its X/LinkedIn/Instagram "contacts" were rss.com's own accounts. Now rejected (no offer of its own).
- 1 known LLM miss: Oncology Today is a medical-education company (Research To Practice) that Gemini called a creator. Left as is; the owner's 40-lead audit in Phase 7 measures how often this happens.
- 1 unconfirmed: Good Areas (Jarrod Kimber), country GB from "live in South London" on the show's website; the stored text does not show whose sentence it is.

**After the fixes**, the run from verify gives: 49 qualified, 49 unique after dedupe (Dr. John Campbell's re-upload feed now fails at verify: its only offer was a link in an episode note), **42 after caps: US 25 (60%), GB 9, AU 3, CA 3, NZ 1, IE 1**. All rules pass. rejected.csv: 3,257 rows. No new API calls (all Gemini answers came from the cache).

**Phase 2 is done:** tests pass for the activity rule, dedupe, caps and missing evidence, and the 20-row check found 3 rule bugs, now fixed.

## Phase 3: Score and route

Done when every lead has a best channel, a backup channel and a score, and weights are documented in DECISIONS.md.

| Module | Status |
|---|---|
| `engine/score.py` | done (2026-10-28) |
| `engine/route.py` | done (2026-10-28) |

**Score built (2026-10-28):** weights chosen by the owner ("Balanced"; DECISIONS.md). Caps now trims by the same score. On the 42 leads:
- scores 61 to 88, median 77; **25 Priority A, 17 B, 0 C**. A is 19 US, 5 GB, 1 AU.
- The spread is narrow: no lead has the need in its own words and 37 of 42 are "no transcripts" (15 points), so order comes mostly from volume, offer type and contacts.
- Caps trimmed the 7 lowest-scoring US leads (54 to 66); the US leads kept in A score 75 to 88.
- Known doubtful rows rank high: Oncology Today (a company the LLM called a creator) is 3rd, and Storied: San Francisco (country quote about a photographer) is in A. The score trusts verify, so the owner's Phase 7 audit should start with the A list.
- Tests: `tests/test_score.py` (9 tests: each part, full marks, A/B/C split, stable ties, table) and a caps test that the lowest score is trimmed first.

**Route built (2026-10-28):** every lead has a best and a backup channel with its URL and evidence URL. Requiring a backup moved into verify's "reachable" check, so the numbers changed: **49 -> 44 qualified, 40 final leads: US 24 (60%), GB 9, AU 3, CA 3, NZ 1; 25 A, 15 B**. IE is gone (Easy Double has one email only); 5 countries still pass.
- Best: Email 37, Contact form 3. Backup: Contact form 26, Instagram 8, LinkedIn 3, guest-pitch page 2, a second email 1.
- Hand check of all 40 pairs: emails on the creator's own domain were picked over a network producer's and a sales desk's address; `info@mysite.com` (a template placeholder) was skipped; Storied's backup is the show's own Instagram, not a contributor's.
- Doubtful: Good Areas' backup is the only Instagram its site links (`ishitk86`), which may not be Jarrod Kimber's. Dave Smith Dharma has two gmail addresses and nothing says which is his; the engine takes the first alphabetically.
- Tests: `tests/test_route.py` (12 tests) and a verify test for the missing backup.

**Phase 3 is done:** every lead has a best channel, a backup channel and a score, and the weights are in DECISIONS.md.

Open questions for later phases:
- Phase 4: drafting needs the LLM again; Priority A sequences use the A list above.
