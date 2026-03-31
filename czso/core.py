"""Core functions for accessing CZSO open data.

API endpoints:
- Catalogue: https://vdb.czso.cz/pll/eweb/lkod_ld.seznam (CSV)
- Dataset metadata: https://vdb.czso.cz/pll/eweb/lkod_ld.datova_sada?id={dataset_id} (JSON-LD)
- Dataset data: https://vdb.czso.cz/pll/eweb/package_show?id={dataset_id} (JSON with resource URLs)
- SPARQL: https://data.gov.cz/sparql (alternative catalogue access)
"""

import io
import json
import tempfile
import zipfile
from pathlib import Path
from typing import Literal, overload

import pandas as pd
import requests

BASE_URL = "https://vdb.czso.cz/pll/eweb"
CATALOGUE_URL = f"{BASE_URL}/lkod_ld.seznam"
METADATA_URL = f"{BASE_URL}/lkod_ld.datova_sada"
PACKAGE_URL = f"{BASE_URL}/package_show"
SPARQL_URL = "https://data.gov.cz/sparql"

_USER_AGENT = "czso-python/0.1.0"


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": _USER_AGENT})
    return s


def get_catalogue() -> pd.DataFrame:
    """Retrieve the full catalogue of available CZSO open datasets.

    Returns a DataFrame with columns: dataset_iri, dataset_id, title, provider,
    description, spatial, modified, page, periodicity, start, end, keywords_all.
    """
    resp = _session().get(CATALOGUE_URL)
    resp.raise_for_status()
    # CZSO uses backslash-escaped quotes (\"…\") instead of the standard
    # RFC 4180 doubled quotes (""…""). Tell pandas about the escape character.
    df = pd.read_csv(io.StringIO(resp.text), escapechar="\\")
    for col in ("modified", "start", "end"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


class DatasetNotFoundError(ValueError):
    """Raised when a dataset ID does not exist in the CZSO catalogue."""


def get_dataset_metadata(dataset_id: str) -> dict:
    """Retrieve JSON-LD metadata for a dataset.

    Args:
        dataset_id: CZSO dataset identifier (e.g. "110079").

    Returns:
        Parsed JSON dict with dataset metadata including resources, frequency,
        spatial coverage, and schema links.

    Raises:
        DatasetNotFoundError: If the dataset ID does not exist.
    """
    resp = _session().get(PACKAGE_URL, params={"id": dataset_id})
    resp.raise_for_status()
    data = resp.json()
    if not data.get("success"):
        error = data.get("error", {})
        msg = error.get("message", "Unknown error")
        raise DatasetNotFoundError(
            f"Dataset '{dataset_id}' not found: {msg}"
        )
    return data


def get_table_schema(dataset_id: str, resource_num: int = 0) -> dict | None:
    """Retrieve the JSON table schema for a dataset resource.

    Args:
        dataset_id: CZSO dataset identifier.
        resource_num: Index of the resource (default 0 = first).

    Returns:
        Parsed JSON schema dict, or None if no schema is available.
    """
    meta = get_dataset_metadata(dataset_id)
    resources = meta.get("result", {}).get("resources", [])
    if resource_num >= len(resources):
        return None
    schema_url = resources[resource_num].get("describedBy")
    if not schema_url:
        return None
    resp = _session().get(schema_url)
    resp.raise_for_status()
    # CZSO schema files sometimes include a UTF-8 BOM
    text = resp.text.removeprefix("\ufeff")
    return json.loads(text)


@overload
def get_table(
    dataset_id: str,
    resource_num: int = ...,
    force_redownload: bool = ...,
    dest_dir: str | Path | None = ...,
    clean: bool = ...,
    include_metadata: Literal[False] = ...,
) -> pd.DataFrame: ...


@overload
def get_table(
    dataset_id: str,
    resource_num: int = ...,
    force_redownload: bool = ...,
    dest_dir: str | Path | None = ...,
    clean: bool = ...,
    include_metadata: Literal[True] = ...,
) -> tuple[pd.DataFrame, dict]: ...


def get_table(
    dataset_id: str,
    resource_num: int = 0,
    force_redownload: bool = False,
    dest_dir: str | Path | None = None,
    clean: bool = True,
    include_metadata: bool = False,
) -> pd.DataFrame | tuple[pd.DataFrame, dict]:
    """Download and read a CZSO dataset table.

    Args:
        dataset_id: CZSO dataset identifier (e.g. "290038r19").
        resource_num: Which resource to download (default 0 = first).
        force_redownload: If True, skip cache and re-download.
        dest_dir: Directory for caching downloaded files. Defaults to temp dir.
        clean: If True (default), drop code columns (_cis, _kod), rename _txt
            columns to friendly names, and translate core columns to English.
            Set to False for raw CZSO output.
        include_metadata: If True, return (DataFrame, metadata_dict) instead of
            just DataFrame. Metadata includes title, description, temporal coverage,
            tags, and source URL from the CZSO API.

    Returns:
        DataFrame with the dataset (or tuple of DataFrame and metadata dict when
        include_metadata=True). When clean=True, columns use friendly names
        (e.g. 'value', 'year', 'uzemi'). When clean=False, original CZSO columns.
    """
    meta = get_dataset_metadata(dataset_id)
    result = meta.get("result", {})
    resources = result.get("resources", [])

    if not resources:
        raise ValueError(f"No resources found for dataset '{dataset_id}'")
    if resource_num >= len(resources):
        raise ValueError(
            f"Resource {resource_num} not found; dataset has {len(resources)} resources"
        )

    resource = resources[resource_num]
    url = resource["url"]
    fmt = resource.get("format", "")

    # Resolve cache path
    if dest_dir is None:
        dest_dir = Path(tempfile.gettempdir()) / "czso"
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Build a cache filename from the URL; fall back to dataset_id when the
    # URL path is ambiguous (e.g. codelist URLs that all share the same path).
    url_filename = url.rsplit("/", 1)[-1].split("?")[0]
    if "." in url_filename:
        filename = url_filename
    else:
        ext = ".csv"
        if "zip" in fmt.lower() or url_filename.endswith(".zip"):
            ext = ".zip"
        filename = f"{dataset_id}-r{resource_num}{ext}"
    local_path = dest_dir / filename

    # Download if needed
    if force_redownload or not local_path.exists():
        resp = _session().get(url)
        resp.raise_for_status()
        local_path.write_bytes(resp.content)

    # Detect file type from extension first, then from resource metadata,
    # and finally by sniffing the first bytes (ZIP magic: PK\x03\x04).
    content_head = local_path.read_bytes()[:4] if local_path.exists() else b""
    is_zip = (
        local_path.suffix.lower() == ".zip"
        or "zip" in fmt.lower()
        or content_head[:4] == b"PK\x03\x04"
    )
    is_csv = local_path.suffix.lower() == ".csv" or "csv" in fmt.lower()

    if is_zip:
        df = _read_zip(local_path)
    elif is_csv:
        df = _read_csv(local_path)
    else:
        raise ValueError(
            f"Unsupported format '{fmt}' for resource. File saved to {local_path}"
        )

    if clean:
        df = _clean_df(df)

    if include_metadata:
        resource = resources[resource_num]
        metadata = {
            "dataset_id": dataset_id,
            "title": result.get("title", ""),
            "description": result.get("notes", ""),
            "frequency": result.get("frequency", ""),
            "temporal_start": result.get("temporal_start", ""),
            "temporal_end": result.get("temporal_end", ""),
            "source_url": resource.get("url", ""),
            "tags": [t["name"] for t in result.get("tags", [])],
        }
        return df, metadata

    return df


def get_codelist(
    codelist_id: int | str | tuple[int | str, int | str],
    **kwargs,
) -> pd.DataFrame:
    """Retrieve a CZSO codelist (číselník).

    Codelists are available as regular datasets in the CZSO catalogue. This function
    builds the dataset_id and downloads the CSV resource.

    Args:
        codelist_id: Numeric ID or string like "cis100". Pass a tuple of two IDs
            (e.g. (100, 43)) to get a relational table between two codelists.
        **kwargs: Passed to get_table (e.g. force_redownload, dest_dir).

    Returns:
        DataFrame with codelist entries (CHODNOTA, TEXT, KODCIS, etc.).
    """
    if isinstance(codelist_id, (list, tuple)):
        id1, id2 = codelist_id
        dataset_id = f"cis{_normalize_codelist_id(id1)}vaz{_normalize_codelist_id(id2)}"
    else:
        dataset_id = f"cis{_normalize_codelist_id(codelist_id)}"

    # Codelists typically have resource 0=XML, 1=CSV — find the CSV one
    meta = get_dataset_metadata(dataset_id)
    resources = meta.get("result", {}).get("resources", [])
    csv_idx = 0
    for i, res in enumerate(resources):
        if (
            "csv" in res.get("format", "").lower()
            or "csv" in res.get("name", "").lower()
        ):
            csv_idx = i
            break

    kwargs.setdefault("clean", False)
    return get_table(dataset_id, resource_num=csv_idx, **kwargs)


def _normalize_codelist_id(cid: int | str) -> str:
    """Normalize codelist ID to numeric string."""
    s = str(cid)
    # Strip "cis" prefix if present
    if s.lower().startswith("cis"):
        s = s[3:]
    return s


def _clean_df(df: pd.DataFrame) -> pd.DataFrame:
    """Clean up CZSO data by removing code columns and renaming to friendly names.

    CZSO datasets use triplets of columns for each dimension:
      {dim}_cis (codelist ID), {dim}_kod (code value), {dim}_txt (text label)
    This function keeps only the text labels and renames them.
    For orphaned _kod columns (no matching _txt), the codelist is fetched
    and codes are replaced with text labels.
    """
    # 1. Resolve orphaned _kod columns (have _cis but no _txt) via codelist lookup
    txt_bases = {
        c.lower().rsplit("_txt", 1)[0] for c in df.columns if c.lower().endswith("_txt")
    }
    cis_cols = {c for c in df.columns if c.lower().endswith("_cis")}
    # Build a case-insensitive lookup for _kod columns
    kod_col_map = {c.lower(): c for c in df.columns if c.lower().endswith("_kod")}
    for cis_col in list(cis_cols):
        base = cis_col.lower().rsplit("_cis", 1)[0]
        kod_col = kod_col_map.get(f"{base}_kod")
        if kod_col and base not in txt_bases:
            codelist_id = df[cis_col].dropna().unique()
            if len(codelist_id) == 1:
                try:
                    cl = get_codelist(int(codelist_id[0]))
                    # Column names may be upper or lowercase depending on the codelist
                    val_col = "CHODNOTA" if "CHODNOTA" in cl.columns else "chodnota"
                    txt_col = "TEXT" if "TEXT" in cl.columns else "text"
                    mapping = dict(zip(cl[val_col].astype(str), cl[txt_col]))
                    df[kod_col] = (
                        df[kod_col].astype(str).map(mapping).fillna(df[kod_col])
                    )
                except Exception:
                    pass  # keep raw codes if codelist lookup fails

    # 2. Drop _cis columns (codelist IDs — never needed for analysis)
    df = df.drop(columns=list(cis_cols))

    # 3. Drop _kod columns where a corresponding _txt column exists
    kod_cols = [
        c
        for c in df.columns
        if c.lower().endswith("_kod") and c.lower().rsplit("_kod", 1)[0] in txt_bases
    ]
    df = df.drop(columns=kod_cols)

    # 3b. Drop stapro_kod if STAPRO_TXT exists (special case — no _kod/_txt symmetry)
    if "STAPRO_TXT" in df.columns and "stapro_kod" in df.columns:
        df = df.drop(columns=["stapro_kod"])

    # 3c. Drop any remaining _kod columns that have a single constant value —
    #     these are dataset-level type codes, not useful dimensions.
    const_kod = [
        c
        for c in df.columns
        if c.lower().endswith("_kod") and df[c].nunique(dropna=True) <= 1
    ]
    df = df.drop(columns=const_kod)

    # 4. Drop idhod (internal row ID)
    if "idhod" in df.columns:
        df = df.drop(columns=["idhod"])

    # 5. Rename _txt → base name, core columns to English
    renames = {}
    for c in df.columns:
        if c.lower().endswith("_txt"):
            renames[c] = c.lower().rsplit("_txt", 1)[0]
    renames.update({"hodnota": "value", "rok": "year", "ctvrtleti": "quarter"})
    df = df.rename(columns={k: v for k, v in renames.items() if k in df.columns})

    # 6. Lowercase all column names
    df.columns = [c.lower() for c in df.columns]

    return df


def _read_zip(path: Path) -> pd.DataFrame:
    """Extract and read CSV from a ZIP archive."""
    with zipfile.ZipFile(path) as zf:
        csv_names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        if not csv_names:
            raise ValueError(f"No CSV file found in {path}")
        # Read the first (or largest) CSV
        csv_name = csv_names[0]
        with zf.open(csv_name) as f:
            return _read_csv_bytes(f.read())


def _read_csv(path: Path) -> pd.DataFrame:
    """Read a CSV file with encoding detection."""
    return _read_csv_bytes(path.read_bytes())


def _read_csv_bytes(data: bytes) -> pd.DataFrame:
    """Read CSV bytes with encoding fallback and type coercion."""
    for encoding in ("utf-8", "windows-1250", "iso-8859-2"):
        try:
            text = data.decode(encoding)
            df = pd.read_csv(io.StringIO(text), low_memory=False)
            if len(df.columns) > 1:
                break
        except (UnicodeDecodeError, pd.errors.ParserError):
            continue
    else:
        raise ValueError("Could not decode CSV with any supported encoding")

    # Type coercion matching R package conventions
    if "rok" in df.columns:
        df["rok"] = pd.to_numeric(df["rok"], errors="coerce").astype("Int64")
    if "ctvrtleti" in df.columns:
        df["ctvrtleti"] = pd.to_numeric(df["ctvrtleti"], errors="coerce").astype(
            "Int64"
        )
    if "hodnota" in df.columns:
        df["hodnota"] = pd.to_numeric(df["hodnota"], errors="coerce")

    return df
