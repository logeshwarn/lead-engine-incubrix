"""seedtest: only the owner's test accounts, scheduled sends, tracked links and logged replies."""

import pandas as pd
import pytest

import seedtest
from engine import draft
from tests.test_export import drafted_rows


@pytest.fixture
def seeded(conn, config, tmp_path, monkeypatch):
    monkeypatch.setenv("SEED_TO_EMAIL", "me.test@gmail.com")
    monkeypatch.setenv("SEED_LINKEDIN_TO", "My Test Profile")
    monkeypatch.setenv("SEED_INSTAGRAM_TO", "@my_test_account")
    monkeypatch.setenv("SEED_SMTP_USER", "me.sender@gmail.com")
    monkeypatch.setenv("SEED_SMTP_PASSWORD", "not-a-real-password")
    monkeypatch.setattr(seedtest, "load_dotenv", lambda: None)  # the test values above, not the real .env
    out = tmp_path / "out"
    out.mkdir()
    db = seedtest.connect(out)
    drafted_rows(config).to_sql("drafted", db, index=False)
    seedtest.plan(out, 1, config)
    return out, db


def test_plan_schedules_three_channels_to_test_accounts_only(seeded):
    out, db = seeded
    s = pd.read_sql("SELECT * FROM seed_schedule", db)
    assert sorted(s["channel"].value_counts().to_dict().items()) == [("Email", 3), ("Instagram", 1), ("LinkedIn", 1)]
    assert set(s["recipient"]) == {"me.test@gmail.com", "My Test Profile", "@my_test_account"}
    assert s["message"].str.contains("http://localhost:8765/c/S").all()  # every message has its tracked link
    days = (pd.to_datetime(s.loc[s["channel"] == "Email", "send_at"]).diff().dt.total_seconds() / 60).tolist()[1:]
    assert days == [8.0, 10.0]  # day 4 and day 9 at 2 minutes per day


def test_send_emails_only_due_messages(seeded, monkeypatch):
    out, db = seeded
    sent = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            assert (host, port) == ("smtp.gmail.com", 587)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def starttls(self):
            pass

        def login(self, user, password):
            pass

        def send_message(self, msg):
            sent.append(msg["To"])

    monkeypatch.setattr(seedtest.smtplib, "SMTP", FakeSMTP)
    seedtest.send(out)
    assert sent == ["me.test@gmail.com"]  # only the day-0 email is due; follow-ups wait for their time
    events = pd.read_sql("SELECT * FROM seed_events", db)
    assert events["event"].tolist() == ["sent"]


def test_mark_and_report(seeded):
    out, db = seeded
    seedtest.mark(out, "S004", "sent")
    seedtest.mark(out, "S004", "reply")
    seedtest.log_event(db, "S001", "click", "test")
    seedtest.report(out)
    report = (out / "seed_test" / "seed_report.md").read_text("utf-8")
    assert "| Email | 3 | 0 | 1 | 0 |" in report
    assert "| Instagram | 1 | 1 | 0 | 1 |" in report


def test_missing_recipients_stop_the_plan(conn, config, tmp_path, monkeypatch):
    monkeypatch.setattr(seedtest, "load_dotenv", lambda: None)
    for key in ("SEED_TO_EMAIL", "SEED_LINKEDIN_TO", "SEED_INSTAGRAM_TO"):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(SystemExit, match="Set the test recipients"):
        seedtest.plan(tmp_path, 1, config)


def test_tracked_link_goes_before_sign_off():
    text = draft.follow_up(
        {"recent_content_title": "T", "need_kind": "captions", "platform": "podcast"}, 1, "Contact form",
        {"draft": {"title_chars": 70, "dm_title_chars": 40, "follow_up_offer": "x"},
         "sender": {"name": "N", "description": "d", "postal_address": "{p}"}},
    )  # fmt: skip
    assert "localhost:8765/c/S001" in seedtest.with_link(text, "S001")
