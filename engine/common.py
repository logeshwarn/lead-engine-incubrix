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


# leads.csv columns, locked to Submission Workbook tab 02_LEADS (row 4, columns A-AD).
# Order matters: the workbook rows are pasted straight from leads.csv.
# tests/test_leads_schema.py re-reads the workbook so any drift fails a test.
LEADS_COLUMNS = [
    "lead_id",
    "creator_name",
    "creator_segment",
    "country_iso2",
    "primary_language",
    "primary_platform",
    "profile_url",
    "stable_creator_id",
    "followers_or_subscribers",
    "last_content_date",
    "recent_content_url",
    "content_count_30d",
    "longform_count_60d",
    "monetization_signal",
    "monetization_evidence_url",
    "incubrix_need",
    "need_evidence_url",
    "best_channel",
    "channel_handle_or_url",
    "channel_evidence_url",
    "backup_channel",
    "personalization_hook",
    "first_message",
    "checked_date",
    "priority",
    "lead_score",
    "candidate_status",
    "rejection_reason",
    "duplicate_check",
    "completeness_check",
]

# Allowed values from the workbook's 02_LEADS dropdowns. Segment and country lists
# live in config.yaml because the caps stage also uses them.
CHANNELS = [
    "Email",
    "LinkedIn",
    "Instagram",
    "X",
    "YouTube",
    "TikTok",
    "Community",
    "Podcast guest pitch",
    "Contact form",
    "Partner referral",
    "Other",
]  # best_channel and backup_channel
PRIORITIES = ["A", "B", "C"]
CANDIDATE_STATUSES = ["Qualified", "Rejected"]


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
