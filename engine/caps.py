"""Stage 5, caps: the `deduped` table -> the `capped` table, plus the `cap_checks` table.

The final lead set must meet the hard constraints (brief section 6, assignment section 2):
- at least 80% of leads from the approved countries (US, CA, GB, IE, AU, NZ, SG)
- at least 3 countries
- no country above 60%
- every lead in an approved segment, with mainly English content

Decision 2026-10-28 (owner): when one country is above 60%, its lowest-ranked qualified leads are
marked Rejected ("cap: ...") until it is at 60%. "Lowest-ranked" means the lowest score
(engine/score.py), so the best leads are kept. Then every rule is checked and written to
`cap_checks`. A rule that still fails (too few countries, too few approved) cannot be fixed by
trimming, so it is reported as failed: the later stages still run, so the output can be inspected,
but run.py exits with an error and the run report says FAILED.
"""

import logging

import pandas as pd

from engine.dedupe import DEDUPED_COLUMNS
from engine.score import rank_key

log = logging.getLogger("caps")

CAP_CHECK_COLUMNS = ["rule", "value", "limit", "passed"]


def shares(qualified):
    """Share of qualified leads per country, largest first."""
    return qualified["country_iso2"].value_counts(normalize=True)


def trim_top_country(out, config):
    """Reject the lowest-ranked leads of a country above the share limit. Returns how many were trimmed.

    Only done when the set already has enough countries: with 1 or 2 countries, trimming would
    throw away most leads and still fail the "at least 3 countries" rule.
    """
    limit = config["countries"]["max_country_share"]
    q = out[out["candidate_status"] == "Qualified"]
    if q.empty or q["country_iso2"].nunique() < config["countries"]["min_countries"]:
        return 0
    top = shares(q).index[0]
    rows = q[q["country_iso2"] == top]
    others = len(q) - len(rows)
    # Most leads of `top` that stay within the limit: keep / (keep + others) <= limit.
    keep = int(limit * others / (1 - limit) + 1e-9)
    if len(rows) <= keep:
        return 0
    # Lowest score goes first (the same score the score stage gives; it depends only on the lead).
    ranked = sorted(rows.index, key=lambda i: rank_key(out.loc[i], config["score"]))
    for i in ranked[keep:]:
        out.loc[i, ["candidate_status", "rejection_reason"]] = [
            "Rejected",
            f"cap: {top} above {limit:.0%} of leads (ranked {ranked.index(i) + 1} of {len(rows)} {top} leads)",
        ]
    trimmed = len(rows) - keep
    log.info("%s trimmed from %d to %d leads to stay at or under %.0f%%", top, len(rows), keep, limit * 100)
    return trimmed


def check_rules(qualified, config):
    """Every hard constraint on the final set, as rows of cap_checks."""
    c = config["countries"]
    n = len(qualified)
    approved_share = qualified["country_iso2"].isin(c["approved"]).mean() if n else 0.0
    top = shares(qualified)
    english = (qualified["primary_language"] == config["language"]["required"]).mean() if n else 0.0
    in_segment = qualified["creator_segment"].isin(config["segments"]).mean() if n else 0.0
    checks = [
        ("approved-country share", round(approved_share, 3), f">= {c['min_approved_share']}",
         approved_share >= c["min_approved_share"]),
        ("countries", qualified["country_iso2"].nunique(), f">= {c['min_countries']}",
         qualified["country_iso2"].nunique() >= c["min_countries"]),
        (f"largest country share ({top.index[0] if n else '-'})", round(top.iloc[0], 3) if n else 0.0,
         f"<= {c['max_country_share']}", bool(n) and top.iloc[0] <= c["max_country_share"]),
        ("mainly English share", round(english, 3), "= 1.0", bool(n) and english == 1.0),
        ("approved segment share", round(in_segment, 3), "= 1.0", bool(n) and in_segment == 1.0),
    ]  # fmt: skip
    return pd.DataFrame(checks, columns=CAP_CHECK_COLUMNS)


def caps(deduped, config):
    """Return (capped table, cap_checks table, number trimmed)."""
    out = deduped.astype(object).where(deduped.notna(), None)
    trimmed = trim_top_country(out, config)
    checks = check_rules(out[out["candidate_status"] == "Qualified"], config)
    return out[DEDUPED_COLUMNS], checks, trimmed


def run(conn, config):
    """Writes `capped` and `cap_checks`. Returns the failed rules (empty when the set is valid)."""
    deduped = pd.read_sql("SELECT * FROM deduped", conn)
    capped, checks, trimmed = caps(deduped, config)
    capped.to_sql("capped", conn, if_exists="replace", index=False)
    checks.to_sql("cap_checks", conn, if_exists="replace", index=False)
    mix = capped.loc[capped["candidate_status"] == "Qualified", "country_iso2"].value_counts().to_dict()
    log.info("%d trimmed by caps, %d leads left, countries %s", trimmed, sum(mix.values()), mix)
    failed = [f"{r.rule} is {r.value}, needs {r.limit}" for r in checks.itertuples() if not r.passed]
    for f in failed:
        log.error("CAP RULE FAILED: %s", f)  # loud on purpose: the set is not valid for submission
    return failed
