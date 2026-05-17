"""Unit tests for doubler-plate sizing, continuity-plate need-check,
and the SectionProperties detailing-offset fields they depend on."""

from __future__ import annotations

import math

import baseUnits as u
import pytest

from apeSteel import (
    A992,
    AISCv16Catalog,
    BeamColumnConnection,
    ContinuityPlateRecommendationReport,
    DoublerPlateRecommendationReport,
    DoublySymmetricISection,
    EuropeanIPECatalog,
    check_continuity_plates_required_358,
    check_panel_zone_shear_341,
    recommend_doubler_plate_thickness_341,
)
from apeSteel.sections.properties import SectionProperties
from apeSteel.seismic.doubler_plate_design import (
    LOCAL_BUCKLING_PANEL_ASPECT_RATIO_DIVISOR_90,
)


@pytest.fixture
def beam_section() -> DoublySymmetricISection:
    return DoublySymmetricISection(
        flange_width_bf=165 * u.mm,
        flange_thickness_tf=11.4 * u.mm,
        web_clear_height_hw=504 * u.mm,
        web_thickness_tw=8.9 * u.mm,
    )


@pytest.fixture
def light_column() -> DoublySymmetricISection:
    return DoublySymmetricISection(
        flange_width_bf=369 * u.mm,
        flange_thickness_tf=18.0 * u.mm,
        web_clear_height_hw=318 * u.mm,
        web_thickness_tw=11.2 * u.mm,
    )


@pytest.fixture
def heavy_column() -> DoublySymmetricISection:
    return DoublySymmetricISection(
        flange_width_bf=399 * u.mm,
        flange_thickness_tf=36.6 * u.mm,
        web_clear_height_hw=308 * u.mm,
        web_thickness_tw=22.6 * u.mm,
    )


# ---------------------------------------------------------------------------
# Doubler-plate sizing
# ---------------------------------------------------------------------------
class TestDoublerPlateRequired:
    def test_light_column_needs_doubler(
        self,
        beam_section: DoublySymmetricISection,
        light_column: DoublySymmetricISection,
    ) -> None:
        bsp = beam_section.compute_section_properties()
        csp = light_column.compute_section_properties()
        r = recommend_doubler_plate_thickness_341(bsp, A992, csp, A992)
        assert r.is_doubler_plate_required
        assert r.minimum_doubler_thickness_required_t_dp_min > 0.0
        assert (
            r.recommended_doubler_thickness_t_dp_recommended
            >= r.minimum_doubler_thickness_required_t_dp_min
        )

    def test_heavy_column_needs_no_doubler(
        self,
        beam_section: DoublySymmetricISection,
        heavy_column: DoublySymmetricISection,
    ) -> None:
        bsp = beam_section.compute_section_properties()
        csp = heavy_column.compute_section_properties()
        r = recommend_doubler_plate_thickness_341(bsp, A992, csp, A992)
        assert not r.is_doubler_plate_required
        assert r.minimum_doubler_thickness_required_t_dp_min == 0.0
        assert r.governing_limit_state == "no_doubler_required"


class TestDoublerLocalBucklingLimit:
    def test_local_buckling_limit_is_db_plus_dc_over_90(
        self,
        beam_section: DoublySymmetricISection,
        light_column: DoublySymmetricISection,
    ) -> None:
        bsp = beam_section.compute_section_properties()
        csp = light_column.compute_section_properties()
        r = recommend_doubler_plate_thickness_341(bsp, A992, csp, A992)
        expected = max(
            0.0,
            (bsp.overall_depth_d + csp.overall_depth_d) / 90.0 - csp.web_thickness_tw,
        )
        assert r.minimum_doubler_thickness_for_local_buckling_t_dp_local == pytest.approx(
            expected, rel=1e-12
        )


class TestDoublerShearLimitSatisfiesDcr:
    def test_recommendation_drives_dcr_to_at_most_1(
        self,
        beam_section: DoublySymmetricISection,
        light_column: DoublySymmetricISection,
    ) -> None:
        bsp = beam_section.compute_section_properties()
        csp = light_column.compute_section_properties()
        rec = recommend_doubler_plate_thickness_341(bsp, A992, csp, A992)
        verify = check_panel_zone_shear_341(
            bsp,
            A992,
            csp,
            A992,
            additional_doubler_plate_thickness_t_dp=rec.recommended_doubler_thickness_t_dp_recommended,
        )
        assert verify.is_demand_to_capacity_acceptable
        assert verify.demand_to_capacity_ratio <= 1.0 + 1e-9


class TestDoublerRoundingIncrement:
    def test_default_increment_is_2mm(
        self,
        beam_section: DoublySymmetricISection,
        light_column: DoublySymmetricISection,
    ) -> None:
        bsp = beam_section.compute_section_properties()
        csp = light_column.compute_section_properties()
        rec = recommend_doubler_plate_thickness_341(bsp, A992, csp, A992)
        assert rec.rounding_increment_for_doubler_thickness == 2.0
        if rec.recommended_doubler_thickness_t_dp_recommended > 0.0:
            inc = rec.rounding_increment_for_doubler_thickness
            rem = rec.recommended_doubler_thickness_t_dp_recommended % inc
            assert math.isclose(rem, 0.0, abs_tol=1e-9) or math.isclose(rem, inc, abs_tol=1e-9)

    def test_zero_increment_disables_rounding(
        self,
        beam_section: DoublySymmetricISection,
        light_column: DoublySymmetricISection,
    ) -> None:
        bsp = beam_section.compute_section_properties()
        csp = light_column.compute_section_properties()
        rec = recommend_doubler_plate_thickness_341(
            bsp, A992, csp, A992, rounding_increment_for_doubler_thickness=0.0
        )
        assert rec.recommended_doubler_thickness_t_dp_recommended == pytest.approx(
            rec.minimum_doubler_thickness_required_t_dp_min
        )

    def test_negative_increment_raises(
        self,
        beam_section: DoublySymmetricISection,
        light_column: DoublySymmetricISection,
    ) -> None:
        bsp = beam_section.compute_section_properties()
        csp = light_column.compute_section_properties()
        with pytest.raises(ValueError, match="rounding_increment"):
            recommend_doubler_plate_thickness_341(
                bsp, A992, csp, A992, rounding_increment_for_doubler_thickness=-1.0
            )


class TestDoublerConstants:
    def test_local_buckling_divisor_is_90(self) -> None:
        assert LOCAL_BUCKLING_PANEL_ASPECT_RATIO_DIVISOR_90 == 90.0


class TestDoublerReportShape:
    def test_returns_recommendation_report(
        self,
        beam_section: DoublySymmetricISection,
        light_column: DoublySymmetricISection,
    ) -> None:
        bsp = beam_section.compute_section_properties()
        csp = light_column.compute_section_properties()
        r = recommend_doubler_plate_thickness_341(bsp, A992, csp, A992)
        assert isinstance(r, DoublerPlateRecommendationReport)

    def test_report_is_frozen(
        self,
        beam_section: DoublySymmetricISection,
        light_column: DoublySymmetricISection,
    ) -> None:
        bsp = beam_section.compute_section_properties()
        csp = light_column.compute_section_properties()
        r = recommend_doubler_plate_thickness_341(bsp, A992, csp, A992)
        with pytest.raises(AttributeError):
            r.is_doubler_plate_required = False  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Continuity-plate need check
# ---------------------------------------------------------------------------
class TestContinuityPlateNeed:
    def test_light_column_needs_continuity_plates(
        self,
        beam_section: DoublySymmetricISection,
        light_column: DoublySymmetricISection,
    ) -> None:
        bsp = beam_section.compute_section_properties()
        csp = light_column.compute_section_properties()
        r = check_continuity_plates_required_358(bsp, A992, csp, A992)
        assert r.is_required

    def test_heavy_column_does_not_need_continuity_plates(
        self,
        beam_section: DoublySymmetricISection,
        heavy_column: DoublySymmetricISection,
    ) -> None:
        bsp = beam_section.compute_section_properties()
        csp = heavy_column.compute_section_properties()
        r = check_continuity_plates_required_358(bsp, A992, csp, A992)
        assert not r.is_required
        assert r.minimum_continuity_plate_thickness_t_cp_min == 0.0


class TestContinuityPlateDimensions:
    def test_one_sided_thickness_is_half_beam_tf(
        self,
        beam_section: DoublySymmetricISection,
        light_column: DoublySymmetricISection,
    ) -> None:
        bsp = beam_section.compute_section_properties()
        csp = light_column.compute_section_properties()
        r = check_continuity_plates_required_358(bsp, A992, csp, A992, number_of_beam_sides=1)
        assert r.minimum_continuity_plate_thickness_t_cp_min == pytest.approx(
            bsp.flange_thickness_tf / 2.0
        )

    def test_two_sided_thickness_matches_beam_tf(
        self,
        beam_section: DoublySymmetricISection,
        light_column: DoublySymmetricISection,
    ) -> None:
        bsp = beam_section.compute_section_properties()
        csp = light_column.compute_section_properties()
        r = check_continuity_plates_required_358(bsp, A992, csp, A992, number_of_beam_sides=2)
        assert r.minimum_continuity_plate_thickness_t_cp_min == pytest.approx(
            bsp.flange_thickness_tf
        )

    def test_width_uses_column_k1_when_available(
        self,
        beam_section: DoublySymmetricISection,
        light_column: DoublySymmetricISection,
    ) -> None:
        bsp = beam_section.compute_section_properties()
        csp = light_column.compute_section_properties()
        r = check_continuity_plates_required_358(bsp, A992, csp, A992)
        # Plate-built column's k1 = tw/2; expected = (bf,beam - 2 k1)/2.
        expected_width = max(0.0, (bsp.flange_width_bf - 2.0 * csp.k_one_k1) / 2.0)
        assert r.minimum_continuity_plate_width_b_cp_min == pytest.approx(expected_width, rel=1e-12)

    def test_width_falls_back_to_10mm_offset_when_k1_is_zero(
        self, beam_section: DoublySymmetricISection
    ) -> None:
        # Hand-craft a SectionProperties with k1=0 to exercise the
        # legacy 10 mm-offset fallback path.
        bsp = beam_section.compute_section_properties()
        zero_k1_col = SectionProperties(
            overall_depth_d=400.0,
            gross_area_Ag=10000.0,
            nominal_weight_per_unit_length_w=0.1,
            moment_of_inertia_strong_axis_Ix=1e8,
            elastic_section_modulus_strong_axis_Sx=1e5,
            plastic_section_modulus_strong_axis_Zx=1e5,
            radius_of_gyration_strong_axis_rx=100.0,
            moment_of_inertia_weak_axis_Iy=1e7,
            elastic_section_modulus_weak_axis_Sy=1e4,
            plastic_section_modulus_weak_axis_Zy=1e4,
            radius_of_gyration_weak_axis_ry=50.0,
            torsional_constant_J=1e5,
            warping_constant_Cw=1e11,
            distance_between_flange_centroids_ho=380.0,
            effective_radius_of_gyration_for_LTB_rts=50.0,
            flange_width_to_thickness_ratio_bf_2tf=6.0,
            web_height_to_thickness_ratio_h_tw=30.0,
            web_thickness_tw=12.0,
            flange_width_bf=200.0,
            flange_thickness_tf=15.0,
            # k1 left at default 0.0 -> heuristic kicks in.
        )
        r = check_continuity_plates_required_358(bsp, A992, zero_k1_col, A992)
        if r.is_required:
            expected_fallback = max(
                0.0,
                (bsp.flange_width_bf - zero_k1_col.web_thickness_tw) / 2.0 - 10.0,
            )
            assert r.minimum_continuity_plate_width_b_cp_min == pytest.approx(
                expected_fallback, rel=1e-12
            )

    def test_invalid_number_of_beam_sides_raises(
        self,
        beam_section: DoublySymmetricISection,
        light_column: DoublySymmetricISection,
    ) -> None:
        bsp = beam_section.compute_section_properties()
        csp = light_column.compute_section_properties()
        with pytest.raises(ValueError, match="number_of_beam_sides"):
            check_continuity_plates_required_358(bsp, A992, csp, A992, number_of_beam_sides=3)


class TestContinuityReportShape:
    def test_returns_recommendation_report(
        self,
        beam_section: DoublySymmetricISection,
        light_column: DoublySymmetricISection,
    ) -> None:
        bsp = beam_section.compute_section_properties()
        csp = light_column.compute_section_properties()
        r = check_continuity_plates_required_358(bsp, A992, csp, A992)
        assert isinstance(r, ContinuityPlateRecommendationReport)

    def test_report_is_frozen(
        self,
        beam_section: DoublySymmetricISection,
        light_column: DoublySymmetricISection,
    ) -> None:
        bsp = beam_section.compute_section_properties()
        csp = light_column.compute_section_properties()
        r = check_continuity_plates_required_358(bsp, A992, csp, A992)
        with pytest.raises(AttributeError):
            r.is_required = False  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Composite API
# ---------------------------------------------------------------------------
class TestCompositeApi:
    def test_recommend_doubler_plate_matches_free_function(
        self,
        beam_section: DoublySymmetricISection,
        light_column: DoublySymmetricISection,
    ) -> None:
        beam_el = beam_section.element(A992)
        col_el = light_column.element(A992)
        joint = BeamColumnConnection(beam=beam_el, column=col_el)
        r_composite = joint.recommend_doubler_plate()
        r_free = recommend_doubler_plate_thickness_341(
            beam_section.compute_section_properties(),
            A992,
            light_column.compute_section_properties(),
            A992,
        )
        assert r_composite.recommended_doubler_thickness_t_dp_recommended == pytest.approx(
            r_free.recommended_doubler_thickness_t_dp_recommended
        )

    def test_check_continuity_plates_matches_free_function(
        self,
        beam_section: DoublySymmetricISection,
        light_column: DoublySymmetricISection,
    ) -> None:
        beam_el = beam_section.element(A992)
        col_el = light_column.element(A992)
        joint = BeamColumnConnection(beam=beam_el, column=col_el)
        r_composite = joint.check_continuity_plates()
        r_free = check_continuity_plates_required_358(
            beam_section.compute_section_properties(),
            A992,
            light_column.compute_section_properties(),
            A992,
        )
        assert r_composite.is_required == r_free.is_required
        assert r_composite.minimum_continuity_plate_thickness_t_cp_min == pytest.approx(
            r_free.minimum_continuity_plate_thickness_t_cp_min
        )


# ---------------------------------------------------------------------------
# SectionProperties detailing-offset fields (kdes / kdet / k1)
# ---------------------------------------------------------------------------
class TestDetailingOffsetsAreExposed:
    def test_plate_built_kdes_equals_tf(self, beam_section: DoublySymmetricISection) -> None:
        sp = beam_section.compute_section_properties()
        assert sp.k_design_kdes == pytest.approx(sp.flange_thickness_tf)
        assert sp.k_detailing_kdet == pytest.approx(sp.flange_thickness_tf)

    def test_plate_built_k1_equals_half_tw(self, beam_section: DoublySymmetricISection) -> None:
        sp = beam_section.compute_section_properties()
        assert sp.k_one_k1 == pytest.approx(sp.web_thickness_tw / 2.0)

    def test_aisc_v16_catalog_populates_published_kdes(self) -> None:
        sp = AISCv16Catalog().get_section_properties("W24X94")
        # AISC v16 SI Manual: W24X94 kdes = 35.1, kdet = 54.0, k1 = 36.5.
        assert sp.k_design_kdes == pytest.approx(35.1)
        assert sp.k_detailing_kdet == pytest.approx(54.0)
        assert sp.k_one_k1 == pytest.approx(36.5)

    def test_european_ipe_derives_kdes_from_root_radius(self) -> None:
        sp = EuropeanIPECatalog().get_section_properties("IPE 300")
        # IPE 300: tf=10.7, r=15, tw=7.1.
        # Derived: kdes = tf + r = 25.7, k1 = tw/2 + r = 18.55.
        assert sp.k_design_kdes == pytest.approx(25.7)
        assert sp.k_detailing_kdet == pytest.approx(25.7)
        assert sp.k_one_k1 == pytest.approx(18.55)
