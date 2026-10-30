# Tech used to build the app

Update this file when a development tool is added, removed or upgraded.

| Area | Tool | Version | Notes |
|---|---|---|---|
| Language | Python | 3.11.9 | brief requires 3.11+; 3.13 is also installed on the dev machine but not used |
| Environment | venv | built into Python | `.venv/` folder, ignored by git |
| Dependencies | pip + `requirements.txt` | pip 26.2.2 | direct dependencies pinned exactly |
| Version control | Git | 2.48.1 | private GitHub repository; the owner pushes after each module |
| Editor and AI assist | Claude Code (Claude desktop app, Code tab) | model Claude Opus 5.5 | writes code and docs; every use is logged in [records/AI_TOOLS_SOURCES.md](records/AI_TOOLS_SOURCES.md) |
| Testing | pytest | 9.1.1 | settings in `pyproject.toml`; tests in `tests/` |
| Lint and format | ruff | 0.17.3 | settings in `pyproject.toml` (line length 120, rules E, F, I, B) |
| Config and secrets | `.env`, `.env.example`, `config.yaml` | n/a | `.env` ignored by git; only `.env.example` is committed |
| OS | Windows 11 | n/a | built and run on Windows; README gives Windows and macOS/Linux setup commands |

## Environment setup

```bash
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Checks before each push

```bash
python -m pytest
```

```bash
python -m ruff check .
```

```bash
python -m ruff format --check .
```
