"""Unit tests for compute_shear_strength_G2_doubly_symmetric."""

from __future__ import annotations

import math
from dataclasses import FrozenInstanceError

import pytest

from apeSteel import (
    A992,
    Bracing,
    DoublySymmetricISection,
    ShearG2Report,
    compute_shear_strength_G2_doubly_symmetric,
)
from apeSteel.core import units as u
from apeSteel.shear import compute_Cv1_three_regime, compute_kv_for_stiffened_web


# ---------------------------------------------------------------------------
# Three Cv1 regimes (using compute_Cv1_three_regime directly)
# ---------------------------------------------------------------------------
def test_Cv1_yielding_regime_returns_1p0() -> None:
    """lambda_w well below 1.10*sqrt(kv*E/Fy) -> Cv1 = 1.0."""
    Cv1, regime, _, _ = compute_Cv1_three_regime(
        web_slenderness_ratio_lambda_w=20.0,
        web_plate_buckling_coefficient_kv=5.34,
        elastic_modulus_E=200000.0,
        yield_stress_Fy=345.0,
    )
    assert Cv1 == 1.0
    assert regime == "yielding"


def test_Cv1_inelastic_regime_returns_linear_drop() -> None:
    """In inelastic band: Cv1 = 1.10*sqrt(kv*E/Fy) / lambda_w."""
    kv, E, Fy = 5.34, 200000.0, 345.0
    lambda_1 = 1.10 * math.sqrt(kv * E / Fy)
    lambda_2 = 1.37 * math.sqrt(kv * E / Fy)
    test_lam = (lambda_1 + lambda_2) / 2.0
    Cv1, regime, _, _ = compute_Cv1_three_regime(
        web_slenderness_ratio_lambda_w=test_lam,
        web_plate_buckling_coefficient_kv=kv,
        elastic_modulus_E=E,
        yield_stress_Fy=Fy,
    )
    assert regime == "inelastic_buckling"
    assert math.isclose(Cv1, lambda_1 / test_lam, rel_tol=1e-12)


def test_Cv1_elastic_regime_returns_inverse_lambda_squared() -> None:
    kv, E, Fy = 5.34, 200000.0, 345.0
    lam = 200.0  # well above lambda_2
    Cv1, regime, _, _ = compute_Cv1_three_regime(
        web_slenderness_ratio_lambda_w=lam,
        web_plate_buckling_coefficient_kv=kv,
        elastic_modulus_E=E,
        yield_stress_Fy=Fy,
    )
    assert regime == "elastic_buckling"
    expected = 1.51 * kv * E / (lam**2 * Fy)
    assert math.isclose(Cv1, expected, rel_tol=1e-12)


# ---------------------------------------------------------------------------
# kv helper
# ---------------------------------------------------------------------------
def test_kv_stiffened_small_a_uses_5_plus_term() -> None:
    """At small a/h (<= 3 and within bound), kv = 5 + 5/(a/h)^2."""
    kv = compute_kv_for_stiffened_web(
        web_slenderness_ratio_h_over_tw=75.0,
        transverse_stiffener_spacing_a=300.0,
        web_clear_height_h=300.0,
    )
    # a/h = 1 -> kv = 5 + 5/1 = 10
    assert math.isclose(kv, 10.0, rel_tol=1e-12)


def test_kv_stiffened_large_a_falls_back_to_5() -> None:
    """At a/h > 3, the formula reverts to kv = 5."""
    kv = compute_kv_for_stiffened_web(
        web_slenderness_ratio_h_over_tw=75.0,
        transverse_stiffener_spacing_a=1500.0,
        web_clear_height_h=300.0,
    )
    # a/h = 5 -> kv = 5
    assert kv == 5.0


# ---------------------------------------------------------------------------
# Stocky-rolled phi = 1.0 exception
# ---------------------------------------------------------------------------
def test_stocky_rolled_section_phi_is_1p00() -> None:
    """A stocky rolled section (h/tw <= 2.24*sqrt(E/Fy)) gets phi = 1.0."""
    stocky = DoublySymmetricISection(200 * u.mm, 15 * u.mm, 200 * u.mm, 15 * u.mm)  # h/tw=13.3
    r = compute_shear_strength_G2_doubly_symmetric(
        stocky.compute_section_properties(),
        A992,
        "rolled",
    )
    assert r.phi_LRFD == 1.00
    assert r.is_qualified_for_phi_1p00_stocky_rolled_exception


def test_welded_section_phi_is_0p9_even_if_stocky() -> None:
    """phi = 1.0 only applies to ROLLED sections, not welded."""
    stocky = DoublySymmetricISection(200 * u.mm, 15 * u.mm, 200 * u.mm, 15 * u.mm)
    r = compute_shear_strength_G2_doubly_symmetric(
        stocky.compute_section_properties(),
        A992,
        "welded",
    )
    assert r.phi_LRFD == 0.90
    assert not r.is_qualified_for_phi_1p00_stocky_rolled_exception


def test_slender_rolled_section_phi_is_0p9() -> None:
    """A slender rolled section (h/tw > 2.24*sqrt(E/Fy)) gets phi = 0.9."""
    slender = DoublySymmetricISection(300 * u.mm, 12 * u.mm, 800 * u.mm, 6 * u.mm)  # h/tw=133
    r = compute_shear_strength_G2_doubly_symmetric(
        slender.compute_section_properties(),
        A992,
        "rolled",
    )
    assert r.phi_LRFD == 0.90


# ---------------------------------------------------------------------------
# Aw = d * tw
# ---------------------------------------------------------------------------
def test_Aw_equals_d_times_tw() -> None:
    sec = DoublySymmetricISection(100 * u.mm, 6 * u.mm, 300 * u.mm, 4 * u.mm)
    props = sec.compute_section_properties()
    r = compute_shear_strength_G2_doubly_symmetric(props, A992, "welded")
    expected_Aw = props.overall_depth_d * props.web_thickness_tw
    assert math.isclose(r.web_area_Aw, expected_Aw, rel_tol=1e-12)


# ---------------------------------------------------------------------------
# Vn = 0.6 * Fy * Aw * Cv1
# ---------------------------------------------------------------------------
def test_Vn_matches_formula() -> None:
    sec = DoublySymmetricISection(100 * u.mm, 6 * u.mm, 300 * u.mm, 4 * u.mm)
    props = sec.compute_section_properties()
    r = compute_shear_strength_G2_doubly_symmetric(props, A992, "welded")
    expected = 0.6 * A992.yield_stress_Fy * r.web_area_Aw * r.web_shear_strength_coefficient_Cv1
    assert math.isclose(r.nominal_shear_strength_Vn, expected, rel_tol=1e-12)


# ---------------------------------------------------------------------------
# Element method
# ---------------------------------------------------------------------------
def test_element_shear_strength_G2_matches_pure_function() -> None:
    sec = DoublySymmetricISection(100 * u.mm, 6 * u.mm, 300 * u.mm, 4 * u.mm)
    element = sec.element(
        material=A992, construction="welded", bracing=Bracing(0.001 * u.m, 4.0 * u.m, 1.0)
    )
    pure_report = compute_shear_strength_G2_doubly_symmetric(
        element.section_properties,
        A992,
        "welded",
    )
    method_report = element.shear_strength_G2()
    assert method_report == pure_report


def test_element_shear_strength_G2_with_stiffener_propagates() -> None:
    sec = DoublySymmetricISection(100 * u.mm, 6 * u.mm, 300 * u.mm, 4 * u.mm)
    element = sec.element(material=A992, construction="welded")  # no bracing needed for shear
    r_no_stiff = element.shear_strength_G2()
    r_stiff = element.shear_strength_G2(transverse_stiffener_spacing_a=0.5 * u.m)
    # With stiffener: kv is higher -> Cv1 is higher -> Vn is higher.
    assert r_stiff.web_plate_buckling_coefficient_kv > r_no_stiff.web_plate_buckling_coefficient_kv
    assert r_stiff.nominal_shear_strength_Vn >= r_no_stiff.nominal_shear_strength_Vn


# ---------------------------------------------------------------------------
# Report plumbing
# ---------------------------------------------------------------------------
def test_report_is_frozen() -> None:
    sec = DoublySymmetricISection(100 * u.mm, 6 * u.mm, 300 * u.mm, 4 * u.mm)
    r = compute_shear_strength_G2_doubly_symmetric(
        sec.compute_section_properties(),
        A992,
        "welded",
    )
    with pytest.raises(FrozenInstanceError):
        r.nominal_shear_strength_Vn = 0.0  # type: ignore[misc]


def test_report_returns_ShearG2Report_instance() -> None:
    sec = DoublySymmetricISection(100 * u.mm, 6 * u.mm, 300 * u.mm, 4 * u.mm)
    r = compute_shear_strength_G2_doubly_symmetric(
        sec.compute_section_properties(),
        A992,
        "welded",
    )
    assert isinstance(r, ShearG2Report)


def test_report_carries_AISC_G2_citations() -> None:
    sec = DoublySymmetricISection(100 * u.mm, 6 * u.mm, 300 * u.mm, 4 * u.mm)
    r = compute_shear_strength_G2_doubly_symmetric(
        sec.compute_section_properties(),
        A992,
        "welded",
    )
    eqs = {c.equation for c in r.cited_clauses if c.equation is not None}
    for expected in ("G2-1", "G2-2", "G2-3", "G2-4", "G2-5"):
        assert expected in eqs
