"""Stage 4, dedupe: the `verified` table -> the `deduped` table, one qualified row per creator.

The same creator can be found more than once: a podcast and its YouTube channel, two shows by one
host, or one show listed under Podcast Index and Apple with different IDs. Qualified rows are the
same creator when they share any key (brief section 6):
- the platform ID
- the creator's own website domain
- a business email address

Rows linked through any chain of shared keys form one group (A shares a domain with B, and B an
email with C: all three are one creator). One row per group is kept; the others become Rejected
with "duplicate of ..." and the key that matched, so nothing is dropped silently.

Domains that many creators share (hosting platforms, social sites, link pages, networks) are never
keys: two shows on libsyn.com are not the same creator.

Before grouping, a qualified row is rejected when its email is the contact of many different shows
across ALL verified rows (`dedupe.shared_email_min_shows`). Such an address belongs to a network or
to a feed that re-uploads other people's YouTube channels, not to the creator (2026-10-28: one
gmail address ran 19 feeds named after Dr. John Campbell, MIT OpenCourseWare, Jim Gaffigan and others).
"""

import json
import logging

import pandas as pd

from engine.verify import NOT_CREATOR_EMAIL_DOMAINS, VERIFIED_COLUMNS, registered_domain

log = logging.getLogger("dedupe")

DEDUPED_COLUMNS = VERIFIED_COLUMNS + ["duplicate_of"]  # platform_id of the kept row, for rejected duplicates


def shared_domains(config):
    """Domains that identify a platform, not a creator."""
    return (
        set(config["enrich"]["skip_domains"])
        | NOT_CREATOR_EMAIL_DOMAINS
        | set(config["verify"]["media_domains"])
        | set(config["dedupe"]["shared_domains"])
    )


def emails(row):
    # verify already dropped hosting-platform and no-reply addresses
    return [c["value"].strip().lower() for c in json.loads(row["contacts"] or "[]") if c["channel"] == "Email"]


def keys(row, shared):
    """The dedupe keys of one row, as (kind, value) pairs."""
    out = [("platform ID", row["stable_creator_id"] or row["platform_id"])]
    domain = registered_domain(row["website"])
    if domain and domain not in shared:
        out.append(("website domain", domain))
    out += [("email", e) for e in emails(row)]
    return out


def shows_per_email(rows):
    """How many different shows list each email, over every verified row (qualified or not)."""
    shows = {}
    for row in rows:
        for e in set(emails(row)):
            shows.setdefault(e, set()).add(row["platform_id"])
    return {e: len(ids) for e, ids in shows.items()}


def group_rows(rows, shared):
    """Group row indexes that share a key, through any chain. Returns {root index: [indexes]}.

    Union-find: each row starts alone, and every key seen twice joins the two rows' groups.
    """
    parent = list(range(len(rows)))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]  # shorten the path as we go
            i = parent[i]
        return i

    first_seen = {}  # key -> first row index with that key
    for i, row in enumerate(rows):
        for key in keys(row, shared):
            if key in first_seen:
                parent[root(i)] = root(first_seen[key])
            else:
                first_seen[key] = i
    groups = {}
    for i in range(len(rows)):
        groups.setdefault(root(i), []).append(i)
    return groups


def keep_order(row):
    """Which row of a group to keep: the most recent content, then the most contacts, then the ID.

    The most recent item makes the best opening line, and more channels give route a better choice.
    The ID only breaks ties, so reruns keep the same row.
    """
    return (
        -(pd.Timestamp(row["last_content_date"]).value if row["last_content_date"] else 0),
        -len(json.loads(row["contacts"] or "[]")),
        row["platform_id"],
    )


def dedupe(verified, config):
    """Return the deduped table: every verified row, with duplicates of a kept row rejected."""
    out = verified.astype(object).where(verified.notna(), None)
    out["duplicate_of"] = None

    # An email shared by many shows is a network's or a re-upload feed's, so the row is not the creator.
    counts = shows_per_email(out.to_dict("records"))
    limit = config["dedupe"]["shared_email_min_shows"]
    shared_email = 0
    for i, row in out[out["candidate_status"] == "Qualified"].iterrows():
        widest = max(emails(row), key=lambda e: counts[e], default=None)
        if widest and counts[widest] >= limit:
            out.loc[i, ["candidate_status", "rejection_reason"]] = [
                "Rejected",
                f"not the creator's own contact: {widest} is listed on {counts[widest]} different shows",
            ]
            shared_email += 1
    if shared_email:
        log.info("%d qualified rows rejected for an email shared by %d or more shows", shared_email, limit)

    qualified = out[out["candidate_status"] == "Qualified"]
    rows = qualified.to_dict("records")
    shared = shared_domains(config)
    duplicates = 0
    for idx in group_rows(rows, shared).values():
        if len(idx) == 1:
            continue
        kept = min(idx, key=lambda i: keep_order(rows[i]))
        group_keys = {i: keys(rows[i], shared) for i in idx}
        for i in idx:
            if i == kept:
                continue
            # The key this row shares with another row of the group: why it is a duplicate.
            others = {k for j in idx if j != i for k in group_keys[j]}
            kind, value = next(k for k in group_keys[i] if k in others)
            k = rows[kept]
            out.loc[qualified.index[i], ["candidate_status", "rejection_reason", "duplicate_of"]] = [
                "Rejected",
                f"duplicate of {k['creator_name']} ({k['platform_id']}): same {kind} {value}",
                k["platform_id"],
            ]
            duplicates += 1
        log.info("duplicate group of %d kept %s: %s", len(idx), rows[kept]["platform_id"],
                 ", ".join(rows[i]["platform_id"] for i in idx))  # fmt: skip
    return out[DEDUPED_COLUMNS], duplicates


def run(conn, config):
    verified = pd.read_sql("SELECT * FROM verified", conn)
    deduped, duplicates = dedupe(verified, config)
    # Rebuilt from `verified` every run, so replacing the table keeps the stage rerunnable.
    deduped.to_sql("deduped", conn, if_exists="replace", index=False)
    log.info(
        "%d qualified in, %d duplicates rejected, %d unique creators out",
        (verified["candidate_status"] == "Qualified").sum(),
        duplicates,
        (deduped["candidate_status"] == "Qualified").sum(),
    )
    return deduped
