"""AISC 360 §F3 - flexural strength: non-compact or slender flange + compact web.

§F3 governs doubly-symmetric I-shapes with a COMPACT WEB and a
NON-COMPACT or SLENDER FLANGE.  Two limit states are evaluated and Mn
is the minimum:

* **Lateral-torsional buckling** - same machinery as §F2 (Eq. F2-1
  through F2-7, with Lp / Lr / Mcr).
* **Flange local buckling (FLB)** - new in §F3 (Eq. F3-1 for non-compact,
  Eq. F3-2 for slender, with kc).

Final ``Mn = min(M_LTB, M_FLB)``, capped at Mp.

The caller is responsible for verifying the section has a compact web
(via :func:`apeSteel.classification.classify_flexural_compactness_B4_1b`).
F3 should NOT be invoked when the flange is compact (use F2 instead) or
when the web is slender (use F5 instead).

References
----------
.. [1] AISC 360-22 §F3 "Doubly Symmetric I-Shaped Members With Compact
       Webs and Noncompact or Slender Flanges Bent About Their Major
       Axis", pp. 16.1-50 - 16.1-51.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from apeSteel.classification.flexural_compactness_B4_1b import (
    classify_flexural_compactness_B4_1b,
)
from apeSteel.core.result_types import AISCClauseReference, Report
from apeSteel.flexure._common import (
    CITATIONS_AISC_360_CHAPTER_F,
    OMEGA_FLEXURE_ASD,
    PHI_FLEXURE_LRFD,
    FlexuralLimitState,
)
from apeSteel.flexure.flange_local_buckling import (
    compute_flange_local_buckling_moment_Mn_F3_1,
    compute_flange_local_buckling_moment_Mn_F3_2,
)
from apeSteel.flexure.lateral_torsional_buckling import (
    compute_elastic_LTB_critical_moment_Mcr,
    compute_inelastic_LTB_moment_Mn_F2_2,
    compute_limiting_length_inelastic_LTB_Lr,
    compute_limiting_length_plastic_Lp,
    compute_plastic_moment_Mp,
)

if TYPE_CHECKING:
    from apeSteel.classification import SectionConstruction
    from apeSteel.core.materials import SteelMaterial
    from apeSteel.sections.properties import SectionProperties


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class FlexureF3Report(Report):
    """AISC §F3 flexural strength: LTB + FLB, take the minimum.

    Attributes
    ----------
    Cb_used : float
    unbraced_length_Lb : float
    construction : str
        "rolled" or "welded" (drives FLB Case 10 vs 11).
    limiting_length_plastic_Lp : float
    limiting_length_inelastic_LTB_Lr : float
    plastic_moment_Mp : float
    elastic_LTB_moment_Mcr : float
    nominal_LTB_moment_Mn_LTB : float
        The LTB Mn, capped at Mp, before taking min with FLB.
    flange_slenderness_ratio_lambda_f : float
    flange_compact_limit_lambda_pf : float
    flange_noncompact_limit_lambda_rf : float
    flange_classification : str
        "compact", "non_compact", or "slender" - echoed from the
        classifier.  If "compact", FLB is not active.
    nominal_FLB_moment_Mn_FLB : float
        The FLB Mn, capped at Mp.  Equal to Mp when the flange is
        compact (FLB does not govern).
    governing_flexural_limit_state : str
        "lateral_torsional_buckling" or "flange_local_buckling" - which
        of the two regimes produced the lower Mn.
    nominal_flexural_strength_Mn : float
        min(Mn_LTB, Mn_FLB), capped at Mp.
    """

    Cb_used: float = 0.0
    unbraced_length_Lb: float = 0.0
    construction: SectionConstruction = "welded"
    limiting_length_plastic_Lp: float = 0.0
    limiting_length_inelastic_LTB_Lr: float = 0.0
    plastic_moment_Mp: float = 0.0
    elastic_LTB_moment_Mcr: float = 0.0
    nominal_LTB_moment_Mn_LTB: float = 0.0
    flange_slenderness_ratio_lambda_f: float = 0.0
    flange_compact_limit_lambda_pf: float = 0.0
    flange_noncompact_limit_lambda_rf: float = 0.0
    flange_classification: str = ""
    nominal_FLB_moment_Mn_FLB: float = 0.0
    governing_flexural_limit_state: str = ""
    nominal_flexural_strength_Mn: float = 0.0


# ---------------------------------------------------------------------------
# Citations
# ---------------------------------------------------------------------------
_CITATIONS_F3: tuple[AISCClauseReference, ...] = (
    *CITATIONS_AISC_360_CHAPTER_F,
    AISCClauseReference("AISC 360-22", "F3", None, "16.1-50"),
    AISCClauseReference("AISC 360-22", "F3.1", None, "16.1-50"),
    AISCClauseReference("AISC 360-22", "F3.2", "F3-1", "16.1-50"),
    AISCClauseReference("AISC 360-22", "F3.2", "F3-2", "16.1-50"),
    AISCClauseReference("AISC 360-22", "F2.2", "F2-2", "16.1-49"),
    AISCClauseReference("AISC 360-22", "F2.2", "F2-4", "16.1-49"),
    AISCClauseReference("AISC 360-22", "F2.2", "F2-5", "16.1-49"),
    AISCClauseReference("AISC 360-22", "F2.2", "F2-6", "16.1-50"),
    AISCClauseReference("AISC 360-22", "Table B4.1b", "kc factor", "16.1-15"),
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _compute_LTB_moment_Mn_LTB(
    plastic_moment_Mp: float,
    yield_stress_Fy: float,
    elastic_modulus_E: float,
    Sx: float,
    ry: float,
    rts: float,
    ho: float,
    J: float,
    unbraced_length_Lb: float,
    Cb: float,
) -> tuple[float, float, float, float, FlexuralLimitState]:
    """Run the same three-regime LTB decision tree as F2.

    Returns
    -------
    (Lp, Lr, Mcr, Mn_LTB_capped_at_Mp, ltb_regime)
    """
    Lp = compute_limiting_length_plastic_Lp(ry, elastic_modulus_E, yield_stress_Fy)
    Lr = compute_limiting_length_inelastic_LTB_Lr(
        rts,
        ho,
        J,
        Sx,
        elastic_modulus_E,
        yield_stress_Fy,
    )
    Mcr: float = 0.0
    if unbraced_length_Lb <= Lp:
        return Lp, Lr, Mcr, plastic_moment_Mp, "yielding"
    if unbraced_length_Lb <= Lr:
        Mn_raw = compute_inelastic_LTB_moment_Mn_F2_2(
            plastic_moment_Mp=plastic_moment_Mp,
            yield_stress_Fy=yield_stress_Fy,
            elastic_section_modulus_strong_axis_Sx=Sx,
            lateral_torsional_buckling_modification_factor_Cb=Cb,
            unbraced_length_Lb=unbraced_length_Lb,
            limiting_length_plastic_Lp=Lp,
            limiting_length_inelastic_LTB_Lr=Lr,
        )
        return Lp, Lr, Mcr, min(Mn_raw, plastic_moment_Mp), "inelastic_LTB"
    Mcr = compute_elastic_LTB_critical_moment_Mcr(
        lateral_torsional_buckling_modification_factor_Cb=Cb,
        unbraced_length_Lb=unbraced_length_Lb,
        effective_radius_of_gyration_rts=rts,
        elastic_section_modulus_strong_axis_Sx=Sx,
        distance_between_flange_centroids_ho=ho,
        torsional_constant_J=J,
        elastic_modulus_E=elastic_modulus_E,
    )
    return Lp, Lr, Mcr, min(Mcr, plastic_moment_Mp), "elastic_LTB"


# ---------------------------------------------------------------------------
# Public facade
# ---------------------------------------------------------------------------
def compute_flexural_strength_F3_noncompact_or_slender_flange(
    section_properties: SectionProperties,
    material: SteelMaterial,
    unbraced_length_Lb: float,
    lateral_torsional_buckling_modification_factor_Cb: float,
    construction: SectionConstruction = "welded",
) -> FlexureF3Report:
    """Return Mn per AISC §F3 for a compact-web, non-compact or slender flange.

    Parameters
    ----------
    section_properties : SectionProperties
    material : SteelMaterial
    unbraced_length_Lb : float
        Distance between lateral braces of the compression flange (mm).
    lateral_torsional_buckling_modification_factor_Cb : float
    construction : {"rolled", "welded"}
        Drives FLB Case 10 (rolled) vs Case 11 (welded with kc).

    Returns
    -------
    FlexureF3Report

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

    # --- Mp ---
    Mp: float = compute_plastic_moment_Mp(Fy, Zx)

    # --- LTB (F2 machinery) ---
    Lp, Lr, Mcr, Mn_LTB, ltb_regime = _compute_LTB_moment_Mn_LTB(
        plastic_moment_Mp=Mp,
        yield_stress_Fy=Fy,
        elastic_modulus_E=E,
        Sx=Sx,
        ry=ry,
        rts=rts,
        ho=ho,
        J=J,
        unbraced_length_Lb=unbraced_length_Lb,
        Cb=Cb,
    )

    # --- FLB (F3) ---
    flex_class_report = classify_flexural_compactness_B4_1b(
        section_properties,
        material,
        construction,
    )
    flange_class = flex_class_report.flange
    lam_f = flange_class.slenderness_ratio_lambda
    lam_pf = flange_class.compact_limit_lambda_p
    lam_rf = flange_class.noncompact_limit_lambda_r
    if lam_pf is None:  # defensive - shouldn't happen for flexure
        raise ValueError("B4.1b flexural classifier did not return lambda_p for flange")

    if flange_class.classification == "compact":
        # FLB does not govern; Mn_FLB = Mp.
        Mn_FLB: float = Mp
    elif flange_class.classification == "non_compact":
        Mn_FLB = compute_flange_local_buckling_moment_Mn_F3_1(
            plastic_moment_Mp=Mp,
            yield_stress_Fy=Fy,
            elastic_section_modulus_strong_axis_Sx=Sx,
            flange_slenderness_ratio_lambda_f=lam_f,
            flange_compact_limit_lambda_pf=lam_pf,
            flange_noncompact_limit_lambda_rf=lam_rf,
        )
        Mn_FLB = min(Mn_FLB, Mp)
    else:  # "slender"
        # For Eq. F3-2 we need kc.  Built-up only - rolled doesn't reach
        # slender-flange under normal Fy/AISC limits.  Use the same kc
        # formula the classifier uses.
        from apeSteel.classification._common import compute_kc_for_built_up_flange  # noqa: PLC0415

        kc = compute_kc_for_built_up_flange(
            section_properties.web_height_to_thickness_ratio_h_tw,
        )
        Mn_FLB = compute_flange_local_buckling_moment_Mn_F3_2(
            elastic_section_modulus_strong_axis_Sx=Sx,
            elastic_modulus_E=E,
            flange_plate_buckling_coefficient_kc=kc,
            flange_slenderness_ratio_lambda_f=lam_f,
        )
        Mn_FLB = min(Mn_FLB, Mp)

    # --- Final Mn = min(LTB, FLB) ---
    if Mn_FLB <= Mn_LTB:
        governing: str = "flange_local_buckling"
        Mn: float = Mn_FLB
        # Reuse the LTB-regime label if FLB doesn't dominate; here it does.
        governing_limit_state: FlexuralLimitState = "flange_local_buckling"
    else:
        governing = "lateral_torsional_buckling"
        Mn = Mn_LTB
        governing_limit_state = ltb_regime

    phi_Mn = PHI_FLEXURE_LRFD * Mn

    return FlexureF3Report(
        cited_clauses=_CITATIONS_F3,
        governing_limit_state=governing_limit_state,
        phi_LRFD=PHI_FLEXURE_LRFD,
        omega_ASD=OMEGA_FLEXURE_ASD,
        nominal_strength=Mn,
        phi_strength_LRFD=phi_Mn,
        omega_strength_ASD=Mn / OMEGA_FLEXURE_ASD,
        Cb_used=Cb,
        unbraced_length_Lb=unbraced_length_Lb,
        construction=construction,
        limiting_length_plastic_Lp=Lp,
        limiting_length_inelastic_LTB_Lr=Lr,
        plastic_moment_Mp=Mp,
        elastic_LTB_moment_Mcr=Mcr,
        nominal_LTB_moment_Mn_LTB=Mn_LTB,
        flange_slenderness_ratio_lambda_f=lam_f,
        flange_compact_limit_lambda_pf=lam_pf,
        flange_noncompact_limit_lambda_rf=lam_rf,
        flange_classification=flange_class.classification,
        nominal_FLB_moment_Mn_FLB=Mn_FLB,
        governing_flexural_limit_state=governing,
        nominal_flexural_strength_Mn=Mn,
    )


__all__ = [
    "FlexureF3Report",
    "compute_flexural_strength_F3_noncompact_or_slender_flange",
]
