# Cache and reruns: how the engine reached 1,260 leads

The full run did not happen in one pass. Free LLM quotas allow only a few hundred creator checks a day, so the engine ran several times between 28 and 30 Oct 2026. Each rerun picked up from the cache where the last one stopped. This doc covers how the cache works, why we built it, and the milestones from 7 leads to 1,260.

Timings and counts come from `CHANGELOG.md`, the run logs and the run reports. All times are IST.

## Why a cache

| Need | How the cache meets it |
|---|---|
| **Free quotas.** Gemini's free tier allows 500 requests a day per model, and Groq allows 200,000 tokens a day per model. One full run needs about 2,000 creator checks. | Every LLM answer is stored. A rerun after a quota reset only checks creators that have no answer yet. |
| **Crash recovery.** The brief asks for a run that recovers from a simple failure. | A stopped run loses nothing. The same command reads back every stored answer and goes on. Wave 1 stopped on a bad URL at 01:04 on 29 Oct and resumed this way. |
| **Repeatable output.** The same input should give the same leads. | A repeat run within the cache window reads the same answers, so it gives the same leads and IDs. |
| **Cost and politeness.** The target was $0, and sources should not be fetched twice. | Searches, feeds and pages are fetched once and reused for 7 days. Failed sites are not retried for a day. |
| **Parallel fetching.** | Shard processes (`--fetch-shard K/N`) and other runs (`--merge-cache`) fill the same cache. |

## How it works

- **Storage.** The cache is the `api_cache` table in `<out>/engine.db` (SQLite, WAL mode). Each row holds a cache key, the source, the response and the time it was fetched.
- **Cache key.** Built from the source, the URL and the parameters. API keys are left out of the key, and the key is never stored or logged. For LLM calls the prompt body is part of the key, so the same prompt is never sent twice.
- **How long answers are kept** (`config.yaml`):

  | What | Kept for |
  |---|---|
  | Discovery searches (`cache.search_max_age_days`) | 7 days |
  | Profiles, uploads, feeds and pages (`cache.enrich_max_age_days`) | 7 days |
  | A failed feed or website (`cache.failure_max_age_days`) | 1 day, then tried again. API failures are never remembered, so calls work again as soon as a quota resets. |
  | LLM answers (`llm.cache_days`) | 30 days, the same as the evidence age limit |
  | `--refresh` (`cache.refresh_max_age_days`) | re-fetches anything older than 1 day |

- **Pages are stored small.** Feeds and web pages are parsed first, and only the extracted fields are stored. A missing page (4xx) is stored as "nothing there", so a rerun does not ask again.
- **LLM chain, cache first** (`common.llm_json`). Before calling any model, the engine looks for a stored answer from every model in the chain: 4 Gemini models, then 3 Groq models. Then, for each model in turn:
  - A 429 gets one 60-second wait and a retry. A second 429 marks the model out of quota for the rest of the run.
  - A busy model (5xx) passes the prompt to the next model but stays in the chain.
- **Order of checks.** Non-US creators are checked first, because the 60% US cap limits US leads to 1.5 times the non-US count.
- **Concurrent writes.** Cache and log writes go through `common.write_with_retry`, so several processes can write one database without failing on `database is locked`.

## Milestones

| When (IST) | Leads | What changed |
|---|---|---|
| 28 Oct | 40 to 42 | Small runs on the owner's seeds, used to build and hand-check each stage. |
| 28 Oct 21:44 | — | Wave 1 full run started. Shard processes filled the cache next to it. |
| 29 Oct 01:04 | — | Wave 1 stopped on a malformed URL (`http://.libsyn.com`). All 20,012 feeds were already cached. After the fix, the run resumed from the cache. |
| 29 Oct 01:14–02:00 | **7** | First complete run: 23,943 candidates. Gemini Flash-Lite's free quota ran out after 47 checks, leaving 1,601 creators unchecked. **Fixes:** a Gemini fallback model, non-US creators checked first, and wave 3 seeds (S073–S112). Then Groq was added as a third provider. |
| 29 Oct 03:52–04:50 | **82** | Wave 3's cache merged in (32,589 candidates). Groq `gpt-oss-120b` hit its daily token cap after 125 checks, leaving 2,263 unchecked. **Fixes:** two more Groq models (`gpt-oss-20b`, `qwen3.8-27b`), and wait-and-retry on a per-minute 429. |
| 29 Oct 06:22–06:51 | **211** | Rerun from the cache after the Groq limits rolled over. All 211 leads were non-US, and 1,997 creators were unchecked. **Fixes:** `gemini-3.8-flash` added, and busy models pass the prompt on. |
| 29 Oct ~07:45 | — | The owner tried a billed Gemini key. Its credit ran out before any paid check, so the free key went back. |
| 29 Oct by 12:10 | **493** | Every non-US creator was checked (445 non-US leads). 1,426 US creators were left. **Fix:** `gemini-3.1-flash-lite` added. The owner's AI Studio screenshot showed it has its own 500-a-day quota. |
| 29 Oct 12:32–15:47 | **1,083** | Run after the Gemini reset at 12:30. It made 2,124 creator checks: stored answers plus fresh quota. US 638 (58.9%), GB 193, AU 121, CA 91, NZ 20, IE 13, SG 7. All hard rules pass. |
| 30 Oct 16:00–18:40 | **1,110** | Wave 4: the proof runs' cache merged in, and 29 Apple subgenres added (7,310 new shows, only 13 leads). The first run lost its creator check to a network drop; the rerun from the cache finished it. |
| 30 Oct 18:46–19:15 | **1,125** | Wave 5: 21 country keyword seeds (251 new shows). |
| 30 Oct 19:17–21:25 | **1,222** | Wave 6: 18 Podcast Index categories (8,087 new shows), 39 more non-US leads. |
| 30 Oct 21:26–22:39 | **1,262** | Wave 7: 16 more categories (5,103 new shows). US 757 (60.0%), GB 223, AU 135, CA 105, NZ 20, IE 14, SG 8. All hard rules pass. |
| 30 Oct 23:04–23:56 | **1,260** | Rerun from the cache after the own-words need fix (DECISIONS.md): 4 creators lost their only need, and the A list was re-picked. |

### What moved the count at each step

- **7 → 82:** fallback models and the Groq provider. More checks fit into the same day.
- **82 → 211:** more Groq models, plus wait-and-retry, so a per-minute limit no longer cost a model its whole day.
- **211 → 493:** quota resets, plus `gemini-3.8-flash`. The cache meant every reset went only to new creators.
- **493 → 1,083:** `gemini-3.1-flash-lite`'s separate quota and the 12:30 Gemini reset. Most of the gain is US leads. US creators were checked last by design, and the 445 non-US leads let the cap admit up to about 667 US leads.
- **1,083 → 1,262 (1,260 after the need fix):** new non-US seeds. The 60% cap allows 1.5 US leads per non-US lead, and qualified US creators were already waiting, so every new non-US lead raised the total by about 2.5. Podcast Index categories gave far more than Apple subgenres or keyword searches.

No rule was relaxed along the way. Every lead passed the same checks, and every LLM answer still had to quote the creator's own text word for word.

## Proof runs (29 Oct evening)

These ran on copies of the output folder (`output/proof/`, `output/proof_refresh/`), before the 30 Oct seed waves.

- **Repeat run** (110 min): 1,110 leads. Groq's limit had reset, so 189 creators that were never judged got an answer, and 97 more US creators qualified. All IDs are still unique.
- **Refresh run** on a small seed set plus 2 new seeds (4.2 min): every earlier lead kept its ID, 6 were added, and there were 0 duplicates.
- **Stop and resume:** the run was killed during verify. The same command then finished with 0 new fetches, because everything came from the cache, giving 1,110 leads and 0 duplicates.

## What is left

- Every creator has been checked. 276 qualified US creators are trimmed by the 60% cap; only more non-US leads would let them in.
- The cache stays valid until about 4 Nov (searches and pages) and about 28 Nov (LLM answers). Until then, a rerun of the same command reads it back.

## Commands

```bash
python run.py --input data/seeds.csv --out output/full/
```

Run it again after a stop or a quota reset. It resumes from the cache.

```bash
python run.py --refresh --input data/seeds.csv --out output/full/
```

Re-checks evidence that is more than 1 day old.
