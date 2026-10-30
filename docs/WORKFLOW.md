# App workflow

Update this file when a stage or one of its rules changes.

Each stage is one file in `engine/`. It reads a table and writes a table, so it can be run on its own. Stage tables live in SQLite (`<out>/engine.db`), so a crashed run resumes from the last finished stage.

| # | Stage | File | Input | Output | Status |
|---|---|---|---|---|---|
| 1 | discover | `engine/discover.py` | `data/seeds.csv` | `candidates` table (platform ID, URL, source, query) | **built** |
| 2 | enrich | `engine/enrich.py` | `candidates` | `profiles` and `content_items` tables: profile, recent uploads, links, public contact info (cached) | **built** |
| 3 | verify | `engine/verify.py` | `profiles`, `content_items` | `verified` table: every check with an evidence quote and URL; Qualified or Rejected with reasons (export writes rejects to `rejected.csv`) | **built** |
| 4 | dedupe | `engine/dedupe.py` | `verified` | `deduped` table: every verified row; one Qualified row per creator (platform ID, website domain, email); duplicates and shared-contact rows Rejected with the reason | **built** |
| 5 | caps | `engine/caps.py` | `deduped` | `capped` table (a country above 60% trimmed) and `cap_checks` table (each hard rule, value, limit, passed) | **built** |
| 6 | score | `engine/score.py` | `capped` | `scored` table: 5 score parts, `lead_score` 0-100, `priority` A/B/C | **built** |
| 7 | route | `engine/route.py` | `scored` | `routed` table: best and backup channel, each with its handle or URL and evidence URL | **built** |
| 8 | draft | `engine/draft.py` | `routed` | `drafted` table: first message for every lead, + 2 follow-ups for Priority A, each checked | **built** |
| 9 | export | `engine/export.py` | `drafted` | `leads.csv`, `outreach/`, `rejected.csv`, `run_report.md` | **built** |

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
| `primary_platform` | `youtube`, `podcast` (keyword search), `podcast_category` (the keyword is a Podcast Index category name, e.g. `Fitness`; returns active English shows from the category's trending and recently updated lists), or `apple_chart` (the keyword is an Apple genre name from `discover.apple_genres`, e.g. `Health & Fitness`; returns Apple's top-200 chart for that genre in each store in `discover.chart_stores`) |
| `discovery_keywords` | search terms separated by `;`. Each YouTube term costs one `search.list` call (100 units). No term may repeat |
| `need_signal_to_check` | hint for verify about which need to look for. Never used as evidence |
| `size_min`, `size_max` | subscriber range for YouTube seeds. Blank for podcasts (no public audience count) |
| `status` | `active` (searched) or `paused` (skipped) |

The current file has 198 seeds: the owner's 42, then waves added during the build (DECISIONS.md): Podcast Index categories (S043-S058, S165-S198), Apple charts (S059-S101, S115-S143) and country keyword seeds (S102-S114, S144-S164). By platform: 32 YouTube, 44 podcast keyword, 50 Podcast Index category, 72 Apple chart. One uncached pass makes:
- 84 YouTube searches, about 8,400 quota units
- 131 Podcast Index and 131 iTunes keyword searches, and 100 category-list calls
- 432 Apple chart calls (72 genres x 6 stores) and their lookups

`data/sample_seeds.csv` holds 11 of these seeds (S102-S112, podcast keywords only) for a quick first run: 13.4 minutes from an empty folder, 11 leads from 5 countries (31 Oct).

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

- **Apple chart seeds** (`apple_chart`, added 2026-10-28 for non-US volume): Apple's top-200 chart for one genre in each non-US approved store (GB, AU, CA, IE, NZ, SG), then the iTunes lookup API for each show's feed. A store's chart leans towards that country's listeners, so it finds more non-US creators, which the 60% country cap needs. The store is **never** country evidence; verify still needs the creator's own statement.
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
- **Parallel fetching:** YouTube channels (2 calls each), feeds and websites are fetched 24 at a time (`enrich.workers`; raised from 8 on 2026-10-28 for the full run), each thread with its own database connection (SQLite in WAL mode). Results are put back in input order, so a rerun gives the same tables. Once the YouTube quota runs out, a shared flag stops the remaining channels' calls.
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
| 4 Needs IncuBrix | the creator's own words first, about the show itself ("hiring an editor", "sorry for the delay", "the podcast is on hiatus", "we're taking a short break"; a break from emails or a guest's hiatus does not count), quoted at whole words; otherwise an observed gap: no creator-uploaded captions or transcripts on every one of 3+ recent items (only when the status of every item is known); long videos and no Shorts; long episodes and no YouTube or TikTok link (only when we read their website); or a 21+ day gap between uploads | `incubrix_need`, `need_kind`, `need_evidence`, `need_evidence_url` |
| 5 Reachable | creator active in the last 60 days **and** at least one checkable business channel: an email (on their own domain, labelled for business, on their contact page, or the show's RSS contact; never a hosting-platform or no-reply address, never one seen only in show notes), their contact page, or a guest-pitch page. Social profiles are recorded but cannot pass alone, because their activity cannot be checked without reading the platform | `contacts` (JSON, each with `evidence_url` and a note) |
| 6 Personalisable | a recent item with a title and link to cite. The episode link is used, or the show page when the episode has none. The message itself is checked in draft | `recent_content_title`, `recent_content_url` |
| 7 Fresh evidence | profile checked within 30 days. Uniqueness is checked by dedupe | `checked_date` |

**Country evidence**, strongest first:
1. country stated on the YouTube channel
2. the creator's `<podcast:location>` feed tag
3. a postal address (US "City, ST 12345", UK, Canadian or Australian postcode), but only on a contact or about page or in the description, because a homepage can list an event venue
4. a phone prefix (+44, +353, +61, +64, +65; +1 is skipped because it's shared by US and CA)
5. a sentence placing the creator: "based in", "located in", "X-based", or "we are from" (with a subject, so "lessons from London" does not count). When several places appear, the right-most wins: "Birmingham, Alabama" is US
6. the website's country domain (`.uk`, `.ca`, `.ie`, `.au`, `.nz`, `.sg`), labelled as such in the evidence
7. for a podcast that fails only on country: the country its own linked YouTube channel states on YouTube (`check_linked_country`, 1 cached call shared with the size check). Measured 2026-10-28: 104 of 147 such channels state an approved country

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

**Podcast size** (`check_podcast_size`): podcast directories publish no audience count, so the size of a podcast comes from the creator's own YouTube channel, when their description or website links to one (`/@handle`, `/channel/UC…`, `/user/…`, `/c/…`; watch and playlist links are ignored). One `channels.list` call (1 unit, cached) on rows that pass every other check, before the LLM. Above `verify.podcast_max_youtube_subscribers` (250,000) is a rejection; the count and link are kept in `followers_or_subscribers` and `size_evidence`. No link, a hidden count or a failed call is not a reason.

## Stage 4: dedupe

Input: the `verified` table. Output: the `deduped` table, the same rows plus `duplicate_of`. Nothing is dropped: a row that loses is marked Rejected with the reason, so export can write it to `rejected.csv`.

1. **Shared contact email.** Over every verified row (qualified or not), count how many different shows list each email. A qualified row whose email is on 3 or more shows (`dedupe.shared_email_min_shows`) is rejected: "not the creator's own contact: X is listed on N different shows". Such an address belongs to a network or to a feed that re-uploads other people's YouTube channels. Measured on 3,299 shows: 2,168 emails are on 1 show and 110 on 2; one gmail address ran 19 feeds named after Dr. John Campbell, MIT OpenCourseWare, Jim Gaffigan and others, another 56.
2. **Same creator.** Qualified rows are one creator when they share any key:
   - the platform ID
   - the website's registered domain (`www.JaneDoe.com/podcast` and `janedoe.com` match)
   - an email address (lower-cased)

   Keys chain: if A and B share a domain, and B and C an email, all three are one creator. Domains many creators share never count: `enrich.skip_domains`, `verify.media_domains`, the hosting domains in `engine/verify.py`, and `dedupe.shared_domains` (Substack, Linktree-style pages, page builders, Podpage, Zencastr and others).
3. **Which row is kept:** the most recent content, then the most contacts, then the lowest platform ID, so reruns keep the same row. The others get "duplicate of <name> (<id>): same <key> <value>" and `duplicate_of`.

The table is rebuilt from `verified` every run, so the stage can be rerun on its own.

## Stage 5: caps

Input: the `deduped` table. Output: the `capped` table (same columns) and the `cap_checks` table.

1. **Trim (owner decision 2026-10-28).** If one country is above 60% of qualified leads (`countries.max_country_share`), its lowest-ranked leads are marked Rejected ("cap: US above 60% of leads (ranked 30 of 33 US leads)") until it is at 60%. The lowest scores go first (`engine/score.py`, the same score stage 6 gives), so the best leads are kept. Trimming is skipped when the set has fewer than 3 countries, because it could not fix that rule and would throw most leads away.
2. **Check.** Every hard constraint is checked on the qualified set and written to `cap_checks`: approved-country share >= 80%, at least 3 countries, largest country <= 60%, all leads mainly English, all in an approved segment.
3. **Fail loudly.** A failed rule is logged as `CAP RULE FAILED`. The later stages still run so the output can be inspected, but `run.py` ends with `RUN FAILED` and exit code 2, and the set is not valid for submission.

## Stage 6: score

Input: `capped`. Output: `scored`, the same rows plus `score_need`, `score_volume`, `score_commercial`, `score_reach`, `score_evidence`, `lead_score` and `priority`. Only qualified rows are scored; rejected rows keep these blank. Weights are in `config.yaml` (`score`), chosen by the owner on 2026-10-28; the reasons are in DECISIONS.md.

| Part | Max | Points |
|---|---|---|
| need | 30 | by `need_kind`: own words 30, repurposing 22, captions 15, consistency 12 |
| volume | 20 | long-form items in 60 days: 8 or more earn 20, fewer earn a share (4 items = 10) |
| commercial | 20 | by `monetization_signal`: Sponsorship 20; Service, Course, Product 16; Membership 12; Affiliate 8 |
| reach | 20 | email 12; contact form or guest-pitch page 4; at least 2 kinds of channel 4 |
| evidence | 10 | country from the platform, feed tag, a sentence or an address 10; from the website's country domain only 6 |

**Priority:** the 25 highest scores are A (`priority_a.count`); of the rest, 50 or more is B (`score.priority_b_min_score`), below 50 is C. Equal scores are ordered like dedupe (most recent content, most contacts, lowest ID), so reruns give the same A list.

A score depends only on the lead's own evidence, so caps uses the same function (`rank_key`) to decide which leads to trim: the lowest scores go first.

## Stage 7: route

Input: `scored`. Output: `routed`, the same rows plus `best_channel`, `channel_handle_or_url`, `channel_evidence_url`, `backup_channel`, `backup_handle_or_url`, `backup_evidence_url`. Only contacts the creator published (verify's `contacts`) are used; nothing is guessed.

- **Best channel:** the creator's best email; else a contact form; else a podcast guest-pitch page. These are the channels we can check the creator presents for business contact. A social profile cannot be checked for activity (we do not scrape those platforms), so it is never the best channel.
- **Which email:** an address on the creator's own website domain first (`shannon@shannonoflaherty.com` before `producer@transformationtalkradio.com`); role mailboxes (sales, support, meetings, producer and others) last; website-template placeholders (`info@mysite.com`) never.
- **Backup channel:** another checkable channel of a different kind (usually the contact form); else the creator's own social profile, LinkedIn first, then Instagram, X, TikTok; else a second email address. A social profile counts as the creator's when its handle contains the show's or website's name, or when it is the only profile on that platform their own pages link to. Pages that link several (Storied links 4 Instagram accounts, its contributors') need the name match.

The same `route.choose` runs inside verify's "reachable" check: a lead without both channels is rejected there ("no backup channel (only Email ...)"), so caps and score never count it. Route itself raises an error if a qualified row has no pair, which would mean stale tables.

## Stage 8: draft

Input: `routed`. Output: `drafted`, plus `personalization_hook`, the first message, Priority A's two follow-ups (channel and day of each), `draft_checks` and `draft_ok`.

- **Sequence:** every lead gets a first message on its best channel. Priority A also gets follow-up 1 on day 4 (same channel) and follow-up 2 on day 9 (backup channel) (`draft.follow_up_days`).
- **Templates** (`engine/draft.py`, rendered in `outreach/templates.md`): email (subject, body, sign-off, opt-out, postal address), contact form or guest-pitch page (the same body, no subject; a guest-pitch page message says it is not a guest pitch), and a short social message (LinkedIn, Instagram, X, TikTok; sent by hand). The segment changes one sentence: the angle for a show, a channel, or a coach or educator.
- **Only verified facts are filled in:** the latest item's title (cut at a word boundary to `draft.title_chars`, or `dm_title_chars` for social), the gap verify measured in its own numbers ("none of your last 16 episodes has a transcript", "11 long episodes", "a 24-day gap", or the creator's own words), the segment and the channel. The pitch, call to action and follow-up offer are in `config.yaml` (`draft`); the pitch only uses the assignment's need list (editing, captions, repurposing). No LLM writes the messages (decision 2026-10-28), so nothing can be invented.
- **Checks on every message:** cites the recent item, names the sender, has an opt-out ("won't contact you again"), fits the channel limit (`draft.max_chars`: 1,500 for email and forms, 300 for LinkedIn, 1,000 for other social), never claims the sender works for IncuBrix, and has no unfilled `{placeholder}`. The email postal address is a placeholder until launch (`{sender_postal_address}`), flagged as "fill before real sending" but not a failure. A failed check is logged as an error with the lead and message.

## Stage 9: export

`export.run` writes the --out folder:
- `leads.csv`: qualified leads only, the 30 workbook columns, sorted by `lead_id`. `lead_id` is the stable platform ID, so a refresh keeps every ID. `first_message` holds the subject line first for email. `duplicate_check` and `completeness_check` are filled per row; `followers_or_subscribers` may be blank ("audience size not public": podcast directories publish none). A duplicate `lead_id` stops the export.
- `outreach/`: `sequences.csv` (every message: lead, step, day, channel, send mode, recipient, subject, text), one Markdown file per lead in `A/`, `B/` or `C/` with its checks, and `templates.md`. Email may be sent automatically (test accounts only until launch); every other channel is marked manual.
- `rejected.csv`: see below.
- `run_report.md`: result (all hard rules pass, or FAILED with the rule), counts, country/segment/priority/channel mix, the hard rules, top rejection reasons, runtime, API calls per source (new, cached, failed), Gemini tokens used by new calls, cost and the error count. Every number is read from the database and the run log.

### rejected.csv

`export.write_rejected` reads `capped` and writes every Rejected row to `<out>/rejected.csv` with `REJECTED_COLUMNS`: platform, platform ID, name, profile URL, website, segment, niche, seed, country and its evidence URL, `rejection_reason` (all reasons, separated by semicolons; the first is the main one), `duplicate_of` and `checked_date`. The workbook has no tab for rejects, so these columns are the engine's own. A rejected row without a reason stops the run with an error, because nothing may be dropped silently. `leads.csv`, `outreach/` and `run_report.md` come in Phase 5.

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
- `python run.py --refresh`: re-fetch every search and creator's data cached more than 1 day ago (`cache.refresh_max_age_days`), so all evidence is re-checked today; anything fetched within the day is kept. A normal run already never uses data older than 7 days, so evidence is always well within 30 days
- `python run.py --out output/full/ --merge-cache output/wave2/`: first copy another run's cached fetches into this folder (two runs fetching at once must use separate folders, because every stage replaces its table)
- `python run.py --out output/full/ --fetch-shard 2/4 --workers 8`: while a full run is enriching in `output/full/`, fill the shared cache for one quarter of its creators (a stable hash of `platform_id`), last first. Shards skip discover and YouTube and write no tables; the full run then reads those creators from the cache. Parsing a raw feed is CPU work and one Python process uses about one core, so N shards make the first fetch about N times faster. Afterwards rerun the normal command: everything is cached. A write that finds the database locked by another process waits and retries (up to 10 times) instead of stopping the run.
- `python check_apis.py`: one cheap live call per API to prove the `.env` keys work
- `python seedtest.py plan|send|mark|clicks|replies|report --out <run folder>`: the seed test (above)

## Qualification checks (all must pass, each with a working public link)

Sources: the IncuBrix brief and the assignment (section 3), both kept out of the repository. Where they differ, the stricter rule wins.

1. **Real and relevant**
   - A real creator in an approved segment and country, with an official profile and a stable platform ID.
   - **Excluded:** agencies, management firms, generic brands, publications, directories and fan accounts.
2. **Active**
   - 8+ items in 30 days, or 2+ long-form items (20 minutes or more) in 60 days.
3. **Commercial**
   - Public sponsorship, product, service, course, membership, subscription or affiliate evidence.
   - The evidence is a verbatim quote plus its URL.
   - "Brought to you by" followed by the show's own name or website is the creator promoting themselves, not a sponsor, and does not count.
   - A link to Patreon, Kajabi, Gumroad and similar counts only from the creator's own description or website, not from episode notes (often a guest's or a friend's).
4. **Needs IncuBrix**
   - A need in content creation, repurposing, editing, captions, publishing, consistency, backlog or team workflow. Two kinds of evidence count, each with a link:
     - (a) an **observed gap** in their public content, for example no captions on recent videos, or long episodes with no Shorts or clips, or irregular gaps between uploads;
     - (b) the creator's **own words**, for example "hiring an editor". This scores higher.
5. **Reachable**
   - The channel is real, public, presented by the creator for business contact, and active in the last 60 days.
   - There must be a best and a backup channel (assignment section 1: "the best channel to reach them, a backup channel and the verified public handle or URL"). The rules are in stage 7, route.
   - Never guessed. The YouTube "About" email is behind a captcha and is never used.
   - A hosting platform's own social accounts (x.com/rss, instagram.com/rss_podcasting, linkedin.com/company/rsscom) sit in the footer of every hosted show page and are not the creator's.
6. **Personalised and compliant**
   - The message cites a specific recent piece of content, names the sender and includes an opt-out.
   - It follows platform rules: LinkedIn, Instagram and X messages are drafts for a person to send by hand, with no bulk automation.
   - The sender must not be presented as an IncuBrix employee.
7. **Complete and unique**
   - All workbook fields are filled, evidence was checked within 30 days, and the creator appears once.

## Hard constraints (run fails loudly if broken)

- At least 80% of leads from US, CA, GB, IE, AU, NZ, SG
- At least 3 countries
- No country above 60% (a larger country is trimmed to 60% first)
- Mainly English content

All values are in `config.yaml`. Enforced by `engine/caps.py` (stage 5); `run.py` exits with code 2 when any of them fails.

## Seed test (`seedtest.py`, Phase 6)

Proves scheduling, tracked links and reply logging on 3 channels, using only the owner's own test accounts (`SEED_*` in `.env`; the script refuses any other recipient and stops if one is missing).

1. `python seedtest.py plan --out <run folder> --leads 3`: for the first 3 Priority A leads, schedules the email sequence (first message, follow-up 1, follow-up 2) and one LinkedIn and one Instagram message. One sequence day is `seed_test.minutes_per_day` minutes (2), so the day-4 and day-9 follow-ups arrive 8 and 18 minutes later. Each message gets its own tracked link, `http://localhost:8765/c/<seed id>`. Table `seed_schedule`.
2. `python seedtest.py clicks --out <run folder>` (in a second terminal): the click tracker. Each click is logged to `seed_events` and redirected to incubrix.com.
3. `python seedtest.py send --out <run folder>`: sends every due email by SMTP (Gmail, App Password) and prints every due LinkedIn and Instagram message. Run it again after 8 and 18 minutes for the follow-ups.
4. **By hand (platform rules forbid automated DMs):** send each printed LinkedIn and Instagram message from your account to your second test account, then `python seedtest.py mark --out <run folder> S004 sent`. Reply from the test accounts; for social replies run `mark ... reply`. Screenshot each sent message, the click page and each reply into `<run folder>/seed_test/`.
5. `python seedtest.py replies --out <run folder>`: reads the sender's inbox (IMAP) and logs every reply whose In-Reply-To or References names a seed email.
6. `python seedtest.py report --out <run folder>`: writes `seed_test/seed_report.md` (scheduled, sent, clicks, replies per channel; planned vs sent time per message), `seed_schedule.csv` and `seed_events.csv`.

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
- **Resume after a crash or a stop (Ctrl+C, power, network):** rerun the same command. Every fetch that finished is in the cache, so discover and enrich continue where they stopped and the later stages (minutes) run again in full.
