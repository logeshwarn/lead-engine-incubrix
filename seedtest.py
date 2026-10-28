"""Seed test (Phase 6): send the engine's sequences to test accounts the owner controls, on 3 channels.

Proves scheduling, tracked links and reply logging (brief Phase 6). It never contacts a creator:
every recipient comes from the SEED_* settings in .env, which name the owner's own test accounts.

    python seedtest.py plan    --out output/ --leads 3   # schedule the messages of 3 Priority A leads
    python seedtest.py send    --out output/             # send due emails; print due LinkedIn/Instagram messages
    python seedtest.py mark    --out output/ ID sent     # log a hand-sent message (or: ID reply)
    python seedtest.py clicks  --out output/             # run the click tracker (tracked links point here)
    python seedtest.py replies --out output/             # log email replies found in the sender's inbox
    python seedtest.py report  --out output/             # write <out>/seed_test/seed_report.md

Email is sent automatically by SMTP. LinkedIn and Instagram are sent by hand (their rules forbid
automated messages): the tool prints each due message with its tracked link, the owner sends it to
their own second account, then marks it sent or replied, and saves screenshots.
"""

import argparse
import email
import imaplib
import os
import smtplib
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import make_msgid
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from engine import draft
from engine.common import load_config

SEED_COLUMNS = ["seed_id", "lead_id", "creator_name", "step", "channel", "recipient", "send_at", "subject",
                "message", "tracked_url", "sent_at", "message_id"]  # fmt: skip
MANUAL = {"LinkedIn", "Instagram"}
CLICK_PORT = 8765


def now():
    return datetime.now(timezone.utc)


def recipients():
    """The owner's own test accounts, from .env. Nothing else can ever be a recipient."""
    load_dotenv()
    to = {"Email": os.getenv("SEED_TO_EMAIL", ""), "LinkedIn": os.getenv("SEED_LINKEDIN_TO", ""),
          "Instagram": os.getenv("SEED_INSTAGRAM_TO", "")}  # fmt: skip
    missing = [k for k, v in to.items() if not v]
    if missing:
        raise SystemExit(f"Set the test recipients in .env first: {', '.join(missing)} (see .env.example)")
    return to


def tracked(seed_id):
    return f"http://localhost:{CLICK_PORT}/c/{seed_id}"


def with_link(text, seed_id):
    """The message with its tracked link added before the sign-off (seed test only)."""
    return (
        text.replace("\n\nThanks,", f"\n\nMore about IncuBrix: {tracked(seed_id)}\n\nThanks,", 1)
        if "\n\nThanks," in text
        else f"{text} {tracked(seed_id)}"
    )


def connect(out):
    conn = sqlite3.connect(Path(out) / "engine.db", timeout=60)
    conn.execute("CREATE TABLE IF NOT EXISTS seed_events (at TEXT, seed_id TEXT, event TEXT, detail TEXT)")
    return conn


def plan(out, n_leads, config):
    """Schedule the email sequence and one LinkedIn and one Instagram message for n Priority A leads.

    One sequence day becomes `seed_test.minutes_per_day` minutes, so day 4 and day 9 arrive the same evening.
    """
    to = recipients()
    conn = connect(out)
    drafted = pd.read_sql("SELECT * FROM drafted WHERE priority = 'A'", conn).head(n_leads)
    drafted = drafted.astype(object).where(drafted.notna(), None)
    minutes, start, rows = config["seed_test"]["minutes_per_day"], now(), []
    for r in drafted.to_dict("records"):
        steps = [("first", 0, r["first_message"], r["first_subject"]),
                 ("follow_up_1", r["follow_up_1_day"], r["follow_up_1"], None),
                 ("follow_up_2", r["follow_up_2_day"], draft.follow_up(r, 2, "Email", config), None)]  # fmt: skip
        if r["first_channel"] != "Email":  # the email test needs email text even when the best channel is a form
            steps[0] = (
                "first",
                0,
                draft.first_message(r, "Email", config)[1],
                draft.first_message(r, "Email", config)[0],
            )
            steps[1] = ("follow_up_1", r["follow_up_1_day"], draft.follow_up(r, 1, "Email", config), None)
        for step, day, text, subject in steps:
            rows.append((r, step, "Email", int(day), text, subject or f"Re: {r['first_subject'] or r['creator_name']}"))
        for channel in sorted(MANUAL):
            rows.append((r, "first", channel, 0, draft.first_message(r, channel, config)[1], None))
    out_rows = []
    for n, (r, step, channel, day, text, subject) in enumerate(rows, 1):
        seed_id = f"S{n:03d}"
        out_rows.append({"seed_id": seed_id, "lead_id": r["platform_id"], "creator_name": r["creator_name"],
                         "step": step, "channel": channel, "recipient": to[channel],
                         "send_at": (start + timedelta(minutes=day * minutes)).isoformat(), "subject": subject,
                         "message": with_link(text, seed_id), "tracked_url": tracked(seed_id), "sent_at": None,
                         "message_id": None})  # fmt: skip
    pd.DataFrame(out_rows, columns=SEED_COLUMNS).to_sql("seed_schedule", conn, if_exists="replace", index=False)
    conn.execute("DELETE FROM seed_events")
    conn.commit()
    print(f"scheduled {len(out_rows)} messages for {len(drafted)} Priority A leads; 1 sequence day = {minutes} min")


def log_event(conn, seed_id, event, detail=""):
    conn.execute("INSERT INTO seed_events VALUES (?, ?, ?, ?)", (now().isoformat(), seed_id, event, detail))
    conn.commit()


def send(out):
    """Send every due email (SMTP); print every due manual message for the owner to send by hand."""
    to = recipients()
    conn = connect(out)
    due = pd.read_sql("SELECT * FROM seed_schedule WHERE sent_at IS NULL AND send_at <= ?", conn,
                      params=(now().isoformat(),))  # fmt: skip
    emails = due[due["channel"] == "Email"]
    if len(emails):
        host = os.getenv("SEED_SMTP_HOST") or "smtp.gmail.com"  # blank in .env means Gmail
        port = int(os.getenv("SEED_SMTP_PORT") or "587")
        user, password = os.getenv("SEED_SMTP_USER", ""), os.getenv("SEED_SMTP_PASSWORD", "")
        with smtplib.SMTP(host, port, timeout=30) as smtp:
            smtp.starttls()
            smtp.login(user, password)
            for r in emails.to_dict("records"):
                if r["recipient"] != to["Email"]:  # belt and braces: only the owner's test inbox
                    raise SystemExit(f"refusing to send {r['seed_id']} to {r['recipient']}")
                msg = EmailMessage()
                msg["From"], msg["To"], msg["Subject"] = user, r["recipient"], r["subject"]
                msg["Message-ID"] = make_msgid(domain="leadengine.seedtest")
                msg.set_content(r["message"])
                smtp.send_message(msg)
                conn.execute("UPDATE seed_schedule SET sent_at = ?, message_id = ? WHERE seed_id = ?",
                             (now().isoformat(), msg["Message-ID"], r["seed_id"]))  # fmt: skip
                log_event(conn, r["seed_id"], "sent", f"Email to {r['recipient']}")
                print(f"sent {r['seed_id']} {r['step']} for {r['creator_name']}")
    for r in due[due["channel"].isin(MANUAL)].to_dict("records"):
        print(f"\n--- {r['seed_id']}: send by hand on {r['channel']} to {r['recipient']} ---\n{r['message']}\n"
              f"then: python seedtest.py mark --out {out} {r['seed_id']} sent")  # fmt: skip
    pending = conn.execute("SELECT COUNT(*) FROM seed_schedule WHERE sent_at IS NULL").fetchone()[0]
    print(f"\n{len(emails)} emails sent now; {pending} messages not sent yet (run send again later)")


def mark(out, seed_id, event):
    conn = connect(out)
    if event == "sent":
        conn.execute("UPDATE seed_schedule SET sent_at = ? WHERE seed_id = ?", (now().isoformat(), seed_id))
    log_event(conn, seed_id, event, "logged by hand")
    print(f"{seed_id}: {event} logged")


def click_handler(out):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            seed_id = self.path.rsplit("/", 1)[-1]
            log_event(connect(out), seed_id, "click", self.headers.get("User-Agent", ""))
            self.send_response(302)
            self.send_header("Location", "https://www.incubrix.com/")
            self.end_headers()

        def log_message(self, *args):  # quiet: the click is logged in the database instead
            pass

    return Handler


def clicks(out):
    print(f"click tracker on http://localhost:{CLICK_PORT} (Ctrl+C to stop); clicks go to seed_events")
    HTTPServer(("127.0.0.1", CLICK_PORT), click_handler(out)).serve_forever()


def replies(out):
    """Log replies in the sender's inbox whose In-Reply-To or References name a seed message."""
    load_dotenv()
    conn = connect(out)
    ids = dict(conn.execute("SELECT message_id, seed_id FROM seed_schedule WHERE message_id IS NOT NULL").fetchall())
    seen = {d for (d,) in conn.execute("SELECT detail FROM seed_events WHERE event = 'reply'")}
    imap = imaplib.IMAP4_SSL(os.getenv("SEED_IMAP_HOST") or "imap.gmail.com")
    imap.login(os.getenv("SEED_SMTP_USER", ""), os.getenv("SEED_SMTP_PASSWORD", ""))
    imap.select("INBOX", readonly=True)
    _, data = imap.search(None, "SINCE", (now() - timedelta(days=2)).strftime("%d-%b-%Y"))
    found = 0
    for num in data[0].split():
        _, msg_data = imap.fetch(num, "(BODY.PEEK[HEADER])")
        head = email.message_from_bytes(msg_data[0][1])
        refs = f"{head.get('In-Reply-To', '')} {head.get('References', '')}"
        for message_id, seed_id in ids.items():
            detail = f"reply {head.get('Message-ID')} from {head.get('From')}"
            if message_id in refs and detail not in seen:
                log_event(conn, seed_id, "reply", detail)
                seen.add(detail)
                found += 1
    imap.logout()
    print(f"{found} new replies logged")


def report(out):
    conn = connect(out)
    sched = pd.read_sql("SELECT * FROM seed_schedule", conn)
    sched = sched.astype(object).where(sched.notna(), None)  # unsent rows: None, not NaN
    events = pd.read_sql("SELECT * FROM seed_events", conn)
    folder = Path(out) / "seed_test"
    folder.mkdir(exist_ok=True)
    sched.to_csv(folder / "seed_schedule.csv", index=False, encoding="utf-8")
    events.to_csv(folder / "seed_events.csv", index=False, encoding="utf-8")
    lines = ["# Seed test report", "", f"Generated {now().isoformat()} from seed_schedule and seed_events.", "",
             "| channel | scheduled | sent | clicks | replies |", "|---|---|---|---|---|"]  # fmt: skip
    for channel in ["Email", "LinkedIn", "Instagram"]:
        ids = set(sched.loc[sched["channel"] == channel, "seed_id"])
        ev = events[events["seed_id"].isin(ids)]
        lines.append(f"| {channel} | {len(ids)} | {sched.loc[sched['channel'] == channel, 'sent_at'].notna().sum()} "
                     f"| {(ev['event'] == 'click').sum()} | {(ev['event'] == 'reply').sum()} |")  # fmt: skip
    lines += ["", "## Schedule vs. sent", "", "| seed | channel | step | planned | sent |", "|---|---|---|---|---|"]
    lines += [f"| {r.seed_id} | {r.channel} | {r.step} | {r.send_at[:16]} | {(r.sent_at or '')[:16]} |"
              for r in sched.itertuples()]  # fmt: skip
    lines += ["", "Screenshots of each channel are saved by hand in this folder (see docs/WORKFLOW.md)."]
    (folder / "seed_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {folder / 'seed_report.md'}")


def main(argv=None):
    p = argparse.ArgumentParser(description="Seed test: send the engine's sequences to your own test accounts.")
    p.add_argument("command", choices=["plan", "send", "mark", "clicks", "replies", "report"])
    p.add_argument("args", nargs="*", help="for mark: SEED_ID sent|reply")
    p.add_argument("--out", default="output/", help="the run's output folder (default: output/)")
    p.add_argument("--leads", type=int, default=3, help="for plan: how many Priority A leads (default 3)")
    a = p.parse_args(argv)
    config = load_config()
    if a.command == "plan":
        plan(a.out, a.leads, config)
    elif a.command == "send":
        send(a.out)
    elif a.command == "mark":
        if len(a.args) != 2 or a.args[1] not in ("sent", "reply"):
            p.error("mark needs SEED_ID and sent|reply")
        mark(a.out, *a.args)
    elif a.command == "clicks":
        clicks(a.out)
    elif a.command == "replies":
        replies(a.out)
    else:
        report(a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
