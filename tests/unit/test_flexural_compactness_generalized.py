"""Unit tests for the generalized AISC 360-22 Table B4.1b classifier.

Covers, per design note 10 §5 / F-0 "done" criterion:

* Hand-derived ``lambda_p`` / ``lambda_r`` for **one representative
  shape per** :data:`FlexuralSectionKind` (the limit is recomputed by
  hand inside each test and asserted with ``math.isclose(rel_tol=1e-12)``
  - no shared constant with the library).
* The ``FlexuralPlateElement.classification`` / section-worst rollup.
* ``FlexuralSectionProperties.from_legacy`` bit-exact lift of the
  shipped I-only ``SectionProperties`` (DS and SS).
* Back-compat: the shipped
  ``classify_flexural_compactness_B4_1b`` /
  ``compute_singly_symmetric_web_lambda_pw_case16`` are still importable
  and the generalized SS Case-16 ``lambda_pw`` matches the shipped one
  bit-for-bit.
* The independent stdlib oracle (``_chapterF_full_aisc_oracle``) agrees
  with the classifier per element.

All section properties are supplied via the apeSteel geometry layer
where an I-shape is involved (it has its own scipy / hand-calc
cross-check); the non-I kinds feed raw slenderness ratios directly, as
the generalized classifier's signature intends.
"""

from __future__ import annotations

import math
from dataclasses import FrozenInstanceError
from typing import TYPE_CHECKING

import pytest

from apeSteel import A36, A992, DoublySymmetricISection, SinglySymmetricISection
from apeSteel.classification.flexural_compactness import (
    GeneralizedFlexuralCompactnessReport,
    classify_flexural_compactness,
    compute_singly_symmetric_web_lambda_pw_case16,
)
from apeSteel.classification.flexural_compactness_B4_1b import (
    classify_flexural_compactness_B4_1b,
)
from apeSteel.classification.flexural_compactness_B4_1b import (
    compute_singly_symmetric_web_lambda_pw_case16 as shipped_case16,
)
from apeSteel.core import units as u
from apeSteel.sections.flexural_properties import (
    FlexuralPlateElement,
    FlexuralSectionProperties,
)
from tests.golden._chapterF_full_aisc_oracle import (
    LambdaLimits,
    oracle_lambda_limits,
)

if TYPE_CHECKING:
    from apeSteel.core.materials import SteelMaterial

RTOL = 1e-12


def _s(material: SteelMaterial) -> float:
    """sqrt(E/Fy) for a SteelMaterial (hand-side, no library constant)."""
    return math.sqrt(material.elastic_modulus_E / material.yield_stress_Fy)


# ===========================================================================
# One representative shape per section_kind - hand-derived lambda_p/lambda_r
# ===========================================================================
def test_doubly_symmetric_I_rolled_hand_lambda() -> None:
    # Rolled W: flange Case 10, web Case 15. bf/2tf = 200/(2*10)=10,
    # h/tw = 400/8 = 50.
    r = classify_flexural_compactness(
        A992,
        section_kind="doubly_symmetric_I",
        construction="rolled",
        flange_slenderness_bf_2tf=10.0,
        web_slenderness_h_tw=50.0,
    )
    s = _s(A992)
    flange = next(e for e in r.plate_elements if e.name == "flange")
    web = next(e for e in r.plate_elements if e.name == "web")
    assert math.isclose(flange.compact_limit_lambda_p, 0.38 * s, rel_tol=RTOL)
    assert math.isclose(flange.noncompact_limit_lambda_r, 1.00 * s, rel_tol=RTOL)
    assert flange.aisc_b4_1b_case == "B4.1b Case 10"
    assert math.isclose(web.compact_limit_lambda_p, 3.76 * s, rel_tol=RTOL)
    assert math.isclose(web.noncompact_limit_lambda_r, 5.70 * s, rel_tol=RTOL)
    assert web.aisc_b4_1b_case == "B4.1b Case 15"
    # 10 < 0.38*sqrt(29000/50)=9.15? -> 10 > 9.15 => non_compact flange.
    assert flange.classification == "non_compact"
    assert web.classification == "compact"  # 50 < 90.55
    assert r.section_classification == "non_compact"


def test_doubly_symmetric_I_welded_flange_case11_hand_lambda() -> None:
    # Welded built-up I: flange Case 11 with kc. h/tw=100 => kc=4/sqrt(100)
    # =0.40 (in [0.35,0.76]); FL=0.7*Fy; lambda_rf=0.95*sqrt(kc*E/FL).
    r = classify_flexural_compactness(
        A992,
        section_kind="doubly_symmetric_I",
        construction="welded",
        flange_slenderness_bf_2tf=8.0,
        web_slenderness_h_tw=100.0,
    )
    E = A992.elastic_modulus_E
    Fy = A992.yield_stress_Fy
    kc = 4.0 / math.sqrt(100.0)
    FL = 0.7 * Fy
    lam_rf = 0.95 * math.sqrt(kc * E / FL)
    flange = next(e for e in r.plate_elements if e.name == "flange")
    assert math.isclose(flange.compact_limit_lambda_p, 0.38 * _s(A992), rel_tol=RTOL)
    assert math.isclose(flange.noncompact_limit_lambda_r, lam_rf, rel_tol=RTOL)
    assert flange.aisc_b4_1b_case == "B4.1b Case 11"


def test_singly_symmetric_I_web_case16_hand_lambda() -> None:
    # Case 16: lambda_pw = (hc/hp) sqrt(E/Fy) / (0.54 Mp/My - 0.09)^2,
    # capped at lambda_rw = 5.70 sqrt(E/Fy).
    E = A992.elastic_modulus_E
    Fy = A992.yield_stress_Fy
    hc, hp = 380.0, 360.0
    Mp, My = 1.30e8, 1.00e8
    r = classify_flexural_compactness(
        A992,
        section_kind="singly_symmetric_I",
        construction="welded",
        flange_slenderness_bf_2tf=7.0,
        web_slenderness_h_tw=70.0,
        web_compression_depth_hc=hc,
        web_plastic_depth_hp=hp,
        plastic_moment_Mp=Mp,
        yield_moment_My=My,
    )
    s = math.sqrt(E / Fy)
    lam_rw = 5.70 * s
    den = 0.54 * (Mp / My) - 0.09
    lam_pw_hand = min((hc / hp) * s / den**2, lam_rw)
    web = next(e for e in r.plate_elements if e.name == "web")
    assert web.aisc_b4_1b_case == "B4.1b Case 16"
    assert math.isclose(web.compact_limit_lambda_p, lam_pw_hand, rel_tol=RTOL)
    assert math.isclose(web.noncompact_limit_lambda_r, lam_rw, rel_tol=RTOL)


def test_channel_uses_case10_11_and_case15_like_I() -> None:
    r = classify_flexural_compactness(
        A36,
        section_kind="channel",
        construction="rolled",
        flange_slenderness_bf_2tf=6.0,
        web_slenderness_h_tw=40.0,
    )
    s = _s(A36)
    flange = next(e for e in r.plate_elements if e.name == "flange")
    web = next(e for e in r.plate_elements if e.name == "web")
    assert math.isclose(flange.compact_limit_lambda_p, 0.38 * s, rel_tol=RTOL)
    assert math.isclose(flange.noncompact_limit_lambda_r, 1.00 * s, rel_tol=RTOL)
    assert math.isclose(web.compact_limit_lambda_p, 3.76 * s, rel_tol=RTOL)
    assert math.isclose(web.noncompact_limit_lambda_r, 5.70 * s, rel_tol=RTOL)


def test_rectangular_HSS_flange_and_web_hand_lambda() -> None:
    # Rect HSS flexure: flange lp=1.12 sqrt(E/Fy), lr=1.40 sqrt(E/Fy);
    # web lp=2.42 sqrt(E/Fy), lr=5.70 sqrt(E/Fy).
    r = classify_flexural_compactness(
        A992,
        section_kind="rectangular_HSS",
        hss_flange_slenderness_b_t=25.0,
        hss_web_slenderness_h_t=45.0,
    )
    s = _s(A992)
    flange = next(e for e in r.plate_elements if e.name == "flange")
    web = next(e for e in r.plate_elements if e.name == "web")
    assert math.isclose(flange.compact_limit_lambda_p, 1.12 * s, rel_tol=RTOL)
    assert math.isclose(flange.noncompact_limit_lambda_r, 1.40 * s, rel_tol=RTOL)
    assert math.isclose(web.compact_limit_lambda_p, 2.42 * s, rel_tol=RTOL)
    assert math.isclose(web.noncompact_limit_lambda_r, 5.70 * s, rel_tol=RTOL)
    assert flange.role == "hss_flange"
    assert web.role == "hss_web"


def test_round_HSS_case20_uses_E_over_Fy_not_sqrt() -> None:
    # Case 20 (CONFIRMED label): lp = 0.07 E/Fy, lr = 0.31 E/Fy.
    r = classify_flexural_compactness(
        A992,
        section_kind="round_HSS",
        round_hss_slenderness_D_t=40.0,
    )
    ratio = A992.elastic_modulus_E / A992.yield_stress_Fy
    wall = r.plate_elements[0]
    assert wall.name == "wall"
    assert wall.aisc_b4_1b_case == "B4.1b Case 20"
    assert math.isclose(wall.compact_limit_lambda_p, 0.07 * ratio, rel_tol=RTOL)
    assert math.isclose(wall.noncompact_limit_lambda_r, 0.31 * ratio, rel_tol=RTOL)
    # D/t=40 ; 0.07*E/Fy = 0.07*~580 = ~40.6 -> 40 < 40.6 => compact.
    assert wall.classification == "compact"


def test_tee_flange_case10_and_stem_F9_4_hand_lambda() -> None:
    r = classify_flexural_compactness(
        A992,
        section_kind="tee",
        flange_slenderness_bf_2tf=9.0,
        tee_stem_slenderness_d_tw=20.0,
    )
    s = _s(A992)
    flange = next(e for e in r.plate_elements if e.name == "flange")
    stem = next(e for e in r.plate_elements if e.name == "stem")
    assert math.isclose(flange.compact_limit_lambda_p, 0.38 * s, rel_tol=RTOL)
    assert math.isclose(flange.noncompact_limit_lambda_r, 1.00 * s, rel_tol=RTOL)
    assert math.isclose(stem.compact_limit_lambda_p, 0.84 * s, rel_tol=RTOL)
    assert math.isclose(stem.noncompact_limit_lambda_r, 1.52 * s, rel_tol=RTOL)
    assert stem.role == "stem"


@pytest.mark.parametrize("kind", ["single_angle", "double_angle"])
def test_angle_leg_F10_3_hand_lambda(kind: str) -> None:
    r = classify_flexural_compactness(
        A992,
        section_kind=kind,  # type: ignore[arg-type]
        angle_leg_slenderness_b_t=12.0,
    )
    s = _s(A992)
    leg = r.plate_elements[0]
    assert leg.name == "leg"
    assert leg.role == "leg"
    assert math.isclose(leg.compact_limit_lambda_p, 0.54 * s, rel_tol=RTOL)
    assert math.isclose(leg.noncompact_limit_lambda_r, 0.91 * s, rel_tol=RTOL)


@pytest.mark.parametrize("kind", ["rectangular_bar", "round_bar", "unsymmetric"])
def test_bars_and_unsymmetric_have_no_plate_elements(kind: str) -> None:
    r = classify_flexural_compactness(A992, section_kind=kind)  # type: ignore[arg-type]
    assert r.plate_elements == ()
    assert r.section_classification == "compact"


# ===========================================================================
# FlexuralPlateElement.classification + section-worst rollup
# ===========================================================================
def test_plate_element_classification_three_regimes() -> None:
    pe_c = FlexuralPlateElement("f", "compression_flange", "B4.1b Case 10", 5.0, 9.0, 24.0)
    pe_n = FlexuralPlateElement("f", "compression_flange", "B4.1b Case 10", 15.0, 9.0, 24.0)
    pe_s = FlexuralPlateElement("f", "compression_flange", "B4.1b Case 10", 30.0, 9.0, 24.0)
    assert pe_c.classification == "compact"
    assert pe_n.classification == "non_compact"
    assert pe_s.classification == "slender"


def test_section_classification_is_worst_of_elements() -> None:
    # Flange slender, web compact -> section slender.
    r = classify_flexural_compactness(
        A992,
        section_kind="doubly_symmetric_I",
        construction="rolled",
        flange_slenderness_bf_2tf=40.0,  # >> lambda_rf
        web_slenderness_h_tw=30.0,  # << lambda_pw
    )
    assert next(e for e in r.plate_elements if e.name == "flange").classification == "slender"
    assert next(e for e in r.plate_elements if e.name == "web").classification == "compact"
    assert r.section_classification == "slender"


# ===========================================================================
# Error handling
# ===========================================================================
def test_missing_I_ratios_raises() -> None:
    with pytest.raises(ValueError, match="requires flange_slenderness"):
        classify_flexural_compactness(A992, section_kind="doubly_symmetric_I")


def test_missing_round_hss_ratio_raises() -> None:
    with pytest.raises(ValueError, match="round_hss_slenderness_D_t"):
        classify_flexural_compactness(A992, section_kind="round_HSS")


def test_missing_hss_ratios_raises() -> None:
    with pytest.raises(ValueError, match="hss_flange_slenderness_b_t"):
        classify_flexural_compactness(A992, section_kind="rectangular_HSS")


def test_missing_tee_ratios_raises() -> None:
    with pytest.raises(ValueError, match="tee requires"):
        classify_flexural_compactness(A992, section_kind="tee")


def test_missing_angle_ratio_raises() -> None:
    with pytest.raises(ValueError, match="angle_leg_slenderness_b_t"):
        classify_flexural_compactness(A992, section_kind="single_angle")


def test_case16_helper_rejects_degenerate_inputs() -> None:
    with pytest.raises(ValueError, match="web_plastic_depth_hp"):
        compute_singly_symmetric_web_lambda_pw_case16(380.0, 0.0, 1e8, 1e8, 2e5, 345.0)
    with pytest.raises(ValueError, match="yield_moment_My"):
        compute_singly_symmetric_web_lambda_pw_case16(380.0, 360.0, 1e8, 0.0, 2e5, 345.0)


# ===========================================================================
# Back-compat: shipped functions untouched + Case-16 bit-identity
# ===========================================================================
def test_shipped_B4_1b_classifier_still_importable_and_works() -> None:
    sec = DoublySymmetricISection(100.0 * u.mm, 6.0 * u.mm, 300.0 * u.mm, 4.0 * u.mm)
    r = classify_flexural_compactness_B4_1b(sec.compute_section_properties(), A992)
    assert r.flange.aisc_case == "B4.1b Case 11"
    assert r.web.aisc_case == "B4.1b Case 15"


def test_generalized_case16_matches_shipped_case16_bit_for_bit() -> None:
    # Same inputs through both implementations -> identical float.
    args = (380.0, 360.0, 1.30e8, 1.00e8, A992.elastic_modulus_E, A992.yield_stress_Fy)
    assert compute_singly_symmetric_web_lambda_pw_case16(*args) == shipped_case16(*args)


def test_generalized_DS_flange_web_limits_match_shipped_classifier() -> None:
    # The generalized classifier and the shipped B4.1b classifier must
    # produce identical lambda_p / lambda_r for an I-shape (same Table
    # B4.1b rows). Feed the shipped classifier's own ratios back in.
    sec = DoublySymmetricISection(180.0 * u.mm, 12.0 * u.mm, 360.0 * u.mm, 7.0 * u.mm)
    sp = sec.compute_section_properties()
    shipped = classify_flexural_compactness_B4_1b(sp, A992, construction="rolled")
    gen = classify_flexural_compactness(
        A992,
        section_kind="doubly_symmetric_I",
        construction="rolled",
        flange_slenderness_bf_2tf=sp.flange_width_to_thickness_ratio_bf_2tf,
        web_slenderness_h_tw=sp.web_height_to_thickness_ratio_h_tw,
    )
    gflange = next(e for e in gen.plate_elements if e.name == "flange")
    gweb = next(e for e in gen.plate_elements if e.name == "web")
    assert gflange.compact_limit_lambda_p == shipped.flange.compact_limit_lambda_p
    assert gflange.noncompact_limit_lambda_r == shipped.flange.noncompact_limit_lambda_r
    assert gweb.compact_limit_lambda_p == shipped.web.compact_limit_lambda_p
    assert gweb.noncompact_limit_lambda_r == shipped.web.noncompact_limit_lambda_r


# ===========================================================================
# Independent stdlib oracle agreement (primary regression pin, F-0)
# ===========================================================================
def _assert_agrees(
    report: GeneralizedFlexuralCompactnessReport,
    oracle: dict[str, LambdaLimits],
) -> None:
    """Every classifier plate element matches the stdlib oracle."""
    assert {e.name for e in report.plate_elements} == set(oracle)
    for e in report.plate_elements:
        o = oracle[e.name]
        assert math.isclose(e.compact_limit_lambda_p, o.lambda_p, rel_tol=1e-12)
        assert math.isclose(e.noncompact_limit_lambda_r, o.lambda_r, rel_tol=1e-12)
        assert e.classification == o.classification


def test_oracle_agreement_doubly_symmetric_I_rolled() -> None:
    r = classify_flexural_compactness(
        A992,
        section_kind="doubly_symmetric_I",
        construction="rolled",
        flange_slenderness_bf_2tf=10.0,
        web_slenderness_h_tw=50.0,
    )
    o = oracle_lambda_limits(
        "doubly_symmetric_I",
        A992.yield_stress_Fy,
        A992.elastic_modulus_E,
        construction="rolled",
        flange_lam=10.0,
        web_lam=50.0,
    )
    _assert_agrees(r, o)


def test_oracle_agreement_doubly_symmetric_I_welded() -> None:
    r = classify_flexural_compactness(
        A992,
        section_kind="doubly_symmetric_I",
        construction="welded",
        flange_slenderness_bf_2tf=8.0,
        web_slenderness_h_tw=100.0,
    )
    o = oracle_lambda_limits(
        "doubly_symmetric_I",
        A992.yield_stress_Fy,
        A992.elastic_modulus_E,
        construction="welded",
        flange_lam=8.0,
        web_lam=100.0,
    )
    _assert_agrees(r, o)


def test_oracle_agreement_channel() -> None:
    r = classify_flexural_compactness(
        A36,
        section_kind="channel",
        construction="rolled",
        flange_slenderness_bf_2tf=6.0,
        web_slenderness_h_tw=40.0,
    )
    o = oracle_lambda_limits(
        "channel",
        A36.yield_stress_Fy,
        A36.elastic_modulus_E,
        construction="rolled",
        flange_lam=6.0,
        web_lam=40.0,
    )
    _assert_agrees(r, o)


def test_oracle_agreement_singly_symmetric_I_case16() -> None:
    r = classify_flexural_compactness(
        A992,
        section_kind="singly_symmetric_I",
        construction="welded",
        flange_slenderness_bf_2tf=7.0,
        web_slenderness_h_tw=70.0,
        web_compression_depth_hc=380.0,
        web_plastic_depth_hp=360.0,
        plastic_moment_Mp=1.30e8,
        yield_moment_My=1.00e8,
    )
    o = oracle_lambda_limits(
        "singly_symmetric_I",
        A992.yield_stress_Fy,
        A992.elastic_modulus_E,
        construction="welded",
        flange_lam=7.0,
        web_lam=70.0,
        hc=380.0,
        hp=360.0,
        Mp=1.30e8,
        My=1.00e8,
    )
    _assert_agrees(r, o)


def test_oracle_agreement_rectangular_HSS() -> None:
    r = classify_flexural_compactness(
        A992,
        section_kind="rectangular_HSS",
        hss_flange_slenderness_b_t=25.0,
        hss_web_slenderness_h_t=45.0,
    )
    o = oracle_lambda_limits(
        "rectangular_HSS",
        A992.yield_stress_Fy,
        A992.elastic_modulus_E,
        hss_flange_lam=25.0,
        hss_web_lam=45.0,
    )
    _assert_agrees(r, o)


def test_oracle_agreement_round_HSS() -> None:
    r = classify_flexural_compactness(
        A992,
        section_kind="round_HSS",
        round_hss_slenderness_D_t=40.0,
    )
    o = oracle_lambda_limits(
        "round_HSS",
        A992.yield_stress_Fy,
        A992.elastic_modulus_E,
        round_D_t=40.0,
    )
    _assert_agrees(r, o)


def test_oracle_agreement_tee() -> None:
    r = classify_flexural_compactness(
        A992,
        section_kind="tee",
        flange_slenderness_bf_2tf=9.0,
        tee_stem_slenderness_d_tw=20.0,
    )
    o = oracle_lambda_limits(
        "tee",
        A992.yield_stress_Fy,
        A992.elastic_modulus_E,
        flange_lam=9.0,
        tee_stem_lam=20.0,
    )
    _assert_agrees(r, o)


@pytest.mark.parametrize("kind", ["single_angle", "double_angle"])
def test_oracle_agreement_angles(kind: str) -> None:
    r = classify_flexural_compactness(
        A992,
        section_kind=kind,  # type: ignore[arg-type]
        angle_leg_slenderness_b_t=12.0,
    )
    o = oracle_lambda_limits(
        kind,
        A992.yield_stress_Fy,
        A992.elastic_modulus_E,
        angle_leg_lam=12.0,
    )
    _assert_agrees(r, o)


# ===========================================================================
# Report plumbing
# ===========================================================================
def test_report_is_frozen() -> None:
    r = classify_flexural_compactness(
        A992, section_kind="round_HSS", round_hss_slenderness_D_t=30.0
    )
    with pytest.raises(FrozenInstanceError):
        r.section_classification = "slender"  # type: ignore[misc]


def test_report_is_generalized_type_and_carries_citations() -> None:
    r = classify_flexural_compactness(
        A992, section_kind="round_HSS", round_hss_slenderness_D_t=30.0
    )
    assert isinstance(r, GeneralizedFlexuralCompactnessReport)
    sections = {c.section for c in r.cited_clauses}
    assert "Table B4.1b" in sections


# ===========================================================================
# FlexuralSectionProperties.from_legacy - bit-exact lift (DS + SS)
# ===========================================================================
def test_from_legacy_doubly_symmetric_is_bit_exact() -> None:
    sec = DoublySymmetricISection(200.0 * u.mm, 15.0 * u.mm, 400.0 * u.mm, 9.0 * u.mm)
    sp = sec.compute_section_properties()
    fp = FlexuralSectionProperties.from_legacy(
        sp,
        kind="doubly_symmetric_I",
        symmetry="doubly_symmetric",
        construction="welded",
    )
    assert fp.section_kind == "doubly_symmetric_I"
    assert fp.symmetry == "doubly_symmetric"
    # Gross / both axes: identical floats (no tolerance).
    assert fp.overall_depth_d == sp.overall_depth_d
    assert fp.gross_area_Ag == sp.gross_area_Ag
    assert fp.moment_of_inertia_Ix == sp.moment_of_inertia_strong_axis_Ix
    assert fp.elastic_modulus_Sx == sp.elastic_section_modulus_strong_axis_Sx
    assert fp.plastic_modulus_Zx == sp.plastic_section_modulus_strong_axis_Zx
    assert fp.radius_of_gyration_rx == sp.radius_of_gyration_strong_axis_rx
    assert fp.moment_of_inertia_Iy == sp.moment_of_inertia_weak_axis_Iy
    assert fp.elastic_modulus_Sy == sp.elastic_section_modulus_weak_axis_Sy
    assert fp.plastic_modulus_Zy == sp.plastic_section_modulus_weak_axis_Zy
    assert fp.radius_of_gyration_ry == sp.radius_of_gyration_weak_axis_ry
    assert fp.torsional_constant_J == sp.torsional_constant_J
    assert fp.warping_constant_Cw == sp.warping_constant_Cw
    assert fp.distance_between_flange_centroids_ho == sp.distance_between_flange_centroids_ho
    assert (
        fp.effective_radius_of_gyration_for_LTB_rts == sp.effective_radius_of_gyration_for_LTB_rts
    )
    # Eq. F2-8a: c = 1 for doubly-symmetric I.
    assert fp.section_constant_c == 1.0
    # SS optionals via resolved_* -> DS-equivalent, bit-for-bit.
    assert fp.elastic_modulus_compression_flange_Sxc == sp.resolved_Sxc()
    assert fp.elastic_modulus_tension_flange_Sxt == sp.resolved_Sxt()
    assert fp.moment_of_inertia_compression_flange_Iyc == sp.resolved_Iyc()
    assert fp.web_compression_depth_hc == sp.resolved_hc()
    assert fp.web_plastic_depth_hp == sp.plastic_neutral_axis_depth_hp
    # DS: resolved_Sxc == resolved_Sxt == Sx.
    assert fp.elastic_modulus_compression_flange_Sxc == sp.elastic_section_modulus_strong_axis_Sx
    # from_legacy never classifies (layer rule).
    assert fp.plate_elements == ()
    assert fp.section_classification == "compact"


def test_from_legacy_singly_symmetric_lifts_SS_optionals_bit_exact() -> None:
    sec = SinglySymmetricISection(
        top_flange_width_bf_top=300.0 * u.mm,
        top_flange_thickness_tf_top=20.0 * u.mm,
        bot_flange_width_bf_bot=180.0 * u.mm,
        bot_flange_thickness_tf_bot=14.0 * u.mm,
        web_clear_height_hw=500.0 * u.mm,
        web_thickness_tw=10.0 * u.mm,
    )
    sp = sec.compute_section_properties(compression_flange_side="top")
    fp = FlexuralSectionProperties.from_legacy(
        sp,
        kind="singly_symmetric_I",
        symmetry="singly_symmetric",
        construction="welded",
    )
    # SS optionals must equal the resolved_* the shipped F4.py reads.
    assert fp.elastic_modulus_compression_flange_Sxc == sp.resolved_Sxc()
    assert fp.elastic_modulus_tension_flange_Sxt == sp.resolved_Sxt()
    assert fp.moment_of_inertia_compression_flange_Iyc == sp.resolved_Iyc()
    assert fp.web_compression_depth_hc == sp.resolved_hc()
    # SS section actually populated hp (the F4 SS detector).
    assert sp.plastic_neutral_axis_depth_hp > 0.0
    assert fp.web_plastic_depth_hp == sp.plastic_neutral_axis_depth_hp
    # And SS really is asymmetric: Sxc != Sxt.
    assert fp.elastic_modulus_compression_flange_Sxc != fp.elastic_modulus_tension_flange_Sxt
    assert fp.symmetry == "singly_symmetric"


def test_from_legacy_result_is_frozen() -> None:
    sec = DoublySymmetricISection(120.0 * u.mm, 8.0 * u.mm, 300.0 * u.mm, 5.0 * u.mm)
    fp = FlexuralSectionProperties.from_legacy(
        sec.compute_section_properties(),
        kind="doubly_symmetric_I",
        symmetry="doubly_symmetric",
        construction="rolled",
    )
    with pytest.raises(FrozenInstanceError):
        fp.gross_area_Ag = 1.0  # type: ignore[misc]
