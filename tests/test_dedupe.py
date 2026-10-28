"""dedupe: one qualified row per creator, matched by platform ID, website domain or email."""

import json

import pandas as pd

from engine import dedupe
from engine.verify import VERIFIED_COLUMNS


def row(pid, website=None, emails=(), last="2026-10-20", status="Qualified", name=None):
    r = dict.fromkeys(VERIFIED_COLUMNS)
    contacts = [{"channel": "Email", "value": e, "evidence_url": "x", "note": ""} for e in emails]
    r.update(
        platform="podcast",
        platform_id=pid,
        stable_creator_id=pid,
        creator_name=name or pid,
        website=website,
        contacts=json.dumps(contacts),
        last_content_date=last,
        candidate_status=status,
        rejection_reason=None if status == "Qualified" else "country not evidenced",
    )
    return r


def run(config, rows):
    out, n = dedupe.dedupe(pd.DataFrame(rows, columns=VERIFIED_COLUMNS), config)
    return out.set_index("platform_id"), n


def qualified(out):
    return sorted(out.index[out["candidate_status"] == "Qualified"])


def test_same_website_domain_is_one_creator(config):
    out, n = run(
        config, [row("a", "https://www.JaneDoe.com/podcast"), row("b", "http://janedoe.com", last="2026-10-01")]
    )
    assert qualified(out) == ["a"] and n == 1
    assert out.loc["b", "rejection_reason"] == "duplicate of a (a): same website domain janedoe.com"
    assert out.loc["b", "duplicate_of"] == "a"


def test_same_email_is_one_creator(config):
    out, _ = run(config, [row("a", emails=["Jane@Gmail.com"]), row("b", emails=["jane@gmail.com"], last="2026-09-30")])
    assert qualified(out) == ["a"]
    assert "same email jane@gmail.com" in out.loc["b", "rejection_reason"]


def test_same_platform_id_is_one_creator(config):
    out, n = run(config, [row("a", last="2026-10-01"), row("a")])
    assert n == 1 and (out["candidate_status"] == "Qualified").sum() == 1


def test_keys_chain_into_one_group(config):
    # a and b share a domain, b and c share an email: all three are one creator.
    rows = [
        row("a", "https://janedoe.com", last="2026-10-01"),
        row("b", "https://janedoe.com", emails=["jane@janemedia.co"], last="2026-10-25"),
        row("c", emails=["jane@janemedia.co"], last="2026-10-02"),
    ]
    out, n = run(config, rows)
    assert qualified(out) == ["b"] and n == 2  # b has the most recent content
    assert "same website domain janedoe.com" in out.loc["a", "rejection_reason"]
    assert "same email jane@janemedia.co" in out.loc["c", "rejection_reason"]


def test_shared_platform_domains_are_not_keys(config):
    rows = [
        row("a", "https://janeshow.libsyn.com"),
        row("b", "https://bobshow.libsyn.com"),
        row("c", "https://linktr.ee/jane"),
        row("d", "https://linktr.ee/bob"),
        row("e", "https://jane.substack.com"),
        row("f", "https://bob.substack.com"),
    ]
    out, n = run(config, rows)
    assert n == 0 and qualified(out) == ["a", "b", "c", "d", "e", "f"]


def test_different_creators_stay_apart(config):
    out, n = run(config, [row("a", "https://janedoe.com", ["jane@janedoe.com"]), row("b", "https://bob.co.uk")])
    assert n == 0 and qualified(out) == ["a", "b"]


def test_more_contacts_breaks_a_date_tie(config):
    rows = [row("a", "https://janedoe.com"), row("b", "https://janedoe.com", emails=["hi@janedoe.com"])]
    assert qualified(run(config, rows)[0]) == ["b"]


def test_rejected_rows_are_not_deduped_against(config):
    rows = [row("a", "https://janedoe.com", last="2026-09-01"), row("b", "https://janedoe.com", status="Rejected")]
    out, n = run(config, rows)
    assert n == 0 and qualified(out) == ["a"]
    assert out.loc["b", "rejection_reason"] == "country not evidenced"  # earlier reason kept


def test_run_writes_table_and_rerun_is_identical(conn, config):
    rows = [row("a", "https://janedoe.com"), row("b", "https://janedoe.com", last="2026-01-01"), row("c")]
    pd.DataFrame(rows, columns=VERIFIED_COLUMNS).to_sql("verified", conn, index=False)
    first = dedupe.run(conn, config)
    second = dedupe.run(conn, config)
    pd.testing.assert_frame_equal(first, second)
    table = pd.read_sql("SELECT * FROM deduped", conn)
    assert list(table.columns) == dedupe.DEDUPED_COLUMNS and len(table) == 3  # nothing dropped silently
    q = table[table["candidate_status"] == "Qualified"]
    assert not q["platform_id"].duplicated().any()


def test_email_on_many_shows_is_not_the_creators(config):
    # A re-upload feed: one gmail address is the contact of 3 shows; only one of them passed verify.
    farm = "uploader123@gmail.com"
    rows = [
        row("a", emails=[farm], name="Dr. Famous"),
        row("b", emails=[farm], status="Rejected"),
        row("c", emails=[farm], status="Rejected"),
        row("d", emails=["jane@janedoe.com"]),
    ]
    out, _ = run(config, rows)
    assert qualified(out) == ["d"]
    assert out.loc["a", "rejection_reason"] == f"not the creator's own contact: {farm} is listed on 3 different shows"


def test_email_on_two_shows_is_one_creator_not_a_network(config):
    rows = [row("a", emails=["darren@marlarhouse.com"]), row("b", emails=["darren@marlarhouse.com"], status="Rejected")]
    out, _ = run(config, rows)
    assert qualified(out) == ["a"]
