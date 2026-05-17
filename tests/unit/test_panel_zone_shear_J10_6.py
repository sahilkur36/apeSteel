"""Unit tests for the AISC 360 §J10.6 panel-zone shear check."""

from __future__ import annotations

import baseUnits as u
import pytest

from apeSteel import (
    A992,
    BeamColumnConnection,
    DoublySymmetricISection,
    PanelZoneShearReport,
    check_panel_zone_shear_341,
)
from apeSteel.core.materials import SteelMaterial
from apeSteel.seismic.panel_zone_shear_J10_6 import (
    PANEL_ZONE_DEFORMATION_BOOST_COEFFICIENT_3,
    PHI_PANEL_ZONE_SHEAR_LRFD,
    AXIAL_REDUCTION_COEFFICIENT_J10_10_1p4,
    AXIAL_REDUCTION_COEFFICIENT_J10_12_1p2,
    AXIAL_REDUCTION_COEFFICIENT_J10_12_1p9,
    DEFAULT_PROBABLE_STRAIN_HARDENING_FACTOR_Cpr_IF_FU_UNKNOWN,
    PANEL_ZONE_SHEAR_NOMINAL_STRESS_COEFFICIENT_0p6,
    PROBABLE_STRAIN_HARDENING_FACTOR_Cpr_UPPER_BOUND_1p2,
)


@pytest.fixture
def beam_section() -> DoublySymmetricISection:
    # W21X44-ish.
    return DoublySymmetricISection(
        flange_width_bf=165 * u.mm,
        flange_thickness_tf=11.4 * u.mm,
        web_clear_height_hw=504 * u.mm,
        web_thickness_tw=8.9 * u.mm,
    )


@pytest.fixture
def column_section() -> DoublySymmetricISection:
    # W14X90-ish.
    return DoublySymmetricISection(
        flange_width_bf=369 * u.mm,
        flange_thickness_tf=18.0 * u.mm,
        web_clear_height_hw=318 * u.mm,
        web_thickness_tw=11.2 * u.mm,
    )


class TestConstants:
    def test_0p6_coefficient(self) -> None:
        assert PANEL_ZONE_SHEAR_NOMINAL_STRESS_COEFFICIENT_0p6 == 0.6

    def test_1p4_J10_10(self) -> None:
        assert AXIAL_REDUCTION_COEFFICIENT_J10_10_1p4 == 1.4

    def test_3_boost(self) -> None:
        assert PANEL_ZONE_DEFORMATION_BOOST_COEFFICIENT_3 == 3.0

    def test_1p9_and_1p2_J10_12(self) -> None:
        assert AXIAL_REDUCTION_COEFFICIENT_J10_12_1p9 == 1.9
        assert AXIAL_REDUCTION_COEFFICIENT_J10_12_1p2 == 1.2

    def test_phi_is_0p90(self) -> None:
        assert PHI_PANEL_ZONE_SHEAR_LRFD == 0.90


class TestJ109BaselineEquation:
    """Zero axial load, no panel-zone-deformation boost."""

    def test_governing_equation_label_is_J10_9(
        self,
        beam_section: DoublySymmetricISection,
        column_section: DoublySymmetricISection,
    ) -> None:
        bsp = beam_section.compute_section_properties()
        csp = column_section.compute_section_properties()
        r = check_panel_zone_shear_341(bsp, A992, csp, A992)
        assert r.governing_equation == "J10-9"

    def test_Rn_matches_0p6_Ry_Fy_dc_tw(
        self,
        beam_section: DoublySymmetricISection,
        column_section: DoublySymmetricISection,
    ) -> None:
        bsp = beam_section.compute_section_properties()
        csp = column_section.compute_section_properties()
        r = check_panel_zone_shear_341(bsp, A992, csp, A992)
        expected_Rn = (
            0.6
            * A992.yield_stress_Fy
            * A992.expected_yield_ratio_Ry
            * csp.overall_depth_d
            * csp.web_thickness_tw
        )
        assert r.panel_zone_shear_capacity_Rn == pytest.approx(expected_Rn, rel=1e-12)


class TestJ1010AxialReductionWithoutBoost:
    def test_governing_equation_label_is_J10_10(
        self,
        beam_section: DoublySymmetricISection,
        column_section: DoublySymmetricISection,
    ) -> None:
        bsp = beam_section.compute_section_properties()
        csp = column_section.compute_section_properties()
        Pc = A992.yield_stress_Fy * csp.gross_area_Ag
        # Pr/Pc = 0.5 -> J10-10 governs (0.4 < 0.5).
        r = check_panel_zone_shear_341(bsp, A992, csp, A992, column_axial_demand_Pr=0.5 * Pc)
        assert r.governing_equation == "J10-10"

    def test_Rn_scales_by_1p4_minus_Pr_over_Pc(
        self,
        beam_section: DoublySymmetricISection,
        column_section: DoublySymmetricISection,
    ) -> None:
        bsp = beam_section.compute_section_properties()
        csp = column_section.compute_section_properties()
        Pc = A992.yield_stress_Fy * csp.gross_area_Ag
        base = check_panel_zone_shear_341(bsp, A992, csp, A992)
        reduced = check_panel_zone_shear_341(bsp, A992, csp, A992, column_axial_demand_Pr=0.5 * Pc)
        expected_ratio = 1.4 - 0.5
        assert reduced.panel_zone_shear_capacity_Rn == pytest.approx(
            base.panel_zone_shear_capacity_Rn * expected_ratio, rel=1e-12
        )


class TestJ1011FrameStabilityBoost:
    def test_governing_equation_label_is_J10_11(
        self,
        beam_section: DoublySymmetricISection,
        column_section: DoublySymmetricISection,
    ) -> None:
        bsp = beam_section.compute_section_properties()
        csp = column_section.compute_section_properties()
        r = check_panel_zone_shear_341(
            bsp, A992, csp, A992, consider_panel_zone_deformation_in_frame_stability=True
        )
        assert r.governing_equation == "J10-11"

    def test_boost_adds_flange_term(
        self,
        beam_section: DoublySymmetricISection,
        column_section: DoublySymmetricISection,
    ) -> None:
        bsp = beam_section.compute_section_properties()
        csp = column_section.compute_section_properties()
        base = check_panel_zone_shear_341(bsp, A992, csp, A992)
        boosted = check_panel_zone_shear_341(
            bsp,
            A992,
            csp,
            A992,
            consider_panel_zone_deformation_in_frame_stability=True,
        )
        # Boost factor = 1 + 3 * bcf * tcf^2 / (db * dc * tw)
        expected_boost = 1.0 + 3.0 * csp.flange_width_bf * csp.flange_thickness_tf**2 / (
            bsp.overall_depth_d * csp.overall_depth_d * csp.web_thickness_tw
        )
        assert boosted.panel_zone_shear_capacity_Rn == pytest.approx(
            base.panel_zone_shear_capacity_Rn * expected_boost, rel=1e-12
        )


class TestJ1012BoostPlusAxialReduction:
    def test_governing_equation_label_is_J10_12(
        self,
        beam_section: DoublySymmetricISection,
        column_section: DoublySymmetricISection,
    ) -> None:
        bsp = beam_section.compute_section_properties()
        csp = column_section.compute_section_properties()
        Pc = A992.yield_stress_Fy * csp.gross_area_Ag
        # Pr/Pc = 0.85 > 0.75 -> J10-12 governs.
        r = check_panel_zone_shear_341(
            bsp,
            A992,
            csp,
            A992,
            column_axial_demand_Pr=0.85 * Pc,
            consider_panel_zone_deformation_in_frame_stability=True,
        )
        assert r.governing_equation == "J10-12"

    def test_axial_factor_is_1p9_minus_1p2_Pr_over_Pc(
        self,
        beam_section: DoublySymmetricISection,
        column_section: DoublySymmetricISection,
    ) -> None:
        bsp = beam_section.compute_section_properties()
        csp = column_section.compute_section_properties()
        Pc = A992.yield_stress_Fy * csp.gross_area_Ag
        # Compare J10-11 (no axial penalty) vs J10-12 at Pr/Pc=0.85.
        r11 = check_panel_zone_shear_341(
            bsp,
            A992,
            csp,
            A992,
            consider_panel_zone_deformation_in_frame_stability=True,
        )
        r12 = check_panel_zone_shear_341(
            bsp,
            A992,
            csp,
            A992,
            column_axial_demand_Pr=0.85 * Pc,
            consider_panel_zone_deformation_in_frame_stability=True,
        )
        expected_ratio = 1.9 - 1.2 * 0.85
        assert r12.panel_zone_shear_capacity_Rn == pytest.approx(
            r11.panel_zone_shear_capacity_Rn * expected_ratio, rel=1e-12
        )


class TestDoublerPlateContribution:
    def test_Rn_scales_linearly_with_tw_effective_in_J10_9(
        self,
        beam_section: DoublySymmetricISection,
        column_section: DoublySymmetricISection,
    ) -> None:
        bsp = beam_section.compute_section_properties()
        csp = column_section.compute_section_properties()
        base = check_panel_zone_shear_341(bsp, A992, csp, A992)
        with_dp = check_panel_zone_shear_341(
            bsp,
            A992,
            csp,
            A992,
            additional_doubler_plate_thickness_t_dp=8.0 * u.mm,
        )
        expected_ratio = (csp.web_thickness_tw + 8.0) / csp.web_thickness_tw
        assert with_dp.panel_zone_shear_capacity_Rn == pytest.approx(
            base.panel_zone_shear_capacity_Rn * expected_ratio, rel=1e-12
        )


class TestDemand:
    def test_two_sided_doubles_demand(
        self,
        beam_section: DoublySymmetricISection,
        column_section: DoublySymmetricISection,
    ) -> None:
        bsp = beam_section.compute_section_properties()
        csp = column_section.compute_section_properties()
        r_one = check_panel_zone_shear_341(bsp, A992, csp, A992, number_of_beam_sides=1)
        r_two = check_panel_zone_shear_341(bsp, A992, csp, A992, number_of_beam_sides=2)
        assert r_two.panel_zone_shear_demand_Vu_pz == pytest.approx(
            2.0 * r_one.panel_zone_shear_demand_Vu_pz, rel=1e-12
        )

    def test_column_shear_credit_reduces_demand(
        self,
        beam_section: DoublySymmetricISection,
        column_section: DoublySymmetricISection,
    ) -> None:
        bsp = beam_section.compute_section_properties()
        csp = column_section.compute_section_properties()
        no_credit = check_panel_zone_shear_341(bsp, A992, csp, A992)
        with_credit = check_panel_zone_shear_341(
            bsp, A992, csp, A992, column_shear_credit_Vu_col=100 * u.kN
        )
        assert with_credit.panel_zone_shear_demand_Vu_pz == pytest.approx(
            no_credit.panel_zone_shear_demand_Vu_pz - 100 * u.kN, rel=1e-12
        )

    def test_negative_demand_clamped_to_zero(
        self,
        beam_section: DoublySymmetricISection,
        column_section: DoublySymmetricISection,
    ) -> None:
        bsp = beam_section.compute_section_properties()
        csp = column_section.compute_section_properties()
        # Huge column-shear credit -> demand floor is 0, not negative.
        r = check_panel_zone_shear_341(
            bsp, A992, csp, A992, column_shear_credit_Vu_col=10_000 * u.kN
        )
        assert r.panel_zone_shear_demand_Vu_pz == 0.0

    def test_invalid_number_of_beam_sides_raises(
        self,
        beam_section: DoublySymmetricISection,
        column_section: DoublySymmetricISection,
    ) -> None:
        bsp = beam_section.compute_section_properties()
        csp = column_section.compute_section_properties()
        with pytest.raises(ValueError, match="number_of_beam_sides"):
            check_panel_zone_shear_341(bsp, A992, csp, A992, number_of_beam_sides=3)


class TestCprStrainHardeningFactor:
    def test_default_falls_back_to_1p15_when_Fu_zero(self) -> None:
        # Build a SteelMaterial with Fu=0 to trigger the fallback.
        no_fu = SteelMaterial(
            name="hypothetical_no_Fu",
            yield_stress_Fy=345.0,
            tensile_stress_Fu=0.0,
            elastic_modulus_E=200000.0,
            shear_modulus_G=77200.0,
            density_rho=7.85e-9,
            expected_yield_ratio_Ry=1.1,
            expected_tensile_ratio_Rt=1.1,
        )
        beam = DoublySymmetricISection(165 * u.mm, 11.4 * u.mm, 504 * u.mm, 8.9 * u.mm)
        col = DoublySymmetricISection(369 * u.mm, 18 * u.mm, 318 * u.mm, 11.2 * u.mm)
        r = check_panel_zone_shear_341(
            beam.compute_section_properties(),
            no_fu,
            col.compute_section_properties(),
            A992,
        )
        assert r.probable_strain_hardening_factor_Cpr == pytest.approx(
            DEFAULT_PROBABLE_STRAIN_HARDENING_FACTOR_Cpr_IF_FU_UNKNOWN
        )

    def test_capped_at_1p2(self) -> None:
        # Engineer a material with Fy=100, Fu=300 -> Cpr = (100+300)/200 = 2.0, capped at 1.2.
        wild = SteelMaterial(
            name="wild",
            yield_stress_Fy=100.0,
            tensile_stress_Fu=300.0,
            elastic_modulus_E=200000.0,
            shear_modulus_G=77200.0,
            density_rho=7.85e-9,
            expected_yield_ratio_Ry=1.1,
            expected_tensile_ratio_Rt=1.1,
        )
        beam = DoublySymmetricISection(165 * u.mm, 11.4 * u.mm, 504 * u.mm, 8.9 * u.mm)
        col = DoublySymmetricISection(369 * u.mm, 18 * u.mm, 318 * u.mm, 11.2 * u.mm)
        r = check_panel_zone_shear_341(
            beam.compute_section_properties(),
            wild,
            col.compute_section_properties(),
            A992,
        )
        assert r.probable_strain_hardening_factor_Cpr == pytest.approx(
            PROBABLE_STRAIN_HARDENING_FACTOR_Cpr_UPPER_BOUND_1p2
        )


class TestReportShape:
    def test_returns_panel_zone_shear_report(
        self,
        beam_section: DoublySymmetricISection,
        column_section: DoublySymmetricISection,
    ) -> None:
        bsp = beam_section.compute_section_properties()
        csp = column_section.compute_section_properties()
        r = check_panel_zone_shear_341(bsp, A992, csp, A992)
        assert isinstance(r, PanelZoneShearReport)

    def test_is_frozen(
        self,
        beam_section: DoublySymmetricISection,
        column_section: DoublySymmetricISection,
    ) -> None:
        bsp = beam_section.compute_section_properties()
        csp = column_section.compute_section_properties()
        r = check_panel_zone_shear_341(bsp, A992, csp, A992)
        with pytest.raises(AttributeError):
            r.panel_zone_shear_demand_Vu_pz = 0.0  # type: ignore[misc]


class TestCompositeApi:
    def test_BeamColumnConnection_check_panel_zone_shear(
        self,
        beam_section: DoublySymmetricISection,
        column_section: DoublySymmetricISection,
    ) -> None:
        beam = beam_section.element(A992)
        col = column_section.element(A992)
        joint = BeamColumnConnection(beam=beam, column=col)
        r_composite = joint.check_panel_zone_shear()
        r_free = check_panel_zone_shear_341(
            beam_section.compute_section_properties(),
            A992,
            column_section.compute_section_properties(),
            A992,
        )
        assert r_composite.panel_zone_shear_capacity_Rn == pytest.approx(
            r_free.panel_zone_shear_capacity_Rn
        )
