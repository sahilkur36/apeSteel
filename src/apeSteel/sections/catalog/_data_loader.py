"""Lazy, cached AISC v16 CSV loader.

The loader is intentionally minimal - it owns one job: read
``data/AISC_v16_shapes.csv`` once, rename the columns that aren't valid
Python identifiers, scale every numeric column to apeSteel base units,
and hand out
:class:`~apeSteel.sections.catalog._aisc_v16_row.CatalogRowAISCv16`
instances by ``AISC_Manual_Label``.

A single load is cached at the module level so multiple
:class:`~apeSteel.sections.catalog.aisc_v16.AISCv16Catalog` instances
share the parsed DataFrame.  The cache is keyed on the CSV path so
test code can point to a fixture file without polluting the default
catalog.
"""

from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path
from typing import Final

import pandas as pd

from apeSteel.sections.catalog._aisc_v16_row import CatalogRowAISCv16
from apeSteel.sections.catalog._unit_conversion import AISC_V16_COLUMN_UNIT_TO_BASE_FACTOR

AISC_V16_CSV_COLUMN_RENAMES: Final[dict[str, str]] = {
    "bf/2tf": "bf_2tf",
    "b/t": "b_t",
    "b/tdes": "b_tdes",
    "h/tw": "h_tw",
    "h/tdes": "h_tdes",
    "D/t": "D_t",
    "twdet/2": "twdet_2",
    "tan(α)": "tan_alpha",
}
"""Map invalid-identifier CSV column names to Python-safe equivalents."""

DEFAULT_AISC_V16_CSV_PATH: Final[Path] = (
    Path(__file__).resolve().parent / "data" / "AISC_v16_shapes.csv"
)
"""Path to the shipped AISC v16 CSV next to the catalog package."""


def _normalize_value(raw: object, base_factor: float) -> float | None:
    """Convert a raw CSV cell into a base-units float or None."""
    if isinstance(raw, float) and math.isnan(raw):
        return None
    if raw is None or raw == "":
        return None
    return float(raw) * base_factor  # type: ignore[arg-type]


def _row_dataframe_to_dict(row: pd.Series) -> dict[str, object]:
    """Turn a DataFrame row into a dict ready for ``CatalogRowAISCv16``.

    * Renames CSV columns whose names aren't valid Python identifiers.
    * Applies the column-specific unit conversion to every numeric cell.
    * Leaves :class:`str` columns (``Type``, ``AISC_Manual_Label``)
      untouched.
    """
    payload: dict[str, object] = {}
    for csv_column_name, raw_value in row.items():
        python_field_name: str = AISC_V16_CSV_COLUMN_RENAMES.get(
            str(csv_column_name), str(csv_column_name)
        )
        if python_field_name in ("Type", "AISC_Manual_Label"):
            payload[python_field_name] = (
                None if (isinstance(raw_value, float) and math.isnan(raw_value)) else str(raw_value)
            )
            continue
        base_factor: float = AISC_V16_COLUMN_UNIT_TO_BASE_FACTOR.get(python_field_name, 1.0)
        payload[python_field_name] = _normalize_value(raw_value, base_factor)
    return payload


@lru_cache(maxsize=4)
def _load_dataframe_cached(csv_path: str) -> pd.DataFrame:
    """Read the CSV into a DataFrame and uppercase the label column."""
    df: pd.DataFrame = pd.read_csv(Path(csv_path))
    df["AISC_Manual_Label"] = df["AISC_Manual_Label"].astype(str).str.upper()
    return df


def load_aisc_v16_dataframe(csv_path: Path | None = None) -> pd.DataFrame:
    """Load (and cache) the AISC v16 CSV."""
    resolved: Path = csv_path if csv_path is not None else DEFAULT_AISC_V16_CSV_PATH
    return _load_dataframe_cached(str(resolved.resolve()))


def build_catalog_row_aisc_v16(row: pd.Series) -> CatalogRowAISCv16:
    """Validate a DataFrame row into a :class:`CatalogRowAISCv16`."""
    payload: dict[str, object] = _row_dataframe_to_dict(row)
    return CatalogRowAISCv16.model_validate(payload)


__all__ = [
    "AISC_V16_CSV_COLUMN_RENAMES",
    "DEFAULT_AISC_V16_CSV_PATH",
    "build_catalog_row_aisc_v16",
    "load_aisc_v16_dataframe",
]
