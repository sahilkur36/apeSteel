"""AISC 360 §F5 - flexural strength of slender-web plate girders.

§F5 covers doubly-symmetric and singly-symmetric I-shapes with a
SLENDER WEB.  The slender web is too thin to develop the plastic stress
block at the compression flange, so AISC introduces a bend-buckling
reduction factor Rpg (Eq. F5-6) that scales every limit-state moment
down.  In this Phase-8 port we cover the doubly-symmetric I path.

Three limit states are evaluated, with Mn = min:

* **Compression-flange yielding (CFY)** Eq. F5-1
  ``Mn_CFY = Rpg * Fy * Sxc``

* **Lateral-torsional buckling (LTB)** Eq. F5-2 to F5-4
  Three regimes based on Lb vs (Lp, Lr) computed with the F5-specific
  ``rt = bfc / sqrt(12*(1 + aw/6))`` (NOT the F2 rts).
      Lb <= Lp  -> Fcr = Fy
      Lp < Lb <= Lr  -> Fcr = Cb*(Fy - 0.3*Fy*(Lb-Lp)/(Lr-Lp)) <= Fy
      Lb > Lr   -> Fcr = Cb * pi^2 * E / (Lb/rt)^2 <= Fy
  Mn_LTB = Rpg * Fcr * Sxc

* **Compression-flange local buckling (FLB)** Eq. F5-7 to F5-9
      Compact flange   -> not active
      Non-compact      -> Fcr = Fy - 0.3*Fy*(lambda_f-lambda_pf)/(lambda_rf-lambda_pf)
      Slender flange   -> Fcr = 0.9*E*kc/lambda_f^2
  Mn_FLB = Rpg * Fcr * Sxc

The web-bend-buckling parameter:

    aw = (hc * tw) / (bfc * tfc),  capped at 10  (Eq. F5-12)
    Rpg = 1 - (aw / (1200 + 300*aw)) * (hc/tw - 5.7*sqrt(E/Fy))  <= 1.0

For doubly-symmetric: hc = hw, bfc = bf, tfc = tf, Sxc = Sx.

References
----------
.. [1] AISC 360-22 §F5, pp. 16.1-52 - 16.1-54.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from apeSteel.classification._common import compute_kc_for_built_up_flange
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
from apeSteel.flexure.lateral_torsional_buckling import compute_plastic_moment_Mp
from apeSteel.sections.flexural_properties import FlexuralSectionProperties

if TYPE_CHECKING:
    from apeSteel.classification import SectionConstruction
    from apeSteel.core.materials import SteelMaterial
    from apeSteel.sections.compression_properties import SectionSymmetry
    from apeSteel.sections.flexural_properties import FlexuralSectionKind
    from apeSteel.sections.properties import SectionProperties

# AISC §F5 coefficients
F5_RPG_COEFFICIENT_5p7: float = 5.7
F5_RPG_DENOMINATOR_OFFSET_1200: float = 1200.0
F5_RPG_DENOMINATOR_AW_COEFFICIENT_300: float = 300.0
F5_AW_UPPER_BOUND: float = 10.0
F5_LTB_REDUCED_STRESS_FACTOR_0p3: float = 0.3
F5_LP_COEFFICIENT_1p1: float = 1.1
F5_RT_DENOMINATOR_COEFFICIENT_12: float = 12.0
F5_RT_AW_DIVISOR_6: float = 6.0
F5_ELASTIC_FLB_COEFFICIENT_0p9: float = 0.9


@dataclass(frozen=True, slots=True)
class FlexureF5Report(Report):
    """AISC §F5 plate-girder flexural-strength result."""

    Cb_used: float = 0.0
    unbraced_length_Lb: float = 0.0
    construction: SectionConstruction = "welded"
    web_to_flange_area_ratio_aw: float = 0.0
    bend_buckling_reduction_factor_Rpg: float = 0.0
    F5_effective_radius_rt: float = 0.0
    limiting_length_plastic_Lp_F5: float = 0.0
    limiting_length_inelastic_LTB_Lr_F5: float = 0.0
    plastic_moment_Mp: float = 0.0
    flange_classification: str = ""
    nominal_CFY_moment_Mn_CFY: float = 0.0
    nominal_LTB_moment_Mn_LTB: float = 0.0
    nominal_FLB_moment_Mn_FLB: float = 0.0
    governing_F5_limit_state: str = ""
    nominal_flexural_strength_Mn: float = 0.0


_CITATIONS_F5: tuple[AISCClauseReference, ...] = (
    *CITATIONS_AISC_360_CHAPTER_F,
    AISCClauseReference("AISC 360-22", "F5", None, "16.1-52"),
    AISCClauseReference("AISC 360-22", "F5.1", "F5-1", "16.1-52"),
    AISCClauseReference("AISC 360-22", "F5.2", "F5-2", "16.1-53"),
    AISCClauseReference("AISC 360-22", "F5.2", "F5-3", "16.1-53"),
    AISCClauseReference("AISC 360-22", "F5.2", "F5-4", "16.1-53"),
    AISCClauseReference("AISC 360-22", "F5.2", "F5-5", "16.1-53"),
    AISCClauseReference("AISC 360-22", "F5.2", "F5-6", "16.1-53"),
    AISCClauseReference("AISC 360-22", "F5.3", "F5-7", "16.1-54"),
    AISCClauseReference("AISC 360-22", "F5.3", "F5-8", "16.1-54"),
    AISCClauseReference("AISC 360-22", "F5.3", "F5-9", "16.1-54"),
)


def compute_aw_for_F5(
    web_clear_height_hc: float,
    web_thickness_tw: float,
    compression_flange_width_bfc: float,
    compression_flange_thickness_tfc: float,
) -> float:
    """Web/compression-flange area ratio per AISC Eq. F5-12, capped at 10."""
    raw = (web_clear_height_hc * web_thickness_tw) / (
        compression_flange_width_bfc * compression_flange_thickness_tfc
    )
    return min(raw, F5_AW_UPPER_BOUND)


def compute_Rpg(
    web_to_flange_area_ratio_aw: float,
    web_slenderness_ratio_h_over_tw: float,
    elastic_modulus_E: float,
    yield_stress_Fy: float,
) -> float:
    """AISC Eq. F5-6 bend-buckling reduction factor, capped at 1.0."""
    aw = web_to_flange_area_ratio_aw
    lambda_w = web_slenderness_ratio_h_over_tw
    threshold = F5_RPG_COEFFICIENT_5p7 * math.sqrt(elastic_modulus_E / yield_stress_Fy)
    if lambda_w <= threshold:
        return 1.0
    denominator = F5_RPG_DENOMINATOR_OFFSET_1200 + F5_RPG_DENOMINATOR_AW_COEFFICIENT_300 * aw
    Rpg = 1.0 - (aw / denominator) * (lambda_w - threshold)
    return min(Rpg, 1.0)


def compute_rt_for_F5(
    compression_flange_width_bfc: float,
    web_to_flange_area_ratio_aw: float,
) -> float:
    """AISC Eq. F5-11: rt = bfc / sqrt(12*(1 + aw/6))."""
    inside_sqrt = F5_RT_DENOMINATOR_COEFFICIENT_12 * (
        1.0 + web_to_flange_area_ratio_aw / F5_RT_AW_DIVISOR_6
    )
    return compression_flange_width_bfc / math.sqrt(inside_sqrt)


def compute_flexural_strength_F5_slender_web_plate_girder(  # noqa: PLR0912, PLR0915
    section_properties: SectionProperties,
    material: SteelMaterial,
    unbraced_length_Lb: float,
    lateral_torsional_buckling_modification_factor_Cb: float,
    construction: SectionConstruction = "welded",
) -> FlexureF5Report:
    """Return Mn per AISC §F5 for a doubly- or singly-symmetric slender-web I.

    AISC 360-22 §F5 (spec_chapterF.txt printed 16.1-60/61) covers
    **doubly-symmetric and singly-symmetric** I-shaped members with
    slender webs.  Four limit states, ``Mn`` is the lowest:

    * §F5.1 compression-flange yielding   ``Mp = Rpg*Fy*Sxc``      (F5-1)
    * §F5.2 lateral-torsional buckling     ``Mn = Rpg*Fcr*Sxc``    (F5-2)
    * §F5.3 compression-flange local buckling ``Mn = Rpg*Fcr*Sxc`` (F5-7)
    * §F5.4 tension-flange yielding ``Mn = Fy*Sxt`` (only ``Sxt < Sxc``)
      (F5-10)

    The shipped doubly-symmetric path is preserved **byte-for-byte**:
    for a DS section ``Sxc = Sxt = Sx`` and ``hc = hw`` so the four
    equations collapse to the exact prior expressions (F5-10 is inactive
    because ``Sxt == Sxc``).  Section geometry is now lifted through
    :meth:`FlexuralSectionProperties.from_legacy` (which copies
    ``Zx``/``Sx`` verbatim and ``Sxc``/``Sxt`` via the *same*
    ``resolved_*`` accessors), so no DS number moves.  The
    singly-symmetric path (``hp > 0`` - the same discriminator §F4 uses)
    is **purely additive**: no shipped test exercises an SS slender web.

    Caller should verify the section's web is slender (use
    classify_flexural_compactness_B4_1b).  F5 is a valid choice for
    slender-web sections; for compact-web use F2/F3 instead.
    """
    if unbraced_length_Lb <= 0.0:
        raise ValueError(f"unbraced_length_Lb must be positive, got {unbraced_length_Lb!r}")

    Fy: float = material.yield_stress_Fy
    E: float = material.elastic_modulus_E
    # Singly-symmetric iff the geometry populated the plastic-zone depth
    # hp (DS leaves it at the 0.0 sentinel) - identical discriminator to
    # the shipped F4.py.  The DS branch reproduces the prior code
    # exactly; the SS branch is new (§F5 SS, design note 10 §F-1).
    is_singly_symmetric: bool = section_properties.plastic_neutral_axis_depth_hp > 0.0

    # Lift the shipped I-only currency into the generalized Chapter-F
    # model.  ``from_legacy`` copies Zx/Sx verbatim and Sxc/Sxt through
    # the identical ``resolved_*`` accessors, so for a DS section
    # Sxc == Sxt == Sx bit-for-bit and every shipped F5 number is
    # unchanged.  Classification keeps reading ``section_properties``
    # (conservative path).  ``c`` (Eq. F2-8a/8b) is not used by §F5.
    fsp_kind: FlexuralSectionKind = (
        "singly_symmetric_I" if is_singly_symmetric else "doubly_symmetric_I"
    )
    fsp_symmetry: SectionSymmetry = (
        "singly_symmetric" if is_singly_symmetric else "doubly_symmetric"
    )
    fsp: FlexuralSectionProperties = FlexuralSectionProperties.from_legacy(
        section_properties,
        kind=fsp_kind,
        symmetry=fsp_symmetry,
        construction=construction,
    )
    Zx: float = fsp.plastic_modulus_Zx
    # §F5 references everything to the compression flange (Eq. F5-1/2/7);
    # for a DS section ``Sxc == Sxt == Sx`` (resolved), so using ``Sxc``
    # is byte-identical to the shipped ``Sx`` path.  ``Sx`` itself is no
    # longer read - the four limit states are all in terms of Sxc/Sxt.
    Sxc: float = fsp.elastic_modulus_compression_flange_Sxc
    Sxt: float = fsp.elastic_modulus_tension_flange_Sxt
    tw: float = section_properties.web_thickness_tw
    lambda_w: float = section_properties.web_height_to_thickness_ratio_h_tw
    hw: float = lambda_w * tw  # web clear height (DS aw numerator)
    Cb: float = lateral_torsional_buckling_modification_factor_Cb

    # AISC §F5 needs the *actual* compression-flange width/thickness for
    # aw (Eq. F4-12), rt (Eq. F4-11) and hence Rpg / Lp / Lr / Fcr.  Use
    # the explicit (resolved) flange dimensions carried on
    # SectionProperties - NOT a back-solve from Ag, which would fold a
    # rolled section's fillet / k area into the flange and corrupt aw.
    bf: float = section_properties.resolved_compression_flange_width_bfc()
    tf: float = section_properties.resolved_compression_flange_thickness_tfc()
    if bf <= 0.0 or tf <= 0.0:
        raise ValueError(
            "F5 requires the compression-flange dimensions on "
            "SectionProperties (flange_width_bf / flange_thickness_tf); "
            f"got bf={bf!r}, tf={tf!r}."
        )

    # --- Mp ---
    Mp: float = compute_plastic_moment_Mp(Fy, Zx)

    # --- aw, Rpg, rt ---
    # Eq. F4-12 aw uses the web compression depth hc; Eq. F5-6 Rpg uses
    # hc/tw.  For a DS section hc == hw and hc/tw == lambda_w *exactly*
    # (the shipped values), so the DS branch passes the prior arguments
    # (hw, lambda_w) verbatim - byte-identical.  The SS branch uses the
    # resolved hc.
    if is_singly_symmetric:
        hc: float = section_properties.resolved_hc()
        aw = compute_aw_for_F5(
            web_clear_height_hc=hc,
            web_thickness_tw=tw,
            compression_flange_width_bfc=bf,
            compression_flange_thickness_tfc=tf,
        )
        Rpg = compute_Rpg(
            web_to_flange_area_ratio_aw=aw,
            web_slenderness_ratio_h_over_tw=hc / tw,
            elastic_modulus_E=E,
            yield_stress_Fy=Fy,
        )
    else:
        aw = compute_aw_for_F5(
            web_clear_height_hc=hw,
            web_thickness_tw=tw,
            compression_flange_width_bfc=bf,
            compression_flange_thickness_tfc=tf,
        )
        Rpg = compute_Rpg(
            web_to_flange_area_ratio_aw=aw,
            web_slenderness_ratio_h_over_tw=lambda_w,
            elastic_modulus_E=E,
            yield_stress_Fy=Fy,
        )
    rt = compute_rt_for_F5(
        compression_flange_width_bfc=bf,
        web_to_flange_area_ratio_aw=aw,
    )

    # --- LTB regime --- (Eq. F5-2..F5-5; Lp = Eq. F4-7, Lr = Eq. F5-5)
    Lp = F5_LP_COEFFICIENT_1p1 * rt * math.sqrt(E / Fy)
    Lr = math.pi * rt * math.sqrt(E / (0.7 * Fy))
    Lb = unbraced_length_Lb

    if Lb <= Lp:
        Fcr_LTB: float = Fy
    elif Lb <= Lr:
        Fcr_LTB = Cb * (Fy - F5_LTB_REDUCED_STRESS_FACTOR_0p3 * Fy * (Lb - Lp) / (Lr - Lp))
        Fcr_LTB = min(Fcr_LTB, Fy)
    else:
        Fcr_LTB = Cb * math.pi**2 * E / ((Lb / rt) ** 2)
        Fcr_LTB = min(Fcr_LTB, Fy)
    # Eq. F5-2  Mn = Rpg*Fcr*Sxc.  DS: Sxc == Sx -> identical to prior.
    Mn_LTB: float = Rpg * Fcr_LTB * Sxc

    # --- CFY --- Eq. F5-1  Mp = Rpg*Fy*Sxc.  DS: Sxc == Sx.
    Mn_CFY: float = Rpg * Fy * Sxc

    # --- FLB --- Eq. F5-7..F5-9.  DS: Sxc == Sx -> identical to prior.
    flex_class_report = classify_flexural_compactness_B4_1b(
        section_properties,
        material,
        construction,
    )
    flange_class = flex_class_report.flange.classification
    lam_f = flex_class_report.flange.slenderness_ratio_lambda
    lam_pf = flex_class_report.flange.compact_limit_lambda_p
    lam_rf = flex_class_report.flange.noncompact_limit_lambda_r
    if lam_pf is None:
        raise ValueError("flexural classifier did not return lambda_p for flange")

    if flange_class == "compact":
        Mn_FLB: float = Mn_CFY  # FLB not active; same as CFY
    elif flange_class == "non_compact":
        Fcr_FLB = Fy - F5_LTB_REDUCED_STRESS_FACTOR_0p3 * Fy * (
            (lam_f - lam_pf) / (lam_rf - lam_pf)
        )
        Mn_FLB = Rpg * Fcr_FLB * Sxc
    else:  # slender flange
        kc = compute_kc_for_built_up_flange(lambda_w)
        Fcr_FLB = F5_ELASTIC_FLB_COEFFICIENT_0p9 * E * kc / (lam_f**2)
        Mn_FLB = Rpg * Fcr_FLB * Sxc

    # --- Final Mn = min over active limit states, capped at Mp ---
    Mn_candidates: dict[str, float] = {
        "compression_flange_yielding": Mn_CFY,
        "lateral_torsional_buckling": Mn_LTB,
        "flange_local_buckling": Mn_FLB,
    }
    # §F5.4 Eq. F5-10  Mn = Fy*Sxt: tension-flange yielding applies only
    # when Sxt < Sxc (so inactive for a DS section, where Sxt == Sxc -
    # the shipped DS result is therefore unchanged).
    if Sxt < Sxc:
        Mn_candidates["tension_flange_yielding"] = Fy * Sxt
    governing = min(Mn_candidates, key=lambda k: Mn_candidates[k])
    Mn: float = min(Mn_candidates[governing], Mp)
    if Mn == Mp and Mn_candidates[governing] >= Mp:
        # The Mp cap struck; reflect that in the governing label.
        governing_limit_state: FlexuralLimitState = "yielding"
    else:
        governing_limit_state = governing  # type: ignore[assignment]

    return FlexureF5Report(
        cited_clauses=_CITATIONS_F5,
        governing_limit_state=governing_limit_state,
        phi_LRFD=PHI_FLEXURE_LRFD,
        omega_ASD=OMEGA_FLEXURE_ASD,
        nominal_strength=Mn,
        phi_strength_LRFD=PHI_FLEXURE_LRFD * Mn,
        omega_strength_ASD=Mn / OMEGA_FLEXURE_ASD,
        Cb_used=Cb,
        unbraced_length_Lb=Lb,
        construction=construction,
        web_to_flange_area_ratio_aw=aw,
        bend_buckling_reduction_factor_Rpg=Rpg,
        F5_effective_radius_rt=rt,
        limiting_length_plastic_Lp_F5=Lp,
        limiting_length_inelastic_LTB_Lr_F5=Lr,
        plastic_moment_Mp=Mp,
        flange_classification=flange_class,
        nominal_CFY_moment_Mn_CFY=Mn_CFY,
        nominal_LTB_moment_Mn_LTB=Mn_LTB,
        nominal_FLB_moment_Mn_FLB=Mn_FLB,
        governing_F5_limit_state=governing,
        nominal_flexural_strength_Mn=Mn,
    )


__all__ = [
    "FlexureF5Report",
    "compute_Rpg",
    "compute_aw_for_F5",
    "compute_flexural_strength_F5_slender_web_plate_girder",
    "compute_rt_for_F5",
]
