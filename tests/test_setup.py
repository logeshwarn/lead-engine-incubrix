"""Phase 0 checks: the run command, config and secret handling."""

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from engine.common import REQUIRED_SECTIONS, load_config

ROOT = Path(__file__).resolve().parent.parent


def test_help_works():
    # Phase 0 "done when": python run.py --help works.
    result = subprocess.run([sys.executable, "run.py", "--help"], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0
    for flag in ["--input", "--out", "--refresh", "--config"]:
        assert flag in result.stdout


def test_config_loads_with_brief_values():
    config = load_config(ROOT / "config.yaml")
    # GB, not UK: the workbook uses ISO codes
    assert config["countries"]["approved"] == ["US", "CA", "GB", "IE", "AU", "NZ", "SG"]
    assert config["segments"] == ["Podcaster/Video Podcaster", "YouTuber/Video-First Creator", "Expert-Led Creator"]
    assert config["countries"]["min_approved_share"] == 0.80
    assert config["countries"]["min_countries"] == 3
    assert config["countries"]["max_country_share"] == 0.60
    assert config["activity"] == {
        "recent_items": 8,
        "recent_days": 30,
        "long_form_items": 2,
        "long_form_days": 60,
        "long_form_min_minutes": 20,
    }
    assert config["http"]["retries"] == 3
    assert config["evidence"]["max_age_days"] == 30
    assert config["priority_a"]["count"] == 25


def test_config_missing_section_fails_loudly(tmp_path):
    bad = tmp_path / "config.yaml"
    full = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    del full["countries"]
    bad.write_text(yaml.safe_dump(full), encoding="utf-8")
    with pytest.raises(ValueError, match="countries"):
        load_config(bad)
    assert "countries" in REQUIRED_SECTIONS


def test_env_example_has_no_values():
    # .env.example is committed, so every key must be blank.
    for line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            key, _, value = line.partition("=")
            assert value == "", f"{key} has a value in .env.example"


def test_gitignore_blocks_secrets_and_outputs():
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".env" in ignored
    assert "output/" in ignored


def test_required_docs_exist():
    docs = [
        "README.md",
        "CHANGELOG.md",
        "docs/TECH_BUILD.md",
        "docs/TECH_RUNTIME.md",
        "docs/WORKFLOW.md",
        "docs/PHASES.md",
        "docs/DECISIONS.md",
        "docs/records/AI_TOOLS_SOURCES.md",
        "docs/records/MANUAL_WORK.md",
    ]
    missing = [d for d in docs if not (ROOT / d).is_file()]
    assert not missing, f"missing docs: {missing}"


def test_refresh_shortens_the_cache_window(monkeypatch, tmp_path):
    import run

    seen = {}

    def fake_discover(conn, config, path):
        seen.update(config["cache"])
        raise SystemExit  # stop after discover: only the config matters here

    monkeypatch.setattr(run.discover, "run", fake_discover)
    seeds = tmp_path / "s.csv"
    seeds.write_text("seed_id\n")
    try:
        run.main(["--input", str(seeds), "--out", str(tmp_path / "out"), "--refresh"])
    except SystemExit:
        pass
    assert seen["search_max_age_days"] == seen["enrich_max_age_days"] == seen["refresh_max_age_days"] == 1


def test_fetch_shard_argument_and_needs_a_discovered_run(tmp_path):
    import run

    assert run.parse_args(["--fetch-shard", "2/4"]).fetch_shard == (2, 4)
    for bad in ("0/4", "5/4", "x"):
        with pytest.raises(SystemExit):
            run.parse_args(["--fetch-shard", bad])
    seeds = tmp_path / "s.csv"
    seeds.write_text("seed_id\n")
    assert run.main(["--input", str(seeds), "--out", str(tmp_path / "out"), "--fetch-shard", "1/2"]) == 1
