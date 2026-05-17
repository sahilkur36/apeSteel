"""Seismic checks - AISC 341 panel zone, future SMF/IMF/OMF, BRBF, EBF, SPSW.

Phase 8c ships four joint-level checks:

* :func:`check_column_flange_tension_341` - AISC 341 §E3.6e column-
  flange tension check.
* :func:`check_panel_zone_shear_341` - AISC 341 §E3.6e + AISC 360
  §J10.6 panel-zone shear check.  All four equations
  (J10-9 - J10-12) are covered.
* :func:`recommend_doubler_plate_thickness_341` - shop-practical
  doubler-plate sizing that handles both shear deficit and AISC 341
  §E3.6e(2) local buckling.
* :func:`check_continuity_plates_required_358` - AISC 358 §2.4.4
  need check + AISC 360 §J10.8 minimum dimensions for transverse
  stiffeners.
"""

from __future__ import annotations

from apeSteel.seismic.continuity_plate_design import (
    ContinuityPlateRecommendationReport,
    check_continuity_plates_required_358,
)
from apeSteel.seismic.doubler_plate_design import (
    DoublerPlateRecommendationReport,
    recommend_doubler_plate_thickness_341,
)
from apeSteel.seismic.panel_zone_341 import (
    PHI_FLANGE_TENSION_LRFD,
    PanelZoneColumnFlangeTensionReport,
    check_column_flange_tension_341,
)
from apeSteel.seismic.panel_zone_shear_J10_6 import (
    PHI_PANEL_ZONE_SHEAR_LRFD,
    PanelZoneEquationLabel,
    PanelZoneShearReport,
    check_panel_zone_shear_341,
)

__all__ = [
    "PHI_FLANGE_TENSION_LRFD",
    "PHI_PANEL_ZONE_SHEAR_LRFD",
    "ContinuityPlateRecommendationReport",
    "DoublerPlateRecommendationReport",
    "PanelZoneColumnFlangeTensionReport",
    "PanelZoneEquationLabel",
    "PanelZoneShearReport",
    "check_column_flange_tension_341",
    "check_continuity_plates_required_358",
    "check_panel_zone_shear_341",
    "recommend_doubler_plate_thickness_341",
]
