"""One command to run the IncuBrix Lead Engine.

python run.py --input data/seeds.csv --out output/
python run.py --refresh
"""

import argparse
import logging
import sys
import time
from pathlib import Path

from engine import caps, dedupe, discover, enrich, export, route, score, verify
from engine.common import connect_db, load_config, setup_logging

# Pipeline order from docs/WORKFLOW.md. Each name becomes engine/<name>.py as it is built.
STAGES = ["discover", "enrich", "verify", "dedupe", "caps", "score", "route", "draft", "export"]
BUILT = ["discover", "enrich", "verify", "dedupe", "caps", "score", "route"]


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
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    config = load_config(args.config)
    log_file = setup_logging(Path(args.out) / "logs")
    log = logging.getLogger("run")
    log.info("run started: input=%s out=%s refresh=%s log=%s", args.input, args.out, args.refresh, log_file)
    if not Path(args.input).is_file():
        log.error("input file not found: %s", args.input)
        return 1
    conn = connect_db(args.out)
    started = time.monotonic()
    discover.run(conn, config, args.input)
    enrich.run(conn, config)
    verify.run(conn, config)
    dedupe.run(conn, config)
    # A broken cap rule does not stop the run: the later stages still run so the output can be
    # inspected, but the run ends with an error (owner decision 2026-10-28).
    cap_failures = caps.run(conn, config)
    score.run(conn, config)
    route.run(conn, config)
    export.write_rejected(conn, args.out)  # the rest of export (leads.csv, report) comes in Phase 5
    # Say plainly which stages are still missing rather than pretend the run is complete.
    log.warning("stages not built yet: %s", ", ".join(s for s in STAGES if s not in BUILT))
    log.info("run finished in %.1f s", time.monotonic() - started)
    conn.close()
    if cap_failures:
        log.error("RUN FAILED: the lead set breaks %d hard rule(s): %s", len(cap_failures), "; ".join(cap_failures))
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
