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
    compute_Pey_H1_2,
)
from tests.golden._chapterH_aisc_oracle import (
    Pey_H1_2,
    cb_amplification_H1_2,
    interaction_H1_1,
    interaction_H1_3_in_plane,
    interaction_H1_3_out_of_plane,
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
