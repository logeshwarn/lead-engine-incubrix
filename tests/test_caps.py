"""caps: trim a country above 60%, then check every hard rule on the final set."""

import pandas as pd

from engine import caps
from engine.dedupe import DEDUPED_COLUMNS


def lead(i, country, last="2026-10-20", status="Qualified", language="en", segment="Podcaster/Video Podcaster"):
    r = dict.fromkeys(DEDUPED_COLUMNS)
    r.update(
        platform="podcast",
        platform_id=f"p{i:03d}",
        creator_name=f"Creator {i}",
        country_iso2=country,
        primary_language=language,
        creator_segment=segment,
        contacts="[]",
        last_content_date=last,
        candidate_status=status,
    )
    return r


def leads(mix, **kw):
    """mix like {"US": 7, "GB": 2}: that many qualified leads per country."""
    rows, i = [], 0
    for country, n in mix.items():
        for _ in range(n):
            rows.append(lead(i, country, **kw))
            i += 1
    return pd.DataFrame(rows, columns=DEDUPED_COLUMNS)


def run(config, df):
    out, checks, trimmed = caps.caps(df, config)
    q = out[out["candidate_status"] == "Qualified"]
    return out, checks.set_index("rule"), trimmed, q["country_iso2"].value_counts().to_dict()


def test_top_country_trimmed_to_sixty_percent(config):
    # Today's real mix: US 33 of 51.
    out, checks, trimmed, mix = run(config, leads({"US": 33, "GB": 9, "CA": 4, "AU": 3, "NZ": 1, "IE": 1}))
    assert trimmed == 6 and mix["US"] == 27  # 27 of 45 = 60%
    assert checks["passed"].all()
    reasons = out.loc[out["rejection_reason"].notna(), "rejection_reason"]
    assert len(reasons) == 6 and reasons.str.startswith("cap: US above 60% of leads").all()


def test_lowest_ranked_are_trimmed_first(config):
    df = leads({"US": 4, "GB": 1, "CA": 1})  # US 4 of 6 is 67%; keep 3 (3 of 5 = 60%)
    df.loc[0, "last_content_date"] = "2026-01-01"  # the oldest content is trimmed
    out, _, trimmed, _ = run(config, df)
    assert trimmed == 1 and out.loc[0, "candidate_status"] == "Rejected"


def test_mix_within_limits_is_untouched(config):
    df = leads({"US": 6, "GB": 2, "CA": 2})  # US exactly 60%
    out, checks, trimmed, _ = run(config, df)
    assert trimmed == 0 and checks["passed"].all()
    pd.testing.assert_frame_equal(out.reset_index(drop=True), df.astype(object).where(df.notna(), None))


def test_too_few_countries_fails_and_is_not_trimmed(config):
    out, checks, trimmed, mix = run(config, leads({"US": 8, "GB": 2}))
    assert trimmed == 0 and mix == {"US": 8, "GB": 2}  # trimming cannot fix 2 countries
    assert not checks.loc["countries", "passed"]
    assert not checks.loc["largest country share (US)", "passed"]


def test_non_approved_share_checked(config):
    df = leads({"US": 3, "GB": 3, "CA": 2, "Other": 3})  # 8 of 11 approved = 73%
    _, checks, _, _ = run(config, df)
    assert not checks.loc["approved-country share", "passed"]


def test_language_and_segment_checked(config):
    df = leads({"US": 2, "GB": 2, "CA": 2})
    df.loc[0, "primary_language"] = None
    df.loc[1, "creator_segment"] = "Brand"
    _, checks, _, _ = run(config, df)
    assert not checks.loc["mainly English share", "passed"]
    assert not checks.loc["approved segment share", "passed"]


def test_rejected_rows_do_not_count(config):
    df = pd.concat([leads({"US": 3, "GB": 2, "CA": 1}), leads({"US": 50}, status="Rejected")], ignore_index=True)
    _, checks, trimmed, _ = run(config, df)
    assert trimmed == 0 and checks["passed"].all()


def test_run_writes_tables_and_reports_failures(conn, config):
    leads({"US": 8, "GB": 2}).to_sql("deduped", conn, index=False)
    failed = caps.run(conn, config)
    assert failed and any(f.startswith("countries is 2") for f in failed)
    assert list(pd.read_sql("SELECT * FROM capped", conn).columns) == DEDUPED_COLUMNS
    assert list(pd.read_sql("SELECT * FROM cap_checks", conn).columns) == caps.CAP_CHECK_COLUMNS


def test_run_passes_on_a_valid_set(conn, config):
    leads({"US": 3, "GB": 2, "CA": 1}).to_sql("deduped", conn, index=False)
    assert caps.run(conn, config) == []
