# AGENTS.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Always run `make check` before committing** to catch formatting, linting, and type errors locally.

## Project

Python wrapper for the Czech Statistical Office (CZSO/ČSÚ) open data API. Published on PyPI as `czso`.

## Commands

```bash
make .venv          # Create venv and install deps (requires uv)
make test           # Full check: formatting → linting → typing → unit tests
make format         # Auto-format with ruff
make lint           # Lint with ruff (ruff check --fix)
make unittest       # Run pytest (excludes live tests by default)
make check          # Alias for test
make clean          # Remove caches and build artifacts
make clobber        # clean + remove .venv
```

Run a single test:
```bash
uv run pytest tests/test_core.py::test_public_api -v
```

Run live integration tests (hits real CZSO API):
```bash
uv run pytest -m live -v
```

## Architecture

Single-module package: all logic lives in `czso/core.py`, re-exported via `czso/__init__.py`.

**Public API** (5 functions + 1 exception):
- `get_catalogue()` → DataFrame of all CZSO datasets
- `get_table(dataset_id)` → DataFrame (with optional metadata tuple return)
- `get_dataset_metadata(dataset_id)` → dict
- `get_table_schema(dataset_id)` → dict or None
- `get_codelist(codelist_id)` → DataFrame
- `DatasetNotFoundError` — raised for invalid dataset IDs

**CZSO column conventions**: datasets use `_cis`/`_kod`/`_txt` triplets for coded dimensions. The `clean=True` mode (default) drops `_cis` and `_kod` columns, renames `_txt` to the base name, and translates core Czech column names (`hodnota`→`value`, `rok`→`year`, `ctvrtleti`→`quarter`).

## CZSO API Quirks

- **Catalogue CSV uses backslash-escaped quotes** (`\"`) instead of RFC 4180 doubled quotes (`""`). Always pass `escapechar="\\"` to `pd.read_csv`.
- **Schema JSON files may have a UTF-8 BOM** (`\ufeff`). Strip it before `json.loads`.
- **Metadata API returns `{"success": false}` for invalid dataset IDs** — it does NOT raise an HTTP error. Always check the `success` field.
- **Older dataset download URLs are often dead (404)**. Use recently-updated datasets in examples/tests. Check the `modified` column in the catalogue.
- **Column values vary across datasets** — don't assume `stapro`, `ucel`, etc. have the same values everywhere. Inspect actual data before writing filters.

## Testing

- `tests/test_core.py` — fast smoke tests (importability, API surface)
- `tests/test_live.py` — integration tests marked `@pytest.mark.live`; these call the real CZSO API and are excluded from default `pytest` runs

## Tooling

- **uv** for dependency management and Python versions
- **ruff** for formatting and linting
- **ty** for type checking
- **pytest** for tests
- Python 3.12+ required; CI tests on 3.12 and 3.13
