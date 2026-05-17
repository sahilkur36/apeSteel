"""Unit tests for ``AISCv16Catalog``.

The catalog is exercised against three families of cases:

* Headline AISC W-shape (W24X94 / W610x140) - every column is checked
  against the AISC v16 SI Manual.
* Edge cases - non-I shapes (HSS, angles, pipes) refuse to adapt to
  ``SectionProperties``.
* Lookup behaviour - case-insensitive exact match, RapidFuzz fuzzy
  fallback, and ``SectionNotFoundError`` for labels outside the
  similarity threshold.
"""

from __future__ import annotations

import logging
import math
import re
from typing import TYPE_CHECKING

import pytest

import apeSteel as ase
from apeSteel.sections.catalog import (
    DOUBLY_SYMMETRIC_I_SHAPE_AISC_TYPES,
    AISCv16Catalog,
    CatalogRowAISCv16,
    SectionNotFoundError,
    SectionTypeNotAdaptableError,
)

if TYPE_CHECKING:
    from apeSteel.sections.properties import SectionProperties


GRAVITATIONAL_ACCELERATION_g_BASE_UNITS: float = 9806.65
"""``baseUnits`` ships the standard-gravity value g = 9.806 65 m/s^2 in
mm/s^2 (= 9806.65). Defined locally so a sneaky import-order change
cannot silently corrupt the test."""


@pytest.fixture(scope="module")
def catalog() -> AISCv16Catalog:
    return AISCv16Catalog()


class TestGetRowHeadlineW24X94:
    """Every numeric column of W24X94 must agree with the AISC v16 SI Manual."""

    @pytest.fixture(scope="class")
    def row(self, catalog: AISCv16Catalog) -> CatalogRowAISCv16:
        return catalog.get_row("W24X94")

    def test_identification(self, row: CatalogRowAISCv16) -> None:
        assert row.Type == "W"
        assert row.AISC_Manual_Label == "W24X94"

    def test_mass_and_area(self, row: CatalogRowAISCv16) -> None:
        # 140 kg/m -> 1.40e-4 tonne/mm in apeSteel base units.
        assert row.W is not None
        assert math.isclose(row.W, 1.40e-4, rel_tol=1e-6)
        assert pytest.approx(17900.0) == row.A

    def test_plate_dimensions(self, row: CatalogRowAISCv16) -> None:
        assert row.d == pytest.approx(617.0)
        assert row.bf == pytest.approx(230.0)
        assert row.tf == pytest.approx(22.2)
        assert row.tw == pytest.approx(13.1)

    def test_strong_axis_properties(self, row: CatalogRowAISCv16) -> None:
        assert row.Ix == pytest.approx(1.120e9, rel=1e-6)
        assert row.Zx == pytest.approx(4.160e6, rel=1e-6)
        assert row.Sx == pytest.approx(3.640e6, rel=1e-6)
        assert row.rx == pytest.approx(251.0, rel=1e-6)

    def test_weak_axis_properties(self, row: CatalogRowAISCv16) -> None:
        assert row.Iy == pytest.approx(4.540e7, rel=1e-6)
        assert row.Zy == pytest.approx(6.150e5, rel=1e-6)
        assert row.Sy == pytest.approx(3.930e5, rel=1e-6)
        assert row.ry == pytest.approx(50.3, rel=1e-6)

    def test_torsion_and_warping(self, row: CatalogRowAISCv16) -> None:
        assert pytest.approx(2.190e6, rel=1e-6) == row.J
        assert row.Cw == pytest.approx(4.030e12, rel=1e-6)

    def test_ltb_specific(self, row: CatalogRowAISCv16) -> None:
        assert row.ho == pytest.approx(594.0)
        assert row.rts == pytest.approx(61.0)

    def test_slenderness_ratios(self, row: CatalogRowAISCv16) -> None:
        assert row.bf_2tf == pytest.approx(5.18)
        assert row.h_tw == pytest.approx(41.9)


class TestGetSectionPropertiesHappyPath:
    @pytest.fixture(scope="class")
    def section_properties(self, catalog: AISCv16Catalog) -> SectionProperties:
        return catalog.get_section_properties("W24X94")

    def test_geometry_passthrough(self, section_properties: SectionProperties) -> None:
        assert section_properties.overall_depth_d == pytest.approx(617.0)
        assert section_properties.gross_area_Ag == pytest.approx(17900.0)

    def test_strong_axis_passthrough(self, section_properties: SectionProperties) -> None:
        assert section_properties.moment_of_inertia_strong_axis_Ix == pytest.approx(1.120e9)
        assert section_properties.plastic_section_modulus_strong_axis_Zx == pytest.approx(4.160e6)

    def test_weight_force_per_length_uses_gravity(
        self, section_properties: SectionProperties
    ) -> None:
        # 140 kg/m * g (= 9806.65 mm/s^2 in base) = 1.3729 N/mm.
        expected_n_per_mm: float = 140.0 * 1e-6 * GRAVITATIONAL_ACCELERATION_g_BASE_UNITS
        assert section_properties.nominal_weight_per_unit_length_w == pytest.approx(
            expected_n_per_mm, rel=1e-5
        )

    def test_ltb_constants_passthrough(self, section_properties: SectionProperties) -> None:
        assert section_properties.torsional_constant_J == pytest.approx(2.190e6)
        assert section_properties.warping_constant_Cw == pytest.approx(4.030e12)
        assert section_properties.distance_between_flange_centroids_ho == pytest.approx(594.0)
        assert section_properties.effective_radius_of_gyration_for_LTB_rts == pytest.approx(61.0)

    def test_dataclass_is_frozen(self, section_properties: SectionProperties) -> None:
        with pytest.raises(AttributeError):
            section_properties.gross_area_Ag = 0.0  # type: ignore[misc]


class TestGetDoublySymmetricIGeometry:
    def test_plate_dimensions_reconstructed(self, catalog: AISCv16Catalog) -> None:
        geom = catalog.get_doubly_symmetric_i_geometry("W24X94")
        assert geom.flange_width_bf == pytest.approx(230.0)
        assert geom.flange_thickness_tf == pytest.approx(22.2)
        assert geom.web_thickness_tw == pytest.approx(13.1)
        # hw = d - 2 tf = 617 - 44.4 = 572.6 mm.
        assert geom.web_clear_height_hw == pytest.approx(572.6)

    def test_plate_built_ag_within_2pct_of_catalog(self, catalog: AISCv16Catalog) -> None:
        # Plate-built reconstruction omits k-radii fillets at the
        # flange-web junction. Discrepancy is well under 2 % for a
        # typical rolled W.
        geom = catalog.get_doubly_symmetric_i_geometry("W24X94")
        plate_built = geom.compute_section_properties()
        catalog_section = catalog.get_section_properties("W24X94")
        rel_diff: float = (
            abs(plate_built.gross_area_Ag - catalog_section.gross_area_Ag)
            / catalog_section.gross_area_Ag
        )
        assert rel_diff < 0.02

    def test_plate_built_ix_within_2pct_of_catalog(self, catalog: AISCv16Catalog) -> None:
        geom = catalog.get_doubly_symmetric_i_geometry("W24X94")
        plate_built = geom.compute_section_properties()
        catalog_section = catalog.get_section_properties("W24X94")
        rel_diff: float = (
            abs(
                plate_built.moment_of_inertia_strong_axis_Ix
                - catalog_section.moment_of_inertia_strong_axis_Ix
            )
            / catalog_section.moment_of_inertia_strong_axis_Ix
        )
        assert rel_diff < 0.02


class TestLookupBehaviour:
    def test_case_insensitive_match(self, catalog: AISCv16Catalog) -> None:
        row = catalog.get_row("w24x94")
        assert row.AISC_Manual_Label == "W24X94"

    def test_leading_trailing_whitespace_stripped(self, catalog: AISCv16Catalog) -> None:
        row = catalog.get_row("   W24X94   ")
        assert row.AISC_Manual_Label == "W24X94"

    def test_fuzzy_fallback_finds_typo(
        self, catalog: AISCv16Catalog, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.WARNING, logger="apeSteel.sections.catalog.aisc_v16")
        row = catalog.get_row("W24X95")
        assert row.AISC_Manual_Label == "W24X94"
        assert any("fuzzy match" in rec.message.lower() for rec in caplog.records)

    def test_not_found_raises_below_threshold(self, catalog: AISCv16Catalog) -> None:
        with pytest.raises(SectionNotFoundError) as exc_info:
            catalog.get_row("XYZ_NOT_A_SECTION_999")
        assert exc_info.value.requested_label == "XYZ_NOT_A_SECTION_999"
        assert exc_info.value.similarity_threshold == pytest.approx(80.0)

    def test_lookup_threshold_can_be_lowered(self) -> None:
        permissive_catalog = AISCv16Catalog(fuzzy_similarity_threshold=0.0)
        row = permissive_catalog.get_row("XYZNOTASECTION")
        assert row.AISC_Manual_Label


class TestNonIShapeRejection:
    @pytest.mark.parametrize(
        "label",
        [
            "HSS20X12X5/8",
            "L8X8X1",
            "Pipe26STD",
            "C15X50",
            "WT22X167.5",
        ],
    )
    def test_section_properties_rejects_non_i(self, catalog: AISCv16Catalog, label: str) -> None:
        with pytest.raises(SectionTypeNotAdaptableError) as exc_info:
            catalog.get_section_properties(label)
        assert exc_info.value.section_label.upper() == label.upper()
        assert exc_info.value.requested_adapter == "get_section_properties"

    def test_geometry_reconstruction_rejects_non_i(self, catalog: AISCv16Catalog) -> None:
        with pytest.raises(SectionTypeNotAdaptableError):
            catalog.get_doubly_symmetric_i_geometry("HSS20X12X5/8")


class TestCoverageAcrossSectionTypes:
    """Every AISC v16 section type loads without raising."""

    @pytest.mark.parametrize(
        "label",
        [
            "W24X94",
            "M12.5X12.4",
            "S24X121",
            "HP14X117",
            "C15X50",
            "MC18X58",
            "L8X8X1",
            "WT22X167.5",
            "MT6X5.9",
            "ST12X60.5",
            "2L12X12X1-3/8",
            "HSS20X12X5/8",
            "Pipe26STD",
        ],
    )
    def test_row_loads_for_every_section_type(self, catalog: AISCv16Catalog, label: str) -> None:
        row = catalog.get_row(label)
        assert row.AISC_Manual_Label.upper() == label.upper()
        assert row.A is not None
        assert row.A > 0


class TestPublicApiSurface:
    def test_catalog_exposed_at_top_level(self) -> None:
        assert ase.AISCv16Catalog is AISCv16Catalog

    def test_exception_types_exposed(self) -> None:
        assert ase.SectionNotFoundError is SectionNotFoundError
        assert ase.SectionTypeNotAdaptableError is SectionTypeNotAdaptableError

    def test_i_shape_type_constant(self) -> None:
        assert frozenset({"W", "M", "S", "HP"}) == DOUBLY_SYMMETRIC_I_SHAPE_AISC_TYPES

    def test_section_not_found_error_message_describes_request(self) -> None:
        err = SectionNotFoundError(
            "foo",
            best_fuzzy_match=None,
            best_fuzzy_score=None,
            similarity_threshold=80.0,
        )
        assert "foo" in str(err)
        assert re.search(r"not found", str(err), flags=re.IGNORECASE)
