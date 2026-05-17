"""Unit tests for compute_Cb_from_quarter_point_moments."""

from __future__ import annotations

import math

import pytest

from apeSteel import compute_Cb_from_quarter_point_moments


def test_cb_for_uniform_moment_equals_1() -> None:
    # All four moments equal -> Cb = 12.5/(2.5+3+4+3) = 12.5/12.5 = 1.
    cb = compute_Cb_from_quarter_point_moments(100.0, 100.0, 100.0, 100.0)
    assert math.isclose(cb, 1.0, rel_tol=1e-12)


def test_cb_for_simply_supported_parabolic_UDL_about_1p14() -> None:
    # Parabolic moment: M(x) = Mmax * 4*x*(L-x)/L^2.
    # At x=L/4: M = 0.75*Mmax; at L/2: Mmax; at 3L/4: 0.75*Mmax.
    Mmax = 100.0
    cb = compute_Cb_from_quarter_point_moments(Mmax, 0.75 * Mmax, Mmax, 0.75 * Mmax)
    # 12.5*100 / (2.5*100 + 3*75 + 4*100 + 3*75) = 1250 / 1100 = 1.1364
    assert math.isclose(cb, 1250.0 / 1100.0, rel_tol=1e-12)
    assert 1.10 < cb < 1.20


def test_cb_for_cantilever_with_tip_load_is_high() -> None:
    # Cantilever with tip load: M is linear, max at root, zero at tip.
    # Quarter-point moments along the unbraced length (root to tip):
    #   x=0 (root): Mmax. x=L/4: 0.75*Mmax. x=L/2: 0.5*Mmax.
    #   x=3L/4: 0.25*Mmax.
    # MA, MB, MC are at quarter, mid, three-quarter of the segment.
    Mmax = 100.0
    cb = compute_Cb_from_quarter_point_moments(Mmax, 0.75 * Mmax, 0.5 * Mmax, 0.25 * Mmax)
    # 1250 / (250 + 225 + 200 + 75) = 1250 / 750 = 1.667
    assert math.isclose(cb, 1250.0 / 750.0, rel_tol=1e-12)


def test_cb_raises_on_zero_denominator() -> None:
    with pytest.raises(ValueError, match="undefined"):
        compute_Cb_from_quarter_point_moments(0.0, 0.0, 0.0, 0.0)


def test_cb_uses_Rm_multiplicatively() -> None:
    cb1 = compute_Cb_from_quarter_point_moments(
        100.0, 50.0, 100.0, 50.0, cross_section_monosymmetry_parameter_Rm=1.0
    )
    cb05 = compute_Cb_from_quarter_point_moments(
        100.0, 50.0, 100.0, 50.0, cross_section_monosymmetry_parameter_Rm=0.5
    )
    assert math.isclose(cb05, 0.5 * cb1, rel_tol=1e-12)
