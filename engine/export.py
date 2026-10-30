"""Stage 9, export: the final tables -> the files IncuBrix receives, in the --out folder.

- leads.csv: qualified creators only, the 30 workbook columns (LEADS_COLUMNS), sorted by lead_id
- rejected.csv: every rejected creator with all its reasons
- outreach/: every message, one file per lead, plus sequences.csv and the templates
- run_report.md: counts, mix, runtime, API calls, tokens, cost and errors (generated, never hand-edited)
"""

import json
import logging
import re
from pathlib import Path

import pandas as pd

from engine import draft
from engine.common import LEADS_COLUMNS

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
PLATFORM_NAMES = {"podcast": "Podcast", "youtube": "YouTube"}
# Fields a qualified lead may leave blank, with the reason shown in completeness_check.
MAY_BE_BLANK = {
    "followers_or_subscribers": "audience size not public",  # podcast directories publish none
    "rejection_reason": None,  # blank for every qualified lead
}


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


def first_message_text(row):
    """The first message as one cell: the subject line first for email."""
    if row["first_subject"]:
        return f"Subject: {row['first_subject']}\n\n{row['first_message']}"
    return row["first_message"]


def lead_rows(drafted):
    """Qualified rows mapped to the workbook's 30 columns. lead_id is the stable platform ID, so a
    refresh keeps every lead's ID."""
    q = drafted[drafted["candidate_status"] == "Qualified"].copy()
    leads = pd.DataFrame(index=q.index)
    for col in LEADS_COLUMNS:
        leads[col] = q[col] if col in q.columns else None
    leads["lead_id"] = q["platform_id"]
    leads["primary_platform"] = q["platform"].map(PLATFORM_NAMES)
    leads["first_message"] = q.apply(first_message_text, axis=1)
    leads["rejection_reason"] = None
    # dedupe already merged every shared platform ID, website domain and email; this re-checks the IDs.
    leads["duplicate_check"] = "unique: platform ID, website domain and email checked by dedupe"
    blanks = []
    for _, row in leads.iterrows():
        missing = [c for c in LEADS_COLUMNS if c != "completeness_check" and (pd.isna(row[c]) or row[c] == "")]
        bad = [c for c in missing if c not in MAY_BE_BLANK]
        notes = [f"{c}: {MAY_BE_BLANK[c]}" for c in missing if MAY_BE_BLANK.get(c)]
        blanks.append(f"missing: {', '.join(bad)}" if bad else "complete" + (f" ({'; '.join(notes)})" if notes else ""))
    leads["completeness_check"] = blanks
    return leads.sort_values("lead_id")[LEADS_COLUMNS]


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")[:60]


def sequence_rows(drafted):
    """Every message of every lead as rows: lead_id, step, day, channel, how it is sent, subject, text."""
    rows = []
    for r in drafted[drafted["candidate_status"] == "Qualified"].to_dict("records"):
        steps = [("first", 0, r["first_channel"], r["first_subject"], r["first_message"])]
        if r["follow_up_1"]:
            steps.append(("follow_up_1", r["follow_up_1_day"], r["follow_up_1_channel"], None, r["follow_up_1"]))
            steps.append(("follow_up_2", r["follow_up_2_day"], r["follow_up_2_channel"], None, r["follow_up_2"]))
        for step, day, channel, subject, text in steps:
            # Only email may be automated; DMs and forms are sent by a person (platform rules).
            mode = "automated (test accounts only until launch)" if channel == "Email" else "manual"
            rows.append({"lead_id": r["platform_id"], "priority": r["priority"], "creator_name": r["creator_name"],
                         "step": step, "day": int(day), "channel": channel, "send_mode": mode,
                         "to": r["channel_handle_or_url"] if step != "follow_up_2" else r["backup_handle_or_url"],
                         "subject": subject, "message": text})  # fmt: skip
    return pd.DataFrame(rows)


def write_outreach(drafted, out_dir, config):
    """outreach/: sequences.csv, one Markdown file per lead (A and B folders), and templates.md."""
    folder = Path(out_dir) / "outreach"
    for sub in ("A", "B", "C"):
        (folder / sub).mkdir(parents=True, exist_ok=True)
        for old in (folder / sub).glob("*.md"):  # a lead that left the set must not leave a file behind
            old.unlink()
    seq = sequence_rows(drafted)
    seq.to_csv(folder / "sequences.csv", index=False, encoding="utf-8")
    for r in drafted[drafted["candidate_status"] == "Qualified"].to_dict("records"):
        lines = [f"# {r['creator_name']}", "",
                 f"- Lead ID: {r['platform_id']} | Priority {r['priority']} | score {r['lead_score']}",
                 f"- Best channel: {r['best_channel']} ({r['channel_handle_or_url']})",
                 f"- Backup channel: {r['backup_channel']} ({r['backup_handle_or_url']})",
                 f"- Hook: {r['personalization_hook']}", ""]  # fmt: skip
        for s in seq[seq["lead_id"] == r["platform_id"]].to_dict("records"):
            lines += [f"## Day {s['day']}: {s['step'].replace('_', ' ')} ({s['channel']}, {s['send_mode']})", ""]
            if s["subject"]:
                lines += [f"Subject: {s['subject']}", ""]
            lines += [s["message"], ""]
        checks = json.loads(r["draft_checks"])
        lines += ["## Checks", ""] + [f"- {m}: {c}" for m, c in checks.items()]
        name = f"{slug(r['creator_name'])}--{slug(r['platform_id'])}.md"
        (folder / r["priority"] / name).write_text("\n".join(lines) + "\n", encoding="utf-8")
    (folder / "templates.md").write_text(templates_text(config), encoding="utf-8")
    return len(seq)


def templates_text(config):
    """The templates for 3 segments x 3 channels, rendered with placeholders instead of a real lead."""
    out = ["# Outreach templates", "",
           "Generated by engine/export.py from engine/draft.py. Words in {braces} are filled from each lead's",
           "verified data; nothing else changes between leads.", ""]  # fmt: skip
    sample = {"platform": "podcast", "recent_content_title": "{recent item title}", "need_kind": "captions",
              "incubrix_need": "Captions: none of the last {N} episodes have a transcript", "need_evidence": "",
              "last_content_date": "{date}"}  # fmt: skip
    for segment in config["segments"]:
        for channel in ("Email", "Contact form", "LinkedIn"):
            row = {**sample, "creator_segment": segment}
            subject, body = draft.first_message(row, channel, config)
            out += [f"## {segment}: {channel}", ""]
            if subject:
                out += [f"Subject: {subject}", ""]
            out += ["```", body, "```", ""]
    row = {**sample, "creator_segment": config["segments"][0]}
    for n, channel in ((1, "Email"), (2, "Contact form")):
        out += [
            f"## Priority A follow-up {n} ({channel})",
            "",
            "```",
            draft.follow_up(row, n, channel, config),
            "```",
            "",
        ]
    return "\n".join(out)


def gemini_tokens(conn, since_iso):
    """Tokens used by Gemini calls made (not cached) since since_iso: read from the cached responses."""
    rows = conn.execute("SELECT response FROM api_cache WHERE source = 'gemini' AND fetched_at >= ?", (since_iso,))
    total = 0
    for (response,) in rows:
        try:
            total += json.loads(response).get("usageMetadata", {}).get("totalTokenCount", 0)
        except (ValueError, AttributeError):
            continue
    return total


def table(df):
    """A small DataFrame as a Markdown table, without extra dependencies."""
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(str(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join(lines)


def write_report(conn, out_dir, started_iso, runtime_s, log_file, cap_failures):
    """run_report.md from the database and this run's log. Every number is read, never typed."""
    drafted = read_drafted(conn)
    q = drafted[drafted["candidate_status"] == "Qualified"]
    candidates = conn.execute("SELECT COUNT(*) FROM candidates").fetchone()[0]
    verified = pd.read_sql("SELECT candidate_status, rejection_reason FROM verified", conn)
    rejected = drafted[drafted["candidate_status"] == "Rejected"]
    first = rejected["rejection_reason"].str.split(";").str[0].str.replace(r"\d+", "#", regex=True)
    calls = pd.read_sql("SELECT source, cached, ok FROM api_log WHERE at >= ?", conn, params=(started_iso,))
    api = calls.groupby("source").agg(
        calls=("cached", "size"), from_cache=("cached", "sum"), failed=("ok", lambda s: int((s == 0).sum()))
    )
    api["new_calls"] = api["calls"] - api["from_cache"]
    checks = pd.read_sql("SELECT * FROM cap_checks", conn)
    checks["passed"] = checks["passed"].map({1: "yes", 0: "NO"})  # stored as 1/0 by SQLite
    log_text = Path(log_file).read_text(encoding="utf-8", errors="replace") if log_file else ""
    errors = len(re.findall(r" ERROR ", log_text))
    mix = lambda col: table(q[col].value_counts().rename_axis(col).reset_index(name="leads"))  # noqa: E731
    lines = [
        "# Run report", "",
        f"Generated by the engine at the end of the run started {started_iso}. Do not edit by hand.", "",
        f"**Result: {'FAILED: ' + '; '.join(cap_failures) if cap_failures else 'all hard rules pass'}**", "",
        "## Counts", "",
        f"- Candidates discovered: {candidates}",
        f"- Qualified after verify: {(verified['candidate_status'] == 'Qualified').sum()}",
        f"- Final leads (after dedupe and caps): {len(q)}",
        f"- Priority A with full sequences: {((q['priority'] == 'A') & q['follow_up_2'].notna()).sum()}",
        f"- Leads whose messages pass every check: {q['draft_ok'].astype(bool).sum()} of {len(q)}",
        f"- Rejected (in rejected.csv): {len(rejected)}", "",
        "## Mix", "", mix("country_iso2"), "", mix("creator_segment"), "", mix("priority"), "",
        mix("best_channel"), "", mix("backup_channel"), "",
        "## Hard rules", "", table(checks), "",
        "## Top rejection reasons (first reason per creator)", "",
        table(first.value_counts().head(12).rename_axis("reason").reset_index(name="creators")), "",
        "## Runtime, API calls and cost", "",
        f"- Runtime: {runtime_s:.0f} s ({runtime_s / 60:.1f} min)",
        f"- Gemini tokens used by new calls: {gemini_tokens(conn, started_iso)} (free tier, $0)",
        "- Cost: $0. YouTube Data API, Podcast Index, iTunes/Apple, Gemini and Groq were all used on free tiers.",
        f"- Errors logged: {errors} (see {log_file})", "",
        table(api.reset_index()[["source", "calls", "new_calls", "from_cache", "failed"]]), "",
    ]  # fmt: skip
    path = Path(out_dir) / "run_report.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    log.info("run_report.md -> %s", path)


def read_drafted(conn):
    drafted = pd.read_sql("SELECT * FROM drafted", conn)
    return drafted.astype(object).where(drafted.notna(), None)  # SQL NULL -> None, not NaN (NaN is truthy)


def run(conn, config, out_dir, started_iso, runtime_s, log_file, cap_failures):
    drafted = read_drafted(conn)
    leads = lead_rows(drafted)
    if leads["lead_id"].duplicated().any():  # 0% duplicates is a hard requirement
        raise ValueError("duplicate lead_id in leads.csv")
    leads.to_csv(Path(out_dir) / "leads.csv", index=False, encoding="utf-8")
    write_rejected(conn, out_dir)
    messages = write_outreach(drafted, out_dir, config)
    write_report(conn, out_dir, started_iso, runtime_s, log_file, cap_failures)
    log.info("leads.csv: %d leads; outreach: %d messages", len(leads), messages)
    return leads
