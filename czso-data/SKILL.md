---
name: czso-data
description: Access Czech Statistical Office (CZSO/ČSÚ) open data using the czso Python library. Use when the user needs Czech demographic, economic, or social statistics, mentions CZSO, ČSÚ, Czech statistics, or wants data about the Czech Republic (population, wages, prices, employment, regions, etc.).
---

# CZSO Data Access

Use the `czso` Python package to access open data from the Czech Statistical Office (CZSO/ČSÚ).

## Quick Reference

All scripts use inline dependencies and are run with `uv run --no-project script.py`.

### Browse the catalogue

```python
# /// script
# dependencies = ["czso"]
# ///

import czso

catalogue = czso.get_catalogue()
# Returns DataFrame with columns: dataset_id, title, description, modified, periodicity, ...
# ~1000+ datasets covering demographics, economy, prices, wages, trade, etc.

# Search by keyword in title
catalogue[catalogue["title"].str.contains("mzd", case=False, na=False)]
```

### Download a dataset

```python
# /// script
# dependencies = ["czso"]
# ///

# Clean version — friendly column names, code columns removed
df = czso.get_table("110079")
# Columns: value, year, quarter, uzemi_kod, stapro, mj, typosoby, odvetvi

# Raw version — original CZSO columns with _cis/_kod/_txt triplets
df_raw = czso.get_table("110079", clean=False)
# Columns: idhod, hodnota, stapro_kod, odvetvi_cis, odvetvi_kod, odvetvi_txt, rok, ...

# With metadata
df, meta = czso.get_table("110079", include_metadata=True)
# meta keys: dataset_id, title, description, frequency, temporal_start, temporal_end, source_url, tags
```

### Get dataset metadata (without downloading data)

```python
meta = czso.get_dataset_metadata("110079")
# Returns dict with keys: success, result
# result contains: title, notes, frequency, resources, tags, temporal_start, temporal_end
```

### Get a codelist (číselník)

```python
# Single codelist — e.g. 100 = Czech regions (kraje)
regions = czso.get_codelist(100)
# Columns: kodcis, chodnota, text, zkrtext, cznuts, ...

# Relational codelist — e.g. regions → municipalities
rel = czso.get_codelist((100, 43))
# Columns: chodnota1, text1, chodnota2, text2, ...
```

## How the Clean Transform Works

CZSO datasets use column triplets for each dimension:

- `{dim}_cis` — codelist ID (dropped by clean)
- `{dim}_kod` — code value (dropped when `_txt` exists)
- `{dim}_txt` — human-readable label (renamed to `{dim}`)

The `clean=True` default also:

- Renames `hodnota` → `value`, `rok` → `year`, `ctvrtleti` → `quarter`
- Drops the internal row ID (`idhod`)
- Lowercases all column names

## Common Dataset IDs

| ID | Description | Frequency |
|----|-------------|-----------|
| `110079` | Employees and average wages by industry | Quarterly |
| `010022` | Consumer price indices (CPI) | Monthly |
| `130185` | Deaths by week and age group | Weekly |
| `020064` | Hotel guests by country | Monthly |
| `050101` | Regional accounts (GDP by region) | Annual |

## Tips

- **Dataset IDs** are strings like `"110079"` or `"290038r19"` — find them via `get_catalogue()`.
- **Codelist IDs** are integers (e.g. `100` for regions). They appear in `_cis` columns of raw data.
- The catalogue has Czech titles — search with Czech keywords for best results.
- Use `force_redownload=True` if you need fresh data (files are cached in a temp directory).
- Some older datasets have broken download URLs (404). Try a more recent one if this happens.
