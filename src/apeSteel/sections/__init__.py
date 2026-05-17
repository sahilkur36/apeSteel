"""Sections subpackage: geometry, properties, and catalog.

Layout:
* apeSteel.sections.geometry: plate-built shape classes (no material info).
* apeSteel.sections.properties: the universal SectionProperties frozen
  dataclass that every downstream calculator consumes.
* apeSteel.sections.catalog: AISC v16 and European catalogs (Phase 6).

See docs/design_notes/01_section_catalog.md for the design.
"""

from apeSteel.sections.catalog import (
    AISCv16Catalog,
    CatalogError,
    CatalogRowAISCv16,
    CatalogRowEuropeanIPE,
    EuropeanIPECatalog,
    SectionNotFoundError,
    SectionTypeNotAdaptableError,
)
from apeSteel.sections.geometry import (
    CompressionFlangeSide,
    DoublySymmetricISection,
    ISection,
    SinglySymmetricISection,
)
from apeSteel.sections.properties import SectionProperties

__all__ = [
    "AISCv16Catalog",
    "CatalogError",
    "CatalogRowAISCv16",
    "CatalogRowEuropeanIPE",
    "CompressionFlangeSide",
    "DoublySymmetricISection",
    "EuropeanIPECatalog",
    "ISection",
    "SectionNotFoundError",
    "SectionProperties",
    "SectionTypeNotAdaptableError",
    "SinglySymmetricISection",
]
