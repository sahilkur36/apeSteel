"""Continuity-plate (transverse-stiffener) need check and sizing.

A continuity plate is a stiffener welded across the column web,
aligned with each beam flange, used when the column flange alone
cannot develop the beam flange tension/compression locally.  AISC
358-22 §2.4.4 gives the rules for when continuity plates are
required; when they are, their dimensions follow AISC 360-22 §J10.8.

Need-check (AISC 358 §2.4.4)
-----------------------------
Continuity plates are NOT required if all three of the following hold
(simplified, sufficient set for prequalified moment connections):

* ``tcf >= 0.40 * sqrt(1.8 b_{f,beam} t_{f,beam} F_{y,beam} R_{y,beam}
                      / (F_{y,col} R_{y,col}))``  -- the capacity
  limit reused from :mod:`apeSteel.seismic.panel_zone_341`.
* ``tcf >= b_{f,beam} / 6``  -- the geometric limit also reused
  from the column-flange tension check.
* ``b_{f,col} >= b_{f,beam}`` and detailing constraints satisfied.

If any limit is violated continuity plates are required; if all three
pass, they may still be required by the prequalification chapter the
user is following (e.g. RBS, BFP).  This module's ``is_required``
flag is conservative: it returns ``True`` whenever the first two
limits are not jointly met.

Minimum dimensions when required (AISC 360-22 §J10.8)
-----------------------------------------------------
The continuity plate is a pair of stiffeners (one each side of the
web).  Minimum dimensions returned:

* **Thickness** ``t_cp,min = max(t_{f,beam} / 2, t_{f,beam} for
  two-sided beams)`` -- one-half the beam flange thickness for
  one-sided beam attachment; matching the beam flange thickness when
  beams frame in from both sides of the column.
* **Width** ``b_cp,min = (b_{f,beam} - 2 k_{des}) / 2 - tw_col/2``
  approximated by ``b_cp,min ~ b_{f,beam}/2 - tw_col/2 -
  10 mm`` (a conservative AISC-358-compatible heuristic, since the
  column's k-detail dimension is not present in
  :class:`SectionProperties`).

These dimensions are *minimum* values; final selection is up to the
detailer with full access to the column's k-detail dimensions.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from apeSteel.core.result_types import AISCClauseReference, Report
from apeSteel.seismic.panel_zone_341 import (
    MINIMUM_FLANGE_THICKNESS_GEOMETRIC_LIMIT_DIVISOR_BF_OVER_6,
    MINIMUM_FLANGE_THICKNESS_CAPACITY_COEFFICIENT_0p40,
)

if TYPE_CHECKING:
    from apeSteel.core.materials import SteelMaterial
    from apeSteel.sections.properties import SectionProperties

# ---------------------------------------------------------------------------
# Named constants
# ---------------------------------------------------------------------------
CONTINUITY_PLATE_WIDTH_BARE_OFFSET_FROM_BEAM_FLANGE_10MM: float = 10.0
"""Conservative detailing offset (mm) subtracted from the geometric
flange-pair-half-width to account for the column's k-detail dimension
(which is not stored in :class:`SectionProperties`)."""


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class ContinuityPlateRecommendationReport(Report):
    """Continuity-plate need check and minimum dimensions.

    Attributes
    ----------
    is_required : bool
        ``True`` when the column flange alone cannot develop the beam-
        flange force, per the AISC 358 §2.4.4 limits.
    column_flange_thickness_tcf : float
        Echoed (mm).
    beam_flange_width_bf_beam : float
        Echoed (mm).
    beam_flange_thickness_tf_beam : float
        Echoed (mm).
    minimum_column_flange_thickness_for_no_continuity : float
        ``max(tcf_min_1, tcf_min_2)`` reused from the column-flange
        tension check (mm).
    minimum_continuity_plate_thickness_t_cp_min : float
        Recommended thickness of each plate (mm).
    minimum_continuity_plate_width_b_cp_min : float
        Recommended width per side of the web (mm).
    number_of_beam_sides : int
        1 for exterior (single beam framing into the joint),
        2 for interior (beams on both sides of the column).
    """

    is_required: bool = False
    column_flange_thickness_tcf: float = 0.0
    beam_flange_width_bf_beam: float = 0.0
    beam_flange_thickness_tf_beam: float = 0.0
    minimum_column_flange_thickness_for_no_continuity: float = 0.0
    minimum_continuity_plate_thickness_t_cp_min: float = 0.0
    minimum_continuity_plate_width_b_cp_min: float = 0.0
    number_of_beam_sides: int = 1


_CITATIONS_CONTINUITY_PLATE: tuple[AISCClauseReference, ...] = (
    AISCClauseReference("AISC 358-22", "2.4.4", None, None),
    AISCClauseReference("AISC 360-22", "J10.8", None, "16.1-131"),
    AISCClauseReference("AISC 341-22", "E3.6f", None, "9.1-47"),
)


# ---------------------------------------------------------------------------
# Calculator
# ---------------------------------------------------------------------------
def check_continuity_plates_required_358(
    beam_section_properties: SectionProperties,
    beam_material: SteelMaterial,
    column_section_properties: SectionProperties,
    column_material: SteelMaterial,
    *,
    number_of_beam_sides: int = 1,
) -> ContinuityPlateRecommendationReport:
    """Determine whether continuity plates are required and, if so,
    return minimum-dimension recommendations.

    Parameters
    ----------
    beam_section_properties : SectionProperties
        Source of ``bf,beam`` and ``tf,beam``.
    beam_material : SteelMaterial
        Source of ``Fy,beam`` and ``Ry,beam``.
    column_section_properties : SectionProperties
        Source of ``tcf``, ``tw,col``, and ``bf,col``.
    column_material : SteelMaterial
        Source of ``Fy,col`` and ``Ry,col``.
    number_of_beam_sides : int
        1 for an exterior joint, 2 for an interior joint with beams
        framing in from both sides.

    Returns
    -------
    ContinuityPlateRecommendationReport
        Frozen report.  ``is_required`` is ``True`` when the bare
        column flange does NOT satisfy both ``tcf_min_1`` and
        ``tcf_min_2`` from AISC 358 §2.4.4.

    Raises
    ------
    ValueError
        If beam ``bf`` / ``tf`` or column ``tcf`` / ``tw`` / ``bf`` are
        not positive (older :class:`SectionProperties` instances may
        have these as the 0.0 default).
    """
    if number_of_beam_sides not in (1, 2):
        msg = f"number_of_beam_sides must be 1 or 2; got {number_of_beam_sides}."
        raise ValueError(msg)

    bf_beam: float = beam_section_properties.flange_width_bf
    tf_beam: float = beam_section_properties.flange_thickness_tf
    if bf_beam <= 0.0 or tf_beam <= 0.0:
        msg = (
            "beam_section_properties must expose positive flange_width_bf "
            f"and flange_thickness_tf; got bf={bf_beam}, tf={tf_beam}."
        )
        raise ValueError(msg)
    tcf: float = column_section_properties.flange_thickness_tf
    tw_col: float = column_section_properties.web_thickness_tw
    if tcf <= 0.0 or tw_col <= 0.0:
        msg = (
            "column_section_properties must expose positive flange_thickness_tf "
            f"and web_thickness_tw; got tcf={tcf}, tw_col={tw_col}."
        )
        raise ValueError(msg)

    Fy_beam: float = beam_material.yield_stress_Fy
    Ry_beam: float = beam_material.expected_yield_ratio_Ry
    Fy_col: float = column_material.yield_stress_Fy
    Ry_col: float = column_material.expected_yield_ratio_Ry

    # --- AISC 358 §2.4.4 thresholds (shared with panel_zone_341) ---
    # Capacity-based:
    #   tcf_min_2 = 0.40 * sqrt(1.8 b_{f,b} t_{f,b} F_{y,b} R_{y,b} / (F_{y,c} R_{y,c}))
    Tu_capacity_term: float = (
        1.8 * bf_beam * tf_beam * Fy_beam * Ry_beam
    )  # equals Tu from the column-flange tension check
    tcf_min_capacity: float = MINIMUM_FLANGE_THICKNESS_CAPACITY_COEFFICIENT_0p40 * math.sqrt(
        Tu_capacity_term / (Fy_col * Ry_col)
    )
    # Geometric:
    tcf_min_geometric: float = bf_beam / MINIMUM_FLANGE_THICKNESS_GEOMETRIC_LIMIT_DIVISOR_BF_OVER_6
    tcf_min_required: float = max(tcf_min_capacity, tcf_min_geometric)

    is_required: bool = tcf < tcf_min_required

    # --- recommended continuity-plate dimensions ---
    if is_required:
        # One-half the beam flange (one-sided beam) or full beam
        # flange (two-sided): conservative AISC 360 §J10.8 envelope.
        t_cp_min: float = tf_beam if number_of_beam_sides == 2 else tf_beam / 2.0
        # Width per side of the column web.  The plate clears the
        # column k-detail region: ``b_cp = (bf,beam - 2*k1,col) / 2``
        # when the column's ``k1`` is available, falling back to a
        # 10 mm detailing-clip heuristic when it isn't.
        column_k1: float = column_section_properties.k_one_k1
        if column_k1 > 0.0:
            b_cp_min: float = max(0.0, (bf_beam - 2.0 * column_k1) / 2.0)
        else:
            b_cp_min = max(
                0.0,
                (bf_beam - tw_col) / 2.0 - CONTINUITY_PLATE_WIDTH_BARE_OFFSET_FROM_BEAM_FLANGE_10MM,
            )
        governing: str = (
            "continuity_plate_required_capacity"
            if tcf_min_capacity >= tcf_min_geometric
            else "continuity_plate_required_geometric"
        )
    else:
        t_cp_min = 0.0
        b_cp_min = 0.0
        governing = "no_continuity_plate_required"

    return ContinuityPlateRecommendationReport(
        cited_clauses=_CITATIONS_CONTINUITY_PLATE,
        governing_limit_state=governing,
        is_required=is_required,
        column_flange_thickness_tcf=tcf,
        beam_flange_width_bf_beam=bf_beam,
        beam_flange_thickness_tf_beam=tf_beam,
        minimum_column_flange_thickness_for_no_continuity=tcf_min_required,
        minimum_continuity_plate_thickness_t_cp_min=t_cp_min,
        minimum_continuity_plate_width_b_cp_min=b_cp_min,
        number_of_beam_sides=number_of_beam_sides,
    )


__all__ = [
    "CONTINUITY_PLATE_WIDTH_BARE_OFFSET_FROM_BEAM_FLANGE_10MM",
    "ContinuityPlateRecommendationReport",
    "check_continuity_plates_required_358",
]
