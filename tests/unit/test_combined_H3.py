"""Reviewer-signable hand calcs for AISC 360-22 §H3.

§H3.1 Tn=Fcr*C (round Eq. H3-2a/2b, rect Eq. H3-4/5), §H3.2 Eq. H3-6,
§H3.3 limiting Fn (Eq. H3-7/8/9).  Bit-exact anchor in
``tests/golden/test_chapterH_independent.py``.  Base units: MPa, mm,
N, N*mm.
"""

from __future__ import annotations

import math

from apeSteel.combined import (
    CombinedH32Report,
    NonHSSTorsionH33Report,
    TorsionH3Report,
    compute_combined_strength_H3_2,
    compute_nonHSS_torsion_limit_H3_3,
    compute_torsional_strength_rect_HSS_H3_1,
    compute_torsional_strength_round_HSS_H3_1,
)

_REL = 1e-12


def test_H3_1_round_HSS_cap_governs_hand_calc() -> None:
    # AISC 360-22 §H3.1(a), Eq. H3-1/H3-2a/H3-2b, p. 16.1-86.
    #   Fy=345, E=200000, D=200, t=10, L=3000  -> D/t = 20
    #   Fcr,2a = 1.23E/(sqrt(L/D)*(D/t)^1.25) ~ 1502 MPa
    #   Fcr,2b = 0.60E/(D/t)^1.5             ~ 1342 MPa
    #   max(.) = 1502 >= 0.6Fy = 207  -> Fcr = 0.6*345 = 207 (shear yield)
    #   C  = pi*(D-t)^2*t/2 = pi*190^2*10/2
    #   Tn = Fcr*C ; phi_T = 0.90
    rep = compute_torsional_strength_round_HSS_H3_1(345.0, 200000.0, 200.0, 10.0, 3000.0)
    assert isinstance(rep, TorsionH3Report)
    assert rep.governing_torsion_state == "shear_yielding_0p6Fy"
    assert math.isclose(rep.critical_stress_Fcr, 0.6 * 345.0, rel_tol=_REL)
    c_expected = math.pi * (200.0 - 10.0) ** 2 * 10.0 / 2.0
    assert math.isclose(rep.torsional_constant_C, c_expected, rel_tol=_REL)
    assert math.isclose(rep.nominal_torsional_strength_Tn, 207.0 * c_expected, rel_tol=_REL)
    assert math.isclose(rep.phi_strength_LRFD, 0.90 * 207.0 * c_expected, rel_tol=_REL)


def test_H3_1_round_HSS_buckling_governs_hand_calc() -> None:
    # Thin/long pipe -> buckling Fcr below the 0.6Fy cap.
    fy, e_mod, d, t, ell = 345.0, 200000.0, 350.0, 4.0, 9000.0
    dt = d / t
    fcr_2a = 1.23 * e_mod / (math.sqrt(ell / d) * dt**1.25)
    fcr_2b = 0.60 * e_mod / dt**1.5
    fcr_expected = max(fcr_2a, fcr_2b)
    assert fcr_expected < 0.6 * fy  # confirm buckling, not the cap
    rep = compute_torsional_strength_round_HSS_H3_1(fy, e_mod, d, t, ell)
    assert rep.governing_torsion_state in ("H3-2a", "H3-2b")
    assert math.isclose(rep.critical_stress_Fcr, fcr_expected, rel_tol=_REL)


def test_H3_1_rect_HSS_H3_4_band_hand_calc() -> None:
    # h/t in the Eq. H3-4 band: Fcr = 0.6*Fy * (2.45*sqrt(E/Fy)) / (h/t).
    fy, e_mod, c_const = 345.0, 200000.0, 1.0e6
    s = math.sqrt(e_mod / fy)
    h_t = 2.76 * s  # between 2.45 s and 3.07 s
    rep = compute_torsional_strength_rect_HSS_H3_1(fy, e_mod, h_t, c_const)
    assert rep.governing_torsion_state == "H3-4"
    fcr_expected = 0.6 * fy * (2.45 * s) / h_t
    assert math.isclose(rep.critical_stress_Fcr, fcr_expected, rel_tol=_REL)
    assert math.isclose(rep.nominal_torsional_strength_Tn, fcr_expected * c_const, rel_tol=_REL)


def test_H3_2_torsion_negligible_reverts_to_H1() -> None:
    # Tr = 10 <= 0.2*Tc = 20 -> torsion neglected, check by §H1.
    rep = compute_combined_strength_H3_2(100.0, 900.0, 200.0, 400.0, 50.0, 300.0, 10.0, 100.0)
    assert isinstance(rep, CombinedH32Report)
    assert rep.torsion_is_negligible is True
    assert rep.governing_limit_state == "torsion_negligible_H1"
    assert rep.demand_capacity_ratio == 0.0
    assert rep.unity_check_passes is True


def test_H3_2_combined_Eq_H3_6_hand_calc() -> None:
    # Tr = 30 > 0.2*Tc = 20 -> Eq. H3-6.
    #   (Pr/Pc + Mr/Mc) = 100/900 + 200/400 = 0.111111 + 0.5 = 0.611111
    #   (Vr/Vc + Tr/Tc) = 50/300 + 30/100  = 0.166667 + 0.3 = 0.466667
    #   DCR = 0.611111 + 0.466667^2 = 0.611111 + 0.217778 = 0.828889
    rep = compute_combined_strength_H3_2(100.0, 900.0, 200.0, 400.0, 50.0, 300.0, 30.0, 100.0)
    af = 100.0 / 900.0 + 200.0 / 400.0
    vt = 50.0 / 300.0 + 30.0 / 100.0
    assert rep.torsion_is_negligible is False
    assert math.isclose(rep.axial_flexure_term, af, rel_tol=_REL)
    assert math.isclose(rep.shear_torsion_term, vt, rel_tol=_REL)
    assert math.isclose(rep.demand_capacity_ratio, af + vt**2, rel_tol=_REL)
    assert rep.governing_limit_state == "H3-6"
    assert rep.unity_check_passes is True


def test_H3_3_nonHSS_limiting_Fn_hand_calc() -> None:
    # No Fcr -> min(Fy, 0.6Fy) = 0.6Fy (Eq. H3-8).
    rep = compute_nonHSS_torsion_limit_H3_3(345.0)
    assert isinstance(rep, NonHSSTorsionH33Report)
    assert rep.governing_limit_state == "H3-8"
    assert math.isclose(rep.governing_Fn, 0.6 * 345.0, rel_tol=_REL)
    assert rep.nominal_torsional_strength_Tn is None

    # Low Fcr -> buckling Eq. H3-9 governs; C -> Tn, phi_T=0.90.
    rep2 = compute_nonHSS_torsion_limit_H3_3(
        345.0, buckling_stress_Fcr=120.0, torsional_constant_C=5.0e5
    )
    assert rep2.governing_limit_state == "H3-9"
    assert math.isclose(rep2.governing_Fn, 120.0, rel_tol=_REL)
    assert rep2.nominal_torsional_strength_Tn is not None
    assert math.isclose(rep2.nominal_torsional_strength_Tn, 120.0 * 5.0e5, rel_tol=_REL)
    assert math.isclose(rep2.phi_strength_LRFD, 0.90 * 120.0 * 5.0e5, rel_tol=_REL)
