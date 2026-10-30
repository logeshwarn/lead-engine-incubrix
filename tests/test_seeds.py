"""data/seeds.csv must only ask for what the engine can actually search."""

from pathlib import Path

import pandas as pd

from engine.common import load_config

ROOT = Path(__file__).resolve().parent.parent
COLUMNS = [
    "seed_id",
    "segment",
    "niche",
    "primary_platform",
    "discovery_keywords",
    "need_signal_to_check",
    "size_min",
    "size_max",
    "status",
]

seeds = pd.read_csv(ROOT / "data" / "seeds.csv")
config = load_config(ROOT / "config.yaml")


def test_columns():
    assert list(seeds.columns) == COLUMNS


def test_seed_ids_unique():
    assert seeds["seed_id"].is_unique


def test_segments_match_workbook():
    assert set(seeds["segment"]) <= set(config["segments"])


def test_platforms_are_searchable():
    # LinkedIn and Instagram have no discovery API in the brief, so they cannot be seeds.
    assert set(seeds["primary_platform"]) <= set(config["discovery_platforms"])


def test_every_row_has_keywords():
    keywords = seeds["discovery_keywords"].fillna("").str.split(";")
    assert keywords.map(lambda ks: all(k.strip() for k in ks)).all()


def test_no_keyword_repeated():
    # A repeated YouTube keyword wastes 100 quota units for no new candidates. The same name on two
    # platforms is not a repeat: "Business" as an Apple chart and as a Podcast Index category are different lists.
    rows = seeds.assign(keyword=seeds["discovery_keywords"].str.split(";")).explode("keyword")
    keys = rows["primary_platform"] + ":" + rows["keyword"].str.strip().str.lower()
    assert keys.is_unique


def test_size_band_valid():
    # Podcasts publish no audience count, so their band must stay blank rather than be guessed.
    podcast = seeds[seeds["primary_platform"] == "podcast"]
    assert podcast[["size_min", "size_max"]].isna().all().all()
    youtube = seeds[seeds["primary_platform"] == "youtube"]
    assert (youtube["size_min"] <= youtube["size_max"]).all()


def test_status_values():
    assert set(seeds["status"]) <= {"active", "paused"}
