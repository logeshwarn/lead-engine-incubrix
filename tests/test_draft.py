"""draft: messages built only from the lead's facts, and every message checked."""

import json

import pandas as pd

from engine import draft


def lead(priority="A", best="Email", backup="Contact form", need="captions", platform="podcast",
         title="How We Grew to 10k Listeners Without Ads", segment="Podcaster/Video Podcaster"):  # fmt: skip
    r = dict.fromkeys(draft.DRAFTED_COLUMNS)
    summaries = {
        "captions": "Captions: none of the last 12 episodes have a transcript",
        "repurposing": "Repurposing: 9 long episodes and no YouTube or TikTok link on feed or site",
        "consistency": "Consistency: 24-day gap between uploads before 2026-10-01",
        "own words": "Creator says: looking for an editor",
    }
    r.update(platform="podcast" if platform == "podcast" else "youtube", platform_id="p1", creator_name="Jane Show",
             creator_segment=segment, recent_content_title=title, last_content_date="2026-10-27", need_kind=need,
             incubrix_need=summaries[need], need_evidence="looking for an editor", priority=priority,
             best_channel=best, backup_channel=backup, candidate_status="Qualified")  # fmt: skip
    return r


def run(config, rows):
    return draft.draft(pd.DataFrame(rows, columns=draft.DRAFTED_COLUMNS), config)


def test_priority_a_gets_a_full_sequence_that_passes(config):
    out = run(config, [lead()]).iloc[0]
    assert out.draft_ok and out.first_channel == "Email" and out.first_subject
    assert (out.follow_up_1_channel, out.follow_up_2_channel) == ("Email", "Contact form")
    checks = json.loads(out.draft_checks)
    assert set(checks) == {"first_message", "follow_up_1", "follow_up_2"}
    assert checks["first_message"]["postal_address"] == "placeholder: fill before real sending"


def test_b_lead_gets_a_first_message_only(config):
    out = run(config, [lead(priority="B")]).iloc[0]
    assert out.first_message and out.follow_up_1 is None and out.follow_up_2 is None


def test_message_cites_the_recent_item_and_the_measured_gap(config):
    msg = run(config, [lead()]).iloc[0].first_message
    assert '"How We Grew to 10k Listeners Without Ads"' in msg
    assert "none of your last 12 episodes has a transcript" in msg
    assert "Logeshwaran" in msg and "won't contact you again" in msg


def test_each_need_kind_has_its_own_sentence(config):
    out = run(config, [lead(need=k) for k in ("captions", "repurposing", "consistency", "own words")])
    assert out["first_message"].str.contains("transcript").iloc[0]
    assert out["first_message"].str.contains("9 long episodes").iloc[1]
    assert out["first_message"].str.contains("24-day gap").iloc[2]
    assert out["first_message"].str.contains('"looking for an editor"').iloc[3]
    assert out["draft_ok"].all()


def test_linkedin_message_fits_300_characters(config):
    long_title = "A Very Long Episode Title About Building Sustainable Habits For Busy Founders And Their Teams"
    out = run(config, [lead(best="LinkedIn", title=long_title, priority="B")]).iloc[0]
    assert len(out.first_message) <= 300 and out.draft_ok
    assert out.first_subject is None  # only email has a subject


def test_long_titles_are_cut_at_a_word():
    assert draft.short_title("Your Greatest Asset Isn't in Your Bank Account", 30) == "Your Greatest Asset Isn't in…"


def test_checks_catch_a_bad_message(config):
    row = lead()
    bad = "Hi, I work at IncuBrix and want to sell you editing. {first_name}"
    checks = draft.check_message(bad, row, "Email", config)
    assert checks["content_reference"] is False and checks["sender_named"] is False
    assert checks["opt_out"] is False and checks["not_an_employee_claim"] is False
    assert checks["no_unfilled_placeholder"] is False and not draft.passed(checks)


def test_guest_pitch_page_says_it_is_not_a_guest_pitch(config):
    msg = run(config, [lead(best="Podcast guest pitch", priority="B")]).iloc[0].first_message
    assert msg.startswith("Hi,\n\nI know this page is for guest ideas")


def test_run_writes_table(conn, config):
    pd.DataFrame([lead()], columns=draft.DRAFTED_COLUMNS[: -len(draft.DRAFT_COLUMNS)]).to_sql(
        "routed", conn, index=False
    )
    draft.run(conn, config)
    assert list(pd.read_sql("SELECT * FROM drafted", conn).columns) == draft.DRAFTED_COLUMNS
