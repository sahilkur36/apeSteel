"""H-0 scaffold: Chapter-H stubs raise, and the independent oracle is sane.

The numerical correctness of the Chapter-H engine is anchored
independently from H-1 onward in
``tests/golden/test_chapterH_independent.py`` (oracle, bit-exact) and
``tests/golden/test_combined_excel_anchor.py`` (workbook).  This file
only pins the H-0 deliverables: every ``combined``/``tension`` calculator
is a stub that raises ``NotImplementedError`` pointing at design note 09,
and the standalone oracle reproduces a small set of hand calculations.
"""

from __future__ import annotations

import math

import pytest

from apeSteel.combined import (
    compute_combined_strength,
    compute_combined_strength_H3_2,
    compute_torsional_strength_rect_HSS_H3_1,
    compute_torsional_strength_round_HSS_H3_1,
)
from apeSteel.combined._common import PHI_TORSION_LRFD
from tests.golden._chapterH_aisc_oracle import (
    cb_amplification_H1_2,
    interaction_H1_1,
    interaction_H1_3_out_of_plane,
    interaction_H2,
    interaction_H3_2,
    nonHSS_limiting_Fn_H3_3,
    torsion_rect_HSS_H3_1,
    torsion_round_HSS_H3_1,
)

_REL = 1e-12


# --------------------------------------------------------------------------- #
# H-0: every public calculator is still a NotImplementedError stub.
# --------------------------------------------------------------------------- #
def test_combined_and_tension_stubs_raise() -> None:
    # §H1.1 (phase H-1) and §H1.2 + the thin §D2(a) tension slice
    # (phase H-2) are implemented; their behaviour is anchored in
    # test_combined_H1_1.py / test_combined_H1_2.py /
    # test_tension_yielding_D2.py / test_chapterH_independent.py.
    # §H1.1/§H1.2/§H1.3 (H-1..H-3) and §H2 (H-4) are implemented and
    # anchored in their own files.  The §H3 calculators below are still
    # H-5 stubs.
    with pytest.raises(NotImplementedError, match="H-5"):
        compute_torsional_strength_round_HSS_H3_1(345.0, 200000.0, 200.0, 10.0, 3000.0)
    with pytest.raises(NotImplementedError, match="H-5"):
        compute_torsional_strength_rect_HSS_H3_1(345.0, 200000.0, 65.0, 1.0e6)
    with pytest.raises(NotImplementedError, match="H-5"):
        compute_combined_strength_H3_2(100.0, 900.0, 200.0, 400.0, 50.0, 300.0, 30.0, 100.0)
    with pytest.raises(NotImplementedError, match="09_combined_H"):
        compute_combined_strength()


def test_phi_torsion_constant_is_0p90() -> None:
    assert PHI_TORSION_LRFD == 0.90


# --------------------------------------------------------------------------- #
# Oracle sanity (hand calcs).  These freeze the independent re-derivation
# that the H-1+ facade will be pinned to.
# --------------------------------------------------------------------------- #
def test_oracle_H1_1a_hand_calc() -> None:
    # Pr/Pc = 180/900 = 0.2 -> Eq. H1-1a; Mrx/Mcx = 0.5, Mry = 0.
    # 0.2 + 8/9 * 0.5 = 0.64444...
    r = interaction_H1_1(180.0, 900.0, 2400.0, 4800.0)
    assert r.equation == "H1-1a"
    assert math.isclose(r.dcr, 0.2 + (8.0 / 9.0) * 0.5, rel_tol=_REL)
    assert r.passes is True


def test_oracle_H1_1b_hand_calc() -> None:
    # Pr/Pc = 90/900 = 0.1 < 0.2 -> Eq. H1-1b; biaxial 0.5 + 0.5 = 1.0.
    # 0.1/2 + 1.0 = 1.05 -> fails.
    r = interaction_H1_1(90.0, 900.0, 2400.0, 4800.0, 600.0, 1200.0)
    assert r.equation == "H1-1b"
    assert math.isclose(r.dcr, 0.05 + 1.0, rel_tol=_REL)
    assert r.passes is False


def test_oracle_H1_1_guards() -> None:
    with pytest.raises(ValueError, match="Pc must be positive"):
        interaction_H1_1(100.0, 0.0, 100.0, 200.0)
    with pytest.raises(ValueError, match="Mcy must be positive"):
        interaction_H1_1(100.0, 900.0, 0.0, 0.0, 50.0, 0.0)


def test_oracle_Cb_amplification_H1_2_hand_calc() -> None:
    pey = math.pi**2 * 200000.0 * 20.0e6 / 4000.0**2
    got = cb_amplification_H1_2(500000.0, pey, alpha=1.0)
    assert math.isclose(got, math.sqrt(1.0 + 500000.0 / pey), rel_tol=_REL)


def test_oracle_H1_3_out_of_plane_hand_calc() -> None:
    # Pr/Pcy = 0.2; Cb*Mcx = min(1.14*1000, 1500) = 1140.
    # 0.2*(1.5-0.1) + (900/1140)^2 = 0.28 + 0.6232687 = 0.9032687
    r = interaction_H1_3_out_of_plane(300.0, 1500.0, 900.0, 1.14, 1000.0, 1500.0)
    assert r.equation == "H1-2"
    expected = 0.2 * (1.5 - 0.5 * 0.2) + (900.0 / 1140.0) ** 2
    assert math.isclose(r.dcr, expected, rel_tol=_REL)
    assert r.passes is True


def test_oracle_H2_signed_sum_hand_calc() -> None:
    # -50/150 + 80/200 + 20/100 = -0.33333 + 0.4 + 0.2 = 0.26667
    r = interaction_H2(-50.0, 150.0, 80.0, 200.0, 20.0, 100.0)
    assert r.equation == "H2-1"
    assert math.isclose(r.dcr, abs(-1.0 / 3.0 + 0.4 + 0.2), rel_tol=_REL)
    assert r.passes is True


def test_oracle_round_HSS_torsion_capped_at_0p6Fy() -> None:
    # Thick, short pipe -> buckling Fcr exceeds the 0.6*Fy shear-yield cap.
    r = torsion_round_HSS_H3_1(345.0, 200000.0, 200.0, 10.0, 3000.0)
    assert r.governing == "shear_yielding_0p6Fy"
    assert math.isclose(r.Fcr, 0.6 * 345.0, rel_tol=_REL)
    c_expected = math.pi * (200.0 - 10.0) ** 2 * 10.0 / 2.0
    assert math.isclose(r.C, c_expected, rel_tol=_REL)
    assert math.isclose(r.Tn, r.Fcr * c_expected, rel_tol=_REL)


def test_oracle_rect_HSS_torsion_H3_4_regime() -> None:
    fy, e_mod = 345.0, 200000.0
    s = math.sqrt(e_mod / fy)
    h_t = 0.5 * (2.45 * s + 3.07 * s)  # squarely in the Eq. H3-4 band
    r = torsion_rect_HSS_H3_1(fy, e_mod, h_t, 1.0e6)
    assert r.governing == "H3-4"
    assert math.isclose(r.Fcr, 0.6 * fy * (2.45 * s) / h_t, rel_tol=_REL)
    assert math.isclose(r.Tn, r.Fcr * 1.0e6, rel_tol=_REL)


def test_oracle_H3_2_torsion_neglect_then_combined() -> None:
    neg, flag = interaction_H3_2(100.0, 900.0, 200.0, 400.0, 50.0, 300.0, 10.0, 100.0)
    assert flag is True
    assert neg is None
    res, flag2 = interaction_H3_2(100.0, 900.0, 200.0, 400.0, 50.0, 300.0, 30.0, 100.0)
    assert flag2 is False
    assert res is not None
    expected = (100.0 / 900.0 + 200.0 / 400.0) + (50.0 / 300.0 + 30.0 / 100.0) ** 2
    assert math.isclose(res.dcr, expected, rel_tol=_REL)


def test_oracle_nonHSS_limiting_Fn_H3_3() -> None:
    _, _, _, fn_gov, label = nonHSS_limiting_Fn_H3_3(345.0)
    assert label == "H3-8"
    assert math.isclose(fn_gov, 0.6 * 345.0, rel_tol=_REL)
    _, _, _, fn_gov2, label2 = nonHSS_limiting_Fn_H3_3(345.0, Fcr=120.0)
    assert label2 == "H3-9"
    assert math.isclose(fn_gov2, 120.0, rel_tol=_REL)
