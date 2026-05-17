"""Reviewer-signable hand calcs for AISC 360-22 §H2 (Eq. H2-1).

    | fra/Fca + frbw/Fcbw + frbz/Fcbz | <= 1.0

Required stresses are signed; available stresses positive.  Bit-exact
anchor is in ``tests/golden/test_chapterH_independent.py``.  Stresses
in MPa.
"""

from __future__ import annotations

import math

from apeSteel.combined import CombinedH2Report, compute_combined_strength_H2

_REL = 1e-12


def test_H2_mixed_sign_passes_hand_calc() -> None:
    # AISC 360-22 §H2, Eq. H2-1, p. 16.1-85.
    #   fra/Fca   = -50/150 = -0.333333
    #   frbw/Fcbw =  80/200 =  0.400000
    #   frbz/Fcbz =  20/100 =  0.200000
    #   signed sum = 0.266667 ; |sum| = 0.266667 <= 1.0  -> OK
    rep = compute_combined_strength_H2(-50.0, 150.0, 80.0, 200.0, 20.0, 100.0)
    assert isinstance(rep, CombinedH2Report)
    assert rep.governing_limit_state == "H2-1"
    assert math.isclose(rep.axial_stress_ratio, -50.0 / 150.0, rel_tol=_REL)
    assert math.isclose(rep.signed_interaction_sum, -1.0 / 3.0 + 0.4 + 0.2, rel_tol=_REL)
    assert math.isclose(rep.demand_capacity_ratio, abs(-1.0 / 3.0 + 0.4 + 0.2), rel_tol=_REL)
    assert rep.unity_check_passes is True


def test_H2_overstressed_fails_hand_calc() -> None:
    #   0.6 + 0.5 + 0.444444 = 1.544444 > 1.0  -> fails
    rep = compute_combined_strength_H2(120.0, 200.0, 90.0, 180.0, 40.0, 90.0)
    assert math.isclose(rep.demand_capacity_ratio, 0.6 + 0.5 + 40.0 / 90.0, rel_tol=_REL)
    assert rep.demand_capacity_ratio > 1.0
    assert rep.unity_check_passes is False


def test_H2_sign_convention_matters_hand_calc() -> None:
    # Signs partially cancel: -0.8 - 0.4 + 0.25 = -0.95 -> |sum| = 0.95 (OK).
    # If signs were ignored: 0.8 + 0.4 + 0.25 = 1.45 (would wrongly fail).
    rep = compute_combined_strength_H2(-200.0, 250.0, -60.0, 150.0, 30.0, 120.0)
    assert math.isclose(rep.signed_interaction_sum, -0.95, rel_tol=_REL)
    assert math.isclose(rep.demand_capacity_ratio, 0.95, rel_tol=_REL)
    assert rep.unity_check_passes is True
    cited = {(c.section, c.equation) for c in rep.cited_clauses}
    assert ("H2", "H2-1") in cited
