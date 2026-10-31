"""leads.csv columns and allowed values must match the Submission Workbook exactly."""

import re
import zipfile
from pathlib import Path

import pytest

from engine.common import CANDIDATE_STATUSES, CHANNELS, LEADS_COLUMNS, PRIORITIES, load_config

ROOT = Path(__file__).resolve().parent.parent
WORKBOOK = ROOT / "docs" / "Submission_Workbook.xlsx"
LEADS_SHEET = "xl/worksheets/sheet3.xml"  # tab 02_LEADS

# The workbook comes from IncuBrix and is kept out of git (DECISIONS.md, 2026-10-31). Put it in docs/ to run these.
pytestmark = pytest.mark.skipif(not WORKBOOK.exists(), reason="docs/Submission_Workbook.xlsx is not in the repository")


def _read(name):
    with zipfile.ZipFile(WORKBOOK) as z:
        return z.read(name).decode("utf-8")


def _workbook_header():
    # Read the xlsx as zipped XML so the test needs no extra library (openpyxl is not a dependency).
    # Excel stores text in a shared-strings table; a workbook re-saved by openpyxl stores it inline in the cell.
    with zipfile.ZipFile(WORKBOOK) as z:
        shared = z.read("xl/sharedStrings.xml").decode("utf-8") if "xl/sharedStrings.xml" in z.namelist() else ""
    strings = [re.sub("<[^>]+>", "", s) for s in re.findall(r"<si>(.*?)</si>", shared, re.S)]
    row4 = re.search(r'<row [^>]*r="4"[^>]*>(.*?)</row>', _read(LEADS_SHEET), re.S).group(1)
    header = []
    for cell in re.findall(r'<c r="[A-Z]+4".*?</c>', row4, re.S):
        if 't="s"' in cell:
            header.append(strings[int(re.search(r"<v>(\d+)</v>", cell).group(1))])
        elif 't="inlineStr"' in cell:
            header.append(re.sub("<[^>]+>", "", re.search(r"<is>(.*?)</is>", cell, re.S).group(1)))
    return header


def _dropdown(column_letter):
    # Workbook dropdowns are stored as "A,B,C" lists on the data-validation rule for that column
    # (quoted as &quot; or a plain "). Excel may merge identical rules into one: sqref="R5:R1004 U5:U1004".
    match = re.search(
        rf'sqref="(?:[^"]* )?{column_letter}5:[^"]*"[^>]*><formula1>(?:&quot;|")(.*?)(?:&quot;|")</formula1>',
        _read(LEADS_SHEET),
    )
    return match.group(1).split(",")


def test_tab_is_02_leads():
    assert 'name="02_LEADS"' in _read("xl/workbook.xml")


def test_columns_match_workbook():
    assert LEADS_COLUMNS == _workbook_header()
    assert len(LEADS_COLUMNS) == 30


def test_segments_match_workbook():
    assert load_config(ROOT / "config.yaml")["segments"] == _dropdown("C")


def test_countries_match_workbook():
    # The workbook adds "Other"; the approved list is everything else.
    assert load_config(ROOT / "config.yaml")["countries"]["approved"] + ["Other"] == _dropdown("D")


def test_channels_match_workbook():
    assert CHANNELS == _dropdown("R") == _dropdown("U")


def test_priority_and_status_match_workbook():
    assert PRIORITIES == _dropdown("Y")
    assert CANDIDATE_STATUSES == _dropdown("AA")
