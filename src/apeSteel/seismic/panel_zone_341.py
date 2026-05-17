"""Panel-zone column-flange tension check (AISC 341 §E3.6e).

For a beam-to-column moment connection in a special moment frame (SMF),
AISC 341-22 §E3.6e (and AISC 358 prequalification §5.3.1) require that
the **column flange** be thick enough to resist the demand from the
beam-flange tension.

This module implements that single check.  Companion panel-zone checks
(shear capacity per §J10.6, doubler-plate design, continuity-plate
design) are scoped to a follow-up phase.

Equations
---------
Beam-flange tension demand (probable, amplified):

.. math::

    T_u = 1.8 \\, b_{f,beam} \\, t_{f,beam} \\, F_{y,beam} \\, R_{y,beam}

The factor of 1.8 captures :math:`R_y` plus a strain-hardening
allowance.

Column-flange tension capacity (AISC 360 §J10.1 amplified by
:math:`R_{y,col}` for capacity-design demand):

.. math::

    R_n = 6.25 \\, t_{cf}^{2} \\, F_{y,col} \\, R_{y,col}, \\quad
    \\varphi R_n = 0.9 \\, R_n.

Minimum column-flange thickness — two governing limits, take the larger:

* Geometric (AISC 358 §5.3.1):  :math:`t_{cf,min,1} = b_{f,beam} / 6`.
* Capacity-based:

  .. math::

      t_{cf,min,2} = 0.40 \\sqrt{\\frac{1.8 \\, b_{f,beam} \\, t_{f,beam}
                                       \\, F_{y,beam} \\, R_{y,beam}}{F_{y,col} \\, R_{y,col}}}

A connection passes when ``tcf ≥ max(tcf_min_1, tcf_min_2)`` and
``φRn ≥ Tu`` simultaneously.

References
----------
.. [1] AISC 341-22 §E3.6e, "Panel-zone of beam-to-column connections
       (in special moment frames)".
.. [2] AISC 358-22 §5.3.1, "Prequalified moment connection limits".
.. [3] AISC 360-22 §J10.1 Eq. J10-2, "Concentrated tension force on
       flange".
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from apeSteel.core.result_types import AISCClauseReference, Report

if TYPE_CHECKING:
    from apeSteel.core.materials import SteelMaterial
    from apeSteel.sections.properties import SectionProperties


# ---------------------------------------------------------------------------
# Constants (named so a reader can grep the AISC equations directly)
# ---------------------------------------------------------------------------
BEAM_TENSION_DEMAND_AMPLIFICATION_1p8: float = 1.8
"""Coefficient that multiplies ``b_f t_f F_y R_y`` to give the
probable beam-flange tension Tu.  Captures :math:`R_y` plus strain
hardening (AISC 341 §E3 commentary)."""

COLUMN_FLANGE_TENSION_COEFFICIENT_J10_2: float = 6.25
"""Coefficient in AISC 360 Eq. J10-2: :math:`R_n = 6.25 t_{cf}^{2} F_y`.
We amplify by :math:`R_y` for capacity-design demand per AISC 341."""

PHI_FLANGE_TENSION_LRFD: float = 0.90
"""LRFD strength reduction factor for the column-flange tension
limit state (AISC 360 §J1.4(a))."""

MINIMUM_FLANGE_THICKNESS_GEOMETRIC_LIMIT_DIVISOR_BF_OVER_6: float = 6.0
"""``tcf_min,1 = bf,beam / 6`` per AISC 358 §5.3.1."""

MINIMUM_FLANGE_THICKNESS_CAPACITY_COEFFICIENT_0p40: float = 0.40
"""Coefficient in the capacity-based ``tcf_min,2`` limit."""


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class PanelZoneColumnFlangeTensionReport(Report):
    """Frozen result of the AISC 341 §E3.6e column-flange tension check.

    Attributes
    ----------
    beam_flange_tension_demand_Tu : float
        :math:`T_u = 1.8 b_{f,beam} t_{f,beam} F_{y,beam} R_{y,beam}` (N).
    column_flange_thickness_tcf : float
        Actual column flange thickness (mm).  Pulled from
        ``column_section_properties.flange_thickness_tf``.
    column_flange_tension_capacity_Rn : float
        :math:`R_n = 6.25 t_{cf}^{2} F_{y,col} R_{y,col}` (N).
    phi_column_flange_tension_capacity_phi_Rn_LRFD : float
        :math:`\\varphi R_n` (N).
    minimum_column_flange_thickness_geometric_tcf_min_1 : float
        :math:`b_{f,beam} / 6` (mm).
    minimum_column_flange_thickness_capacity_tcf_min_2 : float
        :math:`0.40 \\sqrt{T_u / (F_{y,col} R_{y,col})}` (mm).
    minimum_column_flange_thickness_required_tcf_min : float
        ``max(tcf_min_1, tcf_min_2)`` (mm).
    is_thickness_acceptable : bool
        ``tcf >= tcf_min_required``.
    is_demand_to_capacity_acceptable : bool
        ``Tu <= phi*Rn``  (equivalently ``DCR <= 1``).
    demand_to_capacity_ratio : float
        :math:`T_u / (\\varphi R_n)`.
    """

    beam_flange_tension_demand_Tu: float = 0.0
    column_flange_thickness_tcf: float = 0.0
    column_flange_tension_capacity_Rn: float = 0.0
    phi_column_flange_tension_capacity_phi_Rn_LRFD: float = 0.0
    minimum_column_flange_thickness_geometric_tcf_min_1: float = 0.0
    minimum_column_flange_thickness_capacity_tcf_min_2: float = 0.0
    minimum_column_flange_thickness_required_tcf_min: float = 0.0
    is_thickness_acceptable: bool = True
    is_demand_to_capacity_acceptable: bool = True
    demand_to_capacity_ratio: float = 0.0


_CITATIONS_PANEL_ZONE_341: tuple[AISCClauseReference, ...] = (
    AISCClauseReference("AISC 341-22", "E3.6e", None, "9.1-46"),
    AISCClauseReference("AISC 358-22", "5.3.1", None, None),
    AISCClauseReference("AISC 360-22", "J10.1", "J10-2", "16.1-129"),
)


# ---------------------------------------------------------------------------
# Calculator
# ---------------------------------------------------------------------------
def check_column_flange_tension_341(
    beam_section_properties: SectionProperties,
    beam_material: SteelMaterial,
    column_section_properties: SectionProperties,
    column_material: SteelMaterial,
) -> PanelZoneColumnFlangeTensionReport:
    """Run the AISC 341 §E3.6e column-flange tension check.

    Parameters
    ----------
    beam_section_properties : SectionProperties
        Source of ``bf,beam`` and ``tf,beam``.  These must be populated
        — every Phase 1+ ``SectionProperties`` producer in apeSteel
        sets them (DoublySymmetricISection, AISC v16 catalog, European
        IPE catalog).  A ``ValueError`` is raised when either is zero.
    beam_material : SteelMaterial
        Source of :math:`F_{y,beam}` and :math:`R_{y,beam}`.
    column_section_properties : SectionProperties
        Source of ``tcf`` (column flange thickness).
    column_material : SteelMaterial
        Source of :math:`F_{y,col}` and :math:`R_{y,col}`.

    Returns
    -------
    PanelZoneColumnFlangeTensionReport
        Frozen report.  ``governing_limit_state`` is
        ``"thickness_and_capacity_acceptable"`` when both checks pass,
        otherwise it names the failing check.

    Notes
    -----
    The phi factor in :attr:`Report.phi_LRFD` is set to 0.9 (the J10
    flange-tension factor).  :attr:`Report.nominal_strength` is the
    column-flange tension capacity :math:`R_n`, so ``phi * Rn`` lands in
    :attr:`Report.phi_strength_LRFD`.

    The legacy ``panelZone`` class in ``to_review/`` reported only
    :math:`T_u / \\varphi R_n` and the geometric ``bf/6`` limit.  This
    port preserves those quantities and additionally exposes the
    capacity-based ``tcf_min_2`` and the explicit ``tcf_min_required``
    boundary that AISC 358 enforces.
    """
    # --- read inputs ---
    bf_beam: float = beam_section_properties.flange_width_bf
    tf_beam: float = beam_section_properties.flange_thickness_tf
    if bf_beam <= 0.0 or tf_beam <= 0.0:
        msg = (
            "beam_section_properties must expose positive flange_width_bf "
            "and flange_thickness_tf; got "
            f"bf={bf_beam}, tf={tf_beam}.  Phase 1 producers populate these; "
            "an older SectionProperties created before Phase 8c may leave "
            "them at the 0.0 default."
        )
        raise ValueError(msg)
    tcf: float = column_section_properties.flange_thickness_tf
    if tcf <= 0.0:
        msg = (
            f"column_section_properties must expose a positive flange_thickness_tf; got tcf={tcf}."
        )
        raise ValueError(msg)

    Fy_beam: float = beam_material.yield_stress_Fy
    Ry_beam: float = beam_material.expected_yield_ratio_Ry
    Fy_col: float = column_material.yield_stress_Fy
    Ry_col: float = column_material.expected_yield_ratio_Ry

    # --- demand (Tu) ---
    # AISC 341 §E3.6e commentary:
    #     Tu = 1.8 * bf,beam * tf,beam * Fy,beam * Ry,beam
    Tu: float = BEAM_TENSION_DEMAND_AMPLIFICATION_1p8 * bf_beam * tf_beam * Fy_beam * Ry_beam

    # --- capacity (Rn, phi*Rn) ---
    # AISC 360 Eq. J10-2 (modified for capacity-design demand by Ry,col):
    #     Rn  = 6.25 * tcf^2 * Fy,col * Ry,col
    #     phi*Rn = 0.90 * Rn
    Rn: float = COLUMN_FLANGE_TENSION_COEFFICIENT_J10_2 * tcf**2 * Fy_col * Ry_col
    phi_Rn: float = PHI_FLANGE_TENSION_LRFD * Rn

    # --- minimum thickness limits ---
    tcf_min_1: float = bf_beam / MINIMUM_FLANGE_THICKNESS_GEOMETRIC_LIMIT_DIVISOR_BF_OVER_6
    # Capacity-based limit derives directly from setting Tu == phi*Rn
    # with phi = 1 and solving for tcf, then applying the 0.40 factor
    # AISC 358 uses.
    tcf_min_2: float = MINIMUM_FLANGE_THICKNESS_CAPACITY_COEFFICIENT_0p40 * math.sqrt(
        Tu / (Fy_col * Ry_col)
    )
    tcf_min_required: float = max(tcf_min_1, tcf_min_2)

    # --- acceptance and DCR ---
    is_thickness_ok: bool = tcf >= tcf_min_required
    demand_to_capacity_ratio: float = Tu / phi_Rn if phi_Rn > 0.0 else math.inf
    is_dcr_ok: bool = demand_to_capacity_ratio <= 1.0

    if is_thickness_ok and is_dcr_ok:
        governing: str = "thickness_and_capacity_acceptable"
    elif not is_thickness_ok and not is_dcr_ok:
        governing = "thickness_and_capacity_both_exceeded"
    elif not is_thickness_ok:
        governing = "minimum_flange_thickness_violated"
    else:
        governing = "demand_to_capacity_exceeded"

    return PanelZoneColumnFlangeTensionReport(
        cited_clauses=_CITATIONS_PANEL_ZONE_341,
        governing_limit_state=governing,
        phi_LRFD=PHI_FLANGE_TENSION_LRFD,
        omega_ASD=1.67,  # AISC 360 §J1.4(b) — not exercised in capacity design.
        nominal_strength=Rn,
        phi_strength_LRFD=phi_Rn,
        omega_strength_ASD=Rn / 1.67,
        beam_flange_tension_demand_Tu=Tu,
        column_flange_thickness_tcf=tcf,
        column_flange_tension_capacity_Rn=Rn,
        phi_column_flange_tension_capacity_phi_Rn_LRFD=phi_Rn,
        minimum_column_flange_thickness_geometric_tcf_min_1=tcf_min_1,
        minimum_column_flange_thickness_capacity_tcf_min_2=tcf_min_2,
        minimum_column_flange_thickness_required_tcf_min=tcf_min_required,
        is_thickness_acceptable=is_thickness_ok,
        is_demand_to_capacity_acceptable=is_dcr_ok,
        demand_to_capacity_ratio=demand_to_capacity_ratio,
    )


__all__ = [
    "COLUMN_FLANGE_TENSION_COEFFICIENT_J10_2",
    "MINIMUM_FLANGE_THICKNESS_GEOMETRIC_LIMIT_DIVISOR_BF_OVER_6",
    "PHI_FLANGE_TENSION_LRFD",
    "BEAM_TENSION_DEMAND_AMPLIFICATION_1p8",
    "MINIMUM_FLANGE_THICKNESS_CAPACITY_COEFFICIENT_0p40",
    "PanelZoneColumnFlangeTensionReport",
    "check_column_flange_tension_341",
]
