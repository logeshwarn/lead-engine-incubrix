"""Shared helpers used by every stage: config loading and per-run logging."""

import logging
from datetime import datetime
from pathlib import Path

import yaml
from dotenv import load_dotenv

# Sections the stages rely on; checking them up front fails fast on a broken config
# instead of crashing halfway through a run.
REQUIRED_SECTIONS = [
    "paths",
    "http",
    "segments",
    "countries",
    "language",
    "activity",
    "reachable",
    "evidence",
    "priority_a",
    "targets",
]


def load_config(path="config.yaml"):
    """Read config.yaml and load secrets from .env into the environment."""
    # .env is optional here so --help and tests work without keys;
    # each stage checks for the keys it needs.
    load_dotenv()
    with open(path, encoding="utf-8") as f:
        config = yaml.safe_load(f)
    missing = [s for s in REQUIRED_SECTIONS if s not in (config or {})]
    if missing:
        raise ValueError(f"config.yaml is missing sections: {', '.join(missing)}")
    return config


def setup_logging(log_dir):
    """Log to the console and to one new file per run."""
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"run_{datetime.now():%Y%m%d_%H%M%S}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(log_file, encoding="utf-8"), logging.StreamHandler()],
        force=True,  # replace any earlier handlers so each run gets its own file
    )
    return log_file
