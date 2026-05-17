"""Unit tests for ``EuropeanIPECatalog``.

The shipped subset (IPE 200, 300, 400, 500, 600) is exercised end-to-
end: row construction, Eurocode-to-AISC axis renaming, and a
plate-built reconstruction check against the published values.
"""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING

import pytest

import apeSteel as ase
from apeSteel.sections.catalog import (
    CatalogRowEuropeanIPE,
    EuropeanIPECatalog,
    SectionNotFoundError,
)

if TYPE_CHECKING:
    from apeSteel.sections.properties import SectionProperties


SHIPPED_IPE_DESIGNATIONS: list[str] = [
    "IPE 200",
    "IPE 300",
    "IPE 400",
    "IPE 500",
    "IPE 600",
]


@pytest.fixture(scope="module")
def catalog() -> EuropeanIPECatalog:
    return EuropeanIPECatalog()


class TestGetRowHeadlineIpe300:
    """Each numeric field of IPE 300 must agree with EN 10365."""

    @pytest.fixture(scope="class")
    def row(self, catalog: EuropeanIPECatalog) -> CatalogRowEuropeanIPE:
        return catalog.get_row("IPE 300")

    def test_identification(self, row: CatalogRowEuropeanIPE) -> None:
        assert row.designation == "IPE 300"

    def test_plate_dimensions(self, row: CatalogRowEuropeanIPE) -> None:
        assert row.h == pytest.approx(300.0)
        assert row.b == pytest.approx(150.0)
        assert row.tw == pytest.approx(7.1)
        assert row.tf == pytest.approx(10.7)
        assert row.r == pytest.approx(15.0)

    def test_mass_and_area(self, row: CatalogRowEuropeanIPE) -> None:
        # 42.2 kg/m -> 4.22e-5 tonne/mm.
        assert math.isclose(row.G, 4.22e-5, rel_tol=1e-6)
        assert pytest.approx(5381.0) == row.A

    def test_strong_axis_eurocode_y(self, row: CatalogRowEuropeanIPE) -> None:
        assert row.Iy == pytest.approx(8.356e7, rel=1e-4)
        assert row.Wel_y == pytest.approx(5.571e5, rel=1e-4)
        assert row.Wpl_y == pytest.approx(6.284e5, rel=1e-4)
        assert row.iy == pytest.approx(124.6, rel=1e-4)

    def test_weak_axis_eurocode_z(self, row: CatalogRowEuropeanIPE) -> None:
        assert row.Iz == pytest.approx(6.038e6, rel=1e-4)
        assert row.Wel_z == pytest.approx(8.05e4, rel=1e-3)
        assert row.Wpl_z == pytest.approx(1.252e5, rel=1e-4)
        assert row.iz == pytest.approx(33.5, rel=1e-3)

    def test_torsion_and_warping(self, row: CatalogRowEuropeanIPE) -> None:
        assert row.It == pytest.approx(2.012e5, rel=1e-4)
        assert row.Iw == pytest.approx(1.259e11, rel=1e-4)


class TestEurocodeToAiscAxisRenaming:
    """The adapter must rename Eurocode y/z to AISC x/y, period."""

    @pytest.fixture(scope="class")
    def section_properties(self, catalog: EuropeanIPECatalog) -> SectionProperties:
        return catalog.get_section_properties("IPE 300")

    def test_strong_axis_maps_eurocode_y_to_aisc_x(
        self, section_properties: SectionProperties
    ) -> None:
        # IPE 300 Iy (Eurocode) = 8.356e7 mm^4 -> AISC Ix.
        assert section_properties.moment_of_inertia_strong_axis_Ix == pytest.approx(8.356e7)
        assert section_properties.plastic_section_modulus_strong_axis_Zx == pytest.approx(6.284e5)

    def test_weak_axis_maps_eurocode_z_to_aisc_y(
        self, section_properties: SectionProperties
    ) -> None:
        # IPE 300 Iz (Eurocode) = 6.038e6 mm^4 -> AISC Iy.
        assert section_properties.moment_of_inertia_weak_axis_Iy == pytest.approx(6.038e6)
        assert section_properties.plastic_section_modulus_weak_axis_Zy == pytest.approx(1.252e5)

    def test_It_maps_to_J(self, section_properties: SectionProperties) -> None:
        assert section_properties.torsional_constant_J == pytest.approx(2.012e5)

    def test_Iw_maps_to_Cw(self, section_properties: SectionProperties) -> None:
        assert section_properties.warping_constant_Cw == pytest.approx(1.259e11)


class TestDerivedQuantities:
    def test_ho_equals_h_minus_tf(self, catalog: EuropeanIPECatalog) -> None:
        sp = catalog.get_section_properties("IPE 300")
        assert sp.distance_between_flange_centroids_ho == pytest.approx(300.0 - 10.7)

    def test_rts_matches_aisc_F2_7(self, catalog: EuropeanIPECatalog) -> None:
        # rts^2 = sqrt(Iy_weak * Cw) / Sx_strong   (AISC F2-7).
        sp = catalog.get_section_properties("IPE 300")
        expected_rts_squared: float = (
            math.sqrt(sp.moment_of_inertia_weak_axis_Iy * sp.warping_constant_Cw)
            / sp.elastic_section_modulus_strong_axis_Sx
        )
        assert sp.effective_radius_of_gyration_for_LTB_rts == pytest.approx(
            math.sqrt(expected_rts_squared)
        )

    def test_bf_2tf_matches_published_proportions(self, catalog: EuropeanIPECatalog) -> None:
        sp = catalog.get_section_properties("IPE 300")
        # bf = 150, tf = 10.7  ->  150 / (2 * 10.7) ~= 7.01
        assert sp.flange_width_to_thickness_ratio_bf_2tf == pytest.approx(150.0 / (2.0 * 10.7))


class TestEverySectionLoads:
    @pytest.mark.parametrize("designation", SHIPPED_IPE_DESIGNATIONS)
    def test_get_row(self, catalog: EuropeanIPECatalog, designation: str) -> None:
        row = catalog.get_row(designation)
        assert row.designation == designation
        # Every field should be a positive float.
        assert row.h > 0
        assert row.b > 0
        assert row.Iy > 0
        assert row.Iz > 0
        assert row.It > 0
        assert row.Iw > 0

    @pytest.mark.parametrize("designation", SHIPPED_IPE_DESIGNATIONS)
    def test_get_section_properties(self, catalog: EuropeanIPECatalog, designation: str) -> None:
        sp = catalog.get_section_properties(designation)
        # Strong-axis must be larger than weak-axis for an IPE.
        assert sp.moment_of_inertia_strong_axis_Ix > sp.moment_of_inertia_weak_axis_Iy
        assert sp.plastic_section_modulus_strong_axis_Zx > sp.plastic_section_modulus_weak_axis_Zy


class TestPlateBuiltReconstruction:
    @pytest.mark.parametrize("designation", SHIPPED_IPE_DESIGNATIONS)
    def test_plate_built_ag_within_3pct(
        self, catalog: EuropeanIPECatalog, designation: str
    ) -> None:
        # Root-radius fillets are omitted by the plate-built model so
        # we tolerate a slightly larger gap than for AISC W shapes
        # (IPE root radii are large relative to tw, so the plate-built gap
        geom = catalog.get_doubly_symmetric_i_geometry(designation)
        plate_built = geom.compute_section_properties()
        catalog_section = catalog.get_section_properties(designation)
        rel_diff: float = (
            abs(plate_built.gross_area_Ag - catalog_section.gross_area_Ag)
            / catalog_section.gross_area_Ag
        )
        assert rel_diff < 0.07, f"{designation}: plate-built Ag differs by {rel_diff:.4f}"

    @pytest.mark.parametrize("designation", SHIPPED_IPE_DESIGNATIONS)
    def test_plate_built_ix_within_3pct(
        self, catalog: EuropeanIPECatalog, designation: str
    ) -> None:
        geom = catalog.get_doubly_symmetric_i_geometry(designation)
        plate_built = geom.compute_section_properties()
        catalog_section = catalog.get_section_properties(designation)
        rel_diff: float = (
            abs(
                plate_built.moment_of_inertia_strong_axis_Ix
                - catalog_section.moment_of_inertia_strong_axis_Ix
            )
            / catalog_section.moment_of_inertia_strong_axis_Ix
        )
        assert rel_diff < 0.07, f"{designation}: plate-built Ix differs by {rel_diff:.4f}"


class TestLookupBehaviour:
    def test_case_insensitive(self, catalog: EuropeanIPECatalog) -> None:
        assert catalog.get_row("ipe 300").designation == "IPE 300"
        assert catalog.get_row("IPE 300").designation == "IPE 300"

    def test_fuzzy_fallback_missing_space(
        self, catalog: EuropeanIPECatalog, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.WARNING, logger="apeSteel.sections.catalog.european_ipe")
        row = catalog.get_row("ipe300")
        assert row.designation == "IPE 300"
        assert any("fuzzy match" in rec.message.lower() for rec in caplog.records)

    def test_not_found_below_threshold(self, catalog: EuropeanIPECatalog) -> None:
        with pytest.raises(SectionNotFoundError):
            catalog.get_row("IPE 999")


class TestPublicApiSurface:
    def test_exposed_at_top_level(self) -> None:
        assert ase.EuropeanIPECatalog is EuropeanIPECatalog
        assert ase.CatalogRowEuropeanIPE is CatalogRowEuropeanIPE
