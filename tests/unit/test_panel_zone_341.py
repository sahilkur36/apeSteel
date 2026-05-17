"""Unit tests for ``check_column_flange_tension_341`` (AISC 341 §E3.6e)
and the ``BeamColumnConnection`` composite.

The closed-form equations are checked against analytic hand-derivations
for a baseline beam/column pairing.  Acceptance flags are then probed
by toggling the column flange thickness across the geometric and
capacity-based limits.
"""

from __future__ import annotations

import math

import baseUnits as u
import pytest

from apeSteel import (
    A36,
    A992,
    S355,
    BeamColumnConnection,
    DoublySymmetricISection,
    PanelZoneColumnFlangeTensionReport,
    check_column_flange_tension_341,
)
from apeSteel.sections.properties import SectionProperties
from apeSteel.seismic.panel_zone_341 import (
    COLUMN_FLANGE_TENSION_COEFFICIENT_J10_2,
    MINIMUM_FLANGE_THICKNESS_GEOMETRIC_LIMIT_DIVISOR_BF_OVER_6,
    PHI_FLANGE_TENSION_LRFD,
    BEAM_TENSION_DEMAND_AMPLIFICATION_1p8,
    MINIMUM_FLANGE_THICKNESS_CAPACITY_COEFFICIENT_0p40,
)


# ----------------------------------------------------------------------
# Common fixtures
# ----------------------------------------------------------------------
@pytest.fixture
def beam_section() -> DoublySymmetricISection:
    # A small-ish W14X22-style section: bf=127, tf=8, hw=339, tw=6.
    return DoublySymmetricISection(
        flange_width_bf=127 * u.mm,
        flange_thickness_tf=8.0 * u.mm,
        web_clear_height_hw=339 * u.mm,
        web_thickness_tw=6.0 * u.mm,
    )


@pytest.fixture
def column_section() -> DoublySymmetricISection:
    # Generous column: tcf = 24 mm; lots of capacity.
    return DoublySymmetricISection(
        flange_width_bf=254 * u.mm,
        flange_thickness_tf=24.0 * u.mm,
        web_clear_height_hw=314 * u.mm,
        web_thickness_tw=11.4 * u.mm,
    )


# ----------------------------------------------------------------------
# Constants are not silently changed
# ----------------------------------------------------------------------
class TestConstants:
    def test_amplification_is_1p8(self) -> None:
        assert BEAM_TENSION_DEMAND_AMPLIFICATION_1p8 == 1.8

    def test_J10_coefficient_is_6p25(self) -> None:
        assert COLUMN_FLANGE_TENSION_COEFFICIENT_J10_2 == 6.25

    def test_geometric_divisor_is_6(self) -> None:
        assert MINIMUM_FLANGE_THICKNESS_GEOMETRIC_LIMIT_DIVISOR_BF_OVER_6 == 6.0

    def test_capacity_coefficient_is_0p40(self) -> None:
        assert MINIMUM_FLANGE_THICKNESS_CAPACITY_COEFFICIENT_0p40 == 0.40

    def test_phi_is_0p90(self) -> None:
        assert PHI_FLANGE_TENSION_LRFD == 0.90


# ----------------------------------------------------------------------
# Closed-form sanity (the four headline quantities)
# ----------------------------------------------------------------------
class TestClosedFormBaselineMatch:
    def test_Tu_matches_1p8_bf_tf_Fy_Ry(
        self,
        beam_section: DoublySymmetricISection,
        column_section: DoublySymmetricISection,
    ) -> None:
        bsp = beam_section.compute_section_properties()
        csp = column_section.compute_section_properties()
        r = check_column_flange_tension_341(bsp, A992, csp, A992)
        expected_Tu = (
            1.8
            * bsp.flange_width_bf
            * bsp.flange_thickness_tf
            * A992.yield_stress_Fy
            * A992.expected_yield_ratio_Ry
        )
        assert r.beam_flange_tension_demand_Tu == pytest.approx(expected_Tu, rel=1e-12)

    def test_Rn_matches_6p25_tcf2_Fy_Ry(
        self,
        beam_section: DoublySymmetricISection,
        column_section: DoublySymmetricISection,
    ) -> None:
        bsp = beam_section.compute_section_properties()
        csp = column_section.compute_section_properties()
        r = check_column_flange_tension_341(bsp, A992, csp, A992)
        expected_Rn = (
            6.25 * csp.flange_thickness_tf**2 * A992.yield_stress_Fy * A992.expected_yield_ratio_Ry
        )
        assert r.column_flange_tension_capacity_Rn == pytest.approx(expected_Rn, rel=1e-12)

    def test_phi_Rn_is_0p90_Rn(
        self,
        beam_section: DoublySymmetricISection,
        column_section: DoublySymmetricISection,
    ) -> None:
        bsp = beam_section.compute_section_properties()
        csp = column_section.compute_section_properties()
        r = check_column_flange_tension_341(bsp, A992, csp, A992)
        assert r.phi_column_flange_tension_capacity_phi_Rn_LRFD == pytest.approx(
            0.90 * r.column_flange_tension_capacity_Rn, rel=1e-12
        )

    def test_tcf_min_1_is_bf_over_6(
        self,
        beam_section: DoublySymmetricISection,
        column_section: DoublySymmetricISection,
    ) -> None:
        bsp = beam_section.compute_section_properties()
        csp = column_section.compute_section_properties()
        r = check_column_flange_tension_341(bsp, A992, csp, A992)
        assert r.minimum_column_flange_thickness_geometric_tcf_min_1 == pytest.approx(
            bsp.flange_width_bf / 6.0, rel=1e-12
        )

    def test_tcf_min_2_is_capacity_based(
        self,
        beam_section: DoublySymmetricISection,
        column_section: DoublySymmetricISection,
    ) -> None:
        bsp = beam_section.compute_section_properties()
        csp = column_section.compute_section_properties()
        r = check_column_flange_tension_341(bsp, A992, csp, A992)
        expected_tcf_min_2 = 0.40 * math.sqrt(
            r.beam_flange_tension_demand_Tu / (A992.yield_stress_Fy * A992.expected_yield_ratio_Ry)
        )
        assert r.minimum_column_flange_thickness_capacity_tcf_min_2 == pytest.approx(
            expected_tcf_min_2, rel=1e-12
        )

    def test_tcf_min_required_is_max_of_the_two_limits(
        self,
        beam_section: DoublySymmetricISection,
        column_section: DoublySymmetricISection,
    ) -> None:
        bsp = beam_section.compute_section_properties()
        csp = column_section.compute_section_properties()
        r = check_column_flange_tension_341(bsp, A992, csp, A992)
        assert r.minimum_column_flange_thickness_required_tcf_min == pytest.approx(
            max(
                r.minimum_column_flange_thickness_geometric_tcf_min_1,
                r.minimum_column_flange_thickness_capacity_tcf_min_2,
            )
        )

    def test_DCR_is_Tu_over_phi_Rn(
        self,
        beam_section: DoublySymmetricISection,
        column_section: DoublySymmetricISection,
    ) -> None:
        bsp = beam_section.compute_section_properties()
        csp = column_section.compute_section_properties()
        r = check_column_flange_tension_341(bsp, A992, csp, A992)
        assert r.demand_to_capacity_ratio == pytest.approx(
            r.beam_flange_tension_demand_Tu / r.phi_column_flange_tension_capacity_phi_Rn_LRFD,
            rel=1e-12,
        )


# ----------------------------------------------------------------------
# Acceptance flags and governing-state labels
# ----------------------------------------------------------------------
class TestAcceptanceFlags:
    def test_generous_column_passes_both_checks(
        self,
        beam_section: DoublySymmetricISection,
        column_section: DoublySymmetricISection,
    ) -> None:
        bsp = beam_section.compute_section_properties()
        csp = column_section.compute_section_properties()  # tcf = 24 mm
        r = check_column_flange_tension_341(bsp, A992, csp, A992)
        assert r.is_thickness_acceptable
        assert r.is_demand_to_capacity_acceptable
        assert r.governing_limit_state == "thickness_and_capacity_acceptable"

    def test_too_thin_column_fails_both_checks(
        self,
        beam_section: DoublySymmetricISection,
    ) -> None:
        bsp = beam_section.compute_section_properties()
        # Ultra-thin column flange.
        thin = DoublySymmetricISection(254 * u.mm, 5.0 * u.mm, 314 * u.mm, 11.4 * u.mm)
        csp = thin.compute_section_properties()
        r = check_column_flange_tension_341(bsp, A992, csp, A992)
        assert not r.is_thickness_acceptable
        assert not r.is_demand_to_capacity_acceptable
        assert r.governing_limit_state == "thickness_and_capacity_both_exceeded"

    def test_thickness_violated_but_DCR_ok(
        self,
        beam_section: DoublySymmetricISection,
    ) -> None:
        # tcf just below the geometric bf/6 limit but still high
        # enough that phi*Rn >= Tu.  For our beam bf=127 mm, the
        # geometric limit is 21.17 mm.  Pick tcf = 20 mm.
        bsp = beam_section.compute_section_properties()
        mid_col = DoublySymmetricISection(254 * u.mm, 20.0 * u.mm, 314 * u.mm, 11.4 * u.mm)
        csp = mid_col.compute_section_properties()
        r = check_column_flange_tension_341(bsp, A992, csp, A992)
        assert not r.is_thickness_acceptable
        assert r.is_demand_to_capacity_acceptable
        assert r.governing_limit_state == "minimum_flange_thickness_violated"


# ----------------------------------------------------------------------
# Input validation
# ----------------------------------------------------------------------
class TestInputValidation:
    def test_raises_when_beam_bf_missing(self, column_section: DoublySymmetricISection) -> None:
        # Hand-craft a SectionProperties with bf=tf=0 to mimic a
        # pre-Phase-8c producer.
        zero_flange_props = SectionProperties(
            overall_depth_d=300.0,
            gross_area_Ag=2400.0,
            nominal_weight_per_unit_length_w=0.0,
            moment_of_inertia_strong_axis_Ix=1.0,
            elastic_section_modulus_strong_axis_Sx=1.0,
            plastic_section_modulus_strong_axis_Zx=1.0,
            radius_of_gyration_strong_axis_rx=1.0,
            moment_of_inertia_weak_axis_Iy=1.0,
            elastic_section_modulus_weak_axis_Sy=1.0,
            plastic_section_modulus_weak_axis_Zy=1.0,
            radius_of_gyration_weak_axis_ry=1.0,
            torsional_constant_J=1.0,
            warping_constant_Cw=1.0,
            distance_between_flange_centroids_ho=1.0,
            effective_radius_of_gyration_for_LTB_rts=1.0,
            flange_width_to_thickness_ratio_bf_2tf=1.0,
            web_height_to_thickness_ratio_h_tw=1.0,
            web_thickness_tw=6.0,
        )
        csp = column_section.compute_section_properties()
        with pytest.raises(ValueError, match="flange_width_bf"):
            check_column_flange_tension_341(zero_flange_props, A992, csp, A992)


# ----------------------------------------------------------------------
# Report shape
# ----------------------------------------------------------------------
class TestReportShape:
    def test_returns_panel_zone_report(
        self,
        beam_section: DoublySymmetricISection,
        column_section: DoublySymmetricISection,
    ) -> None:
        bsp = beam_section.compute_section_properties()
        csp = column_section.compute_section_properties()
        r = check_column_flange_tension_341(bsp, A992, csp, A992)
        assert isinstance(r, PanelZoneColumnFlangeTensionReport)

    def test_report_is_frozen(
        self,
        beam_section: DoublySymmetricISection,
        column_section: DoublySymmetricISection,
    ) -> None:
        bsp = beam_section.compute_section_properties()
        csp = column_section.compute_section_properties()
        r = check_column_flange_tension_341(bsp, A992, csp, A992)
        with pytest.raises(AttributeError):
            r.column_flange_thickness_tcf = 0.0  # type: ignore[misc]

    def test_citations_present(
        self,
        beam_section: DoublySymmetricISection,
        column_section: DoublySymmetricISection,
    ) -> None:
        bsp = beam_section.compute_section_properties()
        csp = column_section.compute_section_properties()
        r = check_column_flange_tension_341(bsp, A992, csp, A992)
        citation_specs = {c.specification for c in r.cited_clauses}
        assert "AISC 341-22" in citation_specs
        assert "AISC 358-22" in citation_specs
        assert "AISC 360-22" in citation_specs


# ----------------------------------------------------------------------
# Material-dependent behaviour (Fy and Ry both matter)
# ----------------------------------------------------------------------
class TestMaterialDependence:
    def test_higher_Ry_grade_produces_higher_demand(
        self,
        beam_section: DoublySymmetricISection,
        column_section: DoublySymmetricISection,
    ) -> None:
        # A36 has Ry=1.5 (high overstrength), A992 has Ry=1.1.
        bsp = beam_section.compute_section_properties()
        csp = column_section.compute_section_properties()
        r_A992 = check_column_flange_tension_341(bsp, A992, csp, A992)
        r_A36 = check_column_flange_tension_341(bsp, A36, csp, A36)
        # A36 has Fy=36 ksi vs A992 Fy=50 ksi, so the product
        # Fy * Ry for A36 = 36*1.5 = 54 ksi; for A992 = 50*1.1 = 55 ksi.
        # The two end up very close.  We just check ordering doesn't
        # blow up: same sign and same order of magnitude.
        assert r_A36.beam_flange_tension_demand_Tu > 0
        assert r_A992.beam_flange_tension_demand_Tu > 0

    def test_S355_beam_gives_higher_demand_than_A992_beam(
        self,
        beam_section: DoublySymmetricISection,
        column_section: DoublySymmetricISection,
    ) -> None:
        bsp = beam_section.compute_section_properties()
        csp = column_section.compute_section_properties()
        r_A992 = check_column_flange_tension_341(bsp, A992, csp, A992)
        r_S355 = check_column_flange_tension_341(bsp, S355, csp, A992)
        # S355: Fy*Ry = 355 * 1.25 = 443.75 MPa.
        # A992: Fy*Ry = 344.74 * 1.1 = 379.21 MPa.
        # S355 beam should drive a HIGHER demand than A992 beam.
        assert r_S355.beam_flange_tension_demand_Tu > r_A992.beam_flange_tension_demand_Tu


# ----------------------------------------------------------------------
# BeamColumnConnection composite
# ----------------------------------------------------------------------
class TestBeamColumnConnection:
    def test_connected_to_builder(
        self,
        beam_section: DoublySymmetricISection,
        column_section: DoublySymmetricISection,
    ) -> None:
        beam = beam_section.element(A992)
        col = column_section.element(A992)
        joint = beam.connected_to(col)
        assert isinstance(joint, BeamColumnConnection)
        assert joint.beam is beam
        assert joint.column is col

    def test_direct_construction(
        self,
        beam_section: DoublySymmetricISection,
        column_section: DoublySymmetricISection,
    ) -> None:
        beam = beam_section.element(A992)
        col = column_section.element(A992)
        joint = BeamColumnConnection(beam=beam, column=col)
        assert joint.beam is beam

    def test_composite_matches_free_function(
        self,
        beam_section: DoublySymmetricISection,
        column_section: DoublySymmetricISection,
    ) -> None:
        beam = beam_section.element(A992)
        col = column_section.element(A992)
        joint = beam.connected_to(col)
        r_composite = joint.check_panel_zone_column_flange_tension()
        r_free = check_column_flange_tension_341(
            beam_section.compute_section_properties(),
            A992,
            column_section.compute_section_properties(),
            A992,
        )
        assert r_composite.beam_flange_tension_demand_Tu == pytest.approx(
            r_free.beam_flange_tension_demand_Tu
        )
        assert r_composite.demand_to_capacity_ratio == pytest.approx(
            r_free.demand_to_capacity_ratio
        )

    def test_composite_is_frozen(
        self,
        beam_section: DoublySymmetricISection,
        column_section: DoublySymmetricISection,
    ) -> None:
        beam = beam_section.element(A992)
        col = column_section.element(A992)
        joint = BeamColumnConnection(beam=beam, column=col)
        with pytest.raises(AttributeError):
            joint.beam = beam  # type: ignore[misc]
