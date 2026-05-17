"""Unit tests for the F3-1 / F3-2 FLB primitives."""

from __future__ import annotations

import math

from apeSteel.flexure import (
    compute_flange_local_buckling_moment_Mn_F3_1,
    compute_flange_local_buckling_moment_Mn_F3_2,
)


def test_F3_1_at_lambda_pf_returns_Mp() -> None:
    """At lambda_f = lambda_pf, interpolation_fraction = 0 -> Mn = Mp."""
    Mp = 100.0
    result = compute_flange_local_buckling_moment_Mn_F3_1(
        plastic_moment_Mp=Mp,
        yield_stress_Fy=345.0,
        elastic_section_modulus_strong_axis_Sx=200.0,
        flange_slenderness_ratio_lambda_f=9.15,
        flange_compact_limit_lambda_pf=9.15,
        flange_noncompact_limit_lambda_rf=24.08,
    )
    assert math.isclose(result, Mp, rel_tol=1e-12)


def test_F3_1_at_lambda_rf_returns_0p7_Fy_Sx() -> None:
    """At lambda_f = lambda_rf, interpolation_fraction = 1 -> Mn = 0.7*Fy*Sx."""
    Mp = 1e9  # huge so interpolation has room to be linear
    Fy = 345.0
    Sx = 200_000.0
    result = compute_flange_local_buckling_moment_Mn_F3_1(
        plastic_moment_Mp=Mp,
        yield_stress_Fy=Fy,
        elastic_section_modulus_strong_axis_Sx=Sx,
        flange_slenderness_ratio_lambda_f=24.08,
        flange_compact_limit_lambda_pf=9.15,
        flange_noncompact_limit_lambda_rf=24.08,
    )
    assert math.isclose(result, 0.7 * Fy * Sx, rel_tol=1e-12)


def test_F3_1_is_monotonically_decreasing_in_lambda_f() -> None:
    """Mn_FLB should decrease as lambda_f increases in the non-compact band."""
    Mp = 1e9
    Fy = 345.0
    Sx = 200_000.0
    args = dict(
        plastic_moment_Mp=Mp,
        yield_stress_Fy=Fy,
        elastic_section_modulus_strong_axis_Sx=Sx,
        flange_compact_limit_lambda_pf=9.15,
        flange_noncompact_limit_lambda_rf=24.08,
    )
    prev = None
    for lam in [10.0, 12.0, 15.0, 18.0, 21.0, 24.0]:
        result = compute_flange_local_buckling_moment_Mn_F3_1(
            flange_slenderness_ratio_lambda_f=lam,
            **args,
        )
        if prev is not None:
            assert result < prev
        prev = result


def test_F3_2_matches_explicit_formula() -> None:
    """Mn = 0.9 * E * kc * Sx / lambda^2."""
    E = 200_000.0
    kc = 0.5
    Sx = 100_000.0
    lam = 25.0
    expected = 0.9 * E * kc * Sx / lam**2
    actual = compute_flange_local_buckling_moment_Mn_F3_2(
        elastic_section_modulus_strong_axis_Sx=Sx,
        elastic_modulus_E=E,
        flange_plate_buckling_coefficient_kc=kc,
        flange_slenderness_ratio_lambda_f=lam,
    )
    assert math.isclose(actual, expected, rel_tol=1e-12)


def test_F3_2_decreases_with_lambda() -> None:
    """Mn_FLB(slender) drops as lambda^-2."""
    kw = dict(
        elastic_section_modulus_strong_axis_Sx=100_000.0,
        elastic_modulus_E=200_000.0,
        flange_plate_buckling_coefficient_kc=0.6,
    )
    smaller_lam = compute_flange_local_buckling_moment_Mn_F3_2(
        flange_slenderness_ratio_lambda_f=25.0,
        **kw,
    )
    larger_lam = compute_flange_local_buckling_moment_Mn_F3_2(
        flange_slenderness_ratio_lambda_f=40.0,
        **kw,
    )
    assert smaller_lam > larger_lam
    # ratio should equal (40/25)^2 = 2.56
    assert math.isclose(smaller_lam / larger_lam, (40.0 / 25.0) ** 2, rel_tol=1e-12)
