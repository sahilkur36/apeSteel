"""Doubler-plate sizing for panel-zone shear deficit (AISC 341 §E3.6e).

When the panel-zone shear capacity falls short of the demand, a
doubler plate welded to the column web increases the effective web
thickness from ``tw,col`` to ``tw,col + t_dp``.  This module computes
the minimum required ``t_dp`` (rounded up to a shop-practical
increment if the caller asks) and enforces the AISC 341 §E3.6e(2)
local-buckling rule that limits the panel-zone aspect ratio:

.. math::

    t_w + t_{dp} \\;\\geq\\; \\frac{d_b + d_c}{90}

A doubler-plate recommendation does *not* re-run the full panel-zone
check; instead it returns a thickness target.  The caller then passes
that thickness to ``check_panel_zone_shear_341`` as the
``additional_doubler_plate_thickness_t_dp`` argument and confirms
``phi*Rn >= Vu``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from apeSteel.core.result_types import AISCClauseReference, Report
from apeSteel.seismic.panel_zone_shear_J10_6 import (
    PHI_PANEL_ZONE_SHEAR_LRFD,
    check_panel_zone_shear_341,
)

if TYPE_CHECKING:
    from apeSteel.core.materials import SteelMaterial
    from apeSteel.sections.properties import SectionProperties


# ---------------------------------------------------------------------------
# Named constants
# ---------------------------------------------------------------------------
LOCAL_BUCKLING_PANEL_ASPECT_RATIO_DIVISOR_90: float = 90.0
"""AISC 341 §E3.6e(2): :math:`(t_w + t_{dp}) \\geq (d_b + d_c) / 90`."""


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class DoublerPlateRecommendationReport(Report):
    """Recommended doubler-plate thickness.

    Attributes
    ----------
    is_doubler_plate_required : bool
        ``True`` when the bare column web (``t_dp = 0``) cannot resist
        the panel-zone shear demand.
    minimum_doubler_thickness_for_shear_t_dp_shear : float
        Doubler thickness (mm) required to bring panel-zone shear DCR
        to <=1 by linear scaling on ``tw_effective``.  Only meaningful
        when the bare web is overloaded; reported as zero otherwise.
    minimum_doubler_thickness_for_local_buckling_t_dp_local : float
        Doubler thickness (mm) required to satisfy
        :math:`(t_w + t_{dp}) \\geq (d_b + d_c) / 90`.  May be zero if
        the bare web already meets the limit.
    minimum_doubler_thickness_required_t_dp_min : float
        ``max`` of the two limits above (mm).
    recommended_doubler_thickness_t_dp_recommended : float
        ``t_dp_min`` rounded up to ``rounding_increment_for_doubler_thickness``
        (default 2 mm).
    rounding_increment_for_doubler_thickness : float
        Echoed input.
    panel_zone_demand_Vu_pz : float
        Echoed (or recomputed) panel-zone demand (N).
    bare_web_panel_zone_capacity_phi_Rn : float
        :math:`\\varphi R_n` with ``t_dp = 0`` (N).
    """

    is_doubler_plate_required: bool = False
    minimum_doubler_thickness_for_shear_t_dp_shear: float = 0.0
    minimum_doubler_thickness_for_local_buckling_t_dp_local: float = 0.0
    minimum_doubler_thickness_required_t_dp_min: float = 0.0
    recommended_doubler_thickness_t_dp_recommended: float = 0.0
    rounding_increment_for_doubler_thickness: float = 0.0
    panel_zone_demand_Vu_pz: float = 0.0
    bare_web_panel_zone_capacity_phi_Rn: float = 0.0


_CITATIONS_DOUBLER_PLATE: tuple[AISCClauseReference, ...] = (
    AISCClauseReference("AISC 341-22", "E3.6e(2)", None, "9.1-46"),
    AISCClauseReference("AISC 360-22", "J10.6", None, "16.1-130"),
)


# ---------------------------------------------------------------------------
# Calculator
# ---------------------------------------------------------------------------
def recommend_doubler_plate_thickness_341(
    beam_section_properties: SectionProperties,
    beam_material: SteelMaterial,
    column_section_properties: SectionProperties,
    column_material: SteelMaterial,
    *,
    column_axial_demand_Pr: float = 0.0,
    consider_panel_zone_deformation_in_frame_stability: bool = False,
    number_of_beam_sides: int = 1,
    column_shear_credit_Vu_col: float = 0.0,
    rounding_increment_for_doubler_thickness: float = 2.0,
) -> DoublerPlateRecommendationReport:
    """Recommend the minimum doubler-plate thickness for a joint.

    Both governing limits are computed:

    * **Shear** -- by linearly scaling the bare-web ``phi*Rn`` so that
      ``phi*Rn(tw + t_dp) >= V_{u,pz}``.  For the J10-9 / J10-10
      branches (no panel-zone deformation), ``Rn`` is linear in
      ``tw_effective`` and the closed form is exact:

      .. math::

          t_{dp,shear} = \\max(0, t_w \\cdot (V_{u,pz}/(\\varphi R_n^{(t_w)}) - 1))

      For the J10-11 / J10-12 branches the closed form is more
      complicated because of the ``+ 3 bcf tcf^2 / (db dc tw)`` term;
      we still use the linear approximation as a starting estimate
      and then run ``check_panel_zone_shear_341`` with the candidate
      thickness to verify (and bump up by one rounding increment if
      it still falls short).
    * **Local buckling** (AISC 341 §E3.6e(2)):
      :math:`(t_w + t_{dp}) \\geq (d_b + d_c) / 90`.

    The recommended thickness is ``max`` of the two limits, rounded up
    to ``rounding_increment_for_doubler_thickness`` (default 2 mm;
    pass ``0`` to disable rounding, e.g. for parametric studies).

    Returns ``is_doubler_plate_required = False`` when both limits
    are met by the bare column web (``t_dp = 0``).
    """
    if rounding_increment_for_doubler_thickness < 0.0:
        msg = (
            "rounding_increment_for_doubler_thickness must be >= 0; got "
            f"{rounding_increment_for_doubler_thickness}."
        )
        raise ValueError(msg)

    # --- bare-web panel-zone check ---
    bare = check_panel_zone_shear_341(
        beam_section_properties=beam_section_properties,
        beam_material=beam_material,
        column_section_properties=column_section_properties,
        column_material=column_material,
        column_axial_demand_Pr=column_axial_demand_Pr,
        consider_panel_zone_deformation_in_frame_stability=consider_panel_zone_deformation_in_frame_stability,
        number_of_beam_sides=number_of_beam_sides,
        column_shear_credit_Vu_col=column_shear_credit_Vu_col,
    )

    tw_col: float = column_section_properties.web_thickness_tw
    dc: float = column_section_properties.overall_depth_d
    db: float = beam_section_properties.overall_depth_d

    # --- (1) thickness needed by shear ---
    if bare.is_demand_to_capacity_acceptable:
        t_dp_shear: float = 0.0
    else:
        # Linear-scaling estimate -- exact for J10-9 / J10-10 because
        # those Rn are linear in tw.  For J10-11 / J10-12 this is an
        # underestimate (the boost term decreases as tw grows because
        # of the bcf*tcf^2/(db*dc*tw) factor), so we'll re-run the
        # check with the estimate and bump if needed.
        dcr_bare: float = bare.demand_to_capacity_ratio
        t_dp_estimate: float = tw_col * (dcr_bare - 1.0)
        t_dp_shear = max(0.0, t_dp_estimate)
        # Iterate up to a few times if J10-11/J10-12 (rare in
        # practice) requires more.  Use the rounding step as the
        # bump size to keep the loop deterministic.
        bump: float = (
            rounding_increment_for_doubler_thickness
            if rounding_increment_for_doubler_thickness > 0.0
            else max(0.001 * tw_col, 0.1)
        )
        for _ in range(50):
            trial = check_panel_zone_shear_341(
                beam_section_properties=beam_section_properties,
                beam_material=beam_material,
                column_section_properties=column_section_properties,
                column_material=column_material,
                column_axial_demand_Pr=column_axial_demand_Pr,
                consider_panel_zone_deformation_in_frame_stability=consider_panel_zone_deformation_in_frame_stability,
                number_of_beam_sides=number_of_beam_sides,
                column_shear_credit_Vu_col=column_shear_credit_Vu_col,
                additional_doubler_plate_thickness_t_dp=t_dp_shear,
            )
            if trial.is_demand_to_capacity_acceptable:
                break
            t_dp_shear += bump

    # --- (2) thickness needed by local buckling ---
    local_buckling_required_total_thickness: float = (
        db + dc
    ) / LOCAL_BUCKLING_PANEL_ASPECT_RATIO_DIVISOR_90
    t_dp_local: float = max(0.0, local_buckling_required_total_thickness - tw_col)

    # --- combine ---
    t_dp_min: float = max(t_dp_shear, t_dp_local)
    if rounding_increment_for_doubler_thickness > 0.0 and t_dp_min > 0.0:
        # Round up to the nearest increment.
        n_increments = math.ceil(t_dp_min / rounding_increment_for_doubler_thickness)
        t_dp_recommended: float = n_increments * rounding_increment_for_doubler_thickness
    else:
        t_dp_recommended = t_dp_min

    is_required: bool = t_dp_min > 0.0

    governing: str
    if not is_required:
        governing = "no_doubler_required"
    elif t_dp_shear >= t_dp_local:
        governing = "shear_capacity_governs"
    else:
        governing = "local_buckling_governs"

    return DoublerPlateRecommendationReport(
        cited_clauses=_CITATIONS_DOUBLER_PLATE,
        governing_limit_state=governing,
        phi_LRFD=PHI_PANEL_ZONE_SHEAR_LRFD,
        omega_ASD=1.67,
        nominal_strength=bare.panel_zone_shear_capacity_Rn,
        phi_strength_LRFD=bare.phi_panel_zone_shear_capacity_phi_Rn_LRFD,
        omega_strength_ASD=bare.panel_zone_shear_capacity_Rn / 1.67,
        is_doubler_plate_required=is_required,
        minimum_doubler_thickness_for_shear_t_dp_shear=t_dp_shear,
        minimum_doubler_thickness_for_local_buckling_t_dp_local=t_dp_local,
        minimum_doubler_thickness_required_t_dp_min=t_dp_min,
        recommended_doubler_thickness_t_dp_recommended=t_dp_recommended,
        rounding_increment_for_doubler_thickness=rounding_increment_for_doubler_thickness,
        panel_zone_demand_Vu_pz=bare.panel_zone_shear_demand_Vu_pz,
        bare_web_panel_zone_capacity_phi_Rn=bare.phi_panel_zone_shear_capacity_phi_Rn_LRFD,
    )


__all__ = [
    "LOCAL_BUCKLING_PANEL_ASPECT_RATIO_DIVISOR_90",
    "DoublerPlateRecommendationReport",
    "recommend_doubler_plate_thickness_341",
]
