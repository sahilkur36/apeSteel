"""Section catalogs - AISC v16 and European IPE (Phase 6).

This subpackage adapts the AISC v16 SI shapes database and a small
EN 10365 IPE subset into the universal
:class:`~apeSteel.sections.properties.SectionProperties` frozen
dataclass that every downstream apeSteel calculator consumes.

Two ways in:

* :class:`AISCv16Catalog` - 2 299 rolled shapes (W/M/S/HP I-shapes plus
  channels, angles, HSS, pipes) backed by ``data/AISC_v16_shapes.csv``.
* :class:`EuropeanIPECatalog` - EN 10365 IPE 200, 300, 400, 500, 600
  backed by ``data/european_IPE_subset.csv``.  Users extend by editing
  the CSV or by pointing the catalog at their own file.

Both expose ``get_row``, ``get_section_properties``,
``get_doubly_symmetric_i_geometry`` and fall back to RapidFuzz when an
exact label match is missing.

See ``docs/design_notes/01_section_catalog.md`` for the design.
"""

from __future__ import annotations

from apeSteel.sections.catalog._aisc_v16_row import (
    DOUBLY_SYMMETRIC_I_SHAPE_AISC_TYPES,
    CatalogRowAISCv16,
    SectionType,
)
from apeSteel.sections.catalog._european_ipe_row import CatalogRowEuropeanIPE
from apeSteel.sections.catalog.aisc_v16 import (
    DEFAULT_FUZZY_SIMILARITY_THRESHOLD,
    AISCv16Catalog,
)
from apeSteel.sections.catalog.european_ipe import EuropeanIPECatalog
from apeSteel.sections.catalog.exceptions import (
    CatalogError,
    SectionNotFoundError,
    SectionTypeNotAdaptableError,
)

__all__ = [
    "DEFAULT_FUZZY_SIMILARITY_THRESHOLD",
    "DOUBLY_SYMMETRIC_I_SHAPE_AISC_TYPES",
    "AISCv16Catalog",
    "CatalogError",
    "CatalogRowAISCv16",
    "CatalogRowEuropeanIPE",
    "EuropeanIPECatalog",
    "SectionNotFoundError",
    "SectionType",
    "SectionTypeNotAdaptableError",
]
