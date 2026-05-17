"""Unit tests for compute_flexural_strength_F3_noncompact_or_slender_flange."""

from __future__ import annotations

import math
from dataclasses import FrozenInstanceError

import pytest

from apeSteel import (
    A992,
    DoublySymmetricISection,
    FlexureF3Report,
    compute_flexural_strength_F2_compact_doubly_symmetric,
    compute_flexural_strength_F3_noncompact_or_slender_flange,
)
from apeSteel.core import units as u

# A section with NON-COMPACT flange at A992: bf=200, tf=8 -> bf/(2tf)=12.5
# lambda_pf = 0.38*sqrt(E/Fy) = ~9.15; lambda_rf = 1.0*sqrt(E/Fy) = ~24.08 (rolled)
NONCOMPACT_FLANGE_SECTION = DoublySymmetricISection(
    200.0 * u.mm,
    8.0 * u.mm,
    400.0 * u.mm,
    12.0 * u.mm,
)


def test_F3_with_noncompact_flange_routes_to_F3_1() -> None:
    r = compute_flexural_strength_F3_noncompact_or_slender_flange(
        NONCOMPACT_FLANGE_SECTION.compute_section_properties(),
        A992,
        unbraced_length_Lb=1.0 * u.m,
        lateral_torsional_buckling_modification_factor_Cb=1.0,
        construction="welded",
    )
    assert r.flange_classification == "non_compact"


def test_F3_takes_min_of_LTB_and_FLB() -> None:
    r = compute_flexural_strength_F3_noncompact_or_slender_flange(
        NONCOMPACT_FLANGE_SECTION.compute_section_properties(),
        A992,
        1.0 * u.m,
        1.0,
        "welded",
    )
    assert math.isclose(
        r.nominal_flexural_strength_Mn,
        min(r.nominal_LTB_moment_Mn_LTB, r.nominal_FLB_moment_Mn_FLB),
        rel_tol=1e-12,
    )


def test_F3_at_short_Lb_FLB_governs() -> None:
    r = compute_flexural_strength_F3_noncompact_or_slender_flange(
        NONCOMPACT_FLANGE_SECTION.compute_section_properties(),
        A992,
        0.5 * u.m,
        1.0,
        "welded",
    )
    assert r.governing_flexural_limit_state == "flange_local_buckling"
    assert r.nominal_LTB_moment_Mn_LTB == r.plastic_moment_Mp
    assert r.nominal_FLB_moment_Mn_FLB < r.plastic_moment_Mp


def test_F3_at_long_Lb_LTB_governs() -> None:
    r = compute_flexural_strength_F3_noncompact_or_slender_flange(
        NONCOMPACT_FLANGE_SECTION.compute_section_properties(),
        A992,
        10.0 * u.m,
        1.0,
        "welded",
    )
    assert r.governing_flexural_limit_state == "lateral_torsional_buckling"
    assert r.nominal_LTB_moment_Mn_LTB < r.nominal_FLB_moment_Mn_FLB


def test_F3_with_compact_flange_FLB_does_not_govern() -> None:
    compact_section = DoublySymmetricISection(
        100.0 * u.mm,
        6.0 * u.mm,
        300.0 * u.mm,
        4.0 * u.mm,
    )
    r = compute_flexural_strength_F3_noncompact_or_slender_flange(
        compact_section.compute_section_properties(),
        A992,
        0.5 * u.m,
        1.0,
        "welded",
    )
    assert r.flange_classification == "compact"
    assert math.isclose(r.nominal_FLB_moment_Mn_FLB, r.plastic_moment_Mp, rel_tol=1e-12)


def test_F3_Mn_is_capped_at_Mp() -> None:
    r = compute_flexural_strength_F3_noncompact_or_slender_flange(
        NONCOMPACT_FLANGE_SECTION.compute_section_properties(),
        A992,
        1.0 * u.m,
        3.0,
        "welded",
    )
    assert r.nominal_flexural_strength_Mn <= r.plastic_moment_Mp + 1e-9


def test_F3_phi_factor_is_0p9() -> None:
    r = compute_flexural_strength_F3_noncompact_or_slender_flange(
        NONCOMPACT_FLANGE_SECTION.compute_section_properties(),
        A992,
        1.0 * u.m,
        1.0,
        "welded",
    )
    assert r.phi_LRFD == 0.90
    assert math.isclose(
        r.phi_strength_LRFD,
        0.90 * r.nominal_flexural_strength_Mn,
        rel_tol=1e-12,
    )


def test_F3_returns_FlexureF3Report_instance() -> None:
    r = compute_flexural_strength_F3_noncompact_or_slender_flange(
        NONCOMPACT_FLANGE_SECTION.compute_section_properties(),
        A992,
        1.0 * u.m,
        1.0,
        "welded",
    )
    assert isinstance(r, FlexureF3Report)


def test_F3_report_is_frozen() -> None:
    r = compute_flexural_strength_F3_noncompact_or_slender_flange(
        NONCOMPACT_FLANGE_SECTION.compute_section_properties(),
        A992,
        1.0 * u.m,
        1.0,
        "welded",
    )
    with pytest.raises(FrozenInstanceError):
        r.nominal_flexural_strength_Mn = 0.0  # type: ignore[misc]


def test_F3_invalid_Lb_raises() -> None:
    with pytest.raises(ValueError, match="positive"):
        compute_flexural_strength_F3_noncompact_or_slender_flange(
            NONCOMPACT_FLANGE_SECTION.compute_section_properties(),
            A992,
            -1.0 * u.m,
            1.0,
            "welded",
        )


def test_F3_rolled_vs_welded_use_different_FLB_limits() -> None:
    sec = NONCOMPACT_FLANGE_SECTION
    rolled = compute_flexural_strength_F3_noncompact_or_slender_flange(
        sec.compute_section_properties(),
        A992,
        1.0 * u.m,
        1.0,
        "rolled",
    )
    welded = compute_flexural_strength_F3_noncompact_or_slender_flange(
        sec.compute_section_properties(),
        A992,
        1.0 * u.m,
        1.0,
        "welded",
    )
    assert rolled.flange_noncompact_limit_lambda_rf != welded.flange_noncompact_limit_lambda_rf
    assert rolled.nominal_FLB_moment_Mn_FLB != welded.nominal_FLB_moment_Mn_FLB


def test_F3_with_compact_flange_matches_F2_LTB_strength() -> None:
    compact_section = DoublySymmetricISection(
        100.0 * u.mm,
        6.0 * u.mm,
        300.0 * u.mm,
        4.0 * u.mm,
    )
    props = compact_section.compute_section_properties()
    r_F3 = compute_flexural_strength_F3_noncompact_or_slender_flange(
        props,
        A992,
        1.5 * u.m,
        1.0,
        "welded",
    )
    r_F2 = compute_flexural_strength_F2_compact_doubly_symmetric(
        props,
        A992,
        1.5 * u.m,
        1.0,
    )
    assert math.isclose(
        r_F3.nominal_flexural_strength_Mn,
        r_F2.nominal_flexural_strength_Mn,
        rel_tol=1e-12,
    )
