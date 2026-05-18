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
from apeSteel.sections.flexural_properties import (
    BendingAxis,
    FlexuralPlateElement,
    FlexuralSectionKind,
    FlexuralSectionProperties,
)
from apeSteel.sections.geometry import (
    ChannelSection,
    CompressionFlangeSide,
    DoubleAngleSection,
    DoublySymmetricISection,
    ISection,
    RectangularBar,
    RectangularHSS,
    RoundBar,
    RoundHSS,
    SingleAngleSection,
    SinglySymmetricISection,
    TeeSection,
)
from apeSteel.sections.properties import SectionProperties

__all__ = [
    "AISCv16Catalog",
    "BendingAxis",
    "CatalogError",
    "CatalogRowAISCv16",
    "CatalogRowEuropeanIPE",
    "ChannelSection",
    "CompressionFlangeSide",
    "DoubleAngleSection",
    "DoublySymmetricISection",
    "EuropeanIPECatalog",
    "FlexuralPlateElement",
    "FlexuralSectionKind",
    "FlexuralSectionProperties",
    "ISection",
    "RectangularBar",
    "RectangularHSS",
    "RoundBar",
    "RoundHSS",
    "SectionNotFoundError",
    "SectionProperties",
    "SectionTypeNotAdaptableError",
    "SingleAngleSection",
    "SinglySymmetricISection",
    "TeeSection",
]
