"""Panel-zone shear strength (AISC 360-22 §J10.6, capacity-amplified per
AISC 341-22 §E3.6e).

For a beam-to-column moment connection the panel zone (the column
web bounded by the beam flanges and the continuity plates) must
resist the shear induced by the beam-flange tension/compression
couple.  This module implements the four nominal-strength
expressions (J10-9 through J10-12) that AISC 360-22 §J10.6 gives,
and amplifies the column yield stress by :math:`R_{y,col}` when the
demand comes from capacity design (the AISC 341-22 §E3.6e route).

Equations
---------
Let

    F_y = R_{y,col} \\, F_{y,col},   P_c = F_{y,col} \\, A_{g,col}.

Without considering panel-zone deformation on frame stability:

* (J10-9)  if P_r <= 0.4 P_c:
    R_n = 0.6 F_y d_c t_w
* (J10-10) if P_r >  0.4 P_c:
    R_n = 0.6 F_y d_c t_w (1.4 - P_r/P_c)

Considering panel-zone deformation on frame stability:

* (J10-11) if P_r <= 0.75 P_c:
    R_n = 0.6 F_y d_c t_w [1 + 3 b_{cf} t_{cf}^2 / (d_b d_c t_w)]
* (J10-12) if P_r >  0.75 P_c:
    R_n = 0.6 F_y d_c t_w [1 + 3 b_{cf} t_{cf}^2 / (d_b d_c t_w)]
           x (1.9 - 1.2 P_r/P_c)

Demand
------
The default demand is the simplest one-sided expression:

    V_{u,pz} = M_{pr} / d_b      (one-sided beam, V_col neglected)

where M_{pr} = C_{pr} \\, R_y \\, F_y \\, Z_x,beam and the strain-hardening
factor C_{pr} = (F_y + F_u) / (2 F_y) <= 1.2 per AISC 358 §2.4.3.

Callers with a two-sided interior joint can pass
``number_of_beam_sides=2`` to double the moment contribution; callers
who know the column shear ``Vu_col`` can pass it as a credit (positive
reduces demand).

References
----------
.. [1] AISC 341-22, §E3.6e, "Panel zone of beam-to-column connections".
.. [2] AISC 360-22, §J10.6 "Web panel-zone shear".  Equations
       J10-9, J10-10, J10-11, J10-12.
.. [3] AISC 358-22, §2.4.3, "Probable maximum moment at plastic hinge".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from apeSteel.core.result_types import AISCClauseReference, Report

if TYPE_CHECKING:
    from apeSteel.core.materials import SteelMaterial
    from apeSteel.sections.properties import SectionProperties


# ---------------------------------------------------------------------------
# Named constants
# ---------------------------------------------------------------------------
PANEL_ZONE_SHEAR_NOMINAL_STRESS_COEFFICIENT_0p6: float = 0.6
"""Coefficient ``0.6`` in ``Rn = 0.6 Fy dc tw`` (AISC J10-9)."""

AXIAL_RATIO_LIMIT_FOR_J10_9_AND_J10_10: float = 0.4
"""Pr/Pc threshold separating Eq. J10-9 and J10-10."""

AXIAL_REDUCTION_COEFFICIENT_J10_10_1p4: float = 1.4
"""The ``1.4`` in ``(1.4 - Pr/Pc)`` of Eq. J10-10."""

PANEL_ZONE_DEFORMATION_BOOST_COEFFICIENT_3: float = 3.0
"""The ``3`` multiplier inside the bracket of Eq. J10-11 / J10-12."""

AXIAL_RATIO_LIMIT_FOR_J10_11_AND_J10_12: float = 0.75
"""Pr/Pc threshold separating Eq. J10-11 and J10-12."""

AXIAL_REDUCTION_COEFFICIENT_J10_12_1p9: float = 1.9
"""The ``1.9`` in ``(1.9 - 1.2 Pr/Pc)`` of Eq. J10-12."""

AXIAL_REDUCTION_COEFFICIENT_J10_12_1p2: float = 1.2
"""The ``1.2`` multiplying ``Pr/Pc`` in Eq. J10-12."""

PHI_PANEL_ZONE_SHEAR_LRFD: float = 0.90
"""LRFD strength reduction factor for panel-zone shear (AISC §J1.4)."""

DEFAULT_PROBABLE_STRAIN_HARDENING_FACTOR_Cpr_IF_FU_UNKNOWN: float = 1.15
"""Used when ``material.tensile_stress_Fu`` is not available; AISC 358
gives ``Cpr = (Fy+Fu)/(2Fy) <= 1.2``; 1.15 is a typical value for A992."""

PROBABLE_STRAIN_HARDENING_FACTOR_Cpr_UPPER_BOUND_1p2: float = 1.2
"""AISC 358 §2.4.3 caps ``Cpr`` at 1.2."""


# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------
PanelZoneEquationLabel = Literal[
    "J10-9",
    "J10-10",
    "J10-11",
    "J10-12",
]


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class PanelZoneShearReport(Report):
    """Frozen result of the AISC 360 §J10.6 panel-zone shear check.

    Attributes
    ----------
    panel_zone_shear_demand_Vu_pz : float
        Required panel-zone shear (N), computed from
        ``number_of_beam_sides`` * ``Mpr / db`` minus
        ``column_shear_credit_Vu_col``.
    panel_zone_shear_capacity_Rn : float
        Nominal panel-zone shear capacity (N).
    phi_panel_zone_shear_capacity_phi_Rn_LRFD : float
        :math:`\\varphi R_n` (N).
    governing_equation : str
        Which of ``J10-9 / J10-10 / J10-11 / J10-12`` applies.
    consider_panel_zone_deformation_in_frame_stability : bool
        Echoed input.
    column_axial_demand_Pr : float
        Required factored axial strength of the column (N).
    column_axial_yield_Pc : float
        Column yield (squash) load ``Fy,col * Ag,col`` (N).
    probable_strain_hardening_factor_Cpr : float
        AISC 358 §2.4.3 ``Cpr``.
    probable_beam_plastic_moment_Mpr : float
        Plastic moment at the beam hinge :math:`M_{pr} = C_{pr} R_y F_y
        Z_x` (N*mm).
    number_of_beam_sides : int
        1 for exterior, 2 for interior.
    column_shear_credit_Vu_col : float
        Echoed input.
    demand_to_capacity_ratio : float
        :math:`V_{u,pz} / (\\varphi R_n)`.
    is_demand_to_capacity_acceptable : bool
        ``DCR <= 1``.
    """

    panel_zone_shear_demand_Vu_pz: float = 0.0
    panel_zone_shear_capacity_Rn: float = 0.0
    phi_panel_zone_shear_capacity_phi_Rn_LRFD: float = 0.0
    governing_equation: PanelZoneEquationLabel = "J10-9"
    consider_panel_zone_deformation_in_frame_stability: bool = False
    column_axial_demand_Pr: float = 0.0
    column_axial_yield_Pc: float = 0.0
    probable_strain_hardening_factor_Cpr: float = 1.0
    probable_beam_plastic_moment_Mpr: float = 0.0
    number_of_beam_sides: int = 1
    column_shear_credit_Vu_col: float = 0.0
    demand_to_capacity_ratio: float = 0.0
    is_demand_to_capacity_acceptable: bool = True


_CITATIONS_PANEL_ZONE_SHEAR: tuple[AISCClauseReference, ...] = (
    AISCClauseReference("AISC 341-22", "E3.6e", None, "9.1-46"),
    AISCClauseReference("AISC 360-22", "J10.6", "J10-9", "16.1-130"),
    AISCClauseReference("AISC 360-22", "J10.6", "J10-10", "16.1-130"),
    AISCClauseReference("AISC 360-22", "J10.6", "J10-11", "16.1-130"),
    AISCClauseReference("AISC 360-22", "J10.6", "J10-12", "16.1-130"),
    AISCClauseReference("AISC 358-22", "2.4.3", None, None),
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _compute_Cpr(beam_material: SteelMaterial) -> float:
    """Return AISC 358 §2.4.3 strain-hardening factor Cpr.

    ``Cpr = (Fy + Fu) / (2 Fy) <= 1.2``.

    Falls back to :data:`DEFAULT_PROBABLE_STRAIN_HARDENING_FACTOR_Cpr_IF_FU_UNKNOWN`
    when ``material.tensile_stress_Fu`` is zero.
    """
    if beam_material.tensile_stress_Fu <= 0.0:
        return DEFAULT_PROBABLE_STRAIN_HARDENING_FACTOR_Cpr_IF_FU_UNKNOWN
    cpr_unbounded: float = (beam_material.yield_stress_Fy + beam_material.tensile_stress_Fu) / (
        2.0 * beam_material.yield_stress_Fy
    )
    return min(cpr_unbounded, PROBABLE_STRAIN_HARDENING_FACTOR_Cpr_UPPER_BOUND_1p2)


# ---------------------------------------------------------------------------
# Calculator
# ---------------------------------------------------------------------------
def check_panel_zone_shear_341(
    beam_section_properties: SectionProperties,
    beam_material: SteelMaterial,
    column_section_properties: SectionProperties,
    column_material: SteelMaterial,
    *,
    column_axial_demand_Pr: float = 0.0,
    consider_panel_zone_deformation_in_frame_stability: bool = False,
    number_of_beam_sides: int = 1,
    column_shear_credit_Vu_col: float = 0.0,
    additional_doubler_plate_thickness_t_dp: float = 0.0,
) -> PanelZoneShearReport:
    """Check panel-zone shear per AISC 360 §J10.6 (amplified by Ry,col).

    Parameters
    ----------
    beam_section_properties : SectionProperties
        Source of ``Zx,beam`` (for Mpr) and ``db = overall_depth_d``.
    beam_material : SteelMaterial
        Source of ``Fy,beam``, ``Ry,beam``, ``Fu,beam`` (for Cpr).
    column_section_properties : SectionProperties
        Source of ``dc``, ``tw,col``, ``bcf``, ``tcf``, ``Ag,col``.
    column_material : SteelMaterial
        Source of ``Fy,col`` and ``Ry,col``.
    column_axial_demand_Pr : float, default 0.0
        Required factored axial strength on the column (N).  Zero is
        conservative for the capacity formulas (J10-10 / J10-12
        amplify above the threshold).
    consider_panel_zone_deformation_in_frame_stability : bool, default False
        ``False`` -> use Eq. J10-9/J10-10.
        ``True``  -> use Eq. J10-11/J10-12 (includes the column-flange
        bending contribution; this is *only* valid when the analysis
        explicitly models panel-zone shear deformation).
    number_of_beam_sides : int, default 1
        1 for an exterior joint, 2 for an interior joint with beams
        framing in from both sides.
    column_shear_credit_Vu_col : float, default 0.0
        Estimated column shear above + below the panel zone (N).
        Reduces ``V_{u,pz}``; conservative to leave at 0.
    additional_doubler_plate_thickness_t_dp : float, default 0.0
        Doubler-plate thickness (mm) added to the column web.  When
        non-zero the formulas treat ``tw_effective = tw,col + tdp``.

    Returns
    -------
    PanelZoneShearReport
        Frozen report with the inputs, the governing AISC equation
        label, the nominal and design shear capacities, the demand,
        and the DCR.
    """
    if number_of_beam_sides not in (1, 2):
        msg = f"number_of_beam_sides must be 1 or 2; got {number_of_beam_sides}."
        raise ValueError(msg)

    Fy_col_eff: float = column_material.yield_stress_Fy * column_material.expected_yield_ratio_Ry
    Pc: float = column_material.yield_stress_Fy * column_section_properties.gross_area_Ag
    if Pc <= 0.0:
        msg = "column_section_properties.gross_area_Ag must be positive."
        raise ValueError(msg)

    dc: float = column_section_properties.overall_depth_d
    tw_col: float = column_section_properties.web_thickness_tw
    bcf: float = column_section_properties.flange_width_bf
    tcf: float = column_section_properties.flange_thickness_tf
    if any(v <= 0.0 for v in (dc, tw_col, bcf, tcf)):
        msg = (
            "column_section_properties must expose positive dc/tw/bcf/tcf; "
            f"got dc={dc}, tw={tw_col}, bcf={bcf}, tcf={tcf}."
        )
        raise ValueError(msg)

    db: float = beam_section_properties.overall_depth_d
    if db <= 0.0:
        msg = f"beam_section_properties.overall_depth_d must be positive; got {db}."
        raise ValueError(msg)

    tw_effective: float = tw_col + additional_doubler_plate_thickness_t_dp

    # --- compute Rn ---
    base_term: float = (
        PANEL_ZONE_SHEAR_NOMINAL_STRESS_COEFFICIENT_0p6 * Fy_col_eff * dc * tw_effective
    )
    Pr_over_Pc: float = column_axial_demand_Pr / Pc

    governing_equation: PanelZoneEquationLabel
    if not consider_panel_zone_deformation_in_frame_stability:
        if Pr_over_Pc <= AXIAL_RATIO_LIMIT_FOR_J10_9_AND_J10_10:
            Rn: float = base_term
            governing_equation = "J10-9"
        else:
            Rn = base_term * (AXIAL_REDUCTION_COEFFICIENT_J10_10_1p4 - Pr_over_Pc)
            governing_equation = "J10-10"
    else:
        # Bracketed boost  [1 + 3 bcf tcf^2 / (db dc tw_eff)]
        flange_boost: float = 1.0 + PANEL_ZONE_DEFORMATION_BOOST_COEFFICIENT_3 * (bcf * tcf**2) / (
            db * dc * tw_effective
        )
        if Pr_over_Pc <= AXIAL_RATIO_LIMIT_FOR_J10_11_AND_J10_12:
            Rn = base_term * flange_boost
            governing_equation = "J10-11"
        else:
            Rn = (
                base_term
                * flange_boost
                * (
                    AXIAL_REDUCTION_COEFFICIENT_J10_12_1p9
                    - AXIAL_REDUCTION_COEFFICIENT_J10_12_1p2 * Pr_over_Pc
                )
            )
            governing_equation = "J10-12"

    phi_Rn: float = PHI_PANEL_ZONE_SHEAR_LRFD * Rn

    # --- compute demand ---
    Cpr: float = _compute_Cpr(beam_material)
    Mpr: float = (
        Cpr
        * beam_material.expected_yield_ratio_Ry
        * beam_material.yield_stress_Fy
        * beam_section_properties.plastic_section_modulus_strong_axis_Zx
    )
    Vu_pz: float = number_of_beam_sides * Mpr / db - column_shear_credit_Vu_col
    Vu_pz = max(Vu_pz, 0.0)

    dcr: float = Vu_pz / phi_Rn if phi_Rn > 0.0 else float("inf")
    is_ok: bool = dcr <= 1.0
    governing_limit_state: str = (
        "panel_zone_shear_acceptable" if is_ok else "panel_zone_shear_exceeded"
    )

    return PanelZoneShearReport(
        cited_clauses=_CITATIONS_PANEL_ZONE_SHEAR,
        governing_limit_state=governing_limit_state,
        phi_LRFD=PHI_PANEL_ZONE_SHEAR_LRFD,
        omega_ASD=1.67,
        nominal_strength=Rn,
        phi_strength_LRFD=phi_Rn,
        omega_strength_ASD=Rn / 1.67,
        panel_zone_shear_demand_Vu_pz=Vu_pz,
        panel_zone_shear_capacity_Rn=Rn,
        phi_panel_zone_shear_capacity_phi_Rn_LRFD=phi_Rn,
        governing_equation=governing_equation,
        consider_panel_zone_deformation_in_frame_stability=consider_panel_zone_deformation_in_frame_stability,
        column_axial_demand_Pr=column_axial_demand_Pr,
        column_axial_yield_Pc=Pc,
        probable_strain_hardening_factor_Cpr=Cpr,
        probable_beam_plastic_moment_Mpr=Mpr,
        number_of_beam_sides=number_of_beam_sides,
        column_shear_credit_Vu_col=column_shear_credit_Vu_col,
        demand_to_capacity_ratio=dcr,
        is_demand_to_capacity_acceptable=is_ok,
    )


__all__ = [
    "AXIAL_RATIO_LIMIT_FOR_J10_9_AND_J10_10",
    "AXIAL_RATIO_LIMIT_FOR_J10_11_AND_J10_12",
    "PANEL_ZONE_DEFORMATION_BOOST_COEFFICIENT_3",
    "PHI_PANEL_ZONE_SHEAR_LRFD",
    "AXIAL_REDUCTION_COEFFICIENT_J10_10_1p4",
    "AXIAL_REDUCTION_COEFFICIENT_J10_12_1p2",
    "AXIAL_REDUCTION_COEFFICIENT_J10_12_1p9",
    "DEFAULT_PROBABLE_STRAIN_HARDENING_FACTOR_Cpr_IF_FU_UNKNOWN",
    "PANEL_ZONE_SHEAR_NOMINAL_STRESS_COEFFICIENT_0p6",
    "PROBABLE_STRAIN_HARDENING_FACTOR_Cpr_UPPER_BOUND_1p2",
    "PanelZoneEquationLabel",
    "PanelZoneShearReport",
    "check_panel_zone_shear_341",
]
