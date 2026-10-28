"""One command to run the IncuBrix Lead Engine.

python run.py --input data/seeds.csv --out output/
python run.py --refresh
"""

import argparse
import logging
import sys
import time
from pathlib import Path

from engine import caps, dedupe, discover, draft, enrich, export, route, score, verify
from engine.common import connect_db, load_config, merge_cache, now_utc, setup_logging

# Pipeline order from docs/WORKFLOW.md; each name is engine/<name>.py.
STAGES = ["discover", "enrich", "verify", "dedupe", "caps", "score", "route", "draft", "export"]


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Find, verify and draft outreach for content creators; export leads.csv."
    )
    parser.add_argument("--input", default="data/seeds.csv", help="seed queries CSV (default: data/seeds.csv)")
    parser.add_argument("--out", default="output/", help="output folder (default: output/)")
    parser.add_argument("--config", default="config.yaml", help="settings file (default: config.yaml)")
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="re-check evidence older than 30 days and keep unchanged cached results",
    )
    parser.add_argument(
        "--merge-cache",
        metavar="OTHER_OUT",
        help="first copy the cached fetches of another run's output folder into this one (see README)",
    )
    parser.add_argument(
        "--fetch-shard",
        metavar="K/N",
        type=shard_arg,
        help="only fill the cache for part K of N of the discovered creators, next to a running full run (see README)",
    )
    parser.add_argument("--workers", type=int, help="fetch threads (default: enrich.workers in the config)")
    return parser.parse_args(argv)


def shard_arg(value):
    """'2/4' -> (2, 4)."""
    try:
        k, n = (int(x) for x in value.split("/"))
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected K/N, for example 1/4, not {value!r}") from None
    if not 1 <= k <= n:
        raise argparse.ArgumentTypeError(f"K must be between 1 and N, not {value!r}")
    return k, n


def main(argv=None):
    args = parse_args(argv)
    config = load_config(args.config)
    log_file = setup_logging(Path(args.out) / "logs")
    log = logging.getLogger("run")
    log.info("run started: input=%s out=%s refresh=%s log=%s", args.input, args.out, args.refresh, log_file)
    if not Path(args.input).is_file():
        log.error("input file not found: %s", args.input)
        return 1
    if args.refresh:
        # Re-check every search and every creator's evidence fetched more than a day ago; anything
        # fetched within the day is kept, so a refresh after a crash does not start from zero.
        for key in ("search_max_age_days", "enrich_max_age_days"):
            config["cache"][key] = config["cache"]["refresh_max_age_days"]
    if args.workers:
        config["enrich"]["workers"] = args.workers
    conn = connect_db(args.out)
    if args.fetch_shard:
        # Cache only: no discover (the running full run owns the candidates table) and no tables written.
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'candidates'").fetchone():
            log.error("--fetch-shard needs the candidates of a run in %s: start the full run first", args.out)
            return 1
        enrich.run(conn, config, shard=args.fetch_shard)
        conn.close()
        return 0
    started, started_iso = time.monotonic(), now_utc().isoformat()
    if args.merge_cache:
        added = merge_cache(conn, Path(args.merge_cache) / "engine.db")
        log.info("merged the cache of %s: %d new cached responses", args.merge_cache, added)
    discover.run(conn, config, args.input)
    enrich.run(conn, config)
    verify.run(conn, config)
    dedupe.run(conn, config)
    # A broken cap rule does not stop the run: the later stages still run so the output can be
    # inspected, but the run ends with an error (owner decision 2026-10-28).
    cap_failures = caps.run(conn, config)
    score.run(conn, config)
    route.run(conn, config)
    draft.run(conn, config)
    runtime = time.monotonic() - started
    export.run(conn, config, args.out, started_iso, runtime, log_file, cap_failures)
    log.info("run finished in %.1f s", time.monotonic() - started)
    conn.close()
    if cap_failures:
        log.error("RUN FAILED: the lead set breaks %d hard rule(s): %s", len(cap_failures), "; ".join(cap_failures))
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
