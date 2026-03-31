"""Basic smoke tests for the czso package."""

import czso


def test_public_api():
    """Check that the public API is importable."""
    assert callable(czso.get_catalogue)
    assert callable(czso.get_table)
    assert callable(czso.get_dataset_metadata)
    assert callable(czso.get_table_schema)
    assert callable(czso.get_codelist)
