"""Stage 8, draft: the `routed` table -> the `drafted` table, outreach messages for every lead.

Every lead gets a first message on its best channel. Priority A leads also get 2 follow-ups: the
first on the same channel, the second on the backup channel (brief section 6).

Messages are templates filled only with the lead's own verified facts: its latest item's title,
the gap verify measured (no transcripts, no clips, upload gaps, or the creator's own words), its
segment and its channel. Nothing is generated freely, so nothing can be invented (decision
2026-10-28, deadline plan). The pitch, call to action and sender come from config.yaml (`draft`,
`sender`) so the owner can change the wording without touching code.

Each message is checked automatically: it cites the recent item, names the sender, has an opt-out,
fits the channel's length limit, never claims the sender works for IncuBrix, and has no unfilled
placeholder. The email postal address is a placeholder until launch (DECISIONS.md): flagged, not failed.
"""

import json
import logging
import re

import pandas as pd

from engine.route import ROUTE_COLUMNS
from engine.score import SCORED_COLUMNS

log = logging.getLogger("draft")

DRAFT_COLUMNS = [
    "personalization_hook",
    "first_channel",
    "first_subject",  # email only
    "first_message",
    "follow_up_1_channel",
    "follow_up_1_day",
    "follow_up_1",
    "follow_up_2_channel",
    "follow_up_2_day",
    "follow_up_2",
    "draft_checks",  # JSON: every check of every message, so a failure can be traced
    "draft_ok",
]
DRAFTED_COLUMNS = SCORED_COLUMNS + ROUTE_COLUMNS + DRAFT_COLUMNS

DM_CHANNELS = {"LinkedIn", "Instagram", "X", "TikTok"}  # sent by hand: platforms forbid bulk automation
FORM_CHANNELS = {"Contact form", "Podcast guest pitch"}
OPT_OUT = re.compile(r"won't (contact|message|email|follow up with) you again", re.I)
EMPLOYEE_CLAIM = re.compile(
    r"\b(i|we) (work|am working|are working) (at|for) incubrix|incubrix team|on behalf of incubrix", re.I
)
SEGMENT_ANGLE = {
    "Podcaster/Video Podcaster": "For a show like yours, that could mean each episode reaching people who never "
    "open a podcast app.",
    "YouTuber/Video-First Creator": "For a channel like yours, that could mean Shorts and posts from every long video "
    "without extra editing hours.",
    "Expert-Led Creator": "For a coach or educator, that could mean more of your expertise in front of future "
    "clients, from content you already make.",
}


def noun(row):
    return "video" if row["platform"] == "youtube" else "episode"


def short_title(title, limit):
    """The title, cut at a word boundary to fit `limit` characters (with an ellipsis when cut)."""
    title = re.sub(r"\s+", " ", title or "").strip()
    if len(title) <= limit:
        return title
    cut = title[: limit - 1]
    cut = cut[: cut.rfind(" ")] if " " in cut else cut
    return cut.rstrip(" ,.:;-|") + "…"


def need_sentence(row):
    """One sentence on the gap verify found, in the lead's own numbers. Never more than the evidence says."""
    kind, summary, n = row["need_kind"], row["incubrix_need"] or "", noun(row)
    found = re.search(r"(\d+)", summary)
    count = found.group(1) if found else "{N}"  # "{N}" only in the rendered templates
    if kind == "captions":
        return (f"I noticed none of your last {count} {n}s has a transcript, so what you say there "
                f"can't be found in search or read by people who can't listen.")  # fmt: skip
    if kind == "repurposing":
        return (f"You've published {count} long {n}s in the last two months, but I couldn't find clips "
                f"or a video version bringing new people to them.")  # fmt: skip
    if kind == "consistency":
        return (f"I noticed a {count}-day gap between uploads recently; a steady schedule is hard when "
                f"you edit everything yourself.")  # fmt: skip
    return f'You mentioned "{(row["need_evidence"] or "").strip()}", which is exactly the problem this is for.'


def short_need(row):
    """The same gap in a few words, for follow-ups and DMs."""
    n = noun(row)
    return {
        "captions": f"no transcripts on your recent {n}s",
        "repurposing": f"no clips or video version of your long {n}s",
        "consistency": "keeping a steady upload schedule",
    }.get(row["need_kind"], "the problem you mentioned")


def sign_off(sender):
    description = sender["description"]
    return f"{sender['name']}\n{description[:1].upper()}{description[1:]}"


def first_message(row, channel, config):
    d, sender = config["draft"], config["sender"]
    title = short_title(row["recent_content_title"], d["title_chars"])
    if channel in DM_CHANNELS:
        title = short_title(row["recent_content_title"], d["dm_title_chars"])
        body = (f'Hi! I came across "{title}". I\'m {sender["name"]}, a {sender["description"]}, talking to creators '
                f"about IncuBrix, which helps with things like {short_need(row)}. Open to a quick chat? If not, say no "
                f"and I won't message you again.")  # fmt: skip
        return None, body
    opening = f'I came across your recent {noun(row)} "{title}". {need_sentence(row)}'
    if channel == "Podcast guest pitch":
        opening = "I know this page is for guest ideas; this is a different kind of note. " + opening
    body = (f"Hi,\n\n{opening}\n\n{d['pitch']} {SEGMENT_ANGLE.get(row['creator_segment'], '')}\n\n"
            f"{d['call_to_action']}\n\nThanks,\n{sign_off(sender)}\n\n"
            f"Not useful? Reply \"no thanks\" and I won't contact you again.")  # fmt: skip
    if channel == "Email":
        body += f"\n{sender['postal_address']}"  # CAN-SPAM: a postal address in commercial email
        return f'"{title}": a quick idea', body
    return None, body


def follow_up(row, number, channel, config):
    d, sender = config["draft"], config["sender"]
    title = short_title(
        row["recent_content_title"], d["dm_title_chars"] if channel in DM_CHANNELS else d["title_chars"]
    )
    if number == 1:
        text = (f'Hi again, a quick follow-up on my note about "{title}" and {short_need(row)}. '
                f"{d['follow_up_offer']}")  # fmt: skip
    else:
        text = (f'Hi, I wrote earlier about "{title}" and {short_need(row)}, and how IncuBrix could take that work '
                f"off your plate. This is my last note.")  # fmt: skip
    if channel in DM_CHANNELS:
        return f"{text} {sender['name']}. If it's not for you, say no and I won't message you again."
    text = f'{text}\n\n{sign_off(sender)}\n\nNot useful? Reply "no thanks" and I won\'t contact you again.'
    if channel == "Email":
        text += f"\n{sender['postal_address']}"
    return text


def check_message(text, row, channel, config):
    """Every automatic check on one message, as {check: True/False or a note}."""
    d, sender = config["draft"], config["sender"]
    limit = d["max_chars"].get(channel, d["max_chars"]["default"])
    placeholder = sender["postal_address"]
    title_part = short_title(row["recent_content_title"], d["dm_title_chars"]).rstrip("…")[:30]
    unfilled = re.findall(r"\{[a-z_]+\}", text.replace(placeholder, ""))
    return {
        "content_reference": title_part.lower() in text.lower(),
        "sender_named": sender["name"] in text,
        "opt_out": bool(OPT_OUT.search(text)),
        "length": len(text) <= limit,
        "not_an_employee_claim": not EMPLOYEE_CLAIM.search(text),
        "no_unfilled_placeholder": not unfilled,
        "postal_address": "placeholder: fill before real sending" if placeholder in text else "n/a",
    }


def passed(checks):
    return all(v for v in checks.values() if isinstance(v, bool))


def draft_lead(row, config):
    """The drafted fields for one qualified lead."""
    best, backup = row["best_channel"], row["backup_channel"]
    subject, first = first_message(row, best, config)
    out = {
        "personalization_hook": f'Recent {noun(row)} "{row["recent_content_title"]}" ({row["last_content_date"]}); '
        f"{row['incubrix_need']}",
        "first_channel": best,
        "first_subject": subject,
        "first_message": first,
    }
    checks = {"first_message": check_message(first, row, best, config)}
    if row["priority"] == "A":
        days = config["draft"]["follow_up_days"]
        out.update(
            follow_up_1_channel=best,
            follow_up_1_day=days[0],
            follow_up_1=follow_up(row, 1, best, config),
            follow_up_2_channel=backup,
            follow_up_2_day=days[1],
            follow_up_2=follow_up(row, 2, backup, config),
        )
        checks["follow_up_1"] = check_message(out["follow_up_1"], row, best, config)
        checks["follow_up_2"] = check_message(out["follow_up_2"], row, backup, config)
    out["draft_checks"] = json.dumps(checks)
    out["draft_ok"] = all(passed(c) for c in checks.values())
    return out


def draft(routed, config):
    out = routed.astype(object).where(routed.notna(), None)
    for col in DRAFT_COLUMNS:
        out[col] = None
    for i, row in out[out["candidate_status"] == "Qualified"].iterrows():
        for col, value in draft_lead(row, config).items():
            out.at[i, col] = value
    return out[DRAFTED_COLUMNS]


def run(conn, config):
    routed = pd.read_sql("SELECT * FROM routed", conn)
    drafted = draft(routed, config)
    drafted.to_sql("drafted", conn, if_exists="replace", index=False)
    q = drafted[drafted["candidate_status"] == "Qualified"]
    failed = q[~q["draft_ok"].astype(bool)]
    a = q[q["priority"] == "A"]
    log.info("%d first messages, %d Priority A sequences, %d leads with a failed check", len(q), len(a), len(failed))
    for r in failed.itertuples():
        bad = {m: [k for k, v in c.items() if v is False] for m, c in json.loads(r.draft_checks).items()}
        log.error("draft check failed for %s: %s", r.platform_id, {m: k for m, k in bad.items() if k})
    return drafted
