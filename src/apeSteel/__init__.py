"""apeSteel: structural-steel design library for AISC 360 and AISC 341.

apeSteel is a composition-based, strictly-typed Python library for steel
member and connection design per the American Institute of Steel
Construction specifications, with parallel support for European
EN 10365 IPE rolled shapes.

Domain objects (each owns its own domain):

* `SteelMaterial` (e.g. `A992`, `S355`) - mechanical properties.
* `DoublySymmetricISection` - doubly-symmetric I (equal flanges).
* `SinglySymmetricISection` - singly-symmetric I (unequal flanges,
  Phase 9b).
* `Bracing` - lateral-bracing scenario (Lb_top, Lb_bot, Cb).

Composites:

* `Element` aggregates section + material + construction + bracing
  and exposes every AISC member-level check as a method.  Its
  ``section`` field accepts either ``DoublySymmetricISection`` or
  ``SinglySymmetricISection`` (the ``ISection`` union).
* `BeamColumnConnection` aggregates (beam: Element, column: Element)
  and exposes joint-level seismic checks.

Catalog access:

* `AISCv16Catalog` - the AISC v16 SI shapes database.
* `EuropeanIPECatalog` - EN 10365 IPE subset.

Serviceability:

* `compute_deflection_*` family - elastic mid-span / tip deflections
  for simply-supported and cantilever beams.

Seismic:

* `check_column_flange_tension_341` - AISC 341 §E3.6e column-flange
  tension check at a beam-to-column moment connection.
* `check_panel_zone_shear_341` - AISC 360 §J10.6 panel-zone shear
  capacity (capacity-amplified by Ry,col).
* `recommend_doubler_plate_thickness_341` - shop-practical doubler
  sizing for a panel-zone shear deficit.
* `check_continuity_plates_required_358` - need check and minimum
  dimensions for transverse stiffeners.

See docs/ARCHITECTURE.md, docs/UNITS_AND_CONVENTIONS.md, and
docs/ROADMAP.md for the design contract and phased port plan.
"""

from __future__ import annotations

from apeSteel.beam_column_connection import BeamColumnConnection
from apeSteel.bracing import Bracing
from apeSteel.checks import BeamCheckReport, run_full_beam_check
from apeSteel.classification import (
    AxialCompressionClassificationReport,
    FlexuralCompactnessReport,
    PlateElementClassification,
    SeismicCompactnessReport,
    classify_axial_compression_B4_1a,
    classify_flexural_compactness_B4_1b,
    classify_seismic_compactness_341_D1,
)
from apeSteel.core.materials import (
    A36,
    A992,
    S275,
    S355,
    S460,
    A572_Gr50,
    SteelMaterial,
)
from apeSteel.core.result_types import AISCClauseReference, Report
from apeSteel.core.units import ACTIVE_BASE, EXPECTED_BASE
from apeSteel.element import (
    BothFlangesFlexureF2Report,
    BothFlangesFlexureF3Report,
    BothFlangesFlexureF4Report,
    BothFlangesFlexureF5Report,
    Element,
    GoverningFlange,
)
from apeSteel.flexure import (
    FlexureF2Report,
    FlexureF3Report,
    FlexureF4Report,
    FlexureF5Report,
    compute_Cb_from_quarter_point_moments,
    compute_flexural_strength_F2_compact_doubly_symmetric,
    compute_flexural_strength_F3_noncompact_or_slender_flange,
    compute_flexural_strength_F4,
    compute_flexural_strength_F4_doubly_symmetric_noncompact_web,
    compute_flexural_strength_F5_slender_web_plate_girder,
)
from apeSteel.sections import (
    AISCv16Catalog,
    CatalogError,
    CatalogRowAISCv16,
    CatalogRowEuropeanIPE,
    CompressionFlangeSide,
    DoublySymmetricISection,
    EuropeanIPECatalog,
    ISection,
    SectionNotFoundError,
    SectionProperties,
    SectionTypeNotAdaptableError,
    SinglySymmetricISection,
)
from apeSteel.seismic import (
    ContinuityPlateRecommendationReport,
    DoublerPlateRecommendationReport,
    PanelZoneColumnFlangeTensionReport,
    PanelZoneShearReport,
    check_column_flange_tension_341,
    check_continuity_plates_required_358,
    check_panel_zone_shear_341,
    recommend_doubler_plate_thickness_341,
)
from apeSteel.serviceability import (
    CantileverUDLAndTipLoadDeflectionReport,
    SimplySupportedPointLoadArbitraryDeflectionReport,
    SimplySupportedPointLoadMidspanDeflectionReport,
    SimplySupportedUDLDeflectionReport,
    compute_deflection_cantilever_udl_and_tip_load,
    compute_deflection_simply_supported_point_load_arbitrary,
    compute_deflection_simply_supported_point_load_midspan,
    compute_deflection_simply_supported_udl,
    recommend_camber_from_dead_load_deflection,
)
from apeSteel.shear import (
    ShearG2Report,
    compute_shear_strength_G2_doubly_symmetric,
)

__version__: str = "0.0.0"

__all__ = [
    "A36",
    "A992",
    "ACTIVE_BASE",
    "EXPECTED_BASE",
    "S275",
    "S355",
    "S460",
    "A572_Gr50",
    "AISCClauseReference",
    "AISCv16Catalog",
    "AxialCompressionClassificationReport",
    "BeamCheckReport",
    "BeamColumnConnection",
    "BothFlangesFlexureF2Report",
    "BothFlangesFlexureF3Report",
    "BothFlangesFlexureF4Report",
    "BothFlangesFlexureF5Report",
    "Bracing",
    "CantileverUDLAndTipLoadDeflectionReport",
    "CatalogError",
    "CatalogRowAISCv16",
    "CatalogRowEuropeanIPE",
    "CompressionFlangeSide",
    "ContinuityPlateRecommendationReport",
    "DoublerPlateRecommendationReport",
    "DoublySymmetricISection",
    "Element",
    "EuropeanIPECatalog",
    "FlexuralCompactnessReport",
    "FlexureF2Report",
    "FlexureF3Report",
    "FlexureF4Report",
    "FlexureF5Report",
    "GoverningFlange",
    "ISection",
    "PanelZoneColumnFlangeTensionReport",
    "PanelZoneShearReport",
    "PlateElementClassification",
    "Report",
    "SectionNotFoundError",
    "SectionProperties",
    "SectionTypeNotAdaptableError",
    "SeismicCompactnessReport",
    "ShearG2Report",
    "SimplySupportedPointLoadArbitraryDeflectionReport",
    "SimplySupportedPointLoadMidspanDeflectionReport",
    "SimplySupportedUDLDeflectionReport",
    "SinglySymmetricISection",
    "SteelMaterial",
    "__version__",
    "check_column_flange_tension_341",
    "check_continuity_plates_required_358",
    "check_panel_zone_shear_341",
    "classify_axial_compression_B4_1a",
    "classify_flexural_compactness_B4_1b",
    "classify_seismic_compactness_341_D1",
    "compute_Cb_from_quarter_point_moments",
    "compute_deflection_cantilever_udl_and_tip_load",
    "compute_deflection_simply_supported_point_load_arbitrary",
    "compute_deflection_simply_supported_point_load_midspan",
    "compute_deflection_simply_supported_udl",
    "compute_flexural_strength_F2_compact_doubly_symmetric",
    "compute_flexural_strength_F3_noncompact_or_slender_flange",
    "compute_flexural_strength_F4",
    "compute_flexural_strength_F4_doubly_symmetric_noncompact_web",
    "compute_flexural_strength_F5_slender_web_plate_girder",
    "compute_shear_strength_G2_doubly_symmetric",
    "recommend_camber_from_dead_load_deflection",
    "recommend_doubler_plate_thickness_341",
    "run_full_beam_check",
]
