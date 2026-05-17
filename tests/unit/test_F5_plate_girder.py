"""Unit tests for AISC §F5 (slender-web plate girder)."""

from __future__ import annotations

import math
from dataclasses import FrozenInstanceError

import pytest

from apeSteel import (
    A992,
    Bracing,
    DoublySymmetricISection,
    FlexureF5Report,
    compute_flexural_strength_F5_slender_web_plate_girder,
)
from apeSteel.core import units as u
from apeSteel.flexure import compute_aw_for_F5, compute_Rpg, compute_rt_for_F5

# A truly slender-web section: hw/tw = 600/4 = 150 > 137 = lambda_rw at A992
SLENDER_WEB_SECTION = DoublySymmetricISection(
    150.0 * u.mm,
    12.0 * u.mm,
    600.0 * u.mm,
    4.0 * u.mm,
)


# ---------------------------------------------------------------------------
# Primitives
# ---------------------------------------------------------------------------
def test_aw_is_bounded_at_10() -> None:
    """aw = h*tw / (bf*tf), capped at 10."""
    # Very thin flange to push aw above 10.
    aw = compute_aw_for_F5(
        web_clear_height_hc=1000.0,
        web_thickness_tw=10.0,
        compression_flange_width_bfc=100.0,
        compression_flange_thickness_tfc=5.0,
    )
    # raw = 10000 / 500 = 20 -> capped at 10
    assert aw == 10.0


def test_Rpg_is_1_when_web_below_threshold() -> None:
    """When h/tw <= 5.7*sqrt(E/Fy), no bend-buckling reduction."""
    Rpg = compute_Rpg(
        web_to_flange_area_ratio_aw=1.0,
        web_slenderness_ratio_h_over_tw=20.0,
        elastic_modulus_E=A992.elastic_modulus_E,
        yield_stress_Fy=A992.yield_stress_Fy,
    )
    assert Rpg == 1.0


def test_Rpg_decreases_above_threshold() -> None:
    Rpg = compute_Rpg(
        web_to_flange_area_ratio_aw=2.0,
        web_slenderness_ratio_h_over_tw=200.0,
        elastic_modulus_E=A992.elastic_modulus_E,
        yield_stress_Fy=A992.yield_stress_Fy,
    )
    assert 0.0 < Rpg < 1.0


def test_rt_matches_formula() -> None:
    """rt = bfc / sqrt(12 * (1 + aw/6))."""
    rt = compute_rt_for_F5(compression_flange_width_bfc=200.0, web_to_flange_area_ratio_aw=3.0)
    expected = 200.0 / math.sqrt(12.0 * (1.0 + 3.0 / 6.0))
    assert math.isclose(rt, expected, rel_tol=1e-12)


# ---------------------------------------------------------------------------
# Facade
# ---------------------------------------------------------------------------
def test_F5_routes_slender_web_section_to_compression_flange_yielding_at_short_Lb() -> None:
    r = compute_flexural_strength_F5_slender_web_plate_girder(
        SLENDER_WEB_SECTION.compute_section_properties(),
        A992,
        1.0 * u.m,
        1.0,
        "welded",
    )
    # Short Lb + compact flange -> CFY governs (LTB and FLB both equal CFY here).
    assert r.governing_F5_limit_state in {
        "compression_flange_yielding",
        "lateral_torsional_buckling",
    }


def test_F5_LTB_governs_at_long_Lb() -> None:
    r = compute_flexural_strength_F5_slender_web_plate_girder(
        SLENDER_WEB_SECTION.compute_section_properties(),
        A992,
        10.0 * u.m,
        1.0,
        "welded",
    )
    assert r.governing_F5_limit_state == "lateral_torsional_buckling"


def test_F5_Mn_capped_at_Mp() -> None:
    r = compute_flexural_strength_F5_slender_web_plate_girder(
        SLENDER_WEB_SECTION.compute_section_properties(),
        A992,
        1.0 * u.m,
        4.0,
        "welded",  # high Cb to push Mcr above Mp
    )
    assert r.nominal_flexural_strength_Mn <= r.plastic_moment_Mp + 1e-9


def test_F5_phi_factor_is_0p9() -> None:
    r = compute_flexural_strength_F5_slender_web_plate_girder(
        SLENDER_WEB_SECTION.compute_section_properties(),
        A992,
        1.0 * u.m,
        1.0,
        "welded",
    )
    assert r.phi_LRFD == 0.90
    assert math.isclose(
        r.phi_strength_LRFD,
        0.90 * r.nominal_flexural_strength_Mn,
        rel_tol=1e-12,
    )


def test_F5_invalid_Lb_raises() -> None:
    with pytest.raises(ValueError, match="positive"):
        compute_flexural_strength_F5_slender_web_plate_girder(
            SLENDER_WEB_SECTION.compute_section_properties(),
            A992,
            -1.0 * u.m,
            1.0,
            "welded",
        )


def test_F5_report_is_frozen() -> None:
    r = compute_flexural_strength_F5_slender_web_plate_girder(
        SLENDER_WEB_SECTION.compute_section_properties(),
        A992,
        1.0 * u.m,
        1.0,
        "welded",
    )
    with pytest.raises(FrozenInstanceError):
        r.nominal_flexural_strength_Mn = 0.0  # type: ignore[misc]


def test_F5_returns_FlexureF5Report_instance() -> None:
    r = compute_flexural_strength_F5_slender_web_plate_girder(
        SLENDER_WEB_SECTION.compute_section_properties(),
        A992,
        1.0 * u.m,
        1.0,
        "welded",
    )
    assert isinstance(r, FlexureF5Report)


# ---------------------------------------------------------------------------
# Element method
# ---------------------------------------------------------------------------
def test_element_F5_both_flanges_propagates_construction() -> None:
    e = SLENDER_WEB_SECTION.element(
        material=A992,
        construction="welded",
        bracing=Bracing(0.001 * u.m, 4.0 * u.m, 1.0),
    )
    both = e.flexural_strength_F5_both_flanges()
    assert both.top.construction == "welded"
    assert both.bot.construction == "welded"


def test_element_F5_both_flanges_governing_is_bot_with_long_bot_Lb() -> None:
    e = SLENDER_WEB_SECTION.element(
        material=A992,
        construction="welded",
        bracing=Bracing(0.001 * u.m, 4.0 * u.m, 1.0),
    )
    both = e.flexural_strength_F5_both_flanges()
    assert both.governing_flange == "bot"
