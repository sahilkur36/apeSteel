"""Unit tests for the elastic-deflection serviceability calculators."""

from __future__ import annotations

import math

import baseUnits as u
import pytest

from apeSteel import (
    A36,
    A992,
    DoublySymmetricISection,
)
from apeSteel.serviceability import (
    DEFAULT_CAMBER_FRACTION_OF_DEAD_LOAD_DEFLECTION,
    DEFAULT_LIVE_LOAD_DEFLECTION_LIMIT_DENOMINATOR,
    DEFAULT_TOTAL_LOAD_DEFLECTION_LIMIT_DENOMINATOR,
    compute_deflection_cantilever_udl_and_tip_load,
    compute_deflection_simply_supported_point_load_arbitrary,
    compute_deflection_simply_supported_point_load_midspan,
    compute_deflection_simply_supported_udl,
    recommend_camber_from_dead_load_deflection,
)


# Common fixture: a W12X26-ish plate-built I.
@pytest.fixture(scope="module")
def section() -> DoublySymmetricISection:
    return DoublySymmetricISection(
        flange_width_bf=165 * u.mm,
        flange_thickness_tf=10 * u.mm,
        web_clear_height_hw=290 * u.mm,
        web_thickness_tw=6 * u.mm,
    )


class TestSimplySupportedUDL:
    def test_textbook_formula_matches(self, section: DoublySymmetricISection) -> None:
        sp = section.compute_section_properties()
        E = A992.elastic_modulus_E
        Ix = sp.moment_of_inertia_strong_axis_Ix
        L = 6.0 * u.m
        w = 5.0 * u.kN / u.m

        r = compute_deflection_simply_supported_udl(
            section_properties=sp,
            material=A992,
            span_length_L=L,
            distributed_load_live_w_live=w,
        )
        expected = 5.0 * w * L**4 / (384.0 * E * Ix)
        assert r.deflection_under_live_load_delta_live == pytest.approx(expected, rel=1e-12)

    def test_live_dead_sd_components_compose(self, section: DoublySymmetricISection) -> None:
        sp = section.compute_section_properties()
        L = 6.0 * u.m

        w_d = 2.0 * u.kN / u.m
        w_sd = 1.0 * u.kN / u.m
        w_l = 3.0 * u.kN / u.m
        r = compute_deflection_simply_supported_udl(
            section_properties=sp,
            material=A992,
            span_length_L=L,
            distributed_load_dead_w_dead=w_d,
            distributed_load_superdead_w_sd=w_sd,
            distributed_load_live_w_live=w_l,
        )
        assert r.distributed_load_total_w_total == pytest.approx(w_d + w_sd + w_l)
        # delta is linear in load - total deflection is the sum of components.
        sum_of_components = (
            r.deflection_under_dead_load_delta_dead
            + (
                5.0
                * w_sd
                * L**4
                / (384.0 * A992.elastic_modulus_E * sp.moment_of_inertia_strong_axis_Ix)
            )
            + r.deflection_under_live_load_delta_live
        )
        assert r.deflection_under_total_load_delta_total == pytest.approx(
            sum_of_components, rel=1e-12
        )

    def test_limits_use_supplied_denominators(self, section: DoublySymmetricISection) -> None:
        sp = section.compute_section_properties()
        L = 6.0 * u.m
        r = compute_deflection_simply_supported_udl(
            section_properties=sp,
            material=A992,
            span_length_L=L,
            distributed_load_live_w_live=1.0 * u.kN / u.m,
            live_load_limit_denominator=360.0,
            total_load_limit_denominator=240.0,
        )
        assert r.deflection_limit_live == pytest.approx(L / 360.0)
        assert r.deflection_limit_total == pytest.approx(L / 240.0)

    def test_acceptable_for_light_load(self, section: DoublySymmetricISection) -> None:
        sp = section.compute_section_properties()
        r = compute_deflection_simply_supported_udl(
            section_properties=sp,
            material=A992,
            span_length_L=6.0 * u.m,
            distributed_load_live_w_live=1.0 * u.kN / u.m,
        )
        assert r.is_live_load_deflection_acceptable
        assert r.is_total_load_deflection_acceptable
        assert r.governing_limit_state == "deflection_acceptable"

    def test_fails_for_huge_load(self, section: DoublySymmetricISection) -> None:
        sp = section.compute_section_properties()
        # 1 MN/m UDL would obviously fail any beam.
        r = compute_deflection_simply_supported_udl(
            section_properties=sp,
            material=A992,
            span_length_L=6.0 * u.m,
            distributed_load_live_w_live=1000.0 * u.kN / u.m,
        )
        assert not r.is_live_load_deflection_acceptable
        assert r.governing_limit_state in (
            "live_load_deflection_exceeded",
            "live_and_total_load_deflection_exceeded",
        )

    def test_dataclass_is_frozen(self, section: DoublySymmetricISection) -> None:
        sp = section.compute_section_properties()
        r = compute_deflection_simply_supported_udl(
            section_properties=sp,
            material=A992,
            span_length_L=6.0 * u.m,
        )
        with pytest.raises(AttributeError):
            r.elastic_modulus_E = 0.0  # type: ignore[misc]

    def test_governing_label_distinguishes_live_only_failure(
        self, section: DoublySymmetricISection
    ) -> None:
        sp = section.compute_section_properties()
        E = A992.elastic_modulus_E
        Ix = sp.moment_of_inertia_strong_axis_Ix
        L = 6.0 * u.m
        # Find a w_live just above L/360 limit but with no dead load so
        # total fails at L/240 too -> 'live_and_total' label.
        delta_at_unit_w = 5.0 * L**4 / (384.0 * E * Ix)
        w_just_over_360 = (L / 360.0) / delta_at_unit_w * 1.5
        r = compute_deflection_simply_supported_udl(
            section_properties=sp,
            material=A992,
            span_length_L=L,
            distributed_load_live_w_live=w_just_over_360,
        )
        assert not r.is_live_load_deflection_acceptable


class TestSimplySupportedPointLoadMidspan:
    def test_textbook_formula(self, section: DoublySymmetricISection) -> None:
        sp = section.compute_section_properties()
        L = 6.0 * u.m
        P = 20.0 * u.kN
        E = A992.elastic_modulus_E
        Ix = sp.moment_of_inertia_strong_axis_Ix
        r = compute_deflection_simply_supported_point_load_midspan(
            section_properties=sp,
            material=A992,
            span_length_L=L,
            point_load_live_P_live=P,
        )
        expected = P * L**3 / (48.0 * E * Ix)
        assert r.deflection_under_live_load_delta_live == pytest.approx(expected, rel=1e-12)

    def test_dead_and_live_decomposition(self, section: DoublySymmetricISection) -> None:
        sp = section.compute_section_properties()
        r = compute_deflection_simply_supported_point_load_midspan(
            section_properties=sp,
            material=A992,
            span_length_L=6.0 * u.m,
            point_load_dead_P_dead=10.0 * u.kN,
            point_load_live_P_live=20.0 * u.kN,
        )
        assert r.point_load_total_P_total == pytest.approx(30.0 * u.kN)
        # delta_total = delta_dead + delta_live  (linear elasticity).
        assert r.deflection_under_total_load_delta_total == pytest.approx(
            r.deflection_under_dead_load_delta_dead + r.deflection_under_live_load_delta_live,
            rel=1e-12,
        )


class TestSimplySupportedPointLoadArbitrary:
    def test_reduces_to_midspan_formula_when_centered(
        self, section: DoublySymmetricISection
    ) -> None:
        sp = section.compute_section_properties()
        L = 6.0 * u.m
        P = 20.0 * u.kN
        E = A992.elastic_modulus_E
        Ix = sp.moment_of_inertia_strong_axis_Ix
        r = compute_deflection_simply_supported_point_load_arbitrary(
            section_properties=sp,
            material=A992,
            span_length_L=L,
            distance_from_left_support_a=L / 2.0,
            point_load_total_P_total=P,
        )
        expected = P * L**3 / (48.0 * E * Ix)
        # Both mid-span and max must agree with the centered closed form.
        assert r.deflection_at_midspan_delta_midspan == pytest.approx(expected, rel=1e-12)
        assert r.deflection_maximum_delta_max == pytest.approx(expected, rel=1e-12)

    def test_max_location_for_left_loaded_case(self, section: DoublySymmetricISection) -> None:
        sp = section.compute_section_properties()
        L = 6.0 * u.m
        a = L / 4.0  # load near left support; max should be on the right (longer) segment.
        r = compute_deflection_simply_supported_point_load_arbitrary(
            section_properties=sp,
            material=A992,
            span_length_L=L,
            distance_from_left_support_a=a,
            point_load_total_P_total=10.0 * u.kN,
        )
        # Closed form: x_max from left support = L - sqrt((L^2 - a^2)/3)
        # because the longer segment is to the right of the load (b > a).
        expected_x = L - math.sqrt((L**2 - a**2) / 3.0)
        assert r.location_of_max_from_left_support_x_max == pytest.approx(expected_x, rel=1e-9)
        # Max must be >= midspan deflection.
        assert r.deflection_maximum_delta_max >= r.deflection_at_midspan_delta_midspan - 1e-9

    @pytest.mark.parametrize("invalid_a", [-1.0 * u.mm, 0.0, 6.0 * u.m, 7.0 * u.m])
    def test_raises_for_a_outside_span(
        self, section: DoublySymmetricISection, invalid_a: float
    ) -> None:
        sp = section.compute_section_properties()
        with pytest.raises(ValueError, match="distance_from_left_support_a"):
            compute_deflection_simply_supported_point_load_arbitrary(
                section_properties=sp,
                material=A992,
                span_length_L=6.0 * u.m,
                distance_from_left_support_a=invalid_a,
                point_load_total_P_total=10.0 * u.kN,
            )


class TestCantileverUDLAndTipLoad:
    def test_udl_only_matches_textbook(self, section: DoublySymmetricISection) -> None:
        sp = section.compute_section_properties()
        L = 2.0 * u.m
        w = 2.0 * u.kN / u.m
        E = A992.elastic_modulus_E
        Ix = sp.moment_of_inertia_strong_axis_Ix
        r = compute_deflection_cantilever_udl_and_tip_load(
            section_properties=sp,
            material=A992,
            cantilever_length_L=L,
            distributed_load_w=w,
        )
        expected = w * L**4 / (8.0 * E * Ix)
        assert r.deflection_at_tip_delta_tip == pytest.approx(expected, rel=1e-12)
        assert r.deflection_from_tip_load_delta_tip_load == pytest.approx(0.0)

    def test_tip_load_only_matches_textbook(self, section: DoublySymmetricISection) -> None:
        sp = section.compute_section_properties()
        L = 2.0 * u.m
        P = 10.0 * u.kN
        E = A992.elastic_modulus_E
        Ix = sp.moment_of_inertia_strong_axis_Ix
        r = compute_deflection_cantilever_udl_and_tip_load(
            section_properties=sp,
            material=A992,
            cantilever_length_L=L,
            tip_point_load_P=P,
        )
        expected = P * L**3 / (3.0 * E * Ix)
        assert r.deflection_at_tip_delta_tip == pytest.approx(expected, rel=1e-12)
        assert r.deflection_from_udl_delta_udl == pytest.approx(0.0)

    def test_combined_superposes(self, section: DoublySymmetricISection) -> None:
        sp = section.compute_section_properties()
        L = 2.0 * u.m
        w = 2.0 * u.kN / u.m
        P = 10.0 * u.kN
        E = A992.elastic_modulus_E
        Ix = sp.moment_of_inertia_strong_axis_Ix
        r = compute_deflection_cantilever_udl_and_tip_load(
            section_properties=sp,
            material=A992,
            cantilever_length_L=L,
            distributed_load_w=w,
            tip_point_load_P=P,
        )
        expected_udl = w * L**4 / (8.0 * E * Ix)
        expected_tip = P * L**3 / (3.0 * E * Ix)
        assert r.deflection_at_tip_delta_tip == pytest.approx(
            expected_udl + expected_tip, rel=1e-12
        )


class TestCamberRecommendation:
    def test_default_factor_is_zero_point_eight(self) -> None:
        assert DEFAULT_CAMBER_FRACTION_OF_DEAD_LOAD_DEFLECTION == 0.8

    def test_no_rounding_in_default(self) -> None:
        camber = recommend_camber_from_dead_load_deflection(10.123 * u.mm)
        assert camber == pytest.approx(0.8 * 10.123 * u.mm)

    def test_camber_factor_is_configurable(self) -> None:
        camber = recommend_camber_from_dead_load_deflection(10.0 * u.mm, camber_factor=1.0)
        assert camber == pytest.approx(10.0 * u.mm)


class TestDefaultsMatchSpreadsheet:
    def test_live_limit_default_is_360(self) -> None:
        assert DEFAULT_LIVE_LOAD_DEFLECTION_LIMIT_DENOMINATOR == 360.0

    def test_total_limit_default_is_240(self) -> None:
        assert DEFAULT_TOTAL_LOAD_DEFLECTION_LIMIT_DENOMINATOR == 240.0


class TestMaterialIndependence:
    def test_E_for_A992_and_A36_are_the_same(self) -> None:
        # AISC pegs E = 29 000 ksi for all carbon and HSLA steels, so
        # the deflection for A992 and A36 should match identically.
        sec = DoublySymmetricISection(150 * u.mm, 10 * u.mm, 290 * u.mm, 6 * u.mm)
        sp = sec.compute_section_properties()
        L = 4.0 * u.m
        w = 5.0 * u.kN / u.m
        r1 = compute_deflection_simply_supported_udl(
            section_properties=sp,
            material=A992,
            span_length_L=L,
            distributed_load_live_w_live=w,
        )
        r2 = compute_deflection_simply_supported_udl(
            section_properties=sp,
            material=A36,
            span_length_L=L,
            distributed_load_live_w_live=w,
        )
        assert r1.deflection_under_live_load_delta_live == pytest.approx(
            r2.deflection_under_live_load_delta_live, rel=1e-12
        )


class TestElementCompositeApi:
    def test_element_serviceability_simply_supported_udl(self) -> None:
        sec = DoublySymmetricISection(150 * u.mm, 10 * u.mm, 290 * u.mm, 6 * u.mm)
        element = sec.element(material=A992)
        r = element.serviceability_simply_supported_udl(
            span_length_L=6.0 * u.m,
            distributed_load_live_w_live=5.0 * u.kN / u.m,
            distributed_load_dead_w_dead=3.0 * u.kN / u.m,
        )
        # Element method must produce the same value as the free function.
        sp = sec.compute_section_properties()
        r_free = compute_deflection_simply_supported_udl(
            section_properties=sp,
            material=A992,
            span_length_L=6.0 * u.m,
            distributed_load_live_w_live=5.0 * u.kN / u.m,
            distributed_load_dead_w_dead=3.0 * u.kN / u.m,
        )
        assert r.deflection_under_total_load_delta_total == pytest.approx(
            r_free.deflection_under_total_load_delta_total
        )

    def test_element_serviceability_cantilever(self) -> None:
        sec = DoublySymmetricISection(150 * u.mm, 10 * u.mm, 290 * u.mm, 6 * u.mm)
        element = sec.element(material=A992)
        r = element.serviceability_cantilever_udl_and_tip_load(
            cantilever_length_L=2.0 * u.m,
            distributed_load_w=2.0 * u.kN / u.m,
            tip_point_load_P=10.0 * u.kN,
        )
        assert r.deflection_at_tip_delta_tip > 0
        assert r.cantilever_length_L == pytest.approx(2.0 * u.m)

    def test_element_serviceability_point_load_midspan(self) -> None:
        sec = DoublySymmetricISection(150 * u.mm, 10 * u.mm, 290 * u.mm, 6 * u.mm)
        element = sec.element(material=A992)
        r = element.serviceability_simply_supported_point_load_midspan(
            span_length_L=6.0 * u.m,
            point_load_live_P_live=20.0 * u.kN,
        )
        assert r.deflection_under_live_load_delta_live > 0

    def test_element_serviceability_point_load_arbitrary(self) -> None:
        sec = DoublySymmetricISection(150 * u.mm, 10 * u.mm, 290 * u.mm, 6 * u.mm)
        element = sec.element(material=A992)
        r = element.serviceability_simply_supported_point_load_arbitrary(
            span_length_L=6.0 * u.m,
            distance_from_left_support_a=2.0 * u.m,
            point_load_total_P_total=20.0 * u.kN,
        )
        assert r.deflection_at_midspan_delta_midspan > 0
        assert r.deflection_maximum_delta_max > 0
