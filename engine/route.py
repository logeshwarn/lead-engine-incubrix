"""Stage 7, route: the `scored` table -> the `routed` table, a best and a backup channel per lead.

Each lead needs "the best channel to reach them, a backup channel and the verified public handle or
URL" (assignment section 1). Only channels the creator published for contact are used (verify's
`contacts`), never a guessed address. The rules:

- Best: the creator's best email, else a contact form, else a podcast guest-pitch page. These are
  the channels we can check are presented for business contact. A social link cannot be checked
  for activity (we do not scrape those platforms), so it can only ever be the backup.
- Email order: an address on the creator's own website domain first, role addresses (sales,
  support, a network's producer) last, placeholders (info@mysite.com) never.
- Backup: another checkable channel of a different kind, else one of the creator's own social
  profiles (its handle matches the show or website, or it is the only profile on that platform their
  pages link to: show pages often link guests' and contributors' accounts), else a second email.

`choose` depends only on one lead's contacts, so verify uses it for the "reachable" check: a lead
without both channels is rejected there, before caps and score count it.
"""

import json
import logging
import re

import pandas as pd

log = logging.getLogger("route")

ROUTE_COLUMNS = [
    "best_channel",
    "channel_handle_or_url",
    "channel_evidence_url",
    "backup_channel",
    "backup_handle_or_url",
    "backup_evidence_url",
]
# Order of preference when there is no email, and for the backup.
CHECKABLE = ["Email", "Contact form", "Podcast guest pitch"]
SOCIAL_ORDER = ["LinkedIn", "Instagram", "X", "TikTok"]  # LinkedIn first: expert-led creators sell there
# Mailboxes for a department, not the creator: a pitch there is read late or not at all.
ROLE_LOCAL = re.compile(
    r"^(sales|support|billing|orders?|accounts?|meetings?|events?|careers|jobs|press|media|producer|admin"
    r"|webmaster|privacy|legal|ime\w*|help)(@|$)"
)
# Website-builder template addresses left on the page (hand check 2026-10-28: info@mysite.com).
PLACEHOLDER_DOMAINS = {"mysite.com", "yoursite.com", "yourdomain.com", "yourwebsite.com", "example.com", "domain.com"}
NAME_STOPWORDS = {"podcast", "show", "with", "the", "and", "your", "radio", "daily", "weekly", "talk"}


def compact(text):
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def site_label(website):
    """The website's name without www or suffix: "https://www.jeniferlee.com.au/x" -> "jeniferlee"."""
    host = re.sub(r"^https?://(www\.)?", "", (website or "").lower()).split("/")[0]
    return compact(host.split(".")[0]) if host else ""


def name_tokens(name, website):
    tokens = {t for t in re.findall(r"[a-z0-9]+", (name or "").lower()) if len(t) >= 4 and t not in NAME_STOPWORDS}
    label = site_label(website)
    return tokens | ({label} if len(label) >= 4 else set())


def email_rank(email, website):
    """Lower is better: own website domain, then not a role mailbox."""
    local, _, domain = email.lower().partition("@")
    own = bool(site_label(website)) and compact(domain.split(".")[0]) == site_label(website)
    return (not own, bool(ROLE_LOCAL.match(local + "@")), email.lower())


def handle_of(url):
    return compact(re.sub(r"^(https?:)?//[^/]+/(in/|company/|@)?", "", url).split("/")[0].split("?")[0])


def own_social(contact, tokens, contacts):
    """A social profile counts as the creator's when its handle contains the show's or website's name,
    or when it is the only profile on that platform their own pages link to. A page linking several
    (Storied links 4 Instagram accounts: the show's and its contributors') needs the name match.
    """
    handle = handle_of(contact["value"])
    if any(t in handle or (len(handle) >= 4 and handle in t) for t in tokens):
        return True
    same_platform = {handle_of(c["value"]) for c in contacts if c["channel"] == contact["channel"]}
    return len(same_platform) == 1


def choose(contacts, name, website):
    """(best, backup) contact dicts for one lead, either None when there is none."""
    emails = [
        c for c in contacts if c["channel"] == "Email" and c["value"].split("@")[-1].lower() not in PLACEHOLDER_DOMAINS
    ]
    emails.sort(key=lambda c: email_rank(c["value"], website))
    others = {ch: next((c for c in contacts if c["channel"] == ch), None) for ch in CHECKABLE[1:]}
    checkable = emails[:1] + [others[ch] for ch in CHECKABLE[1:] if others[ch]]
    if not checkable:
        return None, None
    best = checkable[0]
    tokens = name_tokens(name, website)
    socials = sorted(
        (c for c in contacts if c["channel"] in SOCIAL_ORDER and own_social(c, tokens, contacts)),
        key=lambda c: SOCIAL_ORDER.index(c["channel"]),
    )
    backups = checkable[1:] + socials + emails[1:]
    return best, (backups[0] if backups else None)


def route(scored):
    """Return the routed table: the scored rows plus the two channels for every qualified lead."""
    out = scored.astype(object).where(scored.notna(), None)
    for col in ROUTE_COLUMNS:
        out[col] = None
    for i, row in out[out["candidate_status"] == "Qualified"].iterrows():
        best, backup = choose(json.loads(row["contacts"] or "[]"), row["creator_name"], row["website"])
        if best is None or backup is None:  # verify rejects these; reaching here means the tables are stale
            raise ValueError(f"{row['platform_id']} is qualified without a best and backup channel")
        out.loc[i, ROUTE_COLUMNS] = [best["channel"], best["value"], best["evidence_url"],
                                     backup["channel"], backup["value"], backup["evidence_url"]]  # fmt: skip
    return out


def run(conn, config):
    from engine.score import SCORED_COLUMNS  # here, not at the top: verify imports this module

    scored = pd.read_sql("SELECT * FROM scored", conn)
    routed = route(scored)[SCORED_COLUMNS + ROUTE_COLUMNS]
    routed.to_sql("routed", conn, if_exists="replace", index=False)
    q = routed[routed["candidate_status"] == "Qualified"]
    log.info(
        "%d leads routed: best %s, backup %s",
        len(q),
        q["best_channel"].value_counts().to_dict(),
        q["backup_channel"].value_counts().to_dict(),
    )
    return routed
