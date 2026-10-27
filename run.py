"""One command to run the IncuBrix Lead Engine.

python run.py --input data/seeds.csv --out output/
python run.py --refresh
"""

import argparse
import logging
import sys

from engine.common import load_config, setup_logging

# Pipeline order from docs/WORKFLOW.md. Each name becomes engine/<name>.py as it is built.
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
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    config = load_config(args.config)
    log_file = setup_logging(config["paths"]["logs"])
    log = logging.getLogger("run")
    log.info("run started: input=%s out=%s refresh=%s log=%s", args.input, args.out, args.refresh, log_file)
    # No stages are built yet (Phase 0). Say so plainly rather than pretend to run.
    log.warning("no pipeline stages implemented yet; planned order: %s", " -> ".join(STAGES))
    return 0


if __name__ == "__main__":
    sys.exit(main())
