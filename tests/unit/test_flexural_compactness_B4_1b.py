"""Unit tests for classify_flexural_compactness_B4_1b.

Covers:
- Hand-computed lambda, lambda_p, lambda_r for the spreadsheet default
  100x6 / 300x4 at A992 (both rolled and welded paths).
- Classification regime transitions (compact / non-compact / slender)
  by sweeping plate dimensions across the limits.
- Construction-type dispatch (rolled => Case 10; welded => Case 11).
- Report immutability + citation discipline.
"""

from __future__ import annotations

import math
from dataclasses import FrozenInstanceError

import pytest

from apeSteel import (
    A36,
    A992,
    DoublySymmetricISection,
    FlexuralCompactnessReport,
    SteelMaterial,
    classify_flexural_compactness_B4_1b,
)
from apeSteel.classification import compute_kc_for_built_up_flange
from apeSteel.core import units as u


@pytest.fixture
def default_props_and_material() -> tuple[
    type[DoublySymmetricISection], DoublySymmetricISection, SteelMaterial
]:
    section = DoublySymmetricISection(
        flange_width_bf=100.0 * u.mm,
        flange_thickness_tf=6.0 * u.mm,
        web_clear_height_hw=300.0 * u.mm,
        web_thickness_tw=4.0 * u.mm,
    )
    return DoublySymmetricISection, section, A992


# ---------------------------------------------------------------------------
# Hand-computed values for default 100x6/300x4 at A992
# ---------------------------------------------------------------------------
def test_default_section_rolled_construction_lambda_values() -> None:
    sec = DoublySymmetricISection(
        flange_width_bf=100.0 * u.mm,
        flange_thickness_tf=6.0 * u.mm,
        web_clear_height_hw=300.0 * u.mm,
        web_thickness_tw=4.0 * u.mm,
    )
    props = sec.compute_section_properties()
    r = classify_flexural_compactness_B4_1b(props, A992, construction="rolled")

    sqrt_E_over_Fy = math.sqrt(A992.elastic_modulus_E / A992.yield_stress_Fy)
    # Flange Case 10:
    assert math.isclose(r.flange.slenderness_ratio_lambda, 100.0 / 12.0, rel_tol=1e-12)
    assert math.isclose(
        r.flange.compact_limit_lambda_p,  # type: ignore[arg-type]
        0.38 * sqrt_E_over_Fy,
        rel_tol=1e-12,
    )
    assert math.isclose(r.flange.noncompact_limit_lambda_r, 1.0 * sqrt_E_over_Fy, rel_tol=1e-12)
    assert r.flange.aisc_case == "B4.1b Case 10"
    assert r.flange.classification == "compact"  # 8.33 < 9.15

    # Web Case 15:
    assert math.isclose(r.web.slenderness_ratio_lambda, 75.0, rel_tol=1e-12)
    assert math.isclose(
        r.web.compact_limit_lambda_p,  # type: ignore[arg-type]
        3.76 * sqrt_E_over_Fy,
        rel_tol=1e-12,
    )
    assert math.isclose(r.web.noncompact_limit_lambda_r, 5.7 * sqrt_E_over_Fy, rel_tol=1e-12)
    assert r.web.aisc_case == "B4.1b Case 15"
    assert r.web.classification == "compact"  # 75 < 90.55

    assert r.section_classification == "compact"
    assert r.construction == "rolled"


def test_default_section_welded_construction_uses_case_11_with_kc() -> None:
    sec = DoublySymmetricISection(
        flange_width_bf=100.0 * u.mm,
        flange_thickness_tf=6.0 * u.mm,
        web_clear_height_hw=300.0 * u.mm,
        web_thickness_tw=4.0 * u.mm,
    )
    props = sec.compute_section_properties()
    r = classify_flexural_compactness_B4_1b(props, A992, construction="welded")

    # h/tw = 75 -> kc = 4/sqrt(75) = 0.4619, bounded [0.35, 0.76] -> 0.4619
    kc = compute_kc_for_built_up_flange(75.0)
    assert math.isclose(kc, 4.0 / math.sqrt(75.0), rel_tol=1e-12)

    FL = 0.7 * A992.yield_stress_Fy
    expected_lambda_rf = 0.95 * math.sqrt(kc * A992.elastic_modulus_E / FL)
    assert math.isclose(r.flange.noncompact_limit_lambda_r, expected_lambda_rf, rel_tol=1e-12)
    assert r.flange.aisc_case == "B4.1b Case 11"
    assert r.construction == "welded"


def test_kc_is_bounded_at_lower_and_upper_limits() -> None:
    # Very stocky web (small h/tw=10): 4/sqrt(10)=1.265 -> capped to 0.76
    assert math.isclose(compute_kc_for_built_up_flange(10.0), 0.76)
    # Very slender web (h/tw=400): 4/sqrt(400)=0.20 -> floored to 0.35
    assert math.isclose(compute_kc_for_built_up_flange(400.0), 0.35)


# ---------------------------------------------------------------------------
# Regime transitions - sweep flange thickness across compact -> slender
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("flange_thickness_tf_mm", "expected_class"),
    [
        (12.0, "compact"),  # bf/(2tf) = 100/24 = 4.17  << lambda_p
        (5.5, "compact"),  # 100/11 = 9.09 < 9.15 = lambda_p
        (5.0, "non_compact"),  # 100/10 = 10.0; lambda_p=9.15, lambda_rolled=24.08
        (3.0, "non_compact"),  # 100/6 = 16.67; still < 24.08
        (2.0, "slender"),  # 100/4 = 25 > 24.08 = lambda_r
    ],
)
def test_flange_classification_regime_rolled(
    flange_thickness_tf_mm: float,
    expected_class: str,
) -> None:
    sec = DoublySymmetricISection(
        flange_width_bf=100.0 * u.mm,
        flange_thickness_tf=flange_thickness_tf_mm * u.mm,
        web_clear_height_hw=300.0 * u.mm,
        web_thickness_tw=8.0 * u.mm,  # stocky enough web stays compact
    )
    r = classify_flexural_compactness_B4_1b(
        sec.compute_section_properties(),
        A992,
        construction="rolled",
    )
    assert r.flange.classification == expected_class


@pytest.mark.parametrize(
    ("web_thickness_tw_mm", "expected_class"),
    [
        (12.0, "compact"),  # h/tw = 25
        (4.0, "compact"),  # h/tw = 75   < lambda_pw = 90.55
        (3.0, "non_compact"),  # h/tw = 100  > lambda_pw=90.55
        (2.5, "non_compact"),  # h/tw = 120  < lambda_rw=137.3
        (2.0, "slender"),  # h/tw = 150  > lambda_rw=137.3
    ],
)
def test_web_classification_regime(
    web_thickness_tw_mm: float,
    expected_class: str,
) -> None:
    sec = DoublySymmetricISection(
        flange_width_bf=200.0 * u.mm,
        flange_thickness_tf=20.0 * u.mm,
        web_clear_height_hw=300.0 * u.mm,
        web_thickness_tw=web_thickness_tw_mm * u.mm,
    )
    r = classify_flexural_compactness_B4_1b(
        sec.compute_section_properties(),
        A992,
        construction="rolled",
    )
    assert r.web.classification == expected_class


def test_section_classification_is_worst_of_flange_and_web() -> None:
    # Web compact, flange slender => section slender.
    sec = DoublySymmetricISection(
        flange_width_bf=100.0 * u.mm,
        flange_thickness_tf=2.0 * u.mm,  # slender flange
        web_clear_height_hw=300.0 * u.mm,
        web_thickness_tw=12.0 * u.mm,  # compact web
    )
    r = classify_flexural_compactness_B4_1b(
        sec.compute_section_properties(),
        A992,
        construction="rolled",
    )
    assert r.flange.classification == "slender"
    assert r.web.classification == "compact"
    assert r.section_classification == "slender"


# ---------------------------------------------------------------------------
# Report plumbing
# ---------------------------------------------------------------------------
def test_report_is_frozen() -> None:
    sec = DoublySymmetricISection(100.0 * u.mm, 6.0 * u.mm, 300.0 * u.mm, 4.0 * u.mm)
    r = classify_flexural_compactness_B4_1b(sec.compute_section_properties(), A992)
    with pytest.raises(FrozenInstanceError):
        r.section_classification = "slender"  # type: ignore[misc]


def test_report_carries_aisc_citations() -> None:
    sec = DoublySymmetricISection(100.0 * u.mm, 6.0 * u.mm, 300.0 * u.mm, 4.0 * u.mm)
    r = classify_flexural_compactness_B4_1b(sec.compute_section_properties(), A992)
    sections = {c.section for c in r.cited_clauses}
    assert "B4.1b" in sections
    assert "Table B4.1b" in sections


def test_report_returns_FlexuralCompactnessReport_instance() -> None:
    sec = DoublySymmetricISection(100.0 * u.mm, 6.0 * u.mm, 300.0 * u.mm, 4.0 * u.mm)
    r = classify_flexural_compactness_B4_1b(sec.compute_section_properties(), A992)
    assert isinstance(r, FlexuralCompactnessReport)


def test_material_with_lower_Fy_yields_more_generous_limits() -> None:
    # A36 (Fy=36 ksi) has larger sqrt(E/Fy) than A992 (Fy=50 ksi), so
    # limits should be larger.
    sec = DoublySymmetricISection(100.0 * u.mm, 6.0 * u.mm, 300.0 * u.mm, 4.0 * u.mm)
    props = sec.compute_section_properties()
    r_A992 = classify_flexural_compactness_B4_1b(props, A992, "rolled")
    r_A36 = classify_flexural_compactness_B4_1b(props, A36, "rolled")
    assert r_A36.flange.compact_limit_lambda_p > r_A992.flange.compact_limit_lambda_p  # type: ignore[operator]
    assert r_A36.web.compact_limit_lambda_p > r_A992.web.compact_limit_lambda_p  # type: ignore[operator]
