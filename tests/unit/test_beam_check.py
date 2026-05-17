"""Unit tests for run_full_beam_check (the AISC beam-check facade)."""

from __future__ import annotations

import math
from dataclasses import FrozenInstanceError

import pytest

from apeSteel import (
    A992,
    BeamCheckReport,
    BothFlangesFlexureF2Report,
    BothFlangesFlexureF3Report,
    BothFlangesFlexureF5Report,
    Bracing,
    DoublySymmetricISection,
    run_full_beam_check,
)
from apeSteel.core import units as u


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
def _compact_element():
    section = DoublySymmetricISection(100 * u.mm, 6 * u.mm, 300 * u.mm, 4 * u.mm)
    return section.element(
        material=A992,
        construction="welded",
        bracing=Bracing(0.001 * u.m, 4.0 * u.m, 1.0),
    )


def _noncompact_flange_element():
    """bf/(2tf) = 12.5 > 9.15 = lambda_pf -> non-compact flange."""
    section = DoublySymmetricISection(200 * u.mm, 8 * u.mm, 400 * u.mm, 12 * u.mm)
    return section.element(
        material=A992,
        construction="welded",
        bracing=Bracing(0.001 * u.m, 4.0 * u.m, 1.0),
    )


def _slender_web_element():
    """h/tw = 150 > 137 = lambda_rw -> slender web."""
    section = DoublySymmetricISection(150 * u.mm, 12 * u.mm, 600 * u.mm, 4 * u.mm)
    return section.element(
        material=A992,
        construction="welded",
        bracing=Bracing(0.001 * u.m, 4.0 * u.m, 1.0),
    )


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------
def test_compact_section_routes_to_F2() -> None:
    r = run_full_beam_check(_compact_element())
    assert r.routed_flexure_chapter == "F2"
    assert isinstance(r.flexure_both_flanges, BothFlangesFlexureF2Report)


def test_noncompact_flange_routes_to_F3() -> None:
    r = run_full_beam_check(_noncompact_flange_element())
    assert r.routed_flexure_chapter == "F3"
    assert isinstance(r.flexure_both_flanges, BothFlangesFlexureF3Report)
    assert r.flexural_classification.flange.classification == "non_compact"


def test_slender_web_routes_to_F5() -> None:
    r = run_full_beam_check(_slender_web_element())
    assert r.routed_flexure_chapter == "F5"

    assert isinstance(r.flexure_both_flanges, BothFlangesFlexureF5Report)


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------
def test_governing_flexural_phi_Mn_matches_inner_report() -> None:
    r = run_full_beam_check(_compact_element())
    assert r.flexure_both_flanges is not None
    assert r.governing_flexural_phi_Mn == r.flexure_both_flanges.governing_report.phi_strength_LRFD


def test_governing_flange_propagates() -> None:
    r = run_full_beam_check(_compact_element())
    assert r.flexure_both_flanges is not None
    assert r.governing_flexural_flange == r.flexure_both_flanges.governing_flange


def test_shear_runs_independent_of_flexure_routing() -> None:
    """Both F2-routed and F3-routed sections produce a ShearG2Report."""
    r_F2 = run_full_beam_check(_compact_element())
    r_F3 = run_full_beam_check(_noncompact_flange_element())
    assert r_F2.shear is not None
    assert r_F3.shear is not None


def test_stiffener_spacing_propagates_to_shear() -> None:
    e = _compact_element()
    r_unstiff = run_full_beam_check(e)
    r_stiff = run_full_beam_check(e, transverse_stiffener_spacing_a=0.5 * u.m)
    # Stiffened web -> higher kv -> higher Cv1 -> higher Vn
    assert r_stiff.shear is not None
    assert r_unstiff.shear is not None
    assert (
        r_stiff.shear.web_plate_buckling_coefficient_kv
        > r_unstiff.shear.web_plate_buckling_coefficient_kv
    )


# ---------------------------------------------------------------------------
# Element.run_full_check delegates correctly
# ---------------------------------------------------------------------------
def test_element_run_full_check_matches_facade() -> None:
    e = _compact_element()
    method_report = e.run_full_check()
    pure_report = run_full_beam_check(e)
    # Both reports must have the same routing and the same governing phi*Mn.
    assert method_report.routed_flexure_chapter == pure_report.routed_flexure_chapter
    assert math.isclose(
        method_report.governing_flexural_phi_Mn,
        pure_report.governing_flexural_phi_Mn,
        rel_tol=1e-12,
    )


def test_element_run_full_check_requires_bracing() -> None:
    """The facade calls the F2/F3 method which requires bracing."""
    section = DoublySymmetricISection(100 * u.mm, 6 * u.mm, 300 * u.mm, 4 * u.mm)
    no_bracing = section.element(material=A992, construction="welded")
    with pytest.raises(ValueError, match="bracing"):
        no_bracing.run_full_check()


# ---------------------------------------------------------------------------
# Parity with manual calls
# ---------------------------------------------------------------------------
def test_facade_parity_with_manual_calls() -> None:
    """The facade's flexure result must equal a manual F3 call."""
    e = _noncompact_flange_element()
    r = run_full_beam_check(e)
    manual_F3 = e.flexural_strength_F3_both_flanges()
    assert r.flexure_both_flanges == manual_F3
    # And shear matches a manual G2 call.
    manual_G2 = e.shear_strength_G2()
    assert r.shear == manual_G2


# ---------------------------------------------------------------------------
# Plumbing
# ---------------------------------------------------------------------------
def test_report_is_frozen() -> None:
    r = run_full_beam_check(_compact_element())
    with pytest.raises(FrozenInstanceError):
        r.routed_flexure_chapter = "F3"  # type: ignore[misc]


def test_report_returns_BeamCheckReport_instance() -> None:
    r = run_full_beam_check(_compact_element())
    assert isinstance(r, BeamCheckReport)


def test_report_carries_AISC_citations() -> None:
    r = run_full_beam_check(_compact_element())
    sections = {c.section for c in r.cited_clauses}
    # Top-level citations: B4.1b, F2, F3, G2.1
    assert "B4.1b" in sections
    assert "F2" in sections
    assert "F3" in sections
    assert "G2.1" in sections
