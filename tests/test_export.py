"""export: rejected.csv lists every rejected creator with a reason."""

import pandas as pd
import pytest

from engine import export
from engine.dedupe import DEDUPED_COLUMNS


def capped_rows(rows):
    out = []
    for i, (status, reason) in enumerate(rows):
        r = dict.fromkeys(DEDUPED_COLUMNS)
        r.update(platform="podcast", platform_id=f"p{i}", creator_name=f"Creator {i}",
                 candidate_status=status, rejection_reason=reason)  # fmt: skip
        out.append(r)
    return pd.DataFrame(out, columns=DEDUPED_COLUMNS)


def test_rejected_csv_has_every_rejected_row_and_reason(conn, tmp_path):
    rows = [("Qualified", None), ("Rejected", "country not evidenced"), ("Rejected", "cap: US above 60% of leads")]
    capped_rows(rows).to_sql("capped", conn, index=False)
    assert export.write_rejected(conn, tmp_path) == 2
    csv = pd.read_csv(tmp_path / "rejected.csv")
    assert list(csv.columns) == export.REJECTED_COLUMNS
    assert csv["platform_id"].tolist() == ["p1", "p2"]  # the qualified row is not in it
    assert csv["rejection_reason"].notna().all()


def test_rejection_without_reason_fails_loudly(conn, tmp_path):
    capped_rows([("Rejected", None)]).to_sql("capped", conn, index=False)
    with pytest.raises(ValueError, match="no rejection_reason"):
        export.write_rejected(conn, tmp_path)
