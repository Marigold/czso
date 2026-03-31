# czso

Python wrapper around Open Data from the [Czech Statistical Office (CZSO)](https://www.czso.cz/).

Inspired by the R package by Petr Bouchal: [petrbouchal/czso](https://github.com/petrbouchal/czso)

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Marigold/czso/blob/main/demo.ipynb)

## Installation

```bash
pip install czso
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv add czso
```

## Quick start

> **📓 See [`demo.ipynb`](demo.ipynb) for an interactive walkthrough** — browse the catalogue, download datasets, plot wages over time, and explore codelists.

```python
import czso

# Browse available datasets
catalogue = czso.get_catalogue()
print(catalogue[["dataset_id", "title"]].head())

# Download a dataset as a DataFrame
df = czso.get_table("110079")

# Get dataset with metadata
df, meta = czso.get_table("110079", include_metadata=True)
print(meta["title"])

# Get raw (uncleaned) data
df_raw = czso.get_table("110079", clean=False)

# Retrieve a codelist (číselník)
codelist = czso.get_codelist(100)
```

## API

| Function | Description |
|----------|-------------|
| `get_catalogue()` | Full catalogue of available CZSO open datasets |
| `get_table(dataset_id, ...)` | Download and read a dataset as a DataFrame |
| `get_dataset_metadata(dataset_id)` | JSON-LD metadata for a dataset |
| `get_table_schema(dataset_id)` | JSON table schema for a dataset resource |
| `get_codelist(codelist_id)` | Retrieve a CZSO codelist (číselník) |

### `get_table` options

- `resource_num` — which resource to download (default `0`)
- `force_redownload` — skip cache and re-download
- `dest_dir` — directory for caching downloaded files
- `clean` — drop code columns, rename to friendly names (default `True`)
- `include_metadata` — return `(DataFrame, metadata_dict)` tuple

## Related projects

- [mcp-csu](https://github.com/reloadcz/mcp-csu) — MCP server for the CZSO DataStat API. Gives AI assistants (Claude, etc.) direct access to 700+ statistical datasets. Run with `uvx mcp-csu`.
- [petrbouchal/czso](https://github.com/petrbouchal/czso) — R package for CZSO open data (the inspiration for this project).

## Development

```bash
make .venv          # install all deps (including dev: ruff, ty, pytest)
make format         # auto-format with ruff
make lint           # lint + fix with ruff
make check-typing   # typecheck with ty
make test           # format + lint + typecheck + unit tests
```

## License

MIT
