"""AISC 360 §F4 - flexural strength: doubly- AND singly-symmetric I-shapes.

§F4 (AISC 360-22, p. 16.1-56) covers two cases:

* **Doubly-symmetric I-shaped members** bent about their major axis with
  **non-compact webs**.
* **Singly-symmetric I-shaped members** with webs attached at the
  mid-width of the flanges, bent about their major axis, with
  **compact or non-compact webs**.

This module handles both via a single facade
:func:`compute_flexural_strength_F4` that reads ``Sxc``, ``Sxt``,
``Iyc/Iy``, ``hc``, ``bfc``, ``tfc`` from :class:`SectionProperties`.
For doubly-symmetric sections those fields resolve via the
``resolved_*`` accessors to the DS-equivalent (``Sx``, ``Iy/2``, ``hw``,
``bf``, ``tf``), so DS callers see no behavioural change vs. Phase 9a.

The four limit states evaluated (``Mn = min`` of those that apply):

* **CFY** Eq. F4-1                ``Mn = Rpc * Myc``
* **LTB** Eq. F4-2 / F4-3 / F4-5  (three regimes via Lp, Lr, Fcr)
* **CFLB** Eq. F4-13 / F4-14      (only when the compression flange is
                                  non-compact or slender)
* **TFY** Eq. F4-15               ``Mn = Rpt * Myt`` — only when
                                  ``Sxt < Sxc`` (so inactive for DS).

The web-plastification factors:

* ``Rpc`` (Eq. F4-9a/b or F4-10) governs the CFY anchor on the
  compression side.
* ``Rpt`` (Eq. F4-16a/b or F4-17) governs the TFY anchor on the
  tension side.

Both Rpc and Rpt collapse to 1.0 when ``Iyc/Iy <= 0.23`` (Eq. F4-10 /
Eq. F4-17, applicable to very singly-symmetric I-sections where the
compression flange is much smaller than the tension flange).

Backward compatibility (Phase 9a)
---------------------------------
The Phase 9a function name
``compute_flexural_strength_F4_doubly_symmetric_noncompact_web`` is
re-exported here as an alias of the unified
``compute_flexural_strength_F4`` so existing tests and callers continue
to work unchanged.

References
----------
.. [1] AISC 360-22 §F4, pp. 16.1-56 to 16.1-59.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from apeSteel.classification._common import compute_kc_for_built_up_flange
from apeSteel.classification.flexural_compactness_B4_1b import (
    classify_flexural_compactness_B4_1b,
    compute_singly_symmetric_web_lambda_pw_case16,
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


# ---------------------------------------------------------------------------
# AISC §F4 numerical constants
# ---------------------------------------------------------------------------
F4_FL_FRACTION_OF_FY_0p7: float = 0.7
F4_FCR_J_COEFFICIENT_0p078: float = 0.078
F4_LP_COEFFICIENT_1p1: float = 1.1
F4_LR_COEFFICIENT_1p95: float = 1.95
F4_LR_INSIDE_SQRT_6p76: float = 6.76
F4_RT_DENOMINATOR_COEFFICIENT_12: float = 12.0
F4_RT_AW_DIVISOR_6: float = 6.0
F4_CFLB_ELASTIC_COEFFICIENT_0p9: float = 0.9
F4_IYC_OVER_IY_THRESHOLD_0p23: float = 0.23
F4_MP_CAP_FY_SX_COEFFICIENT_1p6: float = 1.6


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class FlexureF4Report(Report):
    """AISC §F4 flexural strength: CFY + LTB + CFLB + TFY."""

    Cb_used: float = 0.0
    unbraced_length_Lb: float = 0.0
    construction: SectionConstruction = "welded"
    web_to_flange_area_ratio_aw: float = 0.0
    web_plastification_factor_Rpc: float = 0.0
    tension_flange_plastification_factor_Rpt: float = 0.0
    iyc_over_iy_ratio: float = 0.0
    F4_effective_radius_rt: float = 0.0
    limit_compression_flange_stress_FL: float = 0.0
    limiting_length_plastic_Lp_F4: float = 0.0
    limiting_length_inelastic_LTB_Lr_F4: float = 0.0
    plastic_moment_Mp: float = 0.0
    yield_moment_compression_flange_Myc: float = 0.0
    yield_moment_tension_flange_Myt: float = 0.0
    Sxc_over_Sxt_ratio: float = 0.0
    flange_classification: str = ""
    web_classification: str = ""
    nominal_CFY_moment_Mn_CFY: float = 0.0
    nominal_LTB_moment_Mn_LTB: float = 0.0
    nominal_FLB_moment_Mn_FLB: float = 0.0
    nominal_TFY_moment_Mn_TFY: float = 0.0
    governing_F4_limit_state: str = ""
    nominal_flexural_strength_Mn: float = 0.0


# ---------------------------------------------------------------------------
# Citations
# ---------------------------------------------------------------------------
_CITATIONS_F4: tuple[AISCClauseReference, ...] = (
    *CITATIONS_AISC_360_CHAPTER_F,
    AISCClauseReference("AISC 360-22", "F4", None, "16.1-56"),
    AISCClauseReference("AISC 360-22", "F4.1", "F4-1", "16.1-56"),
    AISCClauseReference("AISC 360-22", "F4.2", "F4-2", "16.1-56"),
    AISCClauseReference("AISC 360-22", "F4.2", "F4-3", "16.1-56"),
    AISCClauseReference("AISC 360-22", "F4.2", "F4-4", "16.1-56"),
    AISCClauseReference("AISC 360-22", "F4.2", "F4-5", "16.1-57"),
    AISCClauseReference("AISC 360-22", "F4.2", "F4-6a", "16.1-57"),
    AISCClauseReference("AISC 360-22", "F4.2", "F4-6b", "16.1-57"),
    AISCClauseReference("AISC 360-22", "F4.2", "F4-7", "16.1-57"),
    AISCClauseReference("AISC 360-22", "F4.2", "F4-8", "16.1-57"),
    AISCClauseReference("AISC 360-22", "F4.2", "F4-9a", "16.1-57"),
    AISCClauseReference("AISC 360-22", "F4.2", "F4-9b", "16.1-58"),
    AISCClauseReference("AISC 360-22", "F4.2", "F4-10", "16.1-58"),
    AISCClauseReference("AISC 360-22", "F4.2", "F4-11", "16.1-58"),
    AISCClauseReference("AISC 360-22", "F4.2", "F4-12", "16.1-58"),
    AISCClauseReference("AISC 360-22", "F4.3", "F4-13", "16.1-59"),
    AISCClauseReference("AISC 360-22", "F4.3", "F4-14", "16.1-59"),
    AISCClauseReference("AISC 360-22", "F4.4", "F4-15", "16.1-59"),
    AISCClauseReference("AISC 360-22", "F4.4", "F4-16a", "16.1-59"),
    AISCClauseReference("AISC 360-22", "F4.4", "F4-16b", "16.1-59"),
    AISCClauseReference("AISC 360-22", "F4.4", "F4-17", "16.1-60"),
)


# ---------------------------------------------------------------------------
# Equation-level helpers (pure, single-purpose)
# ---------------------------------------------------------------------------
def compute_aw_for_F4(
    web_clear_height_hc: float,
    web_thickness_tw: float,
    compression_flange_width_bfc: float,
    compression_flange_thickness_tfc: float,
) -> float:
    """AISC Eq. F4-12: aw = hc*tw / (bfc*tfc)."""
    return (web_clear_height_hc * web_thickness_tw) / (
        compression_flange_width_bfc * compression_flange_thickness_tfc
    )


def compute_rt_for_F4(
    compression_flange_width_bfc: float,
    web_to_flange_area_ratio_aw: float,
) -> float:
    """AISC Eq. F4-11: rt = bfc / sqrt(12*(1 + aw/6))."""
    inside_sqrt = F4_RT_DENOMINATOR_COEFFICIENT_12 * (
        1.0 + web_to_flange_area_ratio_aw / F4_RT_AW_DIVISOR_6
    )
    return compression_flange_width_bfc / math.sqrt(inside_sqrt)


def compute_web_plastification_factor_Rpc(
    plastic_moment_Mp: float,
    yield_moment_compression_flange_Myc: float,
    web_slenderness_ratio_lambda: float,
    web_compact_limit_lambda_pw: float,
    web_noncompact_limit_lambda_rw: float,
    iyc_over_iy_ratio: float,
) -> float:
    """AISC Eq. F4-9a / F4-9b / F4-10."""
    if iyc_over_iy_ratio <= F4_IYC_OVER_IY_THRESHOLD_0p23:
        return 1.0  # Eq. F4-10
    mp_over_myc = plastic_moment_Mp / yield_moment_compression_flange_Myc
    if web_slenderness_ratio_lambda <= web_compact_limit_lambda_pw:
        return mp_over_myc  # Eq. F4-9a
    fraction = (web_slenderness_ratio_lambda - web_compact_limit_lambda_pw) / (
        web_noncompact_limit_lambda_rw - web_compact_limit_lambda_pw
    )
    Rpc_interp = mp_over_myc - (mp_over_myc - 1.0) * fraction
    return min(Rpc_interp, mp_over_myc)


def compute_tension_flange_plastification_factor_Rpt(
    plastic_moment_Mp: float,
    yield_moment_tension_flange_Myt: float,
    web_slenderness_ratio_lambda: float,
    web_compact_limit_lambda_pw: float,
    web_noncompact_limit_lambda_rw: float,
    iyc_over_iy_ratio: float,
) -> float:
    """AISC Eq. F4-16a / F4-16b / F4-17.

    Tension-flange counterpart to Rpc, used in the F4-15 TFY limit state.
    Same form as Rpc but referenced to ``Myt = Fy * Sxt`` instead of
    ``Myc``.
    """
    if iyc_over_iy_ratio <= F4_IYC_OVER_IY_THRESHOLD_0p23:
        return 1.0  # Eq. F4-17
    mp_over_myt = plastic_moment_Mp / yield_moment_tension_flange_Myt
    if web_slenderness_ratio_lambda <= web_compact_limit_lambda_pw:
        return mp_over_myt  # Eq. F4-16a
    fraction = (web_slenderness_ratio_lambda - web_compact_limit_lambda_pw) / (
        web_noncompact_limit_lambda_rw - web_compact_limit_lambda_pw
    )
    Rpt_interp = mp_over_myt - (mp_over_myt - 1.0) * fraction
    return min(Rpt_interp, mp_over_myt)


def compute_FL_for_F4(
    yield_stress_Fy: float,
    elastic_section_modulus_tension_flange_Sxt: float,
    elastic_section_modulus_compression_flange_Sxc: float,
) -> float:
    """AISC Eq. F4-6a / F4-6b."""
    ratio = (
        elastic_section_modulus_tension_flange_Sxt / elastic_section_modulus_compression_flange_Sxc
    )
    if ratio >= F4_FL_FRACTION_OF_FY_0p7:
        return F4_FL_FRACTION_OF_FY_0p7 * yield_stress_Fy
    FL_raw = yield_stress_Fy * ratio
    FL_floor = 0.5 * yield_stress_Fy
    return max(FL_raw, FL_floor)


def compute_Lp_for_F4(
    effective_radius_rt: float,
    elastic_modulus_E: float,
    yield_stress_Fy: float,
) -> float:
    """AISC Eq. F4-7."""
    return (
        F4_LP_COEFFICIENT_1p1 * effective_radius_rt * math.sqrt(elastic_modulus_E / yield_stress_Fy)
    )


def compute_Lr_for_F4(
    effective_radius_rt: float,
    elastic_modulus_E: float,
    limit_stress_FL: float,
    torsional_constant_J: float,
    elastic_section_modulus_compression_flange_Sxc: float,
    distance_between_flange_centroids_ho: float,
) -> float:
    """AISC Eq. F4-8."""
    J_term = torsional_constant_J / (
        elastic_section_modulus_compression_flange_Sxc * distance_between_flange_centroids_ho
    )
    inner_sqrt = math.sqrt(
        J_term**2 + F4_LR_INSIDE_SQRT_6p76 * (limit_stress_FL / elastic_modulus_E) ** 2
    )
    return (
        F4_LR_COEFFICIENT_1p95
        * effective_radius_rt
        * (elastic_modulus_E / limit_stress_FL)
        * math.sqrt(J_term + inner_sqrt)
    )


def compute_Fcr_for_F4(
    lateral_torsional_buckling_modification_factor_Cb: float,
    unbraced_length_Lb: float,
    effective_radius_rt: float,
    elastic_modulus_E: float,
    torsional_constant_J: float,
    elastic_section_modulus_compression_flange_Sxc: float,
    distance_between_flange_centroids_ho: float,
) -> float:
    """AISC Eq. F4-5.

    Note: per F4-5, when Iyc/Iy <= 0.23 the caller must pass J=0.
    """
    Cb = lateral_torsional_buckling_modification_factor_Cb
    Lb_rt_squared = (unbraced_length_Lb / effective_radius_rt) ** 2
    J_factor = (
        F4_FCR_J_COEFFICIENT_0p078
        * torsional_constant_J
        / (elastic_section_modulus_compression_flange_Sxc * distance_between_flange_centroids_ho)
    )
    return (
        Cb
        * math.pi**2
        * elastic_modulus_E
        / Lb_rt_squared
        * math.sqrt(1.0 + J_factor * Lb_rt_squared)
    )


def compute_inelastic_LTB_moment_Mn_F4_2(
    plastic_anchor_moment_Rpc_times_Myc: float,
    limit_anchor_moment_FL_times_Sxc: float,
    unbraced_length_Lb: float,
    limiting_length_plastic_Lp: float,
    limiting_length_inelastic_LTB_Lr: float,
    lateral_torsional_buckling_modification_factor_Cb: float,
) -> float:
    """AISC Eq. F4-2."""
    fraction = (unbraced_length_Lb - limiting_length_plastic_Lp) / (
        limiting_length_inelastic_LTB_Lr - limiting_length_plastic_Lp
    )
    raw = lateral_torsional_buckling_modification_factor_Cb * (
        plastic_anchor_moment_Rpc_times_Myc
        - (plastic_anchor_moment_Rpc_times_Myc - limit_anchor_moment_FL_times_Sxc) * fraction
    )
    return min(raw, plastic_anchor_moment_Rpc_times_Myc)


def compute_compression_flange_local_buckling_moment_Mn_F4_13(
    plastic_anchor_moment_Rpc_times_Myc: float,
    limit_anchor_moment_FL_times_Sxc: float,
    flange_slenderness_ratio_lambda_f: float,
    flange_compact_limit_lambda_pf: float,
    flange_noncompact_limit_lambda_rf: float,
) -> float:
    """AISC Eq. F4-13."""
    fraction = (flange_slenderness_ratio_lambda_f - flange_compact_limit_lambda_pf) / (
        flange_noncompact_limit_lambda_rf - flange_compact_limit_lambda_pf
    )
    return (
        plastic_anchor_moment_Rpc_times_Myc
        - (plastic_anchor_moment_Rpc_times_Myc - limit_anchor_moment_FL_times_Sxc) * fraction
    )


def compute_compression_flange_local_buckling_moment_Mn_F4_14(
    elastic_section_modulus_compression_flange_Sxc: float,
    elastic_modulus_E: float,
    flange_plate_buckling_coefficient_kc: float,
    flange_slenderness_ratio_lambda_f: float,
) -> float:
    """AISC Eq. F4-14."""
    return (
        F4_CFLB_ELASTIC_COEFFICIENT_0p9
        * elastic_modulus_E
        * flange_plate_buckling_coefficient_kc
        * elastic_section_modulus_compression_flange_Sxc
        / (flange_slenderness_ratio_lambda_f**2)
    )


# ---------------------------------------------------------------------------
# Public facade
# ---------------------------------------------------------------------------
def compute_flexural_strength_F4(  # noqa: PLR0912, PLR0915
    section_properties: SectionProperties,
    material: SteelMaterial,
    unbraced_length_Lb: float,
    lateral_torsional_buckling_modification_factor_Cb: float,
    construction: SectionConstruction = "welded",
) -> FlexureF4Report:
    """Return Mn per AISC §F4 for a doubly- or singly-symmetric I-section.

    The caller passes a :class:`SectionProperties` populated with the
    appropriate ``Sxc / Sxt / Iyc / hc / bfc / tfc`` values for the
    bending direction being checked.  For doubly-symmetric sections the
    SS-specific fields can be left at their sentinel ``0.0``; the
    ``resolved_*`` accessors fall back to the DS equivalents.

    Parameters
    ----------
    section_properties : SectionProperties
    material : SteelMaterial
        Only Fy and E are read.
    unbraced_length_Lb : float
        Distance between lateral braces of the compression flange (mm).
    lateral_torsional_buckling_modification_factor_Cb : float
    construction : {"rolled", "welded"}

    Returns
    -------
    FlexureF4Report

    Raises
    ------
    ValueError
        If ``unbraced_length_Lb <= 0``.
    """
    if unbraced_length_Lb <= 0.0:
        raise ValueError(f"unbraced_length_Lb must be positive, got {unbraced_length_Lb!r}")

    Fy: float = material.yield_stress_Fy
    E: float = material.elastic_modulus_E
    # Lift the shipped I-only currency into the generalized Chapter-F
    # model.  ``from_legacy`` copies the strength geometry verbatim
    # (Zx/Sx/J/ho copied directly; Sxc/Sxt via the *same*
    # ``resolved_*`` accessors §F4 used) so every §F4 limit-state number
    # is bit-identical.  The B4.1b *classification* inputs
    # (``lambda_w``/``lambda_f``/``hc``/``hp``/``iyc_over_iy`` + the
    # classifier and the Case-16 ``lambda_pw`` call) deliberately keep
    # reading ``section_properties`` exactly as shipped - the
    # conservative classification path mandated by design note 10 §F-1
    # (zero classification-number movement on the externally-anchored
    # path).  §F4 covers DS NC-web and SS I (web at flange mid-width):
    # ``c`` (Eq. F2-8a/8b) is not used by §F4 (it has its own rt/Lr).
    # SS iff the geometry populated the plastic-zone depth hp (DS leaves
    # it at the 0.0 sentinel) - the identical discriminator the shipped
    # Case-16 branch below uses.  ``kind``/``symmetry`` do not influence
    # any lifted numeric field (only ``c`` is kind-dependent, and §F4
    # never reads ``c``); they are passed for call-site parity.
    _is_ss: bool = section_properties.plastic_neutral_axis_depth_hp > 0.0
    fsp_kind: FlexuralSectionKind = "singly_symmetric_I" if _is_ss else "doubly_symmetric_I"
    fsp_symmetry: SectionSymmetry = "singly_symmetric" if _is_ss else "doubly_symmetric"
    fsp: FlexuralSectionProperties = FlexuralSectionProperties.from_legacy(
        section_properties,
        kind=fsp_kind,
        symmetry=fsp_symmetry,
        construction=construction,
    )
    Zx: float = fsp.plastic_modulus_Zx
    Sx: float = fsp.elastic_modulus_Sx
    tw: float = section_properties.web_thickness_tw
    J: float = fsp.torsional_constant_J
    ho: float = fsp.distance_between_flange_centroids_ho
    lambda_w: float = section_properties.web_height_to_thickness_ratio_h_tw
    lambda_f: float = section_properties.flange_width_to_thickness_ratio_bf_2tf
    Cb: float = lateral_torsional_buckling_modification_factor_Cb

    # Resolved (SS-aware) compression-side geometry.  bfc/tfc are not
    # carried on the generalized model (it stores Sxc/Sxt/Iyc/hc, not
    # the raw flange plate dims), so they stay on the resolver; Sxc/Sxt
    # come from ``fsp`` where ``from_legacy`` lifted them through the
    # identical ``resolved_Sxc()/resolved_Sxt()`` calls -> bit-identical.
    bfc: float = section_properties.resolved_compression_flange_width_bfc()
    tfc: float = section_properties.resolved_compression_flange_thickness_tfc()
    Sxc: float = fsp.elastic_modulus_compression_flange_Sxc
    Sxt: float = fsp.elastic_modulus_tension_flange_Sxt
    iyc_over_iy: float = section_properties.resolved_iyc_over_iy()
    hc: float = section_properties.resolved_hc()

    # --- Mp, with 1.6*Fy*Sx cap (Sect. F4.2 "Mp" definition) ---
    Mp_raw: float = compute_plastic_moment_Mp(Fy, Zx)
    Mp: float = min(Mp_raw, F4_MP_CAP_FY_SX_COEFFICIENT_1p6 * Fy * Sx)
    Myc: float = Fy * Sxc
    Myt: float = Fy * Sxt

    # --- aw, rt ---
    aw = compute_aw_for_F4(
        web_clear_height_hc=hc,
        web_thickness_tw=tw,
        compression_flange_width_bfc=bfc,
        compression_flange_thickness_tfc=tfc,
    )
    rt = compute_rt_for_F4(
        compression_flange_width_bfc=bfc,
        web_to_flange_area_ratio_aw=aw,
    )

    # --- Classification (for Rpc/Rpt inputs and CFLB regime) ---
    flex_class_report = classify_flexural_compactness_B4_1b(
        section_properties,
        material,
        construction,
    )
    lambda_pw_opt = flex_class_report.web.compact_limit_lambda_p
    if lambda_pw_opt is None:  # defensive
        raise ValueError("flexural classifier did not return lambda_p for web")
    lambda_pw: float = lambda_pw_opt
    lambda_rw: float = flex_class_report.web.noncompact_limit_lambda_r
    web_class = flex_class_report.web.classification

    # AISC 360-22 Table B4.1b: doubly-symmetric webs use Case 15
    # (lambda_pw = 3.76 sqrt(E/Fy), what the classifier returned);
    # singly-symmetric webs must use Case 16, which depends on hc/hp
    # and Mp/My.  A singly-symmetric section is the one whose geometry
    # populated the plastic-zone depth hp (DS leaves it at the 0.0
    # sentinel).  lambda_rw is identical for Cases 15 and 16
    # (5.70 sqrt(E/Fy)), so the F4-vs-F5 slender boundary is unchanged;
    # only lambda_pw (the Rpc/Rpt interpolation anchor) differs.
    if section_properties.plastic_neutral_axis_depth_hp > 0.0:
        lambda_pw = compute_singly_symmetric_web_lambda_pw_case16(
            web_compression_depth_hc=hc,
            web_plastic_depth_hp=section_properties.resolved_hp(),
            plastic_moment_Mp=Mp,
            yield_moment_My=Myc,
            elastic_modulus_E=E,
            yield_stress_Fy=Fy,
        )
        if lambda_w <= lambda_pw:
            web_class = "compact"
        elif lambda_w <= lambda_rw:
            web_class = "non_compact"
        else:
            web_class = "slender"

    flange_class = flex_class_report.flange.classification
    lambda_pf_opt = flex_class_report.flange.compact_limit_lambda_p
    if lambda_pf_opt is None:
        raise ValueError("flexural classifier did not return lambda_p for flange")
    lambda_pf: float = lambda_pf_opt
    lambda_rf: float = flex_class_report.flange.noncompact_limit_lambda_r

    # --- Rpc, Rpt, FL ---
    Rpc = compute_web_plastification_factor_Rpc(
        plastic_moment_Mp=Mp,
        yield_moment_compression_flange_Myc=Myc,
        web_slenderness_ratio_lambda=lambda_w,
        web_compact_limit_lambda_pw=lambda_pw,
        web_noncompact_limit_lambda_rw=lambda_rw,
        iyc_over_iy_ratio=iyc_over_iy,
    )
    Rpt = compute_tension_flange_plastification_factor_Rpt(
        plastic_moment_Mp=Mp,
        yield_moment_tension_flange_Myt=Myt,
        web_slenderness_ratio_lambda=lambda_w,
        web_compact_limit_lambda_pw=lambda_pw,
        web_noncompact_limit_lambda_rw=lambda_rw,
        iyc_over_iy_ratio=iyc_over_iy,
    )
    FL = compute_FL_for_F4(
        yield_stress_Fy=Fy,
        elastic_section_modulus_tension_flange_Sxt=Sxt,
        elastic_section_modulus_compression_flange_Sxc=Sxc,
    )

    # --- Anchor moments used by F4-2 / F4-13 / F4-15 ---
    Rpc_Myc: float = Rpc * Myc
    FL_Sxc: float = FL * Sxc

    # --- Lp, Lr ---
    Lp = compute_Lp_for_F4(rt, E, Fy)
    Lr = compute_Lr_for_F4(
        effective_radius_rt=rt,
        elastic_modulus_E=E,
        limit_stress_FL=FL,
        torsional_constant_J=J,
        elastic_section_modulus_compression_flange_Sxc=Sxc,
        distance_between_flange_centroids_ho=ho,
    )

    # --- CFY (F4-1) ---
    Mn_CFY: float = Rpc_Myc

    # --- LTB (F4-2 / F4-3) ---
    # Per F4-5 note, when Iyc/Iy <= 0.23, J shall be taken as zero in Fcr.
    J_for_Fcr = 0.0 if iyc_over_iy <= F4_IYC_OVER_IY_THRESHOLD_0p23 else J
    Lb = unbraced_length_Lb
    ltb_regime: FlexuralLimitState
    if Lb <= Lp:
        Mn_LTB: float = Rpc_Myc  # LTB does not govern; CFY caps
        ltb_regime = "yielding"
    elif Lb <= Lr:
        Mn_LTB = compute_inelastic_LTB_moment_Mn_F4_2(
            plastic_anchor_moment_Rpc_times_Myc=Rpc_Myc,
            limit_anchor_moment_FL_times_Sxc=FL_Sxc,
            unbraced_length_Lb=Lb,
            limiting_length_plastic_Lp=Lp,
            limiting_length_inelastic_LTB_Lr=Lr,
            lateral_torsional_buckling_modification_factor_Cb=Cb,
        )
        ltb_regime = "inelastic_LTB"
    else:
        Fcr = compute_Fcr_for_F4(
            lateral_torsional_buckling_modification_factor_Cb=Cb,
            unbraced_length_Lb=Lb,
            effective_radius_rt=rt,
            elastic_modulus_E=E,
            torsional_constant_J=J_for_Fcr,
            elastic_section_modulus_compression_flange_Sxc=Sxc,
            distance_between_flange_centroids_ho=ho,
        )
        Mn_LTB = min(Fcr * Sxc, Rpc_Myc)
        ltb_regime = "elastic_LTB"

    # --- CFLB (F4-13 / F4-14) ---
    if flange_class == "compact":
        Mn_FLB: float = Rpc_Myc
    elif flange_class == "non_compact":
        Mn_FLB = compute_compression_flange_local_buckling_moment_Mn_F4_13(
            plastic_anchor_moment_Rpc_times_Myc=Rpc_Myc,
            limit_anchor_moment_FL_times_Sxc=FL_Sxc,
            flange_slenderness_ratio_lambda_f=lambda_f,
            flange_compact_limit_lambda_pf=lambda_pf,
            flange_noncompact_limit_lambda_rf=lambda_rf,
        )
    else:  # slender
        kc = compute_kc_for_built_up_flange(lambda_w)
        Mn_FLB = compute_compression_flange_local_buckling_moment_Mn_F4_14(
            elastic_section_modulus_compression_flange_Sxc=Sxc,
            elastic_modulus_E=E,
            flange_plate_buckling_coefficient_kc=kc,
            flange_slenderness_ratio_lambda_f=lambda_f,
        )

    # --- TFY (F4-15) - only active when Sxt < Sxc ---
    if Sxt < Sxc:
        Mn_TFY: float = Rpt * Myt
        tfy_active = True
    else:
        Mn_TFY = Rpc_Myc  # sentinel "inactive" value (won't govern)
        tfy_active = False

    # --- Final Mn = min over active limit states ---
    candidates: dict[str, float] = {
        "compression_flange_yielding": Mn_CFY,
        "lateral_torsional_buckling": Mn_LTB,
        "flange_local_buckling": Mn_FLB,
    }
    if tfy_active:
        candidates["tension_flange_yielding"] = Mn_TFY

    governing = min(candidates, key=lambda k: candidates[k])
    Mn: float = candidates[governing]

    governing_limit_state: FlexuralLimitState
    if governing == "lateral_torsional_buckling":
        governing_limit_state = ltb_regime
    elif governing == "flange_local_buckling":
        governing_limit_state = "flange_local_buckling"
    elif governing == "tension_flange_yielding":
        governing_limit_state = "tension_flange_yielding"
    else:
        governing_limit_state = "compression_flange_yielding"

    Sxc_over_Sxt = Sxc / Sxt if Sxt > 0 else 0.0

    return FlexureF4Report(
        cited_clauses=_CITATIONS_F4,
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
        web_plastification_factor_Rpc=Rpc,
        tension_flange_plastification_factor_Rpt=Rpt,
        iyc_over_iy_ratio=iyc_over_iy,
        F4_effective_radius_rt=rt,
        limit_compression_flange_stress_FL=FL,
        limiting_length_plastic_Lp_F4=Lp,
        limiting_length_inelastic_LTB_Lr_F4=Lr,
        plastic_moment_Mp=Mp,
        yield_moment_compression_flange_Myc=Myc,
        yield_moment_tension_flange_Myt=Myt,
        Sxc_over_Sxt_ratio=Sxc_over_Sxt,
        flange_classification=flange_class,
        web_classification=web_class,
        nominal_CFY_moment_Mn_CFY=Mn_CFY,
        nominal_LTB_moment_Mn_LTB=Mn_LTB,
        nominal_FLB_moment_Mn_FLB=Mn_FLB,
        nominal_TFY_moment_Mn_TFY=Mn_TFY,
        governing_F4_limit_state=governing,
        nominal_flexural_strength_Mn=Mn,
    )


#: Backward-compatible alias for the Phase 9a public name.  The current
#: implementation handles both doubly- and singly-symmetric I-sections,
#: but Phase 9a callers (and the Phase 9a golden CSV) wrote against the
#: doubly-symmetric-specific name; keep the alias so they continue to
#: work without modification.
compute_flexural_strength_F4_doubly_symmetric_noncompact_web = compute_flexural_strength_F4


__all__ = [
    "F4_RT_AW_DIVISOR_6",
    "F4_RT_DENOMINATOR_COEFFICIENT_12",
    "F4_CFLB_ELASTIC_COEFFICIENT_0p9",
    "F4_FCR_J_COEFFICIENT_0p078",
    "F4_FL_FRACTION_OF_FY_0p7",
    "F4_IYC_OVER_IY_THRESHOLD_0p23",
    "F4_LP_COEFFICIENT_1p1",
    "F4_LR_COEFFICIENT_1p95",
    "F4_LR_INSIDE_SQRT_6p76",
    "F4_MP_CAP_FY_SX_COEFFICIENT_1p6",
    "FlexureF4Report",
    "compute_FL_for_F4",
    "compute_Fcr_for_F4",
    "compute_Lp_for_F4",
    "compute_Lr_for_F4",
    "compute_aw_for_F4",
    "compute_compression_flange_local_buckling_moment_Mn_F4_13",
    "compute_compression_flange_local_buckling_moment_Mn_F4_14",
    "compute_flexural_strength_F4",
    "compute_flexural_strength_F4_doubly_symmetric_noncompact_web",
    "compute_inelastic_LTB_moment_Mn_F4_2",
    "compute_rt_for_F4",
    "compute_tension_flange_plastification_factor_Rpt",
    "compute_web_plastification_factor_Rpc",
]
