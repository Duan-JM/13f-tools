# AGENTS.md

This file provides guidance to AI coding agents when working with code in this repository.

## Project Overview

`sec13f-analyzer` is a SEC 13F holdings analysis toolkit focused on tracking
institutional investors' position changes. It provides:

- Fund CIK lookup and 13F filing discovery against SEC EDGAR
- Holdings ingestion from 13F-HR / 13F-HR/A information tables (with amendment handling)
- Quarter-over-quarter change analysis (new / closed / increased / decreased positions)
- Multi-format export (Excel, CSV, JSON) and matplotlib/plotly visualizations
- A long-running monitoring service that polls portfolios and pushes Feishu webhook notifications

## Commands

```bash
# Install dependencies (includes dev + test groups when iterating)
poetry install --with dev,test

# Run the CLI
poetry run sec13f-cli --help
poetry run sec13f-cli search --fund-name "Berkshire"
poetry run sec13f-cli fetch --cik 0001067983 --quarter 2024Q3

# Run all tests
poetry run pytest

# Run with coverage (CI gate is 70%)
poetry run pytest --cov=src/sec13f_analyzer --cov-report=term-missing --cov-fail-under=70

# Run a single test file or function
poetry run pytest tests/test_analyzer.py -v
poetry run pytest tests/test_analyzer.py::test_get_holdings -v

# Run tests by marker
poetry run pytest -m unit
poetry run pytest -m "not integration"
poetry run pytest -m "not slow"

# Format code (Black + isort, both at line-length 88)
poetry run black src/ tests/
poetry run isort src/ tests/

# Lint (flake8, configured in setup.cfg)
poetry run flake8 src/ tests/

# Type-check (mypy, configured in setup.cfg)
poetry run mypy src/

# Security checks (run in CI as well)
poetry run bandit -r src/
poetry run pip-audit
```

## Architecture

### Source layout: `src/sec13f_analyzer/`

**Entry point**: `cli.py` — Click command group exposed as the `sec13f-cli`
console script (defined in `pyproject.toml` under `[project.scripts]`).
Subcommands include `search`, `info`, `fetch`, `compare`, `monitor`, etc.,
and they all run through a shared `ctx.obj` that carries the SEC `user_agent`.

**Main modules:**

1. **`data_fetcher.py`** — SEC EDGAR access layer.
   - `SEC13FDataFetcher` — HTTP client (requests) for EDGAR; handles CIK
     normalization (10-digit zero-padded), quarter parsing (`YYYYQN`),
     rate-limited polling, retries, and locating the information-table XML
     inside a filing via a prioritized pattern match
     (`form13fInfoTable.xml` > `infotable.xml` > `.*13f.*info.*table.*\.xml` > `\d+\.xml`).
   - XML is parsed with `defusedxml.ElementTree` to avoid XXE.

2. **`models.py`** — Pure dataclass / Enum domain types.
   - `Holding`, `Holdings`, `HoldingChange`, `HoldingsChange`
   - `FundInfo`, `AmendmentInfo`, `AmendmentType`
   - `Holdings.to_dataframe()` is the canonical bridge to pandas.

3. **`analyzer.py`** — Analysis engine.
   - `SEC13FAnalyzer` orchestrates fetch + diff: `get_holdings`,
     `compare_quarters`, top-N selection, etc. Wraps `SEC13FDataFetcher`.

4. **`exporter.py`** — `DataExporter` writes `Holdings` / `HoldingsChange`
   to Excel (multi-sheet via `openpyxl`), CSV, and JSON. Default filenames
   follow `{fund_name}_{quarter}_{type}.{ext}`.

5. **`visualizer.py`** — `HoldingsVisualizer` builds matplotlib charts
   (default seaborn style, 12×8 figsize, Set2 palette). Plotly is also a
   dependency for interactive output.

6. **`monitor.py` / `monitor_config.py` / `notifier.py`** — Monitoring service.
   - `SEC13FMonitor` runs the polling loop with graceful shutdown via
     `signal`, persists `MonitorState` to a JSON state file, and pushes
     `NotificationMessage`s through `FeishuWebhookNotifier` (extends
     `WebhookNotifier`).
   - `MonitorConfigLoader` parses the YAML config (see
     `monitor_config.example.yml`) into `MonitorConfig` / `PortfolioConfig`
     / `WebhookConfig` dataclasses.

7. **`config.py`** — `Config` wraps `configparser` and loads `config.ini`
   from CWD, `../config.ini`, or `~/.sec13f_analyzer/config.ini`. Holds
   the SEC `user_agent` parts (`company_name`, `email`) and request tuning
   (delay, retries, timeout).

### Key patterns

- **Configuration**: Two-tier — `config.ini` (via `configparser`,
  loaded by `config.py`) for SEC fetcher settings, and a YAML file for
  the monitor service. `python-dotenv` is available for env-var overrides.
  CLI args take precedence over config files, which take precedence over
  defaults.
- **SEC API etiquette**: The SEC requires a User-Agent with a real
  contact (company + email). Defaults set a request delay of ~0.2s, 3
  retries with backoff, and a 30s timeout. A 403 almost always means a
  bad User-Agent.
- **Data storage**: No database. Inputs come from SEC EDGAR HTTP; outputs
  are files (Excel/CSV/JSON) under `output/`. The monitor uses a JSON
  state file to remember last-seen filings.
- **Service architecture**: CLI → `SEC13FAnalyzer` / `SEC13FMonitor` →
  `SEC13FDataFetcher` → SEC EDGAR. Visualization/export consume the
  domain models returned by the analyzer.
- **Background work**: `SEC13FMonitor.run()` is a single-threaded polling
  loop with SIGINT/SIGTERM handlers — no Celery/queue.
- **Logging**: `from loguru import logger` everywhere. Do **not** use
  `print` in library code. The CLI re-configures `logger` when `--verbose`
  is set. Prefer structured / f-string log lines with enough context to
  diagnose failures.
- **Error handling**: Network calls are wrapped with retries inside
  `SEC13FDataFetcher`. Parsing is tolerant — malformed records are
  skipped and logged rather than crashing the batch. Missing data is
  returned as `None` / empty structures, not exceptions.
- **XML safety**: Always parse 13F XML through `defusedxml`, never
  `xml.etree.ElementTree` directly.
- **No legacy code**: Deprecated or replaced code MUST be deleted, not
  left behind "for reference". When a module is superseded, remove the
  old files entirely and update all imports, tests, and documentation.

### Infrastructure

- **CI**: `.github/workflows/ci.yml` runs on push to `main`/`master` and
  on every PR. Two jobs: `quality` (black + isort + flake8 + mypy +
  pytest with `--cov-fail-under=70` across Python 3.10/3.11/3.12) and
  `security` (bandit + pip-audit).
- **Pre-commit**: `.pre-commit-config.yaml` runs the same black, isort,
  flake8, mypy checks locally. Install with `poetry run pre-commit install`.
- **No Docker / Compose** in this repo.
- **Example configs**: `monitor_config.example.yml` (monitor service);
  `config.ini` for the fetcher (not committed — create your own).

## Code Style

- **Formatter**: Black, line length **88** (configured in `pyproject.toml`,
  matched by `setup.cfg` `flake8.max-line-length = 88`).
- **Import sorter**: isort with the `black` profile.
- **Linter**: flake8 (NOT ruff). Ignores `E203,E501,W503` per `setup.cfg`.
- **Type-checker**: mypy with `ignore_missing_imports = True`. Note
  `data_fetcher.py` currently has `ignore_errors = True` — keep new code
  outside of that file fully typed.
- Prefer classes over standalone module-level functions for non-trivial logic
  (the codebase organizes behavior on `SEC13FDataFetcher`, `SEC13FAnalyzer`,
  `DataExporter`, etc.).
- Use Chinese or English docstrings consistent with surrounding files; the
  existing modules use Google-style sectioned docstrings (`Args:`, `Returns:`).
- 4-space indentation, PEP 8 compliance.
- Type hints required on all new public functions/methods.
- Descriptive names; comment only non-obvious logic.

## Testing

- Tests live under `tests/` and roughly mirror `src/sec13f_analyzer/`
  (`test_analyzer.py`, `test_data_fetcher.py`, `test_models.py`,
  `test_monitor.py`, `test_notifier.py`, `test_exporter.py`,
  `test_visualizer.py`, `test_cli.py`, `test_config.py`,
  `test_amendment_handling.py`, `test_monitor_config.py`).
- Shared fixtures live in `tests/conftest.py` (e.g. `sample_holding`).
  Real SEC XML samples for integration-style tests are under
  `tests/test_data/`.
- Pytest markers (declared in `pyproject.toml`): `unit`, `integration`,
  `slow`. Use them on new tests so they can be filtered.
- `pythonpath` is set to `src` in pytest config — imports use
  `from sec13f_analyzer.xxx import ...`, never `src.sec13f_analyzer.xxx`.
- External SEC API calls **must** be mocked. Use `pytest-mock`,
  `responses`, or `requests-mock` (all already in the `test` group).
  Patch `SEC13FDataFetcher` methods (e.g. `@patch.object(fetcher, 'get_13f_data')`)
  rather than hitting the network.
- Coverage gate in CI: `--cov-fail-under=70`. Keep new code covered.

## Dependencies

- **Poetry** for all dependency management — never use `pip install`
  directly inside the project.
- Python `>=3.10,<4`.
- Runtime libraries worth knowing:
  - `requests`, `urllib3`, `beautifulsoup4`, `lxml`, `defusedxml` — SEC
    fetching + safe XML parsing.
  - `pandas`, `numpy` — tabular analysis.
  - `matplotlib`, `seaborn`, `plotly` — visualization.
  - `openpyxl` — Excel export.
  - `click` — CLI framework.
  - `loguru` — logging (use this, not the stdlib `logging` module).
  - `pyyaml` — monitor config.
  - `python-dotenv` — optional env-var loading.
- Dev / test groups bring in `black`, `isort`, `flake8`, `mypy`,
  `bandit`, `pip-audit`, `pre-commit`, `pytest`, `pytest-cov`,
  `pytest-mock`, `pytest-asyncio`, `responses`, `requests-mock`.

## Iteration Workflow (MANDATORY for AI agents)

Every code change — feature, fix, refactor, docs, even one-line typos —
must go through this loop. **Direct pushes to `main` are forbidden**,
no exceptions. The loop ensures CI is the single source of truth for
"is this change safe to merge".

### The 6-step loop

1. **Branch from latest `main`**

   ```bash
   git checkout main && git pull --ff-only origin main
   git checkout -b <type>/<slug>
   ```

   `<type>` ∈ {`feat`, `fix`, `docs`, `refactor`, `test`, `chore`} —
   matches Conventional Commits.
   `<slug>` is 2–5 word kebab-case (e.g. `fix/login-redirect-loop`,
   `feat/csv-export`).

2. **Implement and verify locally** before pushing:

   ```bash
   poetry run black --check src/ tests/
   poetry run isort --check-only src/ tests/
   poetry run flake8 src/ tests/
   poetry run mypy src/
   poetry run pytest -m "not slow and not integration"
   ```

3. **Commit** with Conventional Commits format. Every commit message
   must include the trailer:

   ```
   Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
   ```

4. **Push the branch and open a PR**:

   ```bash
   git push -u origin HEAD
   gh pr create --fill --base main
   ```

   The PR body must include a `## Verification` section listing
   exactly what was run locally (the commands from step 2 plus their
   outcomes).

5. **Watch CI and self-heal until green**:

   ```bash
   gh run watch --exit-status        # blocks until the run finishes
   # if it fails:
   gh run view <run-id> --log-failed # diagnose
   # push fix commits to the same branch, repeat
   ```

   **Hard limit: 3 fix attempts.** If CI is still red after the third
   push, stop. Summarize what was tried and surface the failure to the
   human — do NOT keep guessing. Suspected-flaky failures count toward
   this budget; if you believe a failure is flaky, say so explicitly
   in the PR and stop.

6. **Stop after the PR is green. Do NOT auto-merge.** Report the PR URL
   and the final green CI run ID. Merging is the human's call.

### Why no direct pushes to `main`

Changes that "look clean locally" can still fail on CI's cold
environment. The PR + CI loop catches those before they land on `main`,
and gives reviewers a single artifact (the PR diff) to inspect rather
than a moving `main`.
