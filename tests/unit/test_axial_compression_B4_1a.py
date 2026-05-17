"""Unit tests for classify_axial_compression_B4_1a."""

from __future__ import annotations

import math
from dataclasses import FrozenInstanceError

import pytest

from apeSteel import (
    A992,
    AxialCompressionClassificationReport,
    DoublySymmetricISection,
    classify_axial_compression_B4_1a,
)
from apeSteel.classification import compute_kc_for_built_up_flange
from apeSteel.core import units as u


def test_default_section_rolled_construction() -> None:
    """100x6 / 300x4 at A992, rolled: flange non_slender, web slender."""
    sec = DoublySymmetricISection(
        flange_width_bf=100.0 * u.mm,
        flange_thickness_tf=6.0 * u.mm,
        web_clear_height_hw=300.0 * u.mm,
        web_thickness_tw=4.0 * u.mm,
    )
    props = sec.compute_section_properties()
    r = classify_axial_compression_B4_1a(props, A992, "rolled")

    sqrt_E_over_Fy = math.sqrt(A992.elastic_modulus_E / A992.yield_stress_Fy)

    # Flange Case 1: lambda = 8.33 vs lambda_r = 0.56*24.08 = 13.5
    assert math.isclose(r.flange.slenderness_ratio_lambda, 100.0 / 12.0, rel_tol=1e-12)
    assert math.isclose(r.flange.noncompact_limit_lambda_r, 0.56 * sqrt_E_over_Fy, rel_tol=1e-12)
    assert r.flange.compact_limit_lambda_p is None
    assert r.flange.aisc_case == "B4.1a Case 1"
    assert r.flange.classification == "non_slender"

    # Web Case 5: lambda = 75 vs lambda_r = 1.49*24.08 = 35.88 -> SLENDER
    assert math.isclose(r.web.slenderness_ratio_lambda, 75.0, rel_tol=1e-12)
    assert math.isclose(r.web.noncompact_limit_lambda_r, 1.49 * sqrt_E_over_Fy, rel_tol=1e-12)
    assert r.web.aisc_case == "B4.1a Case 5"
    assert r.web.classification == "slender"

    assert r.section_has_slender_element is True
    assert r.construction == "rolled"


def test_default_section_welded_uses_case_2_with_kc() -> None:
    sec = DoublySymmetricISection(
        flange_width_bf=100.0 * u.mm,
        flange_thickness_tf=6.0 * u.mm,
        web_clear_height_hw=300.0 * u.mm,
        web_thickness_tw=4.0 * u.mm,
    )
    props = sec.compute_section_properties()
    r = classify_axial_compression_B4_1a(props, A992, "welded")

    kc = compute_kc_for_built_up_flange(75.0)
    expected_lambda_rf = 0.64 * math.sqrt(kc * A992.elastic_modulus_E / A992.yield_stress_Fy)
    assert math.isclose(r.flange.noncompact_limit_lambda_r, expected_lambda_rf, rel_tol=1e-12)
    assert r.flange.aisc_case == "B4.1a Case 2"


@pytest.mark.parametrize(
    ("flange_thickness_tf_mm", "expected_class"),
    [
        (12.0, "non_slender"),  # bf/(2tf) = 4.17 << lambda_r=13.5
        (4.0, "non_slender"),  # 12.5 < 13.5
        (3.0, "slender"),  # 16.7 > 13.5
    ],
)
def test_flange_slender_transition_rolled(
    flange_thickness_tf_mm: float,
    expected_class: str,
) -> None:
    sec = DoublySymmetricISection(
        flange_width_bf=100.0 * u.mm,
        flange_thickness_tf=flange_thickness_tf_mm * u.mm,
        web_clear_height_hw=300.0 * u.mm,
        web_thickness_tw=20.0 * u.mm,
    )
    r = classify_axial_compression_B4_1a(sec.compute_section_properties(), A992, "rolled")
    assert r.flange.classification == expected_class


@pytest.mark.parametrize(
    ("web_thickness_tw_mm", "expected_class"),
    [
        (12.0, "non_slender"),  # h/tw = 25 < 35.88
        (8.5, "non_slender"),  # 35.3 < 35.88
        (4.0, "slender"),  # 75 > 35.88
    ],
)
def test_web_slender_transition(
    web_thickness_tw_mm: float,
    expected_class: str,
) -> None:
    sec = DoublySymmetricISection(
        flange_width_bf=200.0 * u.mm,
        flange_thickness_tf=20.0 * u.mm,
        web_clear_height_hw=300.0 * u.mm,
        web_thickness_tw=web_thickness_tw_mm * u.mm,
    )
    r = classify_axial_compression_B4_1a(sec.compute_section_properties(), A992, "rolled")
    assert r.web.classification == expected_class


def test_section_has_slender_element_is_or_of_elements() -> None:
    # Both non_slender
    sec = DoublySymmetricISection(
        200.0 * u.mm,
        20.0 * u.mm,
        300.0 * u.mm,
        12.0 * u.mm,
    )
    r = classify_axial_compression_B4_1a(sec.compute_section_properties(), A992)
    assert r.section_has_slender_element is False

    # One slender
    sec = DoublySymmetricISection(
        200.0 * u.mm,
        20.0 * u.mm,
        300.0 * u.mm,
        4.0 * u.mm,  # slender web
    )
    r = classify_axial_compression_B4_1a(sec.compute_section_properties(), A992)
    assert r.section_has_slender_element is True


def test_axial_classification_has_no_compact_limit() -> None:
    sec = DoublySymmetricISection(100.0 * u.mm, 6.0 * u.mm, 300.0 * u.mm, 4.0 * u.mm)
    r = classify_axial_compression_B4_1a(sec.compute_section_properties(), A992)
    # AISC Table B4.1a has only lambda_r; lambda_p must be None.
    assert r.flange.compact_limit_lambda_p is None
    assert r.web.compact_limit_lambda_p is None


def test_report_is_frozen() -> None:
    sec = DoublySymmetricISection(100.0 * u.mm, 6.0 * u.mm, 300.0 * u.mm, 4.0 * u.mm)
    r = classify_axial_compression_B4_1a(sec.compute_section_properties(), A992)
    with pytest.raises(FrozenInstanceError):
        r.section_has_slender_element = False  # type: ignore[misc]


def test_report_carries_AISC_E7_citation_for_slender_treatment() -> None:
    sec = DoublySymmetricISection(100.0 * u.mm, 6.0 * u.mm, 300.0 * u.mm, 4.0 * u.mm)
    r = classify_axial_compression_B4_1a(sec.compute_section_properties(), A992)
    sections = {c.section for c in r.cited_clauses}
    assert "B4.1a" in sections
    assert "E7" in sections


def test_report_returns_AxialCompressionClassificationReport_instance() -> None:
    sec = DoublySymmetricISection(100.0 * u.mm, 6.0 * u.mm, 300.0 * u.mm, 4.0 * u.mm)
    r = classify_axial_compression_B4_1a(sec.compute_section_properties(), A992)
    assert isinstance(r, AxialCompressionClassificationReport)
