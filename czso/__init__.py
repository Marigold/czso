"""Python client for Czech Statistical Office (CZSO) open data.

Inspired by the R package by Petr Bouchal: https://github.com/petrbouchal/czso
"""

from czso.core import (
    DatasetNotFoundError,
    get_catalogue,
    get_codelist,
    get_dataset_metadata,
    get_table,
    get_table_schema,
)

__all__ = [
    "DatasetNotFoundError",
    "get_catalogue",
    "get_codelist",
    "get_dataset_metadata",
    "get_table",
    "get_table_schema",
]
