"""Stage 9, export: final tables -> files in the --out folder.

Built so far: rejected.csv (Phase 2). leads.csv, outreach/ and run_report.md are added in Phase 5.
"""

import logging
from pathlib import Path

import pandas as pd

log = logging.getLogger("export")

# The workbook has no tab for rejected creators, so these columns are ours: enough to find the
# creator again and see why they were left out. Evidence URLs let a reviewer check the reason.
REJECTED_COLUMNS = [
    "platform",
    "platform_id",
    "creator_name",
    "profile_url",
    "website",
    "creator_segment",
    "niche",
    "seed_id",
    "country_iso2",
    "country_evidence_url",
    "rejection_reason",  # every reason found, "; "-separated; the first one is the main one
    "duplicate_of",  # set when dedupe merged this row into another creator
    "checked_date",
]


def write_rejected(conn, out_dir):
    """Write every rejected creator with its reasons to <out>/rejected.csv. Returns the row count."""
    capped = pd.read_sql("SELECT * FROM capped", conn)
    rejected = capped[capped["candidate_status"] == "Rejected"]
    missing = rejected["rejection_reason"].isna().sum()
    if missing:  # a rejection without a reason would break "nothing dropped silently"
        raise ValueError(f"{missing} rejected rows have no rejection_reason")
    path = Path(out_dir) / "rejected.csv"
    rejected[REJECTED_COLUMNS].to_csv(path, index=False, encoding="utf-8")
    log.info("rejected.csv: %d rows -> %s", len(rejected), path)
    return len(rejected)
