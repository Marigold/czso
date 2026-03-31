"""Live integration tests that hit the real CZSO API.

Run with:  pytest tests/test_live.py -v
Skip with: pytest -m "not live"

These tests document the shape and content of real API responses so you can
see exactly what comes back from each function.
"""

import pandas as pd
import pytest

import czso

# Mark every test in this module as "live" so they can be skipped in CI
pytestmark = pytest.mark.live


# ---------------------------------------------------------------------------
# get_catalogue
# ---------------------------------------------------------------------------


class TestGetCatalogue:
    @pytest.fixture(scope="class")
    def catalogue(self) -> pd.DataFrame:
        return czso.get_catalogue()

    def test_returns_dataframe(self, catalogue):
        assert isinstance(catalogue, pd.DataFrame)

    def test_has_expected_columns(self, catalogue):
        expected = {
            "dataset_iri",
            "dataset_id",
            "title",
            "provider",
            "description",
            "spatial",
            "modified",
            "page",
            "periodicity",
            "start",
            "end",
            "keywords_all",
        }
        assert expected == set(catalogue.columns)

    def test_has_many_datasets(self, catalogue):
        # As of 2026-03 there are ~1000+ datasets
        assert len(catalogue) > 500

    def test_modified_is_datetime(self, catalogue):
        assert pd.api.types.is_datetime64_any_dtype(catalogue["modified"])

    def test_start_end_are_datetime(self, catalogue):
        assert pd.api.types.is_datetime64_any_dtype(catalogue["start"])
        assert pd.api.types.is_datetime64_any_dtype(catalogue["end"])

    def test_known_dataset_present(self, catalogue):
        """Dataset 110079 (wages by industry) should be in the catalogue."""
        assert "110079" in catalogue["dataset_id"].values

    def test_dataset_id_is_string(self, catalogue):
        assert pd.api.types.is_string_dtype(catalogue["dataset_id"])


# ---------------------------------------------------------------------------
# get_dataset_metadata
# ---------------------------------------------------------------------------


class TestGetDatasetMetadata:
    """Metadata for dataset 110079 — wages & employee counts by industry."""

    @pytest.fixture(scope="class")
    def metadata(self) -> dict:
        return czso.get_dataset_metadata("110079")

    def test_success_flag(self, metadata):
        assert metadata["success"] is True

    def test_top_level_keys(self, metadata):
        assert set(metadata.keys()) == {"success", "result"}

    def test_result_has_core_fields(self, metadata):
        result = metadata["result"]
        for key in ("name", "title", "notes", "frequency", "resources", "tags"):
            assert key in result, f"Missing key: {key}"

    def test_title(self, metadata):
        title = metadata["result"]["title"]
        assert "mzd" in title.lower() or "zaměstnanc" in title.lower()

    def test_frequency_is_quarterly(self, metadata):
        # This dataset is quarterly (R/P3M)
        assert metadata["result"]["frequency"] == "R/P3M"

    def test_has_at_least_one_resource(self, metadata):
        resources = metadata["result"]["resources"]
        assert len(resources) >= 1

    def test_resource_has_url_and_format(self, metadata):
        res = metadata["result"]["resources"][0]
        assert "url" in res
        assert "format" in res
        assert "csv" in res["format"].lower() or "zip" in res["url"].lower()

    def test_tags_are_list_of_dicts(self, metadata):
        tags = metadata["result"]["tags"]
        assert isinstance(tags, list)
        assert all(isinstance(t, dict) and "name" in t for t in tags)

    def test_temporal_coverage(self, metadata):
        result = metadata["result"]
        assert result["temporal_start"] == "2000-01-01"


# ---------------------------------------------------------------------------
# get_table — dataset 110079 (wages by industry, quarterly)
# ---------------------------------------------------------------------------


class TestGetTableWages:
    """Download dataset 110079: employees and average wages by industry."""

    @pytest.fixture(scope="class")
    def table_raw(self) -> pd.DataFrame:
        return czso.get_table("110079", clean=False)

    @pytest.fixture(scope="class")
    def table_clean(self) -> pd.DataFrame:
        return czso.get_table("110079", clean=True)

    # --- raw table ---

    def test_raw_returns_dataframe(self, table_raw):
        assert isinstance(table_raw, pd.DataFrame)

    def test_raw_has_thousands_of_rows(self, table_raw):
        assert len(table_raw) > 5000

    def test_raw_has_czso_column_triplets(self, table_raw):
        """CZSO data uses _cis/_kod/_txt column triplets for dimensions."""
        cols = set(table_raw.columns)
        # odvetvi (industry) should have all three variants
        assert "odvetvi_cis" in cols
        assert "odvetvi_kod" in cols
        assert "odvetvi_txt" in cols

    def test_raw_has_core_columns(self, table_raw):
        cols = set(table_raw.columns)
        for c in ("idhod", "hodnota", "rok", "ctvrtleti"):
            assert c in cols, f"Missing raw column: {c}"

    def test_raw_hodnota_is_numeric(self, table_raw):
        assert pd.api.types.is_float_dtype(table_raw["hodnota"])

    def test_raw_rok_is_integer(self, table_raw):
        assert table_raw["rok"].dtype.name in ("Int64", "int64")

    # --- clean table ---

    def test_clean_returns_dataframe(self, table_clean):
        assert isinstance(table_clean, pd.DataFrame)

    def test_clean_columns_are_lowercase(self, table_clean):
        for c in table_clean.columns:
            assert c == c.lower(), f"Column not lowercase: {c}"

    def test_clean_renames_hodnota_to_value(self, table_clean):
        assert "value" in table_clean.columns
        assert "hodnota" not in table_clean.columns

    def test_clean_renames_rok_to_year(self, table_clean):
        assert "year" in table_clean.columns
        assert "rok" not in table_clean.columns

    def test_clean_renames_ctvrtleti_to_quarter(self, table_clean):
        assert "quarter" in table_clean.columns
        assert "ctvrtleti" not in table_clean.columns

    def test_clean_drops_idhod(self, table_clean):
        assert "idhod" not in table_clean.columns

    def test_clean_drops_cis_columns(self, table_clean):
        cis_cols = [c for c in table_clean.columns if c.endswith("_cis")]
        assert cis_cols == [], f"Should have no _cis columns, got: {cis_cols}"

    def test_clean_drops_redundant_kod_columns(self, table_clean):
        """_kod columns should be dropped when a matching _txt exists."""
        # odvetvi had _txt, so odvetvi_kod should be gone
        assert "odvetvi_kod" not in table_clean.columns
        # but the friendly name 'odvetvi' (from _txt rename) should exist
        assert "odvetvi" in table_clean.columns

    def test_clean_has_fewer_columns_than_raw(self, table_raw, table_clean):
        assert len(table_clean.columns) < len(table_raw.columns)

    def test_clean_expected_columns(self, table_clean):
        expected = {"value", "year", "quarter", "stapro", "mj", "typosoby", "odvetvi"}
        assert expected == set(table_clean.columns)

    def test_clean_year_range(self, table_clean):
        assert table_clean["year"].min() == 2000
        assert table_clean["year"].max() >= 2024

    def test_clean_quarter_values(self, table_clean):
        assert set(table_clean["quarter"].dropna().unique()) == {1, 2, 3, 4}


# ---------------------------------------------------------------------------
# get_table with include_metadata
# ---------------------------------------------------------------------------


class TestGetTableWithMetadata:
    @pytest.fixture(scope="class")
    def result(self):
        return czso.get_table("110079", include_metadata=True)

    def test_returns_tuple(self, result):
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_first_element_is_dataframe(self, result):
        df, _ = result
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0

    def test_metadata_has_expected_keys(self, result):
        _, meta = result
        expected_keys = {
            "dataset_id",
            "title",
            "description",
            "frequency",
            "temporal_start",
            "temporal_end",
            "source_url",
            "tags",
        }
        assert expected_keys == set(meta.keys())

    def test_metadata_values(self, result):
        _, meta = result
        assert meta["dataset_id"] == "110079"
        assert meta["frequency"] == "R/P3M"
        assert meta["temporal_start"] == "2000-01-01"
        assert isinstance(meta["tags"], list)
        assert len(meta["tags"]) > 0
        assert meta["source_url"].startswith("https://")


# ---------------------------------------------------------------------------
# get_table — dataset 010022 (consumer price index, monthly)
# ---------------------------------------------------------------------------


class TestGetTableCPI:
    """Download dataset 010022: consumer price indices — a very different shape."""

    @pytest.fixture(scope="class")
    def table_clean(self) -> pd.DataFrame:
        return czso.get_table("010022")

    def test_has_many_rows(self, table_clean):
        assert len(table_clean) > 10_000

    def test_has_value_and_year(self, table_clean):
        assert "value" in table_clean.columns
        assert "year" in table_clean.columns

    def test_has_ucel_dimension(self, table_clean):
        """CPI data has 'ucel' (purpose) as a text dimension."""
        assert "ucel" in table_clean.columns

    def test_no_quarter_column(self, table_clean):
        """CPI is monthly, uses 'mesic' not 'ctvrtleti'."""
        assert "quarter" not in table_clean.columns
        assert "mesic" in table_clean.columns

    def test_sample_ucel_values(self, table_clean):
        """Some well-known CPI categories should be present."""
        categories = table_clean["ucel"].unique()
        # There should be a "food" or general category
        assert len(categories) > 5


# ---------------------------------------------------------------------------
# get_codelist
# ---------------------------------------------------------------------------


class TestGetCodelist:
    """Codelist 100 = Czech regions (kraje) by NUTS code."""

    @pytest.fixture(scope="class")
    def codelist(self) -> pd.DataFrame:
        return czso.get_codelist(100)

    def test_returns_dataframe(self, codelist):
        assert isinstance(codelist, pd.DataFrame)

    def test_has_expected_columns(self, codelist):
        cols = set(codelist.columns)
        for c in ("kodcis", "chodnota", "text", "zkrtext"):
            assert c in cols, f"Missing codelist column: {c}"

    def test_kodcis_is_100(self, codelist):
        """All rows should belong to codelist 100."""
        assert (codelist["kodcis"] == 100).all()

    def test_contains_prague(self, codelist):
        texts = codelist["text"].tolist()
        assert any("Praha" in t for t in texts)

    def test_has_14_regions(self, codelist):
        """Czech Republic has 14 regions (kraje), codelist has 14 + Extra-Regio = 15."""
        non_extra = codelist[codelist["text"] != "Extra-Regio"]
        assert len(non_extra) == 14

    def test_has_cznuts_codes(self, codelist):
        """Regions have NUTS codes like CZ010, CZ020, etc."""
        nuts = codelist["cznuts"].dropna().tolist()
        assert any(n.startswith("CZ0") for n in nuts)


class TestGetCodelistRelational:
    """Relational codelist (100, 43) = regions → municipalities."""

    @pytest.fixture(scope="class")
    def codelist(self) -> pd.DataFrame:
        return czso.get_codelist((100, 43))

    def test_returns_dataframe(self, codelist):
        assert isinstance(codelist, pd.DataFrame)

    def test_has_thousands_of_rows(self, codelist):
        # Regions → municipalities: thousands of links
        assert len(codelist) > 3000

    def test_has_relational_columns(self, codelist):
        cols = set(codelist.columns)
        for c in ("chodnota1", "text1", "chodnota2", "text2"):
            assert c in cols

    def test_contains_praha_region(self, codelist):
        assert any("Praha" in t for t in codelist["text1"].values)


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestGetTablePopulation:
    """Download dataset 130149: population by sex and age group.

    This dataset's resource URL contains query parameters (?version=...)
    which previously broke file-type detection.
    """

    @pytest.fixture(scope="class")
    def table_clean(self) -> pd.DataFrame:
        return czso.get_table("130149")

    def test_returns_dataframe(self, table_clean):
        assert isinstance(table_clean, pd.DataFrame)

    def test_has_many_rows(self, table_clean):
        assert len(table_clean) > 100_000

    def test_has_value_and_uzemi(self, table_clean):
        assert "value" in table_clean.columns
        assert "uzemi" in table_clean.columns

    def test_contains_prague(self, table_clean):
        assert any("Praha" in str(v) for v in table_clean["uzemi"].unique())


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrors:
    def test_invalid_dataset_id(self):
        """Non-existent dataset raises DatasetNotFoundError."""
        with pytest.raises(czso.DatasetNotFoundError, match="not found"):
            czso.get_dataset_metadata("XXXXXXXXX_nonexistent")

    def test_no_resources(self):
        """get_table on a dataset with missing resources should raise ValueError."""
        # We test the error path by requesting a resource index out of range
        with pytest.raises(ValueError, match="Resource .* not found"):
            czso.get_table("110079", resource_num=999)
