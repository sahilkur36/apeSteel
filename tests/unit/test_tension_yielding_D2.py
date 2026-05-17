"""Reviewer-signable hand calc for AISC 360-22 §D2(a) (Eq. D2-1).

Eq. D2-1 is a single multiplication ``Pn = Fy*Ag``; the hand
substitution below *is* the independent check (no composition to
re-derive).  All quantities in apeSteel base units (MPa, mm^2, N).
"""

from __future__ import annotations

import math

import pytest

from apeSteel.tension import (
    TensionYieldingD2Report,
    compute_tension_yielding_strength_D2,
)


def test_D2_1_gross_section_yielding_hand_calc() -> None:
    # AISC 360-22 §D2(a), Eq. D2-1, p. 16.1-31.
    #   Fy = 345 MPa, Ag = 5000 mm^2
    #   Pn  = Fy*Ag           = 345 * 5000 = 1_725_000 N
    #   phi_t = 0.90 -> phi*Pn = 0.90 * 1_725_000 = 1_552_500 N
    #   Omega_t = 1.67 -> Pn/Omega = 1_725_000 / 1.67 = 1_032_934.13 N
    rep = compute_tension_yielding_strength_D2(yield_stress_Fy=345.0, gross_area_Ag=5000.0)

    assert isinstance(rep, TensionYieldingD2Report)
    assert rep.governing_limit_state == "tension_yielding_D2"
    assert math.isclose(rep.nominal_tensile_strength_Pn, 345.0 * 5000.0, rel_tol=1e-12)
    assert math.isclose(rep.nominal_strength, 1_725_000.0, rel_tol=1e-12)
    assert rep.phi_LRFD == 0.90
    assert rep.omega_ASD == 1.67
    assert math.isclose(rep.phi_strength_LRFD, 0.90 * 1_725_000.0, rel_tol=1e-12)
    assert math.isclose(rep.omega_strength_ASD, 1_725_000.0 / 1.67, rel_tol=1e-12)
    cited = {(c.section, c.equation) for c in rep.cited_clauses}
    assert ("D2", "D2-1") in cited


def test_D2_1_guards() -> None:
    with pytest.raises(ValueError, match="yield_stress_Fy must be positive"):
        compute_tension_yielding_strength_D2(0.0, 5000.0)
    with pytest.raises(ValueError, match="gross_area_Ag must be positive"):
        compute_tension_yielding_strength_D2(345.0, -1.0)
