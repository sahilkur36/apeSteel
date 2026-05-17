"""Reviewer-signable hand calcs for AISC 360-22 §H1.2 (flexure + tension).

§H1.2 reuses the §H1.1 Eq. H1-1a/H1-1b kernel with the tensile ``Pc``
(here the §D2(a) gross-section yield) and adds the ``Cb`` amplifier
``sqrt(1 + alpha*Pr/Pey)``.  The bit-exact anchor lives in
``tests/golden/test_chapterH_independent.py``; this is the
hand-traceable companion.  Base units: N, N*mm, MPa, mm.
"""

from __future__ import annotations

import math

from apeSteel.combined import (
    compute_Cb_amplification_factor_H1_2,
    compute_combined_strength_H1_2,
    compute_Pey_H1_2,
)
from apeSteel.tension import compute_tension_yielding_strength_D2

_REL = 1e-12


def test_H1_2_interaction_consumes_D2_tension_Pc_hand_calc() -> None:
    # Upstream §D2(a): Fy=345, Ag=5000 -> Pn=1_725_000 N;
    #   Pc = phi_t*Pn = 0.90*1_725_000 = 1_552_500 N.
    d2 = compute_tension_yielding_strength_D2(345.0, 5000.0)
    pc_tension = d2.phi_strength_LRFD
    assert math.isclose(pc_tension, 1_552_500.0, rel_tol=_REL)

    # AISC 360-22 §H1.2 (Eq. H1-1b reused, p. 16.1-84):
    #   Pr = 232_875 N -> Pr/Pc = 232875/1552500 = 0.150 < 0.2 -> H1-1b
    #   Mrx/Mcx = 180/400 = 0.450 ; Mry = 0
    #   DCR = Pr/(2*Pc) + Mrx/Mcx = 0.075 + 0.450 = 0.525
    rep = compute_combined_strength_H1_2(
        required_tension_Pr=232_875.0,
        available_tension_Pc=pc_tension,
        required_moment_x_Mrx=180.0e6,
        available_moment_x_Mcx=400.0e6,
    )
    assert rep.governing_equation == "H1-1b"
    assert math.isclose(rep.axial_ratio_Pr_Pc, 0.15, rel_tol=_REL)
    assert math.isclose(rep.demand_capacity_ratio, 0.075 + 0.45, rel_tol=_REL)
    assert rep.unity_check_passes is True
    # §H1.2 citation block (distinct from §H1.1).
    assert any(c.section == "H1.2" for c in rep.cited_clauses)


def test_H1_2_Pey_hand_calc() -> None:
    # Pey = pi^2 * E * Iy / Lb^2
    #     = pi^2 * 200000 * 20e6 / 4000^2
    #     = pi^2 * 250000 = 2_467_401.100 N
    pey = compute_Pey_H1_2(
        elastic_modulus_E=200000.0, moment_of_inertia_y_Iy=20.0e6, unbraced_length_Lb=4000.0
    )
    assert math.isclose(pey, math.pi**2 * 250000.0, rel_tol=_REL)
    assert math.isclose(pey, 2_467_401.1002726504, rel_tol=1e-9)


def test_H1_2_Cb_amplifier_lrfd_and_asd_hand_calc() -> None:
    pey = math.pi**2 * 250000.0
    # LRFD alpha = 1.0 :  sqrt(1 + 1.0*500000/Pey)
    cb_lrfd = compute_Cb_amplification_factor_H1_2(500_000.0, 200000.0, 20.0e6, 4000.0, alpha=1.0)
    assert math.isclose(cb_lrfd, math.sqrt(1.0 + 500_000.0 / pey), rel_tol=_REL)
    # ASD alpha = 1.6 :  sqrt(1 + 1.6*500000/Pey)  (larger amplifier)
    cb_asd = compute_Cb_amplification_factor_H1_2(500_000.0, 200000.0, 20.0e6, 4000.0, alpha=1.6)
    assert math.isclose(cb_asd, math.sqrt(1.0 + 1.6 * 500_000.0 / pey), rel_tol=_REL)
    assert cb_asd > cb_lrfd > 1.0


def test_H1_2_zero_tension_amplifier_is_unity() -> None:
    # Pr = 0 -> sqrt(1 + 0) = 1.0 (no LTB benefit, no penalty).
    cb = compute_Cb_amplification_factor_H1_2(0.0, 200000.0, 20.0e6, 4000.0)
    assert math.isclose(cb, 1.0, rel_tol=_REL)
