"""Reviewer-signable hand calcs for AISC 360-22 §H1.3.

§H1.3(a) in-plane Eq. H1-1 + §H1.3(b) out-of-plane Eq. H1-2

    Pr/Pcy*(1.5 - 0.5*Pr/Pcy) + (Mrx/(Cb*Mcx))^2 <= 1.0

with the spec note ``Cb*Mcx`` capped at ``phi_b*Mp``.  Bit-exact
anchor is in ``tests/golden/test_chapterH_independent.py``; base units
N, N*mm.
"""

from __future__ import annotations

import math

import pytest

from apeSteel.combined import (
    CombinedH13Report,
    compute_combined_strength_H1_3,
    ensure_h1_3_applicable,
)

_REL = 1e-12


def test_H1_3_out_of_plane_governs_cap_inactive_hand_calc() -> None:
    # AISC 360-22 §H1.3, p. 16.1-84.
    #   Pr=600 kN, Pcx=3000 kN, Pcy=2000 kN, Mrx=250 kN*m,
    #   Mcx,in-plane=600, Mcx,LTB(Cb=1)=480 kN*m, Cb=1.14, phi_b*Mp=660.
    #
    # (a) in-plane Eq. H1-1:  Pr/Pcx = 600/3000 = 0.20 >= 0.2 -> H1-1a
    #     DCR_ip = 0.20 + 8/9*(250/600) = 0.20 + 0.370370 = 0.570370
    #
    # (b) Eq. H1-2:  Cb*Mcx = 1.14*480 = 547.2 < 660 -> cap inactive
    #     rp = 600/2000 = 0.30
    #     DCR_oop = 0.30*(1.5 - 0.5*0.30) + (250/547.2)^2
    #             = 0.30*1.35 + 0.2087315 = 0.405 + 0.2087315 = 0.6137315
    #
    # 0.6137 > 0.5704 -> out-of-plane governs.
    rep = compute_combined_strength_H1_3(
        required_axial_Pr=600.0e3,
        available_axial_in_plane_Pcx=3.0e6,
        available_axial_out_of_plane_Pcy=2.0e6,
        required_moment_x_Mrx=250.0e6,
        available_moment_x_in_plane_Mcx=600.0e6,
        available_moment_x_ltb_Cb1_Mcx=480.0e6,
        lateral_torsional_modification_Cb=1.14,
        available_plastic_moment_phi_b_Mp=660.0e6,
    )
    assert isinstance(rep, CombinedH13Report)

    dcr_ip = 0.20 + (8.0 / 9.0) * (250.0 / 600.0)
    assert rep.in_plane.governing_equation == "H1-1a"
    assert math.isclose(rep.in_plane.demand_capacity_ratio, dcr_ip, rel_tol=_REL)

    cb_mcx = 1.14 * 480.0e6
    assert math.isclose(rep.out_of_plane_capped_Cb_Mcx, cb_mcx, rel_tol=_REL)
    rp = 600.0e3 / 2.0e6
    dcr_oop = rp * (1.5 - 0.5 * rp) + (250.0e6 / cb_mcx) ** 2
    assert math.isclose(rep.out_of_plane_demand_capacity_ratio, dcr_oop, rel_tol=_REL)

    assert rep.governing_check == "out_of_plane"
    assert rep.governing_equation == "H1-2"
    assert math.isclose(rep.demand_capacity_ratio, max(dcr_ip, dcr_oop), rel_tol=_REL)
    assert rep.unity_check_passes is True


def test_H1_3_cap_active_and_in_plane_governs_hand_calc() -> None:
    #   Pr=400, Pcx=3200, Pcy=2400 kN; Mrx=300, Mcx,ip=620,
    #   Mcx,LTB=560 kN*m; Cb=1.67; phi_b*Mp=600.
    # Cb*Mcx = 1.67*560 = 935.2 > 600 -> CAP -> denominator = 600.
    #   rp = 400/2400 = 0.166667
    #   DCR_oop = 0.166667*(1.5-0.5*0.166667) + (300/600)^2
    #           = 0.236111 + 0.25 = 0.486111
    #   in-plane: Pr/Pcx = 400/3200 = 0.125 < 0.2 -> H1-1b
    #   DCR_ip = 0.125/2 + 300/620 = 0.0625 + 0.483871 = 0.546371
    # 0.5464 > 0.4861 -> in-plane governs.
    rep = compute_combined_strength_H1_3(
        required_axial_Pr=400.0e3,
        available_axial_in_plane_Pcx=3.2e6,
        available_axial_out_of_plane_Pcy=2.4e6,
        required_moment_x_Mrx=300.0e6,
        available_moment_x_in_plane_Mcx=620.0e6,
        available_moment_x_ltb_Cb1_Mcx=560.0e6,
        lateral_torsional_modification_Cb=1.67,
        available_plastic_moment_phi_b_Mp=600.0e6,
    )
    # Cap applied: denominator is phi_b*Mp, not Cb*Mcx.
    assert math.isclose(rep.out_of_plane_capped_Cb_Mcx, 600.0e6, rel_tol=_REL)
    rp = 400.0e3 / 2.4e6
    dcr_oop = rp * (1.5 - 0.5 * rp) + (300.0e6 / 600.0e6) ** 2
    dcr_ip = 0.125 / 2.0 + 300.0 / 620.0
    assert math.isclose(rep.out_of_plane_demand_capacity_ratio, dcr_oop, rel_tol=_REL)
    assert rep.in_plane.governing_equation == "H1-1b"
    assert math.isclose(rep.in_plane.demand_capacity_ratio, dcr_ip, rel_tol=_REL)
    assert rep.governing_check == "in_plane"
    assert rep.governing_equation == "H1-1b"
    assert math.isclose(rep.demand_capacity_ratio, max(dcr_ip, dcr_oop), rel_tol=_REL)
    assert rep.unity_check_passes is True


def test_H1_3_applicability_guard() -> None:
    # All-OK call does not raise.
    ensure_h1_3_applicable(
        is_doubly_symmetric=True,
        is_rolled=True,
        is_compact_for_flexure=True,
        effective_length_torsional_KLz=3000.0,
        effective_length_minor_KLy=4000.0,
    )
    with pytest.raises(ValueError, match="doubly-symmetric"):
        ensure_h1_3_applicable(
            is_doubly_symmetric=False,
            is_rolled=True,
            is_compact_for_flexure=True,
            effective_length_torsional_KLz=3000.0,
            effective_length_minor_KLy=4000.0,
        )
    with pytest.raises(ValueError, match="rolled"):
        ensure_h1_3_applicable(
            is_doubly_symmetric=True,
            is_rolled=False,
            is_compact_for_flexure=True,
            effective_length_torsional_KLz=3000.0,
            effective_length_minor_KLy=4000.0,
        )
    with pytest.raises(ValueError, match="compact"):
        ensure_h1_3_applicable(
            is_doubly_symmetric=True,
            is_rolled=True,
            is_compact_for_flexure=False,
            effective_length_torsional_KLz=3000.0,
            effective_length_minor_KLy=4000.0,
        )
    with pytest.raises(ValueError, match="KLz <= KLy"):
        ensure_h1_3_applicable(
            is_doubly_symmetric=True,
            is_rolled=True,
            is_compact_for_flexure=True,
            effective_length_torsional_KLz=5000.0,
            effective_length_minor_KLy=4000.0,
        )
