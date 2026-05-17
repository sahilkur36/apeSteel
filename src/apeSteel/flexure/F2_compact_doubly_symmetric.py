"""AISC 360 §F2 - flexural strength of compact doubly-symmetric I-shapes.

This module contains the facade for §F2: it takes a compact section,
its material, an unbraced length, and a Cb, and returns the nominal
flexural strength Mn with the controlling LTB regime identified.

Three regimes are recognised:

* Lb <= Lp     -> Mn = Mp                          (F2-1, yielding)
* Lp < Lb <= Lr  -> Mn = Cb * inelastic-interpolation, capped at Mp
                                                     (F2-2, inelastic LTB)
* Lb > Lr      -> Mn = Mcr, capped at Mp           (F2-3, elastic LTB)

The caller is responsible for verifying the section is BOTH flange-
compact AND web-compact (via classify_flexural_compactness_B4_1b).
Calling F2 on a non-compact or slender section produces a number, but
that number is not the AISC-compliant strength; for such sections you
must route to F3, F4, or F5 instead.  This responsibility lives in the
upstream BeamCheck facade (Phase 7).

Both flanges:
    Real beams are checked at BOTH the top-flange and the bottom-flange
    unbraced lengths.  The two checks are independent calls to this
    function; the BeamCheck facade picks the lower phi*Mn.

References
----------
.. [1] AISC 360-22 §F2 "I-Shaped Members and Channels Bent About Their
       Major Axis", p. 16.1-49.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from apeSteel.core.result_types import AISCClauseReference, Report
from apeSteel.flexure._common import (
    CITATIONS_AISC_360_CHAPTER_F,
    OMEGA_FLEXURE_ASD,
    PHI_FLEXURE_LRFD,
    FlexuralLimitState,
)
from apeSteel.flexure.lateral_torsional_buckling import (
    compute_elastic_LTB_critical_moment_Mcr,
    compute_inelastic_LTB_moment_Mn_F2_2,
    compute_limiting_length_inelastic_LTB_Lr,
    compute_limiting_length_plastic_Lp,
    compute_plastic_moment_Mp,
)

if TYPE_CHECKING:
    from apeSteel.core.materials import SteelMaterial
    from apeSteel.sections.properties import SectionProperties


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class FlexureF2Report(Report):
    """AISC §F2 flexural-strength result for a compact doubly-symmetric I.

    All moments in apeSteel base units (N*mm); all lengths in mm.

    Attributes
    ----------
    Cb_used : float
        The Cb value passed in (echoed for trace).
    unbraced_length_Lb : float
        Lb input (mm).
    limiting_length_plastic_Lp : float
        Lp per Eq. F2-5 (mm).
    limiting_length_inelastic_LTB_Lr : float
        Lr per Eq. F2-6 (mm).
    plastic_moment_Mp : float
        Mp = Fy * Zx, the F2-1 plateau (N*mm).
    elastic_LTB_moment_Mcr : float
        Elastic LTB critical moment per Eq. F2-4 (N*mm).  Computed
        only when Lb > Lr; for shorter Lb it is reported as 0.0 (the
        formula does not apply).
    nominal_flexural_strength_Mn : float
        Final Mn, capped at Mp (inherits from Report.nominal_strength
        as well).
    """

    Cb_used: float = 0.0
    unbraced_length_Lb: float = 0.0
    limiting_length_plastic_Lp: float = 0.0
    limiting_length_inelastic_LTB_Lr: float = 0.0
    plastic_moment_Mp: float = 0.0
    elastic_LTB_moment_Mcr: float = 0.0
    nominal_flexural_strength_Mn: float = 0.0


# ---------------------------------------------------------------------------
# Equation-set citations
# ---------------------------------------------------------------------------
_CITATIONS_F2: tuple[AISCClauseReference, ...] = (
    *CITATIONS_AISC_360_CHAPTER_F,
    AISCClauseReference("AISC 360-22", "F2", None, "16.1-49"),
    AISCClauseReference("AISC 360-22", "F2.1", "F2-1", "16.1-49"),
    AISCClauseReference("AISC 360-22", "F2.2", "F2-2", "16.1-49"),
    AISCClauseReference("AISC 360-22", "F2.2", "F2-3", "16.1-49"),
    AISCClauseReference("AISC 360-22", "F2.2", "F2-4", "16.1-49"),
    AISCClauseReference("AISC 360-22", "F2.2", "F2-5", "16.1-49"),
    AISCClauseReference("AISC 360-22", "F2.2", "F2-6", "16.1-50"),
    AISCClauseReference("AISC 360-22", "F2.2", "F2-7", "16.1-50"),
)


# ---------------------------------------------------------------------------
# Public facade
# ---------------------------------------------------------------------------
def compute_flexural_strength_F2_compact_doubly_symmetric(
    section_properties: SectionProperties,
    material: SteelMaterial,
    unbraced_length_Lb: float,
    lateral_torsional_buckling_modification_factor_Cb: float,
) -> FlexureF2Report:
    """Return Mn per AISC §F2 for a compact doubly-symmetric I.

    Parameters
    ----------
    section_properties : SectionProperties
        Must come from a flexurally-compact section (caller verifies via
        classify_flexural_compactness_B4_1b).  Reads Sx, Zx, ry, rts,
        J, Cw, ho.
    material : SteelMaterial
        Reads Fy and E.
    unbraced_length_Lb : float
        Distance between points laterally bracing the compression
        flange (mm).  Must be > 0.
    lateral_torsional_buckling_modification_factor_Cb : float
        Cb per AISC Eq. F1-1.  The caller must compute this explicitly;
        no silent default to 1.0.

    Returns
    -------
    FlexureF2Report
        Frozen dataclass with every intermediate quantity exposed.

    Raises
    ------
    ValueError
        If `unbraced_length_Lb <= 0`.
    """
    if unbraced_length_Lb <= 0.0:
        raise ValueError(f"unbraced_length_Lb must be positive, got {unbraced_length_Lb!r}")

    Fy: float = material.yield_stress_Fy
    E: float = material.elastic_modulus_E
    Zx: float = section_properties.plastic_section_modulus_strong_axis_Zx
    Sx: float = section_properties.elastic_section_modulus_strong_axis_Sx
    ry: float = section_properties.radius_of_gyration_weak_axis_ry
    rts: float = section_properties.effective_radius_of_gyration_for_LTB_rts
    ho: float = section_properties.distance_between_flange_centroids_ho
    J: float = section_properties.torsional_constant_J
    Cb: float = lateral_torsional_buckling_modification_factor_Cb

    # --- regime-defining lengths ---
    Lp: float = compute_limiting_length_plastic_Lp(
        radius_of_gyration_weak_axis_ry=ry,
        elastic_modulus_E=E,
        yield_stress_Fy=Fy,
    )
    Lr: float = compute_limiting_length_inelastic_LTB_Lr(
        effective_radius_of_gyration_rts=rts,
        distance_between_flange_centroids_ho=ho,
        torsional_constant_J=J,
        elastic_section_modulus_strong_axis_Sx=Sx,
        elastic_modulus_E=E,
        yield_stress_Fy=Fy,
    )

    # --- plastic-moment plateau ---
    Mp: float = compute_plastic_moment_Mp(
        yield_stress_Fy=Fy,
        plastic_section_modulus_strong_axis_Zx=Zx,
    )

    # --- pick regime ---
    Lb = unbraced_length_Lb
    Mcr: float = 0.0
    if Lb <= Lp:
        governing_regime: FlexuralLimitState = "yielding"
        Mn: float = Mp
    elif Lb <= Lr:
        governing_regime = "inelastic_LTB"
        Mn_raw: float = compute_inelastic_LTB_moment_Mn_F2_2(
            plastic_moment_Mp=Mp,
            yield_stress_Fy=Fy,
            elastic_section_modulus_strong_axis_Sx=Sx,
            lateral_torsional_buckling_modification_factor_Cb=Cb,
            unbraced_length_Lb=Lb,
            limiting_length_plastic_Lp=Lp,
            limiting_length_inelastic_LTB_Lr=Lr,
        )
        # AISC F2-2 caps Mn at Mp.
        Mn = min(Mn_raw, Mp)
    else:
        governing_regime = "elastic_LTB"
        Mcr = compute_elastic_LTB_critical_moment_Mcr(
            lateral_torsional_buckling_modification_factor_Cb=Cb,
            unbraced_length_Lb=Lb,
            effective_radius_of_gyration_rts=rts,
            elastic_section_modulus_strong_axis_Sx=Sx,
            distance_between_flange_centroids_ho=ho,
            torsional_constant_J=J,
            elastic_modulus_E=E,
        )
        # AISC F2-3 caps Mn at Mp.
        Mn = min(Mcr, Mp)

    phi_Mn: float = PHI_FLEXURE_LRFD * Mn
    Mn_over_omega: float = Mn / OMEGA_FLEXURE_ASD

    return FlexureF2Report(
        cited_clauses=_CITATIONS_F2,
        governing_limit_state=governing_regime,
        phi_LRFD=PHI_FLEXURE_LRFD,
        omega_ASD=OMEGA_FLEXURE_ASD,
        nominal_strength=Mn,
        phi_strength_LRFD=phi_Mn,
        omega_strength_ASD=Mn_over_omega,
        Cb_used=Cb,
        unbraced_length_Lb=Lb,
        limiting_length_plastic_Lp=Lp,
        limiting_length_inelastic_LTB_Lr=Lr,
        plastic_moment_Mp=Mp,
        elastic_LTB_moment_Mcr=Mcr,
        nominal_flexural_strength_Mn=Mn,
    )


__all__ = [
    "FlexureF2Report",
    "compute_flexural_strength_F2_compact_doubly_symmetric",
]
