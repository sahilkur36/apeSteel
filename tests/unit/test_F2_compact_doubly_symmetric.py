"""Unit tests for compute_flexural_strength_F2_compact_doubly_symmetric."""

from __future__ import annotations

import math
from dataclasses import FrozenInstanceError

import pytest

from apeSteel import (
    A992,
    DoublySymmetricISection,
    FlexureF2Report,
    compute_flexural_strength_F2_compact_doubly_symmetric,
)
from apeSteel.core import units as u

DEFAULT_SECTION = DoublySymmetricISection(100.0 * u.mm, 6.0 * u.mm, 300.0 * u.mm, 4.0 * u.mm)


# ---------------------------------------------------------------------------
# Regime selection
# ---------------------------------------------------------------------------
def test_yielding_regime_for_Lb_less_than_Lp() -> None:
    """Default section: Lp = 0.866 m.  Lb = 0.5 m must yield."""
    r = compute_flexural_strength_F2_compact_doubly_symmetric(
        DEFAULT_SECTION.compute_section_properties(),
        A992,
        unbraced_length_Lb=0.5 * u.m,
        lateral_torsional_buckling_modification_factor_Cb=1.0,
    )
    assert r.governing_limit_state == "yielding"
    assert math.isclose(
        r.nominal_flexural_strength_Mn,
        r.plastic_moment_Mp,
        rel_tol=1e-12,
    )


def test_inelastic_LTB_regime_for_Lp_lt_Lb_le_Lr() -> None:
    """Default section: Lp=0.866 m, Lr=2.404 m.  Lb=1.5 m is inelastic."""
    r = compute_flexural_strength_F2_compact_doubly_symmetric(
        DEFAULT_SECTION.compute_section_properties(),
        A992,
        unbraced_length_Lb=1.5 * u.m,
        lateral_torsional_buckling_modification_factor_Cb=1.0,
    )
    assert r.governing_limit_state == "inelastic_LTB"
    # 0.7 Fy Sx < Mn < Mp at Cb = 1.0
    Mp = r.plastic_moment_Mp
    Fy = A992.yield_stress_Fy
    Sx = DEFAULT_SECTION.compute_section_properties().elastic_section_modulus_strong_axis_Sx
    assert 0.7 * Fy * Sx < r.nominal_flexural_strength_Mn < Mp


def test_elastic_LTB_regime_for_Lb_gt_Lr() -> None:
    r = compute_flexural_strength_F2_compact_doubly_symmetric(
        DEFAULT_SECTION.compute_section_properties(),
        A992,
        unbraced_length_Lb=5.0 * u.m,
        lateral_torsional_buckling_modification_factor_Cb=1.0,
    )
    assert r.governing_limit_state == "elastic_LTB"
    # Mn must equal Mcr (capped at Mp), and for Lb=5m  Mcr < Mp.
    assert math.isclose(
        r.nominal_flexural_strength_Mn,
        r.elastic_LTB_moment_Mcr,
        rel_tol=1e-12,
    )


# ---------------------------------------------------------------------------
# Caps - Mn <= Mp
# ---------------------------------------------------------------------------
def test_inelastic_LTB_with_high_Cb_is_capped_at_Mp() -> None:
    r = compute_flexural_strength_F2_compact_doubly_symmetric(
        DEFAULT_SECTION.compute_section_properties(),
        A992,
        unbraced_length_Lb=1.0 * u.m,  # just past Lp = 0.866 m
        lateral_torsional_buckling_modification_factor_Cb=3.0,
    )
    # With Cb = 3.0 the raw F2-2 result would exceed Mp; the facade must cap.
    assert math.isclose(
        r.nominal_flexural_strength_Mn,
        r.plastic_moment_Mp,
        rel_tol=1e-12,
    )


def test_elastic_LTB_with_high_Cb_caps_at_Mp_when_appropriate() -> None:
    # At Lb just past Lr, Cb=2 boosts Fcr enough to exceed Mp.
    r = compute_flexural_strength_F2_compact_doubly_symmetric(
        DEFAULT_SECTION.compute_section_properties(),
        A992,
        unbraced_length_Lb=2.5 * u.m,  # just past Lr = 2.404
        lateral_torsional_buckling_modification_factor_Cb=4.0,
    )
    # Mn must be <= Mp.
    assert r.nominal_flexural_strength_Mn <= r.plastic_moment_Mp + 1e-9


# ---------------------------------------------------------------------------
# phi factors
# ---------------------------------------------------------------------------
def test_phi_Mn_is_0p9_times_Mn() -> None:
    r = compute_flexural_strength_F2_compact_doubly_symmetric(
        DEFAULT_SECTION.compute_section_properties(),
        A992,
        unbraced_length_Lb=0.5 * u.m,
        lateral_torsional_buckling_modification_factor_Cb=1.0,
    )
    assert math.isclose(
        r.phi_strength_LRFD,
        0.90 * r.nominal_flexural_strength_Mn,
        rel_tol=1e-12,
    )
    assert r.phi_LRFD == 0.90


def test_omega_Mn_is_Mn_over_1p67() -> None:
    r = compute_flexural_strength_F2_compact_doubly_symmetric(
        DEFAULT_SECTION.compute_section_properties(),
        A992,
        unbraced_length_Lb=0.5 * u.m,
        lateral_torsional_buckling_modification_factor_Cb=1.0,
    )
    assert math.isclose(
        r.omega_strength_ASD,
        r.nominal_flexural_strength_Mn / 1.67,
        rel_tol=1e-12,
    )


# ---------------------------------------------------------------------------
# Both flanges - same code path called twice
# ---------------------------------------------------------------------------
def test_top_and_bottom_flange_LTB_are_independent_calls() -> None:
    """Different Lb values produce different reports - the function is
    pure, so this just verifies independence."""
    props = DEFAULT_SECTION.compute_section_properties()
    r_top = compute_flexural_strength_F2_compact_doubly_symmetric(
        props,
        A992,
        0.5 * u.m,
        1.0,
    )
    r_bot = compute_flexural_strength_F2_compact_doubly_symmetric(
        props,
        A992,
        4.0 * u.m,
        1.0,
    )
    assert r_top.governing_limit_state == "yielding"
    assert r_bot.governing_limit_state == "elastic_LTB"
    assert r_top.nominal_flexural_strength_Mn > r_bot.nominal_flexural_strength_Mn


# ---------------------------------------------------------------------------
# Plumbing
# ---------------------------------------------------------------------------
def test_invalid_Lb_raises() -> None:
    with pytest.raises(ValueError, match="positive"):
        compute_flexural_strength_F2_compact_doubly_symmetric(
            DEFAULT_SECTION.compute_section_properties(),
            A992,
            -1.0 * u.m,
            1.0,
        )


def test_report_is_frozen() -> None:
    r = compute_flexural_strength_F2_compact_doubly_symmetric(
        DEFAULT_SECTION.compute_section_properties(),
        A992,
        1.0 * u.m,
        1.0,
    )
    with pytest.raises(FrozenInstanceError):
        r.nominal_flexural_strength_Mn = 0.0  # type: ignore[misc]


def test_report_returns_FlexureF2Report_instance() -> None:
    r = compute_flexural_strength_F2_compact_doubly_symmetric(
        DEFAULT_SECTION.compute_section_properties(),
        A992,
        1.0 * u.m,
        1.0,
    )
    assert isinstance(r, FlexureF2Report)


def test_report_carries_all_F2_equation_citations() -> None:
    r = compute_flexural_strength_F2_compact_doubly_symmetric(
        DEFAULT_SECTION.compute_section_properties(),
        A992,
        1.0 * u.m,
        1.0,
    )
    equations = {c.equation for c in r.cited_clauses if c.equation is not None}
    for expected in ("F2-1", "F2-2", "F2-3", "F2-4", "F2-5", "F2-6", "F2-7"):
        assert expected in equations
