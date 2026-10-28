# App workflow

Update this file when a stage or one of its rules changes.

Each stage is one file in `engine/`. It reads a table and writes a table, so it can be run on its own. Stage tables live in SQLite (`<out>/engine.db`), so a crashed run resumes from the last finished stage.

| # | Stage | File | Input | Output | Status |
|---|---|---|---|---|---|
| 1 | discover | `engine/discover.py` | `data/seeds.csv` | `candidates` table (platform ID, URL, source, query) | **built** |
| 2 | enrich | `engine/enrich.py` | `candidates` | `profiles` and `content_items` tables: profile, recent uploads, links, public contact info (cached) | **built** |
| 3 | verify | `engine/verify.py` | `profiles`, `content_items` | `verified` table: every check with an evidence quote and URL; Qualified or Rejected with reasons (export writes rejects to `rejected.csv`) | **built** |
| 4 | dedupe | `engine/dedupe.py` | verified | one row per creator (platform ID, domain, email) | not built |
| 5 | caps | `engine/caps.py` | deduped | country and segment rules enforced | not built |
| 6 | score | `engine/score.py` | capped | score from 0 to 100; top 25 flagged Priority A | not built |
| 7 | route | `engine/route.py` | scored | best channel and backup channel | not built |
| 8 | draft | `engine/draft.py` | routed | first message (+ 2 follow-ups for Priority A), opt-out included | not built |
| 9 | export | `engine/export.py` | drafted | `leads.csv`, `outreach/`, `rejected.csv`, `run_report.md` | not built |

Shared helpers live in `engine/common.py`:
- config loading and one log file per run
- the SQLite connection
- `cached_get`: every API call goes through the cache, with retries
- the `leads.csv` schema

`run.py` runs the built stages in order.

## Seeds (`data/seeds.csv`)

Each row is a niche to search, not a lead. `tests/test_seeds.py` checks the file.

| Column | Meaning |
|---|---|
| `seed_id` | unique ID, for example `S001` |
| `segment` | one of the three workbook segment labels in `config.yaml` |
| `niche` | short label, used for segment and country mix reporting |
| `primary_platform` | `youtube`, `podcast` (keyword search), or `podcast_category` (the keyword is a Podcast Index category name, e.g. `Fitness`; returns active English shows from the category's trending and recently updated lists) |
| `discovery_keywords` | search terms separated by `;`. Each YouTube term costs one `search.list` call (100 units). No term may repeat |
| `need_signal_to_check` | hint for verify about which need to look for. Never used as evidence |
| `size_min`, `size_max` | subscriber range for YouTube seeds. Blank for podcasts (no public audience count) |
| `status` | `active` (searched) or `paused` (skipped) |

The current file has 42 seeds. One uncached pass makes:
- 84 YouTube searches, about 8,400 quota units
- 29 Podcast Index calls
- 29 iTunes calls

## Stage 1: discover

- **Input:** active rows of the seeds file.
- **Searches per keyword:**
  - YouTube seeds: one `search.list` with `type=channel`, 50 results, English relevance.
  - Podcast seeds: one Podcast Index `search/byterm` (100 results), then one iTunes Search per store in `discover.itunes_stores` (default US, 50 results).
- **Output:** the `candidates` table. One row per `(platform, platform_id)`:

  | Column | Meaning |
  |---|---|
  | `platform` | `youtube` or `podcast` |
  | `platform_id` | YouTube channel ID (`UC...`), or `itunes:<id>`, or `podcastindex:<id>` when the show has no iTunes ID. Both directories share the iTunes ID, so a show found in both gets one row |
  | `name`, `url`, `description`, `website`, `feed_url`, `language` | as the source returned them. Blank when the source does not give them, never filled in |
  | `itunes_store_country` | the Apple store that listed the show. A hint, not the creator's country |
  | `source`, `query`, `seed_id`, `segment`, `niche` | where the row came from, for tracing evidence |
  | `discovered_at` | date (UTC) |

- **Category seeds** (`podcast_category`): two Podcast Index calls per category, "trending" and "recently updated" (`discover.category_lists`), up to 1,000 English shows each. Every show returned has a recent episode. Keyword search stops at 60 results, so categories are the main volume source.
- **Inactive shows dropped here:** a podcast whose newest episode (as Podcast Index or Apple reports it, column `newest_item_at`) is older than 60 days is removed before enrich, because it can never pass "active". Shows with no reported date are kept and judged by verify. The count dropped is in the log.
- **Duplicates:** when the same creator is found by several keywords or sources, the first hit is kept, in seed-file order.
- **Rerunnable:** the table is rebuilt from the cache each run. A rerun inside the cache window (`cache.search_max_age_days`, 7 days) makes no API calls. Results older than that are fetched again, so a weekly rerun picks up new creators.
- **Not judged here:** discover keeps everything it finds, including agencies and brands. Verify removes them.

Measured on 2026-10-27, with 1 YouTube term and 1 podcast term (S011, S001):
- 90 unique candidates (50 YouTube, 40 podcast) in 29.5 s
- the rerun took 0.1 s with 0 live calls

## Stage 2: enrich

- **Input:** the `candidates` table.
- **YouTube** (about 2-3 quota units per channel):
  1. `channels.list` in batches of 50 (1 unit per batch) gives the title, handle, description, stated country, language, subscribers (blank when hidden), video count and uploads playlist.
  2. If the channel is outside its seed's subscriber band, states a non-approved country, or has no uploads, it is marked `skipped: ...` and steps 3 and 4 are not run. That saves quota for channels that can qualify.
  3. `playlistItems.list` reads the last 50 uploads (1 unit), giving the date of the last upload.
  4. `videos.list` covers the uploads from the last 60 days (1 unit), giving each one's title, URL, date, duration, caption flag and description.
- **Podcasts:** the show's own RSS feed (feedparser) gives:
  - title, language, website and episode count
  - the **owner email the show publishes in its feed** (`itunes:owner`)
  - for episodes from the last 60 days: date, duration, transcript tag (counts as captions) and show notes
- **Creator website** (both platforms):
  1. The homepage is fetched. For YouTube this is the first non-platform link in the channel description; for podcasts it is the feed's website link.
  2. Then the first same-site link containing "contact", and the first containing "about".
  3. `robots.txt` is checked first. If it disallows us, or cannot be read (no answer), the site is not fetched. A missing `robots.txt` (4xx) means allowed.
  4. Domains in `enrich.skip_domains` are never fetched, because their terms forbid scraping or they are not the creator's own site (YouTube, Instagram, X, TikTok, LinkedIn, Facebook, Apple, Spotify, Linktree, Patreon and others). Their links are still recorded.
- **Emails and links:** only addresses and links **written in public text**: the channel description, video descriptions, show notes, the feed owner field, website text and `mailto:` links. Each one keeps the URL it was found on, for evidence. Nothing is constructed or guessed. Image names like `logo@2x.png` and `@example.com` addresses are dropped.
- **Output:**
  - `profiles`: one row per candidate, with `emails`, `links` and `pages` stored as JSON.
  - `content_items`: recent uploads or episodes.
  - `enrich_status` on each profile:
    - `ok`
    - `partial: <what failed>`, for example the website was blocked by robots.txt
    - `skipped: <reason>`, for example size or country
    - `failed: <reason>`, for example no feed URL, feed error, or quota used up
- **Parallel fetching:** feeds and websites are fetched 8 at a time (`enrich.workers`), each thread with its own database connection (SQLite in WAL mode). Results are put back in input order, so a rerun gives the same tables. YouTube stays one call at a time, because it is quota-bound, not slow.
- **Failure handling:** a failed call marks the row and is logged; the run continues. If the YouTube quota runs out, the remaining YouTube rows are marked `failed: quota used up`, and the next run resumes from the cache.
- **Rerunnable:** everything goes through the cache for 7 days (`cache.enrich_max_age_days`). Both tables are rebuilt each run.
  - Missing pages (4xx) are cached too.
  - Feeds, websites and robots.txt that failed (timeouts, SSL errors, 5xx) are **remembered for 1 day** (`cache.failure_max_age_days`), so a same-day rerun skips them instantly instead of waiting through the timeouts again.
  - Measured on 2026-10-28 with 343 candidates: the rerun made 0 live calls and took 3.3 s.

## Stage 3: verify

- **Input:** `profiles` and `content_items`.
- **Output:** the `verified` table, one row per profile. Column names follow the workbook where they match (`country_iso2`, `content_count_30d`, `monetization_signal`, `incubrix_need`, `checked_date`, `candidate_status`, `rejection_reason` and others).
- **Rule:** a check passes only with evidence: a verbatim quote (or a count over public items) plus the URL where it can be seen. Every failed check adds a reason, and all reasons are kept, separated by `; `. Rows that enrich skipped or failed are rejected with that reason.
- **Whose words count:** facts about the creator (country, contact details, social profiles) come only from **the creator's own texts**: the channel or show description and their own website. Episode and video notes often describe guests and sponsors, so they never count for these. Offers (a sponsor read) and needs can come from episodes, because those belong to the show.

| Check | How it passes | Evidence columns |
|---|---|---|
| 1 Real and relevant | approved segment; stable ID and profile URL; not an organisation (rules, then the LLM creator check below); country evidenced and approved; at least 60% of recent items detected as English (`verify.english_min_share`) | `country_iso2`, `country_evidence`, `country_evidence_url`, `english_share` |
| 2 Active | 8+ items in 30 days, or 2+ items of 20+ minutes in 60 days | `content_count_30d`, `longform_count_60d`, `last_content_date`, `recent_content_url` |
| 3 Commercial | offer wording in show notes, description or site (sponsor read, promo code, affiliate disclosure, "work with me", "our course", "join the membership", "support the show", "become a sponsor" and others), or a link to an offer platform (Patreon, Kajabi, Calendly and others). Topics such as "Protein Masterclass" in a title do not count | `monetization_signal`, `monetization_evidence`, `monetization_evidence_url` |
| 4 Needs IncuBrix | the creator's own words first ("hiring an editor", "sorry for the delay", "on hiatus"); otherwise an observed gap: no creator-uploaded captions or transcripts on every one of 3+ recent items (only when the status of every item is known); long videos and no Shorts; long episodes and no YouTube or TikTok link (only when we read their website); or a 21+ day gap between uploads | `incubrix_need`, `need_kind`, `need_evidence`, `need_evidence_url` |
| 5 Reachable | creator active in the last 60 days **and** at least one checkable business channel: an email (on their own domain, labelled for business, on their contact page, or the show's RSS contact; never a hosting-platform or no-reply address, never one seen only in show notes), their contact page, or a guest-pitch page. Social profiles are recorded but cannot pass alone, because their activity cannot be checked without reading the platform | `contacts` (JSON, each with `evidence_url` and a note) |
| 6 Personalisable | a recent item with a title and link to cite. The episode link is used, or the show page when the episode has none. The message itself is checked in draft | `recent_content_title`, `recent_content_url` |
| 7 Fresh evidence | profile checked within 30 days. Uniqueness is checked by dedupe | `checked_date` |

**Country evidence**, strongest first:
1. country stated on the YouTube channel
2. the creator's `<podcast:location>` feed tag
3. a postal address (US "City, ST 12345", UK, Canadian or Australian postcode), but only on a contact or about page or in the description, because a homepage can list an event venue
4. a phone prefix (+44, +353, +61, +64, +65; +1 is skipped because it's shared by US and CA)
5. a sentence placing the creator: "based in", "located in", "X-based", or "we are from" (with a subject, so "lessons from London" does not count). When several places appear, the right-most wins: "Birmingham, Alabama" is US
6. last, the website's country domain (`.uk`, `.ca`, `.ie`, `.au`, `.nz`, `.sg`), labelled as such in the evidence

A sentence or address (4-5 above, and street addresses) can describe someone other than the host: a staff coach, a co-founder, an agent, a parent company, or the topic ("Moscow is a city located in northern Idaho"). So the LLM creator check is also given that quote and answers whom it is about (`country_quote_about`): `host` (the host, or the host's own business, practice or show), `someone else`, or `unclear`. Anything but `host` is a rejection ("country not evidenced: ..."). The platform country, the feed location tag and the country domain are not asked about, because they describe the show itself.

**Organisations excluded, in two steps:**
1. **Rules:** names that are an organisation's own title ("… Podcast Network", "News", "Clips", "Magazine", "Radio Station" and others), or descriptions where the account speaks as one ("we are a digital agency"). Topic words do not exclude: "Smart Agency Masterclass" and "Network Marketing" pass.
   - a show whose website or contact email is on a broadcaster's or podcast network's domain (`verify.media_domains`: LBC/Global, Vox Media, iHeart, Audacy, SiriusXM, BBC, Locked On and others) is that company's programme, even with a named presenter. Hosting platforms (Libsyn, Spreaker, Art19) are not on the list
2. **LLM creator check** (`check_creator`): runs only on rows that pass every other check. Gemini (`llm.model`) reads the name, description and website text and answers `creator`, `organisation` or `unclear`, with a quote. The code then checks the quote appears word for word in the creator's own text:
   - the prompt says a radio or TV station's, broadcaster's, media company's, network's, church's or ministry's programme is `organisation` even with a named presenter
   - only `creator` with a found quote passes
   - `organisation`, `unclear`, a quote that isn't found ("unverified"), and a failed call are all rejections with the reason
   - after 2 failed calls in a row, the rest of the run skips the check ("not run"), and the next run retries
   - answers are cached by prompt for 30 days
   - evidence columns: `creator_kind`, `creator_evidence`, `creator_evidence_url`

**Podcast size** (`check_podcast_size`): podcast directories publish no audience count, so the size of a podcast comes from the creator's own YouTube channel, when their description or website links to one (`/@handle`, `/channel/UC…`, `/user/…`, `/c/…`; watch and playlist links are ignored). One `channels.list` call (1 unit, cached) on rows that pass every other check, before the LLM. Above `verify.podcast_max_youtube_subscribers` (500,000) is a rejection; the count and link are kept in `followers_or_subscribers` and `size_evidence`. No link, a hidden count or a failed call is not a reason.

## Output format (`leads.csv`)

`leads.csv` holds **qualified creators only**. Rejected creators go to `rejected.csv` with a reason. The 30 columns are locked to Submission Workbook tab `02_LEADS`, in workbook order, as `LEADS_COLUMNS` in `engine/common.py`. Allowed values:

- `creator_segment`: the 3 segments in `config.yaml`
- `country_iso2`: the approved list in `config.yaml`, or `Other`
- `best_channel` and `backup_channel`: `CHANNELS`
- `priority`: `A`, `B` or `C`
- `candidate_status`: `Qualified` in `leads.csv` (`Rejected` only appears in `rejected.csv`)

`tests/test_leads_schema.py` fails if any of these drift from the workbook.

## Commands

- `python run.py --input data/seeds.csv --out output/`: full run
- `python run.py --refresh`: re-check evidence older than 30 days, keep unchanged cached results
- `python check_apis.py`: one cheap live call per API to prove the `.env` keys work

## Qualification checks (all must pass, each with a working public link)

Sources: `docs/BRIEF.pdf` and the assignment `docs/IncuBrix_2027_Growth_Engineer_Option_1_Lead_Generation_and_Outreach.pdf` (section 3). Where they differ, the stricter rule wins.

1. **Real and relevant**
   - A real creator in an approved segment and country, with an official profile and a stable platform ID.
   - **Excluded:** agencies, management firms, generic brands, publications, directories and fan accounts.
2. **Active**
   - 8+ items in 30 days, or 2+ long-form items (20 minutes or more) in 60 days.
3. **Commercial**
   - Public sponsorship, product, service, course, membership, subscription or affiliate evidence.
   - The evidence is a verbatim quote plus its URL.
4. **Needs IncuBrix**
   - A need in content creation, repurposing, editing, captions, publishing, consistency, backlog or team workflow. Two kinds of evidence count, each with a link:
     - (a) an **observed gap** in their public content, for example no captions on recent videos, or long episodes with no Shorts or clips, or irregular gaps between uploads;
     - (b) the creator's **own words**, for example "hiring an editor". This scores higher.
5. **Reachable**
   - The channel is real, public, presented by the creator for business contact, and active in the last 60 days.
   - Never guessed. The YouTube "About" email is behind a captcha and is never used.
6. **Personalised and compliant**
   - The message cites a specific recent piece of content, names the sender and includes an opt-out.
   - It follows platform rules: LinkedIn, Instagram and X messages are drafts for a person to send by hand, with no bulk automation.
   - The sender must not be presented as an IncuBrix employee.
7. **Complete and unique**
   - All workbook fields are filled, evidence was checked within 30 days, and the creator appears once.

## Hard constraints (run fails loudly if broken)

- At least 80% of leads from US, CA, GB, IE, AU, NZ, SG
- At least 3 countries
- No country above 60%
- Mainly English content

All values are in `config.yaml`.

## Failure handling

- **Feeds, websites, robots.txt:** a final failure is remembered for 1 day, so a rerun does not repeat it. APIs are not remembered, so a quota error clears when the quota resets.
- **HTTP calls (`cached_get`):** network errors, HTTP 429 and 5xx are retried 3 times with exponential backoff.
  - Other errors (for example 403) are not retried.
  - Either way the failure is logged to `api_log` and the log file, and the search or row is skipped. Failures are never cached and never filled with guessed data.
- **YouTube daily quota used up (`quotaExceeded`):** the remaining YouTube searches are skipped for this run. The next run resumes, because finished searches are cached.
- **Missing API key:** that source is skipped with an error in the log, and the other sources still run.
- **Missing input file:** `run.py` stops with exit code 1.
- **Config:** `run.py` stops at start-up if `config.yaml` is missing a required section.
- **Logs:** each run writes its own log file to `<out>/logs/`.
