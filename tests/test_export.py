"""export: rejected.csv lists every rejected creator with a reason."""

import pandas as pd
import pytest

from engine import draft, export
from engine.common import LEADS_COLUMNS, now_utc
from engine.dedupe import DEDUPED_COLUMNS


def capped_rows(rows):
    out = []
    for i, (status, reason) in enumerate(rows):
        r = dict.fromkeys(DEDUPED_COLUMNS)
        r.update(platform="podcast", platform_id=f"p{i}", creator_name=f"Creator {i}",
                 candidate_status=status, rejection_reason=reason)  # fmt: skip
        out.append(r)
    return pd.DataFrame(out, columns=DEDUPED_COLUMNS)


def test_rejected_csv_has_every_rejected_row_and_reason(conn, tmp_path):
    rows = [("Qualified", None), ("Rejected", "country not evidenced"), ("Rejected", "cap: US above 60% of leads")]
    capped_rows(rows).to_sql("capped", conn, index=False)
    assert export.write_rejected(conn, tmp_path) == 2
    csv = pd.read_csv(tmp_path / "rejected.csv")
    assert list(csv.columns) == export.REJECTED_COLUMNS
    assert csv["platform_id"].tolist() == ["p1", "p2"]  # the qualified row is not in it
    assert csv["rejection_reason"].notna().all()


def test_rejection_without_reason_fails_loudly(conn, tmp_path):
    capped_rows([("Rejected", None)]).to_sql("capped", conn, index=False)
    with pytest.raises(ValueError, match="no rejection_reason"):
        export.write_rejected(conn, tmp_path)


# ---------- leads.csv, outreach/ and run_report.md (2026-10-28) ----------


def drafted_rows(config):
    base = dict.fromkeys(draft.DRAFTED_COLUMNS[: -len(draft.DRAFT_COLUMNS)])
    rows = []
    for i, prio in enumerate(["A", "B"]):
        r = {**base}
        r.update(platform="podcast", platform_id=f"itunes:{i}", stable_creator_id=f"itunes:{i}",
                 creator_name=f"Show {i}", creator_segment="Podcaster/Video Podcaster", country_iso2="GB",
                 primary_language="en", profile_url=f"https://p/{i}", last_content_date="2026-10-27",
                 recent_content_url=f"https://p/{i}/ep", recent_content_title="A Recent Episode Title",
                 content_count_30d=4, longform_count_60d=8, monetization_signal="Service",
                 monetization_evidence_url="https://site", need_kind="captions",
                 incubrix_need="Captions: none of the last 9 episodes have a transcript",
                 need_evidence_url=f"https://p/{i}/ep", best_channel="Email", channel_handle_or_url="a@b.com",
                 channel_evidence_url="https://site/contact", backup_channel="Contact form",
                 backup_handle_or_url="https://site/contact", backup_evidence_url="https://site/contact",
                 checked_date="2026-10-28", priority=prio, lead_score=80, candidate_status="Qualified")  # fmt: skip
        rows.append(r)
    rows.append({**base, "platform_id": "itunes:9", "candidate_status": "Rejected", "rejection_reason": "no contact"})
    return draft.draft(pd.DataFrame(rows, columns=draft.DRAFTED_COLUMNS[: -len(draft.DRAFT_COLUMNS)]), config)


def load_tables(conn, config):
    d = drafted_rows(config)
    d.to_sql("drafted", conn, index=False)
    d[DEDUPED_COLUMNS].to_sql("capped", conn, index=False)
    d[["candidate_status", "rejection_reason"]].to_sql("verified", conn, index=False)
    pd.DataFrame({"platform_id": ["itunes:0", "itunes:1", "itunes:9"]}).to_sql("candidates", conn, index=False)
    pd.DataFrame([["countries", 1, ">= 3", 0]], columns=["rule", "value", "limit", "passed"]).to_sql(
        "cap_checks", conn, index=False
    )


def test_export_writes_leads_outreach_and_report(conn, config, tmp_path):
    load_tables(conn, config)
    export.run(conn, config, tmp_path, now_utc().isoformat(), 12.0, None, ["countries is 1, needs >= 3"])
    leads = pd.read_csv(tmp_path / "leads.csv")
    assert list(leads.columns) == LEADS_COLUMNS and leads["lead_id"].tolist() == ["itunes:0", "itunes:1"]
    assert leads["first_message"].str.startswith("Subject: ").all()
    assert set(leads["completeness_check"]) == {"complete (followers_or_subscribers: audience size not public)"}
    seq = pd.read_csv(tmp_path / "outreach" / "sequences.csv")
    assert len(seq) == 3 + 1  # A: first + 2 follow-ups; B: first only
    assert seq.loc[seq["step"] == "follow_up_2", "to"].tolist() == ["https://site/contact"]
    assert len(list((tmp_path / "outreach" / "A").glob("*.md"))) == 1
    assert "## Podcaster/Video Podcaster: LinkedIn" in (tmp_path / "outreach" / "templates.md").read_text("utf-8")
    report = (tmp_path / "run_report.md").read_text("utf-8")
    assert (
        "**Result: FAILED: countries is 1, needs >= 3**" in report
        and "Final leads (after dedupe and caps): 2" in report
    )


def test_duplicate_lead_id_stops_the_export(conn, config, tmp_path):
    load_tables(conn, config)
    conn.execute("UPDATE drafted SET platform_id = 'itunes:0' WHERE platform_id = 'itunes:1'")
    with pytest.raises(ValueError, match="duplicate lead_id"):
        export.run(conn, config, tmp_path, now_utc().isoformat(), 1.0, None, [])
