"""AISC 360-22 Table B4.1b - generalized flexural classification.

This is the *generalized* Chapter-F plate-element classifier. It
dispatches Table B4.1b by :data:`FlexuralSectionKind` and emits a
:class:`FlexuralPlateElement` list covering every case §F2-§F12 needs:

* I / channel flange (rolled Case 10 / welded Case 11) + web
  (doubly-symmetric Case 15 / singly-symmetric Case 16);
* square / rectangular HSS flange and web in flexure;
* round HSS ``D/t`` (Case 20, confirmed from AISC Manual v15.1
  Ex. F.9B);
* tee stem and single / double-angle leg (their slenderness limits are
  defined in §F9.4 / §F10.3 directly, not in a B4.1b row);
* rectangular / round bars (no local-buckling limit state - §F11);
* unsymmetric shapes (§F12 is elastic - classification is
  informational).

Provenance: the λ_p / λ_r *forms* and *coefficients* come from
``docs/design_notes/_chapterF_citation_reference.md`` Part 2 (curated
from the ``aisc-steel-design`` skill reference and cross-checked against
the staged spec body text). Table B4.1b *case numbers* that could not be
verified from the staged spec extract are emitted as ``"B4.1b Case ?"``
and tracked in that file's ENGINEER-CONFIRM section; the numeric limits
do not depend on the label and the independent oracle re-derives every
limit numerically.

**Back-compatibility.** The shipped, I-only
:func:`apeSteel.classification.classify_flexural_compactness_B4_1b` and
:func:`~apeSteel.classification.compute_singly_symmetric_web_lambda_pw_case16`
are *not* touched by this module - they remain importable and
bit-identical (this module is purely additive; F2-F5 keep using the
shipped function until Phase F-1). The λ coefficients here are
re-declared as named constants rather than imported so a typo in either
implementation surfaces as a test disagreement.

References
----------
.. [1] AISC 360-22, "Specification for Structural Steel Buildings",
       Table B4.1b and Chapter F, pp. 16.1-15 - 16.1-16, 16.1-53 -
       16.1-74. American Institute of Steel Construction, 2022.
.. [2] docs/design_notes/_chapterF_citation_reference.md - Chapter-F
       citation source-of-truth (equation/case provenance).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from apeSteel.classification._common import (
    SectionConstruction,
    compute_kc_for_built_up_flange,
)
from apeSteel.core.result_types import AISCClauseReference, Report
from apeSteel.sections.flexural_properties import (
    FlexuralPlateElement,
    FlexuralSectionKind,
)

if TYPE_CHECKING:
    from apeSteel.core.materials import SteelMaterial
    from apeSteel.sections.flexural_properties import FlexuralPlateClass

# ---------------------------------------------------------------------------
# Constants - AISC 360-22 Table B4.1b flexure coefficients
# (provenance: _chapterF_citation_reference.md Part 2)
# ---------------------------------------------------------------------------
# I / channel flange, flexure. Case 10 (rolled) and Case 11 (welded)
# share lambda_p = 0.38 sqrt(E/Fy). Case 10 lambda_r = 1.0 sqrt(E/Fy);
# Case 11 lambda_r = 0.95 sqrt(kc E / FL), FL = 0.7 Fy (DS major axis).
B4_1B_I_FLANGE_COMPACT_COEFF: float = 0.38
B4_1B_ROLLED_I_FLANGE_NONCOMPACT_COEFF: float = 1.00  # Case 10
B4_1B_WELDED_I_FLANGE_NONCOMPACT_COEFF: float = 0.95  # Case 11
B4_1B_WELDED_I_FLANGE_FL_FRACTION_OF_FY: float = 0.7  # FL = 0.7 Fy (Eq. F4-6a)

# I / channel web, flexure. Case 15 (doubly-symmetric):
# lambda_pw = 3.76 sqrt(E/Fy), lambda_rw = 5.70 sqrt(E/Fy).
B4_1B_WEB_COMPACT_COEFF: float = 3.76  # Case 15
B4_1B_WEB_NONCOMPACT_COEFF: float = 5.70  # Case 15 / Case 16 lambda_rw

# Case 16 (singly-symmetric I web): lambda_pw = (hc/hp) sqrt(E/Fy)
# / (0.54 Mp/My - 0.09)^2  <=  lambda_rw.
B4_1B_CASE16_MP_MY_COEFF: float = 0.54
B4_1B_CASE16_MP_MY_OFFSET: float = 0.09

# Square / rectangular HSS flange in flexure (B4.1b case ENGINEER-CONFIRM
# EC-1, conventionally Case 17): lambda_p = 1.12 sqrt(E/Fy),
# lambda_r = 1.40 sqrt(E/Fy).
B4_1B_HSS_FLANGE_COMPACT_COEFF: float = 1.12
B4_1B_HSS_FLANGE_NONCOMPACT_COEFF: float = 1.40

# Square / rectangular HSS web in flexure (B4.1b case ENGINEER-CONFIRM
# EC-2, conventionally Case 19): lambda_p = 2.42 sqrt(E/Fy),
# lambda_r = 5.70 sqrt(E/Fy).
B4_1B_HSS_WEB_COMPACT_COEFF: float = 2.42
B4_1B_HSS_WEB_NONCOMPACT_COEFF: float = 5.70

# Round HSS in flexure, Case 20 (CONFIRMED - AISC Manual v15.1 Ex. F.9B
# text, _chapterF_citation_reference.md EC-3): lambda_p = 0.07 E/Fy,
# lambda_r = 0.31 E/Fy. (Note: ratio of E/Fy, not sqrt.)
B4_1B_ROUND_HSS_COMPACT_COEFF: float = 0.07  # Case 20
B4_1B_ROUND_HSS_NONCOMPACT_COEFF: float = 0.31  # Case 20

# Tee stem in flexural compression: §F9.4 supplies the Fcr breakpoints
# directly (Eq. F9-17/18/19, spec_chapterF.txt 16.1-67/68). The
# compact/noncompact stem boundaries are d/tw = 0.84 sqrt(E/Fy) and
# 1.52 sqrt(E/Fy). (B4.1b case ENGINEER-CONFIRM EC-5.)
F9_4_TEE_STEM_COMPACT_COEFF: float = 0.84  # Eq. F9-17 boundary
F9_4_TEE_STEM_NONCOMPACT_COEFF: float = 1.52  # Eq. F9-19 boundary

# Single / double-angle leg in flexural compression: §F10.3 supplies the
# b/t breakpoints. The slender form (Fcr, Eq. F10-8) is confirmed from
# spec_chapterF.txt 16.1-70; the compact/noncompact numeric limits
# 0.54 / 0.91 sqrt(E/Fy) are on the absent printed 16.1-69
# (ENGINEER-CONFIRM EC-10) - curated, oracle-re-derived.
F10_3_ANGLE_LEG_COMPACT_COEFF: float = 0.54
F10_3_ANGLE_LEG_NONCOMPACT_COEFF: float = 0.91

# Table B4.1b note [c]: kc = 4/sqrt(h/tw), 0.35 <= kc <= 0.76. Provided
# by the shared classification helper compute_kc_for_built_up_flange.


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class GeneralizedFlexuralCompactnessReport(Report):
    """Per-element flexural classification per AISC 360 Table B4.1b.

    Attributes
    ----------
    section_kind : FlexuralSectionKind
        Echo of the classified section family.
    plate_elements : tuple[FlexuralPlateElement, ...]
        One record per plate element, each carrying its
        ``slenderness_ratio_lambda``, Table B4.1b ``lambda_p`` /
        ``lambda_r``, the B4.1b case label, and a derived
        ``classification`` property.
    section_classification : FlexuralPlateClass
        Worst (least-favourable) of all element classifications, or
        ``"compact"`` when there are no plate elements (bars). Drives
        the §F local-buckling routing.
    construction : SectionConstruction
        Echo of the input construction (``"rolled"`` / ``"welded"``);
        only affects the I/channel flange case.
    """

    section_kind: FlexuralSectionKind = "doubly_symmetric_I"
    plate_elements: tuple[FlexuralPlateElement, ...] = ()
    section_classification: FlexuralPlateClass = "compact"
    construction: SectionConstruction = "welded"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
# Note: the per-element compact / non-compact / slender decision is *not*
# re-implemented here. It lives once, on
# :attr:`FlexuralPlateElement.classification` (the sole source of truth);
# this module only constructs the elements and rolls them up via
# :func:`_worst`, which reads that property. A standalone ``_classify``
# helper would duplicate that decision (drift risk) and was therefore
# removed rather than silenced.


def _worst(elements: tuple[FlexuralPlateElement, ...]) -> FlexuralPlateClass:
    """Worst (least-favourable) class over a plate-element tuple."""
    rank: dict[FlexuralPlateClass, int] = {
        "compact": 0,
        "non_compact": 1,
        "slender": 2,
    }
    worst: FlexuralPlateClass = "compact"
    for element in elements:
        if rank[element.classification] > rank[worst]:
            worst = element.classification
    return worst


def _i_channel_flange_limits(
    sqrt_E_over_Fy: float,
    *,
    construction: SectionConstruction,
    web_height_to_thickness_ratio_h_tw: float,
    elastic_modulus_E: float,
    yield_stress_Fy: float,
) -> tuple[float, float, str]:
    """Return ``(lambda_pf, lambda_rf, case_label)`` for an I/channel flange.

    Case 10 (rolled) or Case 11 (welded built-up, with the ``kc``
    factor). ``lambda_pf = 0.38 sqrt(E/Fy)`` in both. See
    ``_chapterF_citation_reference.md`` Part 2.
    """
    lambda_pf = B4_1B_I_FLANGE_COMPACT_COEFF * sqrt_E_over_Fy
    if construction == "rolled":
        lambda_rf = B4_1B_ROLLED_I_FLANGE_NONCOMPACT_COEFF * sqrt_E_over_Fy
        return lambda_pf, lambda_rf, "B4.1b Case 10"
    if construction == "welded":
        kc = compute_kc_for_built_up_flange(web_height_to_thickness_ratio_h_tw)
        FL = B4_1B_WELDED_I_FLANGE_FL_FRACTION_OF_FY * yield_stress_Fy
        lambda_rf = B4_1B_WELDED_I_FLANGE_NONCOMPACT_COEFF * math.sqrt(kc * elastic_modulus_E / FL)
        return lambda_pf, lambda_rf, "B4.1b Case 11"
    raise ValueError(f"unknown construction {construction!r}")  # pragma: no cover


def _ds_web_limits(sqrt_E_over_Fy: float) -> tuple[float, float]:
    """Return ``(lambda_pw, lambda_rw)`` for a doubly-symmetric I/channel web.

    Table B4.1b Case 15: ``3.76 sqrt(E/Fy)`` / ``5.70 sqrt(E/Fy)``.
    """
    return (
        B4_1B_WEB_COMPACT_COEFF * sqrt_E_over_Fy,
        B4_1B_WEB_NONCOMPACT_COEFF * sqrt_E_over_Fy,
    )


def compute_singly_symmetric_web_lambda_pw_case16(
    web_compression_depth_hc: float,
    web_plastic_depth_hp: float,
    plastic_moment_Mp: float,
    yield_moment_My: float,
    elastic_modulus_E: float,
    yield_stress_Fy: float,
) -> float:
    """Return the §B4.1b **Case 16** web compact limit ``lambda_pw``.

    Singly-symmetric I-shaped members in flexure (AISC 360-22
    Table B4.1b, Case 16)::

        lambda_pw = ( (hc/hp) sqrt(E/Fy) )
                    / (0.54 Mp/My - 0.09)^2     <=  lambda_rw

    with ``lambda_rw = 5.70 sqrt(E/Fy)`` (same as Case 15). This is an
    independent re-derivation kept *separate* from the shipped
    :func:`apeSteel.classification.compute_singly_symmetric_web_lambda_pw_case16`
    (same formula, deliberately not shared, so a typo surfaces as a test
    disagreement).

    Parameters
    ----------
    web_compression_depth_hc : float
        ``hc`` (mm).
    web_plastic_depth_hp : float
        ``hp`` (mm), must be > 0.
    plastic_moment_Mp : float
        ``Mp = Fy Zx`` (N*mm).
    yield_moment_My : float
        ``My = Fy Sxc`` to the compression flange (N*mm), must be > 0.
    elastic_modulus_E, yield_stress_Fy : float
        ``E``, ``Fy`` (MPa).

    Returns
    -------
    float
        ``lambda_pw`` per Case 16, capped at ``lambda_rw``.

    Raises
    ------
    ValueError
        If ``hp <= 0`` or ``My <= 0`` (degenerate geometry).
    """
    if web_plastic_depth_hp <= 0.0:
        raise ValueError(f"web_plastic_depth_hp must be positive, got {web_plastic_depth_hp!r}")
    if yield_moment_My <= 0.0:
        raise ValueError(f"yield_moment_My must be positive, got {yield_moment_My!r}")
    sqrt_E_over_Fy = math.sqrt(elastic_modulus_E / yield_stress_Fy)
    lambda_rw = B4_1B_WEB_NONCOMPACT_COEFF * sqrt_E_over_Fy
    denominator = (
        B4_1B_CASE16_MP_MY_COEFF * (plastic_moment_Mp / yield_moment_My) - B4_1B_CASE16_MP_MY_OFFSET
    )
    if denominator <= 0.0:
        return lambda_rw
    lambda_pw = (
        (web_compression_depth_hc / web_plastic_depth_hp) * sqrt_E_over_Fy
    ) / denominator**2
    return min(lambda_pw, lambda_rw)


# ---------------------------------------------------------------------------
# Per-kind plate-element builders
# ---------------------------------------------------------------------------
# Each builder turns the slenderness ratios relevant to one
# :data:`FlexuralSectionKind` family into the ``FlexuralPlateElement``
# list for that family. Extracting them keeps the public dispatcher a
# flat table (one branch per family) instead of one mega-function.


def _elements_i_channel(
    s: float,
    *,
    section_kind: FlexuralSectionKind,
    construction: SectionConstruction,
    elastic_modulus_E: float,
    yield_stress_Fy: float,
    flange_slenderness_bf_2tf: float | None,
    web_slenderness_h_tw: float | None,
    web_compression_depth_hc: float,
    web_plastic_depth_hp: float,
    plastic_moment_Mp: float,
    yield_moment_My: float,
) -> list[FlexuralPlateElement]:
    """I / channel: flange Case 10/11, web Case 15 (or Case 16 for SS)."""
    if flange_slenderness_bf_2tf is None or web_slenderness_h_tw is None:
        msg = f"{section_kind!r} requires flange_slenderness_bf_2tf and web_slenderness_h_tw"
        raise ValueError(msg)
    lambda_pf, lambda_rf, flange_case = _i_channel_flange_limits(
        s,
        construction=construction,
        web_height_to_thickness_ratio_h_tw=web_slenderness_h_tw,
        elastic_modulus_E=elastic_modulus_E,
        yield_stress_Fy=yield_stress_Fy,
    )
    lambda_pw, lambda_rw = _ds_web_limits(s)
    web_case = "B4.1b Case 15"
    if section_kind == "singly_symmetric_I" and web_plastic_depth_hp > 0.0:
        lambda_pw = compute_singly_symmetric_web_lambda_pw_case16(
            web_compression_depth_hc=web_compression_depth_hc,
            web_plastic_depth_hp=web_plastic_depth_hp,
            plastic_moment_Mp=plastic_moment_Mp,
            yield_moment_My=yield_moment_My,
            elastic_modulus_E=elastic_modulus_E,
            yield_stress_Fy=yield_stress_Fy,
        )
        web_case = "B4.1b Case 16"
    return [
        FlexuralPlateElement(
            name="flange",
            role="compression_flange",
            aisc_b4_1b_case=flange_case,
            slenderness_ratio_lambda=flange_slenderness_bf_2tf,
            compact_limit_lambda_p=lambda_pf,
            noncompact_limit_lambda_r=lambda_rf,
        ),
        FlexuralPlateElement(
            name="web",
            role="web",
            aisc_b4_1b_case=web_case,
            slenderness_ratio_lambda=web_slenderness_h_tw,
            compact_limit_lambda_p=lambda_pw,
            noncompact_limit_lambda_r=lambda_rw,
        ),
    ]


def _elements_rectangular_hss(
    s: float,
    *,
    hss_flange_slenderness_b_t: float | None,
    hss_web_slenderness_h_t: float | None,
) -> list[FlexuralPlateElement]:
    """Square / rectangular HSS: flange + web (ENGINEER-CONFIRM EC-1/EC-2)."""
    if hss_flange_slenderness_b_t is None or hss_web_slenderness_h_t is None:
        msg = "rectangular_HSS requires hss_flange_slenderness_b_t and hss_web_slenderness_h_t"
        raise ValueError(msg)
    return [
        FlexuralPlateElement(
            name="flange",
            role="hss_flange",
            aisc_b4_1b_case="B4.1b Case ?",  # ENGINEER-CONFIRM EC-1 (~17)
            slenderness_ratio_lambda=hss_flange_slenderness_b_t,
            compact_limit_lambda_p=B4_1B_HSS_FLANGE_COMPACT_COEFF * s,
            noncompact_limit_lambda_r=B4_1B_HSS_FLANGE_NONCOMPACT_COEFF * s,
        ),
        FlexuralPlateElement(
            name="web",
            role="hss_web",
            aisc_b4_1b_case="B4.1b Case ?",  # ENGINEER-CONFIRM EC-2 (~19)
            slenderness_ratio_lambda=hss_web_slenderness_h_t,
            compact_limit_lambda_p=B4_1B_HSS_WEB_COMPACT_COEFF * s,
            noncompact_limit_lambda_r=B4_1B_HSS_WEB_NONCOMPACT_COEFF * s,
        ),
    ]


def _elements_round_hss(
    *,
    elastic_modulus_E: float,
    yield_stress_Fy: float,
    round_hss_slenderness_D_t: float | None,
) -> list[FlexuralPlateElement]:
    """Round HSS: single wall element, Case 20 (uses E/Fy, not sqrt)."""
    if round_hss_slenderness_D_t is None:
        raise ValueError("round_HSS requires round_hss_slenderness_D_t")
    # Case 20 uses E/Fy (not sqrt). CONFIRMED label (Manual Ex. F.9B).
    E_over_Fy = elastic_modulus_E / yield_stress_Fy
    return [
        FlexuralPlateElement(
            name="wall",
            role="hss_flange",
            aisc_b4_1b_case="B4.1b Case 20",  # CONFIRMED (EC-3)
            slenderness_ratio_lambda=round_hss_slenderness_D_t,
            compact_limit_lambda_p=B4_1B_ROUND_HSS_COMPACT_COEFF * E_over_Fy,
            noncompact_limit_lambda_r=B4_1B_ROUND_HSS_NONCOMPACT_COEFF * E_over_Fy,
        )
    ]


def _elements_tee(
    s: float,
    *,
    flange_slenderness_bf_2tf: float | None,
    tee_stem_slenderness_d_tw: float | None,
) -> list[FlexuralPlateElement]:
    """Tee: flange uses the rolled I-flange rule (Case 10) + §F9.4 stem."""
    if flange_slenderness_bf_2tf is None or tee_stem_slenderness_d_tw is None:
        msg = "tee requires flange_slenderness_bf_2tf and tee_stem_slenderness_d_tw"
        raise ValueError(msg)
    # Tee flange in flexural compression uses the rolled I-flange rule
    # (Case 10): lambda_pf = 0.38 sqrt(E/Fy), lambda_rf = 1.0 sqrt(E/Fy)
    # (§F9.3 / Table B4.1b Case 10). Stem: §F9.4 breakpoints
    # (Eq. F9-17 / F9-19), not a B4.1b row.
    return [
        FlexuralPlateElement(
            name="flange",
            role="compression_flange",
            aisc_b4_1b_case="B4.1b Case 10",
            slenderness_ratio_lambda=flange_slenderness_bf_2tf,
            compact_limit_lambda_p=B4_1B_I_FLANGE_COMPACT_COEFF * s,
            noncompact_limit_lambda_r=B4_1B_ROLLED_I_FLANGE_NONCOMPACT_COEFF * s,
        ),
        FlexuralPlateElement(
            name="stem",
            role="stem",
            aisc_b4_1b_case="B4.1b Case ?",  # ENGINEER-CONFIRM EC-5 (~14)
            slenderness_ratio_lambda=tee_stem_slenderness_d_tw,
            compact_limit_lambda_p=F9_4_TEE_STEM_COMPACT_COEFF * s,
            noncompact_limit_lambda_r=F9_4_TEE_STEM_NONCOMPACT_COEFF * s,
        ),
    ]


def _elements_angle(
    s: float,
    *,
    section_kind: FlexuralSectionKind,
    angle_leg_slenderness_b_t: float | None,
) -> list[FlexuralPlateElement]:
    """Single / double-angle leg: §F10.3 breakpoints (ENGINEER-CONFIRM EC-10)."""
    if angle_leg_slenderness_b_t is None:
        msg = f"{section_kind!r} requires angle_leg_slenderness_b_t"
        raise ValueError(msg)
    # §F10.3 leg breakpoints (slender Fcr = Eq. F10-8 confirmed; the
    # compact/NC numeric limits are ENGINEER-CONFIRM EC-10).
    return [
        FlexuralPlateElement(
            name="leg",
            role="leg",
            aisc_b4_1b_case="B4.1b Case ?",  # ENGINEER-CONFIRM EC-4 (~12)
            slenderness_ratio_lambda=angle_leg_slenderness_b_t,
            compact_limit_lambda_p=F10_3_ANGLE_LEG_COMPACT_COEFF * s,
            noncompact_limit_lambda_r=F10_3_ANGLE_LEG_NONCOMPACT_COEFF * s,
        )
    ]


# ---------------------------------------------------------------------------
# Public generalized classifier
# ---------------------------------------------------------------------------
_CITED_CLAUSES: tuple[AISCClauseReference, ...] = (
    AISCClauseReference(
        specification="AISC 360-22",
        section="B4.1b",
        equation=None,
        page="16.1-19",
    ),
    AISCClauseReference(
        specification="AISC 360-22",
        section="Table B4.1b",
        equation="Cases 10, 11, 15, 16, 20",
        page=None,
    ),
)


def classify_flexural_compactness(
    material: SteelMaterial,
    *,
    section_kind: FlexuralSectionKind,
    construction: SectionConstruction = "welded",
    # --- I / channel ---
    flange_slenderness_bf_2tf: float | None = None,
    web_slenderness_h_tw: float | None = None,
    # --- singly-symmetric I web (Table B4.1b Case 16) ---
    web_compression_depth_hc: float = 0.0,
    web_plastic_depth_hp: float = 0.0,
    plastic_moment_Mp: float = 0.0,
    yield_moment_My: float = 0.0,
    # --- HSS (rect / square) ---
    hss_flange_slenderness_b_t: float | None = None,
    hss_web_slenderness_h_t: float | None = None,
    # --- round HSS / pipe ---
    round_hss_slenderness_D_t: float | None = None,
    # --- tee stem ---
    tee_stem_slenderness_d_tw: float | None = None,
    # --- single / double-angle leg ---
    angle_leg_slenderness_b_t: float | None = None,
) -> GeneralizedFlexuralCompactnessReport:
    """Classify a section per AISC 360 Table B4.1b, dispatched by kind.

    Generalized analogue of
    :func:`classify_flexural_compactness_B4_1b` (which is kept,
    untouched, for the shipped I-only F2-F5 path). Emits a
    :class:`FlexuralPlateElement` list for the requested
    ``section_kind``; pass only the slenderness ratios relevant to that
    kind (the geometry layer computes them).

    Parameters
    ----------
    material : SteelMaterial
        Only ``Fy`` and ``E`` are read.
    section_kind : FlexuralSectionKind
        Selects which Table B4.1b rows to apply.
    construction : {"rolled", "welded"}, optional
        I/channel flange Case 10 vs Case 11. Default ``"welded"``.
    flange_slenderness_bf_2tf, web_slenderness_h_tw : float or None
        I/channel flange ``bf/2tf`` and web ``h/tw`` (or ``hc/tw`` for a
        singly-symmetric web). Required for ``doubly_symmetric_I``,
        ``singly_symmetric_I``, ``channel``.
    web_compression_depth_hc, web_plastic_depth_hp, plastic_moment_Mp, \
yield_moment_My : float
        Table B4.1b Case 16 inputs (singly-symmetric I web only). When
        ``section_kind == "singly_symmetric_I"`` and ``hp > 0`` the web
        ``lambda_pw`` is computed per Case 16; otherwise Case 15.
    hss_flange_slenderness_b_t, hss_web_slenderness_h_t : float or None
        Flat-width ``b/t`` / ``h/t`` for ``rectangular_HSS``.
    round_hss_slenderness_D_t : float or None
        ``D/t`` for ``round_HSS`` (Table B4.1b Case 20).
    tee_stem_slenderness_d_tw : float or None
        Stem ``d/tw`` for ``tee`` (§F9.4 breakpoints).
    angle_leg_slenderness_b_t : float or None
        Leg ``b/t`` for ``single_angle`` / ``double_angle`` (§F10.3
        breakpoints). For a tee, the flange uses the I-flange rule and
        ``flange_slenderness_bf_2tf`` is required as well.

    Returns
    -------
    GeneralizedFlexuralCompactnessReport

    Raises
    ------
    ValueError
        If a slenderness ratio required by ``section_kind`` is missing,
        or ``construction`` is unknown.

    Notes
    -----
    Bars (``rectangular_bar``, ``round_bar``) have **no** local-buckling
    limit state in §F11; they return an empty ``plate_elements`` tuple
    and ``section_classification == "compact"`` (compact by inspection;
    §F11 applies a separate ductility/LTB check, not B4.1b).
    ``unsymmetric`` (§F12) is elastic - classification is informational
    and also returns no plate elements here.
    """
    Fy: float = material.yield_stress_Fy
    E: float = material.elastic_modulus_E
    s: float = math.sqrt(E / Fy)

    elements: list[FlexuralPlateElement]
    if section_kind in ("doubly_symmetric_I", "singly_symmetric_I", "channel"):
        elements = _elements_i_channel(
            s,
            section_kind=section_kind,
            construction=construction,
            elastic_modulus_E=E,
            yield_stress_Fy=Fy,
            flange_slenderness_bf_2tf=flange_slenderness_bf_2tf,
            web_slenderness_h_tw=web_slenderness_h_tw,
            web_compression_depth_hc=web_compression_depth_hc,
            web_plastic_depth_hp=web_plastic_depth_hp,
            plastic_moment_Mp=plastic_moment_Mp,
            yield_moment_My=yield_moment_My,
        )
    elif section_kind == "rectangular_HSS":
        elements = _elements_rectangular_hss(
            s,
            hss_flange_slenderness_b_t=hss_flange_slenderness_b_t,
            hss_web_slenderness_h_t=hss_web_slenderness_h_t,
        )
    elif section_kind == "round_HSS":
        elements = _elements_round_hss(
            elastic_modulus_E=E,
            yield_stress_Fy=Fy,
            round_hss_slenderness_D_t=round_hss_slenderness_D_t,
        )
    elif section_kind == "tee":
        elements = _elements_tee(
            s,
            flange_slenderness_bf_2tf=flange_slenderness_bf_2tf,
            tee_stem_slenderness_d_tw=tee_stem_slenderness_d_tw,
        )
    elif section_kind in ("single_angle", "double_angle"):
        elements = _elements_angle(
            s,
            section_kind=section_kind,
            angle_leg_slenderness_b_t=angle_leg_slenderness_b_t,
        )
    elif section_kind in ("rectangular_bar", "round_bar", "unsymmetric"):
        # §F11 bars: no local-buckling limit state (compact by
        # inspection). §F12 unsymmetric: elastic Fn*S - classification
        # is informational. Either way, no plate element.
        elements = []
    else:  # pragma: no cover - exhaustive over the Literal
        raise ValueError(f"unknown section_kind {section_kind!r}")

    plate_elements = tuple(elements)
    section_classification = _worst(plate_elements)

    return GeneralizedFlexuralCompactnessReport(
        cited_clauses=_CITED_CLAUSES,
        governing_limit_state="flexural_plate_element_slenderness",
        phi_LRFD=1.0,
        omega_ASD=1.0,
        nominal_strength=0.0,
        phi_strength_LRFD=0.0,
        omega_strength_ASD=0.0,
        section_kind=section_kind,
        plate_elements=plate_elements,
        section_classification=section_classification,
        construction=construction,
    )


__all__ = [
    "B4_1B_CASE16_MP_MY_COEFF",
    "B4_1B_CASE16_MP_MY_OFFSET",
    "B4_1B_HSS_FLANGE_COMPACT_COEFF",
    "B4_1B_HSS_FLANGE_NONCOMPACT_COEFF",
    "B4_1B_HSS_WEB_COMPACT_COEFF",
    "B4_1B_HSS_WEB_NONCOMPACT_COEFF",
    "B4_1B_I_FLANGE_COMPACT_COEFF",
    "B4_1B_ROLLED_I_FLANGE_NONCOMPACT_COEFF",
    "B4_1B_ROUND_HSS_COMPACT_COEFF",
    "B4_1B_ROUND_HSS_NONCOMPACT_COEFF",
    "B4_1B_WEB_COMPACT_COEFF",
    "B4_1B_WEB_NONCOMPACT_COEFF",
    "B4_1B_WELDED_I_FLANGE_FL_FRACTION_OF_FY",
    "B4_1B_WELDED_I_FLANGE_NONCOMPACT_COEFF",
    "F9_4_TEE_STEM_COMPACT_COEFF",
    "F9_4_TEE_STEM_NONCOMPACT_COEFF",
    "F10_3_ANGLE_LEG_COMPACT_COEFF",
    "F10_3_ANGLE_LEG_NONCOMPACT_COEFF",
    "GeneralizedFlexuralCompactnessReport",
    "classify_flexural_compactness",
    "compute_singly_symmetric_web_lambda_pw_case16",
]
