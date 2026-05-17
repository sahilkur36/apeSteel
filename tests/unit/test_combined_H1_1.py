"""Reviewer-signable hand calcs for AISC 360-22 §H1.1 (Eq. H1-1a/1b).

Each test states the AISC equation, substitutes by hand, and pins the
arithmetic.  The independent bit-exact anchor lives in
``tests/golden/test_chapterH_independent.py``; this file is the
hand-traceable companion a reviewer can sign.

All quantities in apeSteel base units (N, N*mm).
"""

from __future__ import annotations

import math

from apeSteel.combined import CombinedH1Report, compute_combined_strength_H1_1

_REL = 1e-12


def test_H1_1a_uniaxial_hand_calc() -> None:
    # AISC 360-22 §H1.1, Eq. H1-1a, p. 16.1-83.
    #   Pr = 800 kN, Pc = 2000 kN -> Pr/Pc = 0.400 >= 0.2  -> Eq. H1-1a
    #   Mrx = 150 kN*m, Mcx = 400 kN*m -> Mrx/Mcx = 0.375 ; Mry = 0
    #   DCR = Pr/Pc + 8/9*(Mrx/Mcx) = 0.400 + 8/9*0.375
    #       = 0.400 + 0.333333... = 0.733333...
    rep = compute_combined_strength_H1_1(
        required_axial_Pr=800.0e3,
        available_axial_Pc=2000.0e3,
        required_moment_x_Mrx=150.0e6,
        available_moment_x_Mcx=400.0e6,
    )
    assert isinstance(rep, CombinedH1Report)
    assert rep.governing_equation == "H1-1a"
    assert math.isclose(rep.axial_ratio_Pr_Pc, 0.40, rel_tol=_REL)
    assert math.isclose(rep.moment_ratio_term, 0.375, rel_tol=_REL)
    assert math.isclose(rep.demand_capacity_ratio, 0.40 + (8.0 / 9.0) * 0.375, rel_tol=_REL)
    assert math.isclose(rep.demand_capacity_ratio, 0.7333333333333333, rel_tol=_REL)
    assert rep.unity_check_passes is True


def test_H1_1b_biaxial_hand_calc() -> None:
    # AISC 360-22 §H1.1, Eq. H1-1b, p. 16.1-83.
    #   Pr = 100 kN, Pc = 2000 kN -> Pr/Pc = 0.050 < 0.2  -> Eq. H1-1b
    #   Mrx/Mcx = 200/500 = 0.40 ; Mry/Mcy = 30/120 = 0.25 ; sum = 0.65
    #   DCR = Pr/(2*Pc) + (Mrx/Mcx + Mry/Mcy) = 0.025 + 0.65 = 0.675
    rep = compute_combined_strength_H1_1(
        required_axial_Pr=100.0e3,
        available_axial_Pc=2000.0e3,
        required_moment_x_Mrx=200.0e6,
        available_moment_x_Mcx=500.0e6,
        required_moment_y_Mry=30.0e6,
        available_moment_y_Mcy=120.0e6,
    )
    assert rep.governing_equation == "H1-1b"
    assert math.isclose(rep.moment_ratio_term, 0.65, rel_tol=_REL)
    assert math.isclose(rep.demand_capacity_ratio, 0.025 + 0.65, rel_tol=_REL)
    assert rep.unity_check_passes is True


def test_H1_1a_overstressed_fails() -> None:
    # Pr/Pc = 1800/2000 = 0.90 >= 0.2 -> H1-1a
    # Mrx/Mcx = 200/400 = 0.50
    # DCR = 0.90 + 8/9*0.50 = 0.90 + 0.444444... = 1.344444... > 1.0
    rep = compute_combined_strength_H1_1(1800.0e3, 2000.0e3, 200.0e6, 400.0e6)
    assert rep.governing_equation == "H1-1a"
    assert math.isclose(rep.demand_capacity_ratio, 0.90 + (8.0 / 9.0) * 0.50, rel_tol=_REL)
    assert rep.demand_capacity_ratio > 1.0
    assert rep.unity_check_passes is False


def test_H1_1_axial_ratio_boundary_is_inclusive_H1_1a() -> None:
    # Exactly Pr/Pc = 0.2 must take Eq. H1-1a (the spec break is ">=").
    rep = compute_combined_strength_H1_1(400.0e3, 2000.0e3, 0.0, 1.0)
    assert rep.governing_equation == "H1-1a"
    assert math.isclose(rep.axial_ratio_Pr_Pc, 0.20, rel_tol=_REL)
    assert math.isclose(rep.demand_capacity_ratio, 0.20, rel_tol=_REL)
    assert rep.unity_check_passes is True


def test_H1_1_report_carries_citations_and_no_extra_phi() -> None:
    rep = compute_combined_strength_H1_1(800.0e3, 2000.0e3, 150.0e6, 400.0e6)
    cited = {(c.section, c.equation) for c in rep.cited_clauses}
    assert ("H1.1", "H1-1a") in cited
    assert ("H1.1", "H1-1b") in cited
    # Interaction check: resistance factors live in Pc/Mc, not here.
    assert rep.phi_LRFD == 1.0
    assert rep.omega_ASD == 1.0
