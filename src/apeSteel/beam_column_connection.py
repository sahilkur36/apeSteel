"""BeamColumnConnection - the joint composite.

A :class:`BeamColumnConnection` aggregates two :class:`Element`s
(a beam and a column) into one frozen object that exposes every
joint-level seismic check as a method.

Construction:

    beam   = beam_section.element(material=A992, bracing=...)
    column = column_section.element(material=A992)
    joint  = beam.connected_to(column)
    # or directly:
    joint  = BeamColumnConnection(beam=beam, column=column)

Usage:

    cf_tension = joint.check_panel_zone_column_flange_tension()
    pz_shear   = joint.check_panel_zone_shear()
    doubler    = joint.recommend_doubler_plate()
    cont       = joint.check_continuity_plates()

This module lives at the top of ``src/apeSteel/`` alongside
``element.py`` and ``bracing.py`` because connections are first-class
domain objects, not internal subpackage members.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from apeSteel.seismic.continuity_plate_design import (
    ContinuityPlateRecommendationReport,
    check_continuity_plates_required_358,
)
from apeSteel.seismic.doubler_plate_design import (
    DoublerPlateRecommendationReport,
    recommend_doubler_plate_thickness_341,
)
from apeSteel.seismic.panel_zone_341 import (
    PanelZoneColumnFlangeTensionReport,
    check_column_flange_tension_341,
)
from apeSteel.seismic.panel_zone_shear_J10_6 import (
    PanelZoneShearReport,
    check_panel_zone_shear_341,
)

if TYPE_CHECKING:
    from apeSteel.element import Element


@dataclass(frozen=True, slots=True)
class BeamColumnConnection:
    """A frozen composite of (beam Element, column Element)."""

    beam: Element
    column: Element

    # ------------------------------------------------------------------
    # Column-flange tension (AISC 341 §E3.6e)
    # ------------------------------------------------------------------
    def check_panel_zone_column_flange_tension(
        self,
    ) -> PanelZoneColumnFlangeTensionReport:
        """Run AISC 341 §E3.6e column-flange tension check on this joint."""
        return check_column_flange_tension_341(
            beam_section_properties=self.beam.section_properties,
            beam_material=self.beam.material,
            column_section_properties=self.column.section_properties,
            column_material=self.column.material,
        )

    # ------------------------------------------------------------------
    # Panel-zone shear (AISC 360 §J10.6, capacity-amplified)
    # ------------------------------------------------------------------
    def check_panel_zone_shear(
        self,
        *,
        column_axial_demand_Pr: float = 0.0,
        consider_panel_zone_deformation_in_frame_stability: bool = False,
        number_of_beam_sides: int = 1,
        column_shear_credit_Vu_col: float = 0.0,
        additional_doubler_plate_thickness_t_dp: float = 0.0,
    ) -> PanelZoneShearReport:
        """Run AISC 360 §J10.6 panel-zone shear check (Eq. J10-9 to J10-12).

        See :func:`apeSteel.seismic.panel_zone_shear_J10_6.check_panel_zone_shear_341`
        for the full parameter documentation.
        """
        return check_panel_zone_shear_341(
            beam_section_properties=self.beam.section_properties,
            beam_material=self.beam.material,
            column_section_properties=self.column.section_properties,
            column_material=self.column.material,
            column_axial_demand_Pr=column_axial_demand_Pr,
            consider_panel_zone_deformation_in_frame_stability=consider_panel_zone_deformation_in_frame_stability,
            number_of_beam_sides=number_of_beam_sides,
            column_shear_credit_Vu_col=column_shear_credit_Vu_col,
            additional_doubler_plate_thickness_t_dp=additional_doubler_plate_thickness_t_dp,
        )

    # ------------------------------------------------------------------
    # Doubler-plate sizing
    # ------------------------------------------------------------------
    def recommend_doubler_plate(
        self,
        *,
        column_axial_demand_Pr: float = 0.0,
        consider_panel_zone_deformation_in_frame_stability: bool = False,
        number_of_beam_sides: int = 1,
        column_shear_credit_Vu_col: float = 0.0,
        rounding_increment_for_doubler_thickness: float = 2.0,
    ) -> DoublerPlateRecommendationReport:
        """Recommend doubler-plate thickness for shear + local-buckling demand."""
        return recommend_doubler_plate_thickness_341(
            beam_section_properties=self.beam.section_properties,
            beam_material=self.beam.material,
            column_section_properties=self.column.section_properties,
            column_material=self.column.material,
            column_axial_demand_Pr=column_axial_demand_Pr,
            consider_panel_zone_deformation_in_frame_stability=consider_panel_zone_deformation_in_frame_stability,
            number_of_beam_sides=number_of_beam_sides,
            column_shear_credit_Vu_col=column_shear_credit_Vu_col,
            rounding_increment_for_doubler_thickness=rounding_increment_for_doubler_thickness,
        )

    # ------------------------------------------------------------------
    # Continuity-plate sizing
    # ------------------------------------------------------------------
    def check_continuity_plates(
        self,
        *,
        number_of_beam_sides: int = 1,
    ) -> ContinuityPlateRecommendationReport:
        """Check whether continuity plates are required and return minimum dims."""
        return check_continuity_plates_required_358(
            beam_section_properties=self.beam.section_properties,
            beam_material=self.beam.material,
            column_section_properties=self.column.section_properties,
            column_material=self.column.material,
            number_of_beam_sides=number_of_beam_sides,
        )


__all__ = ["BeamColumnConnection"]
