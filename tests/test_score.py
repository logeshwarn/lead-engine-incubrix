"""score: each part follows the configured weights, the top 25 are Priority A, the rest B or C."""

import json

import pandas as pd

from engine import score
from engine.dedupe import DEDUPED_COLUMNS


def lead(i, need="captions", long60=8, money="Sponsorship", channels=("Email", "Contact form"),
         country_evidence="I live in Austin, TX", status="Qualified", last="2026-10-27"):  # fmt: skip
    r = dict.fromkeys(DEDUPED_COLUMNS)
    contacts = [{"channel": c, "value": f"{c}-{i}", "evidence_url": "x", "note": ""} for c in channels]
    r.update(
        platform="podcast",
        platform_id=f"p{i:03d}",
        creator_name=f"Creator {i}",
        need_kind=need,
        longform_count_60d=long60,
        monetization_signal=money,
        contacts=json.dumps(contacts),
        country_evidence=country_evidence,
        last_content_date=last,
        candidate_status=status,
    )
    return r


def parts(config, **kw):
    return score.score_parts(lead(0, **kw), config["score"])


def test_full_marks(config):
    p = parts(config, need="own words", long60=12)
    assert p == {"score_need": 30, "score_volume": 20, "score_commercial": 20, "score_reach": 20,
                 "score_evidence": 10}  # fmt: skip
    assert score.lead_score(lead(0, need="own words", long60=12), config["score"]) == 100


def test_need_kinds_follow_weights(config):
    assert [parts(config, need=k)["score_need"] for k in ("own words", "repurposing", "captions", "consistency")] == [
        30, 22, 15, 12,
    ]  # fmt: skip


def test_volume_scales_up_to_weekly(config):
    assert [parts(config, long60=n)["score_volume"] for n in (2, 4, 8, 40)] == [5.0, 10.0, 20.0, 20.0]


def test_commercial_kinds(config):
    got = {k: parts(config, money=k)["score_commercial"] for k in ("Sponsorship", "Service", "Membership", "Affiliate")}
    assert got == {"Sponsorship": 20, "Service": 16, "Membership": 12, "Affiliate": 8}


def test_reach(config):
    assert parts(config, channels=("Email",))["score_reach"] == 12
    assert parts(config, channels=("Contact form",))["score_reach"] == 4
    assert parts(config, channels=("Email", "Instagram"))["score_reach"] == 16
    assert parts(config, channels=("Email", "Contact form", "Instagram"))["score_reach"] == 20


def test_country_domain_alone_is_weaker_evidence(config):
    assert parts(config, country_evidence="Website domain jane.co.uk (.uk country domain)")["score_evidence"] == 6
    assert parts(config, country_evidence="Feed location tag: United Kingdom")["score_evidence"] == 10


def test_top_25_are_a_then_b_or_c_by_score(config):
    rows = [lead(i, need="repurposing", long60=8) for i in range(25)]  # 22 + 20 + 20 + 20 + 10 = 92
    rows += [lead(25, need="captions", long60=4)]  # 15 + 10 + 20 + 20 + 10 = 75 -> B
    rows += [lead(26, need="consistency", long60=2, money="Affiliate", channels=("Contact form",),
                  country_evidence="Website domain x.co.uk")]  # 12 + 5 + 8 + 4 + 6 = 35 -> C  # fmt: skip
    rows += [lead(27, status="Rejected")]
    out = score.score(pd.DataFrame(rows, columns=DEDUPED_COLUMNS), config).set_index("platform_id")
    assert (out["priority"] == "A").sum() == 25
    assert out.loc["p025", ["lead_score", "priority"]].tolist() == [75, "B"]
    assert out.loc["p026", ["lead_score", "priority"]].tolist() == [35, "C"]
    assert out.loc["p027", "lead_score"] is None and out.loc["p027", "priority"] is None


def test_ties_broken_the_same_way_every_run(config):
    rows = [lead(i) for i in range(30)]
    first = score.score(pd.DataFrame(rows, columns=DEDUPED_COLUMNS), config)
    second = score.score(pd.DataFrame(rows[::-1], columns=DEDUPED_COLUMNS), config)
    a1 = sorted(first.loc[first["priority"] == "A", "platform_id"])
    a2 = sorted(second.loc[second["priority"] == "A", "platform_id"])
    assert a1 == a2 == [f"p{i:03d}" for i in range(25)]  # equal scores: lowest ID wins


def test_run_writes_table(conn, config):
    pd.DataFrame([lead(0), lead(1)], columns=DEDUPED_COLUMNS).to_sql("capped", conn, index=False)
    score.run(conn, config)
    table = pd.read_sql("SELECT * FROM scored", conn)
    assert list(table.columns) == score.SCORED_COLUMNS and table["priority"].tolist() == ["A", "A"]
