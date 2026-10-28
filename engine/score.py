"""Stage 6, score: the `capped` table -> the `scored` table, a 0-100 score and a priority per lead.

Weights are in config.yaml (`score`) and explained in docs/DECISIONS.md (owner's choice 2026-10-28,
"Balanced"). Five parts, each kept as its own column so every score can be explained:
- need (30): how clearly the lead needs IncuBrix; the creator's own words beat an observed gap
- volume (20): long-form items in 60 days; more content means more editing and repurposing work
- commercial (20): the kind of offer; sponsorship shows a business that already earns from content
- reach (20): an email, a contact form or guest-pitch page, and more than one kind of channel
- evidence (10): how strong the country evidence is (a website's country domain alone is weaker)

A score depends only on the lead's own evidence, never on the other leads, so caps can rank
with the same function before this stage runs.
"""

import json
import logging

import pandas as pd

from engine.dedupe import DEDUPED_COLUMNS, keep_order

log = logging.getLogger("score")

SCORE_PARTS = ["score_need", "score_volume", "score_commercial", "score_reach", "score_evidence"]
SCORED_COLUMNS = DEDUPED_COLUMNS + SCORE_PARTS + ["lead_score", "priority"]


def score_parts(row, weights):
    """The five parts of one lead's score, as a dict of column -> points."""
    channels = {c["channel"] for c in json.loads(row["contacts"] or "[]")}
    volume = weights["volume"]
    reach = weights["reach"]
    evidence = weights["evidence"]
    return {
        "score_need": weights["need"].get(row["need_kind"], 0),
        # Full points at `full_at` long items in 60 days (weekly long-form), less in proportion below it.
        "score_volume": round(volume["max"] * min((row["longform_count_60d"] or 0) / volume["full_at"], 1), 1),
        "score_commercial": weights["commercial"].get(row["monetization_signal"], 0),
        "score_reach": (reach["email"] if "Email" in channels else 0)
        + (reach["form_or_pitch"] if channels & {"Contact form", "Podcast guest pitch"} else 0)
        + (reach["second_channel"] if len(channels) >= 2 else 0),
        "score_evidence": evidence["domain_only"]
        if (row["country_evidence"] or "").startswith("Website domain")
        else evidence["strong"],
    }


def lead_score(row, weights):
    return round(sum(score_parts(row, weights).values()))


def rank_key(row, weights):
    """Highest score first; ties go to dedupe's order (recent content, contacts, ID) so reruns agree."""
    return (-lead_score(row, weights), keep_order(row))


def score(capped, config):
    """Return the scored table: parts, lead_score and priority for qualified rows; blank for rejected ones."""
    weights = config["score"]
    out = capped.astype(object).where(capped.notna(), None)
    for col in SCORE_PARTS + ["lead_score", "priority"]:
        out[col] = None
    qualified = out[out["candidate_status"] == "Qualified"]
    for i, row in qualified.iterrows():
        parts = score_parts(row, weights)
        out.loc[i, list(parts)] = list(parts.values())
        out.loc[i, "lead_score"] = round(sum(parts.values()))
    ranked = sorted(qualified.index, key=lambda i: rank_key(out.loc[i], weights))
    a_count = config["priority_a"]["count"]
    for n, i in enumerate(ranked):
        if n < a_count:
            out.loc[i, "priority"] = "A"
        else:
            out.loc[i, "priority"] = "B" if out.loc[i, "lead_score"] >= weights["priority_b_min_score"] else "C"
    return out[SCORED_COLUMNS]


def run(conn, config):
    capped = pd.read_sql("SELECT * FROM capped", conn)
    scored = score(capped, config)
    scored.to_sql("scored", conn, if_exists="replace", index=False)
    q = scored[scored["candidate_status"] == "Qualified"]
    log.info(
        "%d leads scored: priority %s, score min %s / median %s / max %s",
        len(q),
        q["priority"].value_counts().sort_index().to_dict(),
        q["lead_score"].min() if len(q) else "-",
        q["lead_score"].median() if len(q) else "-",
        q["lead_score"].max() if len(q) else "-",
    )
    if len(q) < config["priority_a"]["count"]:
        log.warning("only %d leads, fewer than the %d Priority A slots", len(q), config["priority_a"]["count"])
    return scored
