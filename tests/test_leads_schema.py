"""leads.csv columns and allowed values must match the Submission Workbook exactly."""

import re
import zipfile
from pathlib import Path

from engine.common import CANDIDATE_STATUSES, CHANNELS, LEADS_COLUMNS, PRIORITIES, load_config

ROOT = Path(__file__).resolve().parent.parent
WORKBOOK = ROOT / "docs" / "Submission_Workbook.xlsx"
LEADS_SHEET = "xl/worksheets/sheet3.xml"  # tab 02_LEADS


def _read(name):
    with zipfile.ZipFile(WORKBOOK) as z:
        return z.read(name).decode("utf-8")


def _workbook_header():
    # Read the xlsx as zipped XML so the test needs no extra library (openpyxl is not a dependency).
    strings = [re.sub("<[^>]+>", "", s) for s in re.findall(r"<si>(.*?)</si>", _read("xl/sharedStrings.xml"), re.S)]
    row4 = re.search(r'<row [^>]*r="4"[^>]*>(.*?)</row>', _read(LEADS_SHEET), re.S).group(1)
    return [strings[int(v)] for v in re.findall(r'<c r="[A-Z]+4"[^>]*t="s"[^>]*><v>(\d+)</v>', row4)]


def _dropdown(column_letter):
    # Workbook dropdowns are stored as "A,B,C" lists on the data-validation rule for that column.
    match = re.search(rf'sqref="{column_letter}5:[^"]*"[^>]*><formula1>&quot;(.*?)&quot;', _read(LEADS_SHEET))
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
