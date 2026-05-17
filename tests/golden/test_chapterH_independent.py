"""Independent correctness anchor for the AISC 360-22 Chapter-H facade.

Pins the ``apeSteel.combined`` calculators to a from-scratch AISC
360-22 re-derivation (:mod:`tests.golden._chapterH_aisc_oracle`) that
imports nothing from :mod:`apeSteel.combined`.  Chapter H is an
interaction chapter, so the *available strengths* ``Pc``/``Mc`` are the
test inputs (exactly as the Chapter-E/F oracles take section
properties); only the Chapter-H composition is checked.  Agreement is
expected **bit-exact** (same spec equations, independently written).

Phase H-1 scope: §H1.1 Eq. H1-1a / H1-1b.  Later phases extend this
file as their calculators land.
"""

from __future__ import annotations

import math

import pytest

from apeSteel.combined import (
    compute_Cb_amplification_factor_H1_2,
    compute_combined_strength_H1_1,
    compute_combined_strength_H1_2,
    compute_combined_strength_H1_3,
    compute_combined_strength_H2,
    compute_combined_strength_H3_2,
    compute_nonHSS_torsion_limit_H3_3,
    compute_Pey_H1_2,
    compute_torsional_strength_rect_HSS_H3_1,
    compute_torsional_strength_round_HSS_H3_1,
)
from tests.golden._chapterH_aisc_oracle import (
    Pey_H1_2,
    cb_amplification_H1_2,
    interaction_H1_1,
    interaction_H1_3_in_plane,
    interaction_H1_3_out_of_plane,
    interaction_H2,
    interaction_H3_2,
    nonHSS_limiting_Fn_H3_3,
    torsion_rect_HSS_H3_1,
    torsion_round_HSS_H3_1,
)

# Stronger than the doctrine's 1e-9 floor: the facade and the oracle
# evaluate the *same* float expression with the same literals, so they
# must agree to full double precision.
REL_TOL = 1e-12

# (Pr, Pc, Mrx, Mcx, Mry, Mcy) - spans both regimes, uniaxial &
# biaxial, the exact Pr/Pc = 0.2 boundary, pure-axial, and a failing
# case (DCR > 1).
_H1_1_CASES: tuple[tuple[float, float, float, float, float, float], ...] = (
    (180.0, 900.0, 2400.0, 4800.0, 0.0, 0.0),  # ratio 0.20 -> H1-1a (boundary)
    (400.0, 1000.0, 1000.0, 5000.0, 200.0, 1500.0),  # 0.40 H1-1a biaxial
    (700.0, 1000.0, 1200.0, 6000.0, 0.0, 0.0),  # 0.70 H1-1a, near unity
    (50.0, 1000.0, 3000.0, 5000.0, 0.0, 0.0),  # 0.05 -> H1-1b
    (90.0, 900.0, 2400.0, 4800.0, 600.0, 1200.0),  # 0.10 H1-1b biaxial, FAILS
    (200.0, 1000.0, 0.0, 1.0, 0.0, 0.0),  # pure axial, ratio 0.20 -> H1-1a
    (10.0, 1000.0, 4000.0, 5000.0, 0.0, 0.0),  # 0.01 H1-1b moment-dominated
    (5.0, 1000.0, 0.0, 1.0, 950.0, 1000.0),  # Mry only, Mrx == 0
    (2.5e6, 9.0e6, 1.8e8, 4.2e8, 3.0e7, 1.1e8),  # realistic N / N*mm magnitudes
)


@pytest.mark.parametrize(("Pr", "Pc", "Mrx", "Mcx", "Mry", "Mcy"), _H1_1_CASES)
def test_H1_1_facade_matches_independent_oracle(
    Pr: float,
    Pc: float,
    Mrx: float,
    Mcx: float,
    Mry: float,
    Mcy: float,
) -> None:
    rep = compute_combined_strength_H1_1(Pr, Pc, Mrx, Mcx, Mry, Mcy)
    ora = interaction_H1_1(Pr, Pc, Mrx, Mcx, Mry, Mcy)

    assert rep.governing_equation == ora.equation
    assert rep.governing_limit_state == ora.equation
    assert math.isclose(rep.demand_capacity_ratio, ora.dcr, rel_tol=REL_TOL)
    assert rep.unity_check_passes is ora.passes
    # The facade carries no extra phi - it is a pure interaction check.
    assert rep.phi_LRFD == 1.0


def test_H1_1_facade_guards_match_oracle() -> None:
    with pytest.raises(ValueError, match="available_axial_Pc must be positive"):
        compute_combined_strength_H1_1(100.0, 0.0, 100.0, 200.0)
    with pytest.raises(ValueError, match="available_moment_x_Mcx must be positive"):
        compute_combined_strength_H1_1(100.0, 900.0, 50.0, 0.0)
    with pytest.raises(ValueError, match="available_moment_y_Mcy must be positive"):
        compute_combined_strength_H1_1(100.0, 900.0, 0.0, 1.0, 50.0, 0.0)


# --------------------------------------------------------------------------- #
# §H1.2 - flexure + axial tension.  Same Eq. H1-1a/1b kernel (anchored
# against the oracle's interaction_H1_1 with the tension Pc), plus the
# Cb amplifier sqrt(1 + alpha*Pr/Pey).
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(("Pr", "Pc", "Mrx", "Mcx", "Mry", "Mcy"), _H1_1_CASES)
def test_H1_2_interaction_matches_independent_oracle(
    Pr: float,
    Pc: float,
    Mrx: float,
    Mcx: float,
    Mry: float,
    Mcy: float,
) -> None:
    # §H1.2 reuses the §H1.1 unity equation with the tensile Pc.
    rep = compute_combined_strength_H1_2(Pr, Pc, Mrx, Mcx, Mry, Mcy)
    ora = interaction_H1_1(Pr, Pc, Mrx, Mcx, Mry, Mcy)
    assert rep.governing_equation == ora.equation
    assert math.isclose(rep.demand_capacity_ratio, ora.dcr, rel_tol=REL_TOL)
    assert rep.unity_check_passes is ora.passes
    # §H1.2 citation block (not §H1.1).
    assert any(c.section == "H1.2" for c in rep.cited_clauses)


_PEY_CASES: tuple[tuple[float, float, float, float], ...] = (
    (500.0e3, 200000.0, 20.0e6, 4000.0),
    (1.2e6, 200000.0, 45.0e6, 6000.0),
    (0.0, 210000.0, 12.5e6, 3500.0),  # zero tension -> amplifier == 1.0
    (2.0e6, 200000.0, 90.0e6, 8000.0),
)


@pytest.mark.parametrize(("Pr", "E", "Iy", "Lb"), _PEY_CASES)
def test_H1_2_Pey_and_Cb_amplifier_match_independent_oracle(
    Pr: float,
    E: float,
    Iy: float,
    Lb: float,
) -> None:
    pey_fac = compute_Pey_H1_2(E, Iy, Lb)
    pey_ora = Pey_H1_2(E, Iy, Lb)
    assert math.isclose(pey_fac, pey_ora, rel_tol=REL_TOL)

    cb_fac = compute_Cb_amplification_factor_H1_2(Pr, E, Iy, Lb, alpha=1.0)
    cb_ora = cb_amplification_H1_2(Pr, pey_ora, alpha=1.0)
    assert math.isclose(cb_fac, cb_ora, rel_tol=REL_TOL)
    assert cb_fac >= 1.0


def test_H1_2_amplifier_guards() -> None:
    with pytest.raises(ValueError, match="unbraced_length_Lb must be positive"):
        compute_Pey_H1_2(200000.0, 20.0e6, 0.0)
    with pytest.raises(ValueError, match="must be >= 0"):
        compute_Cb_amplification_factor_H1_2(-1.0, 200000.0, 20.0e6, 4000.0)


# --------------------------------------------------------------------------- #
# §H1.3 - DS rolled compact, single-axis.  Both sub-checks (in-plane
# Eq. H1-1, out-of-plane Eq. H1-2 with the min(Cb*Mcx, phi_b*Mp) cap)
# must bit-match the independent oracle.
# (Pr, Pcx, Pcy, Mrx, Mcx_in_plane, Mcx_ltb_Cb1, Cb, phi_b_Mp)
# --------------------------------------------------------------------------- #
_H1_3_CASES: tuple[tuple[float, float, float, float, float, float, float, float], ...] = (
    # cap inactive (Cb*Mcx < phi_b*Mp); out-of-plane governs
    (600.0e3, 3.0e6, 2.0e6, 250.0e6, 600.0e6, 480.0e6, 1.14, 660.0e6),
    # cap active (Cb*Mcx > phi_b*Mp -> use phi_b*Mp)
    (400.0e3, 3.2e6, 2.4e6, 300.0e6, 620.0e6, 560.0e6, 1.67, 600.0e6),
    # in-plane governs (weak in-plane Pcx, strong out-of-plane)
    (1.4e6, 1.6e6, 3.0e6, 120.0e6, 640.0e6, 600.0e6, 2.30, 660.0e6),
    # low axial -> in-plane uses H1-1b; out-of-plane mild
    (90.0e3, 3.0e6, 2.8e6, 380.0e6, 600.0e6, 560.0e6, 1.00, 620.0e6),
    # both well below unity
    (200.0e3, 4.0e6, 3.6e6, 150.0e6, 650.0e6, 610.0e6, 1.30, 670.0e6),
)


@pytest.mark.parametrize(
    ("Pr", "Pcx", "Pcy", "Mrx", "Mcx_ip", "Mcx_ltb", "Cb", "phi_b_Mp"),
    _H1_3_CASES,
)
def test_H1_3_facade_matches_independent_oracle(
    Pr: float,
    Pcx: float,
    Pcy: float,
    Mrx: float,
    Mcx_ip: float,
    Mcx_ltb: float,
    Cb: float,
    phi_b_Mp: float,
) -> None:
    rep = compute_combined_strength_H1_3(Pr, Pcx, Pcy, Mrx, Mcx_ip, Mcx_ltb, Cb, phi_b_Mp)
    ora_ip = interaction_H1_3_in_plane(Pr, Pcx, Mrx, Mcx_ip)
    ora_oop = interaction_H1_3_out_of_plane(Pr, Pcy, Mrx, Cb, Mcx_ltb, phi_b_Mp)

    # in-plane sub-check bit-exact
    assert rep.in_plane.governing_equation == ora_ip.equation
    assert math.isclose(rep.in_plane.demand_capacity_ratio, ora_ip.dcr, rel_tol=REL_TOL)
    # out-of-plane Eq. H1-2 bit-exact
    assert math.isclose(rep.out_of_plane_demand_capacity_ratio, ora_oop.dcr, rel_tol=REL_TOL)
    # governing selection + overall pass consistent with the oracle pair
    expected_overall = max(ora_ip.dcr, ora_oop.dcr)
    assert math.isclose(rep.demand_capacity_ratio, expected_overall, rel_tol=REL_TOL)
    assert rep.unity_check_passes is (ora_ip.passes and ora_oop.passes)
    assert rep.governing_check == ("out_of_plane" if ora_oop.dcr >= ora_ip.dcr else "in_plane")


def test_H1_3_guards_and_applicability() -> None:
    with pytest.raises(ValueError, match="available_axial_in_plane_Pcx must be positive"):
        compute_combined_strength_H1_3(100.0e3, 0.0, 2.0e6, 100.0e6, 600.0e6, 500.0e6, 1.0, 660.0e6)
    with pytest.raises(ValueError, match="available_axial_out_of_plane_Pcy must be positive"):
        compute_combined_strength_H1_3(100.0e3, 3.0e6, 0.0, 100.0e6, 600.0e6, 500.0e6, 1.0, 660.0e6)


# --------------------------------------------------------------------------- #
# §H2 - unsymmetric / other members.  Signed elastic-stress interaction
# Eq. H2-1, bit-exact vs the oracle.
# (fra, Fca, frbw, Fcbw, frbz, Fcbz) - signed required, positive available
# --------------------------------------------------------------------------- #
_H2_CASES: tuple[tuple[float, float, float, float, float, float], ...] = (
    (-50.0, 150.0, 80.0, 200.0, 20.0, 100.0),  # mixed signs, passes
    (120.0, 200.0, 90.0, 180.0, 40.0, 90.0),  # 1.544 -> fails
    (0.0, 100.0, 150.0, 200.0, 0.0, 50.0),  # pure flexure, 0.75
    (-200.0, 250.0, -60.0, 150.0, 30.0, 120.0),  # |sum| = 0.95
    (300.0, 300.0, 0.0, 1.0, 0.0, 1.0),  # exactly 1.0 boundary -> passes
)


@pytest.mark.parametrize(("fra", "Fca", "frbw", "Fcbw", "frbz", "Fcbz"), _H2_CASES)
def test_H2_facade_matches_independent_oracle(
    fra: float,
    Fca: float,
    frbw: float,
    Fcbw: float,
    frbz: float,
    Fcbz: float,
) -> None:
    rep = compute_combined_strength_H2(fra, Fca, frbw, Fcbw, frbz, Fcbz)
    ora = interaction_H2(fra, Fca, frbw, Fcbw, frbz, Fcbz)
    assert rep.governing_limit_state == ora.equation
    assert math.isclose(rep.demand_capacity_ratio, ora.dcr, rel_tol=REL_TOL)
    assert rep.unity_check_passes is ora.passes
    assert rep.phi_LRFD == 1.0


def test_H2_facade_guards_match_oracle() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        compute_combined_strength_H2(10.0, 0.0, 10.0, 100.0, 10.0, 100.0)
    with pytest.raises(ValueError, match="must be positive"):
        compute_combined_strength_H2(10.0, 100.0, 10.0, 0.0, 10.0, 100.0)
    with pytest.raises(ValueError, match="must be positive"):
        compute_combined_strength_H2(10.0, 100.0, 10.0, 100.0, 10.0, -1.0)


# --------------------------------------------------------------------------- #
# §H3.1 round HSS - (Fy, E, D, t, L); buckling- vs cap-governed.
# --------------------------------------------------------------------------- #
_ROUND_HSS_CASES: tuple[tuple[float, float, float, float, float], ...] = (
    (345.0, 200000.0, 200.0, 10.0, 3000.0),  # thick/short -> 0.6Fy cap
    (345.0, 200000.0, 350.0, 4.0, 9000.0),  # thin/long -> buckling (H3-2a)
    (250.0, 200000.0, 300.0, 6.0, 6000.0),  # mid -> buckling, lower Fy
    (345.0, 200000.0, 320.0, 4.0, 12800.0),  # thin + very long -> Eq. H3-2b
)


@pytest.mark.parametrize(("Fy", "E", "D", "t", "L"), _ROUND_HSS_CASES)
def test_H3_1_round_HSS_matches_independent_oracle(
    Fy: float, E: float, D: float, t: float, L: float
) -> None:
    rep = compute_torsional_strength_round_HSS_H3_1(Fy, E, D, t, L)
    ora = torsion_round_HSS_H3_1(Fy, E, D, t, L)
    assert rep.governing_torsion_state == ora.governing
    assert math.isclose(rep.critical_stress_Fcr, ora.Fcr, rel_tol=REL_TOL)
    assert math.isclose(rep.torsional_constant_C, ora.C, rel_tol=REL_TOL)
    assert math.isclose(rep.nominal_torsional_strength_Tn, ora.Tn, rel_tol=REL_TOL)
    # phi_T = 0.90
    assert math.isclose(rep.phi_strength_LRFD, 0.90 * ora.Tn, rel_tol=REL_TOL)


# --------------------------------------------------------------------------- #
# §H3.1 rect HSS - (Fy, E, h/t, C); one case per regime + the >260 guard.
# --------------------------------------------------------------------------- #
def _rect_ht(coeff: float, Fy: float = 345.0, E: float = 200000.0) -> float:
    return coeff * math.sqrt(E / Fy)


_RECT_HSS_CASES: tuple[tuple[float, float, float, float], ...] = (
    (345.0, 200000.0, 0.5 * _rect_ht(2.45), 1.0e6),  # < 2.45 sqrt -> 0.6Fy
    (345.0, 200000.0, _rect_ht(2.76), 1.0e6),  # H3-4 band
    (345.0, 200000.0, _rect_ht(4.0), 1.0e6),  # H3-5 band
    (250.0, 200000.0, _rect_ht(3.5, 250.0), 8.0e5),  # H3-5 band, lower Fy
)


@pytest.mark.parametrize(("Fy", "E", "h_t", "C"), _RECT_HSS_CASES)
def test_H3_1_rect_HSS_matches_independent_oracle(
    Fy: float, E: float, h_t: float, C: float
) -> None:
    rep = compute_torsional_strength_rect_HSS_H3_1(Fy, E, h_t, C)
    ora = torsion_rect_HSS_H3_1(Fy, E, h_t, C)
    assert rep.governing_torsion_state == ora.governing
    assert math.isclose(rep.critical_stress_Fcr, ora.Fcr, rel_tol=REL_TOL)
    assert math.isclose(rep.nominal_torsional_strength_Tn, ora.Tn, rel_tol=REL_TOL)


def test_H3_1_rect_HSS_over_260_raises_like_oracle() -> None:
    with pytest.raises(ValueError, match="260"):
        compute_torsional_strength_rect_HSS_H3_1(345.0, 200000.0, 300.0, 1.0e6)
    with pytest.raises(ValueError, match="over 260"):
        torsion_rect_HSS_H3_1(345.0, 200000.0, 300.0, 1.0e6)


# --------------------------------------------------------------------------- #
# §H3.2 HSS combined (Eq. H3-6) - neglect path + interaction.
# (Pr, Pc, Mr, Mc, Vr, Vc, Tr, Tc)
# --------------------------------------------------------------------------- #
_H3_2_CASES: tuple[tuple[float, float, float, float, float, float, float, float], ...] = (
    (100.0, 900.0, 200.0, 400.0, 50.0, 300.0, 10.0, 100.0),  # Tr<=0.2Tc neglect
    (100.0, 900.0, 200.0, 400.0, 50.0, 300.0, 30.0, 100.0),  # combined
    (500.0, 800.0, 300.0, 500.0, 120.0, 250.0, 90.0, 110.0),  # combined, near/over 1
)


@pytest.mark.parametrize(("Pr", "Pc", "Mr", "Mc", "Vr", "Vc", "Tr", "Tc"), _H3_2_CASES)
def test_H3_2_facade_matches_independent_oracle(
    Pr: float,
    Pc: float,
    Mr: float,
    Mc: float,
    Vr: float,
    Vc: float,
    Tr: float,
    Tc: float,
) -> None:
    rep = compute_combined_strength_H3_2(Pr, Pc, Mr, Mc, Vr, Vc, Tr, Tc)
    ora_res, ora_negligible = interaction_H3_2(Pr, Pc, Mr, Mc, Vr, Vc, Tr, Tc)
    assert rep.torsion_is_negligible is ora_negligible
    if ora_negligible:
        assert ora_res is None
        assert rep.governing_limit_state == "torsion_negligible_H1"
        assert rep.unity_check_passes is True
    else:
        assert ora_res is not None
        assert math.isclose(rep.demand_capacity_ratio, ora_res.dcr, rel_tol=REL_TOL)
        assert rep.unity_check_passes is ora_res.passes
        assert rep.governing_limit_state == "H3-6"


def test_H3_2_guards() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        compute_combined_strength_H3_2(1.0, 0.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0)
    with pytest.raises(ValueError, match="must be positive"):
        compute_combined_strength_H3_2(1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.0)


# --------------------------------------------------------------------------- #
# §H3.3 non-HSS limiting Fn (Eq. H3-7/8/9).
# --------------------------------------------------------------------------- #
def test_H3_3_nonHSS_limiting_Fn_matches_independent_oracle() -> None:
    # No Fcr -> governing is 0.6Fy (Eq. H3-8).
    rep = compute_nonHSS_torsion_limit_H3_3(345.0)
    _, _, _, fn_gov, label = nonHSS_limiting_Fn_H3_3(345.0)
    assert rep.governing_limit_state == label
    assert math.isclose(rep.governing_Fn, fn_gov, rel_tol=REL_TOL)

    # With a low Fcr -> buckling (Eq. H3-9) governs; C -> Tn.
    rep2 = compute_nonHSS_torsion_limit_H3_3(
        345.0, buckling_stress_Fcr=120.0, torsional_constant_C=5.0e5
    )
    _, _, _, fn_gov2, label2 = nonHSS_limiting_Fn_H3_3(345.0, Fcr=120.0)
    assert rep2.governing_limit_state == label2
    assert math.isclose(rep2.governing_Fn, fn_gov2, rel_tol=REL_TOL)
    assert rep2.nominal_torsional_strength_Tn is not None
    assert math.isclose(rep2.nominal_torsional_strength_Tn, 120.0 * 5.0e5, rel_tol=REL_TOL)
    assert math.isclose(rep2.phi_strength_LRFD, 0.90 * 120.0 * 5.0e5, rel_tol=REL_TOL)


def test_H3_input_guards() -> None:
    # Round HSS geometry guards.
    with pytest.raises(ValueError, match="yield_stress_Fy must be positive"):
        compute_torsional_strength_round_HSS_H3_1(0.0, 200000.0, 200.0, 10.0, 3000.0)
    with pytest.raises(ValueError, match="must be positive"):
        compute_torsional_strength_round_HSS_H3_1(345.0, 200000.0, 200.0, -1.0, 3000.0)
    with pytest.raises(ValueError, match="less than outside_diameter_D"):
        compute_torsional_strength_round_HSS_H3_1(345.0, 200000.0, 200.0, 200.0, 3000.0)
    with pytest.raises(ValueError, match="member_length_L must be positive"):
        compute_torsional_strength_round_HSS_H3_1(345.0, 200000.0, 200.0, 10.0, 0.0)
    # Rect HSS guards.
    with pytest.raises(ValueError, match="yield_stress_Fy must be positive"):
        compute_torsional_strength_rect_HSS_H3_1(0.0, 200000.0, 50.0, 1.0e6)
    with pytest.raises(ValueError, match="flat_width_to_thickness"):
        compute_torsional_strength_rect_HSS_H3_1(345.0, 200000.0, 0.0, 1.0e6)
    with pytest.raises(ValueError, match="torsional_constant_C must be positive"):
        compute_torsional_strength_rect_HSS_H3_1(345.0, 200000.0, 50.0, 0.0)
    # Non-HSS §H3.3 guards.
    with pytest.raises(ValueError, match="yield_stress_Fy must be positive"):
        compute_nonHSS_torsion_limit_H3_3(0.0)
    with pytest.raises(ValueError, match="buckling_stress_Fcr must be positive"):
        compute_nonHSS_torsion_limit_H3_3(345.0, buckling_stress_Fcr=0.0)
    with pytest.raises(ValueError, match="torsional_constant_C must be positive"):
        compute_nonHSS_torsion_limit_H3_3(345.0, torsional_constant_C=-1.0)


def test_H1_3_out_of_plane_denominator_guard() -> None:
    # Cb*Mcx = 0 and phi_b*Mp = 0 -> min(.) = 0 -> Eq. H1-2 denominator guard.
    with pytest.raises(ValueError, match="H1-2 denominator"):
        compute_combined_strength_H1_3(100.0e3, 3.0e6, 2.0e6, 100.0e6, 600.0e6, 0.0, 0.0, 0.0)
