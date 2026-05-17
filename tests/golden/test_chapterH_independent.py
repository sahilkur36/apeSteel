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

from apeSteel.combined import compute_combined_strength_H1_1
from tests.golden._chapterH_aisc_oracle import interaction_H1_1

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
