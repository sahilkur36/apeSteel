"""Phase 0 smoke tests.

Verifies that the package imports cleanly, the baseUnits BASE assertion
holds, the pre-built materials carry the AISC values they advertise, and
the :class:`Report` / :class:`AISCClauseReference` data classes are
truly immutable.
"""

from __future__ import annotations

import math
from dataclasses import FrozenInstanceError

import baseUnits as bu
import pytest

import apeSteel
from apeSteel import (
    A36,
    A992,
    ACTIVE_BASE,
    EXPECTED_BASE,
    S275,
    S355,
    S460,
    A572_Gr50,
    AISCClauseReference,
    Report,
    SteelMaterial,
)
from apeSteel.core import units as u


# ---------------------------------------------------------------------------
# Package metadata + BASE
# ---------------------------------------------------------------------------
def test_version_string_is_present() -> None:
    assert isinstance(apeSteel.__version__, str)
    assert apeSteel.__version__ != ""


def test_active_base_equals_expected_base() -> None:
    assert ACTIVE_BASE == EXPECTED_BASE
    assert ACTIVE_BASE == "N-mm-tonne-s"
    assert bu.BASE == "N-mm-tonne-s"


# ---------------------------------------------------------------------------
# Unit constants
# ---------------------------------------------------------------------------
def test_basic_unit_constants_have_expected_values() -> None:
    # In N-mm-tonne-s, mm and N and MPa are all 1.0 by definition.
    assert u.mm == 1.0
    assert u.N == 1.0
    assert u.MPa == 1.0
    # m is 1000 mm; kN is 1000 N; GPa is 1000 MPa.
    assert u.m == 1000.0
    assert u.kN == 1000.0
    assert u.GPa == 1000.0


def test_moment_display_unit_kN_m_is_kN_times_m() -> None:
    # 1 kN * 1 m = 1000 N * 1000 mm = 1e6 N*mm.
    assert math.isclose(u.MOMENT_DISPLAY_UNIT_kN_m, u.kN * u.m, rel_tol=1e-12)
    assert math.isclose(u.MOMENT_DISPLAY_UNIT_kN_m, 1_000_000.0, rel_tol=1e-12)


def test_stiffness_display_unit_kN_per_mm_is_kN_over_mm() -> None:
    assert math.isclose(u.STIFFNESS_DISPLAY_UNIT_kN_per_mm, u.kN / u.mm, rel_tol=1e-12)
    assert math.isclose(u.STIFFNESS_DISPLAY_UNIT_kN_per_mm, 1000.0, rel_tol=1e-12)


def test_canonical_display_units_table_has_expected_keys() -> None:
    expected_keys = {
        "length_member",
        "length_plate",
        "force",
        "moment",
        "stress",
        "stiffness_lateral",
        "stiffness_axial",
        "line_load",
        "area_load",
        "angle",
    }
    assert set(u.CANONICAL_DISPLAY_UNITS.keys()) == expected_keys


# ---------------------------------------------------------------------------
# Materials
# ---------------------------------------------------------------------------
def test_A992_has_50_ksi_yield_stress_in_MPa_base_units() -> None:
    # 50 ksi -> 344.7378646 MPa (within rounding of the AISC nominal value).
    fy_in_MPa = A992.yield_stress_Fy / u.MPa
    assert math.isclose(fy_in_MPa, 50.0 * 6.894757293168, rel_tol=1e-9)
    # Sanity: should be close to the commonly-quoted 345 MPa value.
    assert math.isclose(fy_in_MPa, 344.7378, rel_tol=1e-4)


def test_A992_seismic_Ry_and_Rt() -> None:
    assert A992.expected_yield_ratio_Ry == 1.1
    assert A992.expected_tensile_ratio_Rt == 1.1


def test_A36_has_higher_seismic_Ry_per_AISC_341_table_A3_1() -> None:
    # AISC 341 Table A3.1: A36 Ry = 1.5, Rt = 1.2.
    assert A36.expected_yield_ratio_Ry == 1.5
    assert A36.expected_tensile_ratio_Rt == 1.2


def test_S355_has_355_MPa_yield_stress() -> None:
    assert math.isclose(S355.yield_stress_Fy / u.MPa, 355.0, rel_tol=1e-12)


@pytest.mark.parametrize("material", [A36, A572_Gr50, A992, S275, S355, S460])
def test_every_material_has_AISC_E_29000_ksi(material: SteelMaterial) -> None:
    e_in_ksi = material.elastic_modulus_E / u.ksi
    assert math.isclose(e_in_ksi, 29_000.0, rel_tol=1e-9)


@pytest.mark.parametrize("material", [A36, A572_Gr50, A992, S275, S355, S460])
def test_every_material_has_AISC_G_11200_ksi(material: SteelMaterial) -> None:
    g_in_ksi = material.shear_modulus_G / u.ksi
    assert math.isclose(g_in_ksi, 11_200.0, rel_tol=1e-9)


def test_steel_material_is_frozen() -> None:
    with pytest.raises(FrozenInstanceError):
        A992.yield_stress_Fy = 999.0 * u.MPa  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------
def test_AISCClauseReference_is_immutable() -> None:
    citation = AISCClauseReference("AISC 360-22", "F2.2", "F2-5", "16.1-49")
    with pytest.raises(FrozenInstanceError):
        citation.section = "G2.1"  # type: ignore[misc]


def test_AISCClauseReference_short_string_with_equation() -> None:
    citation = AISCClauseReference("AISC 360-22", "F2.2", "F2-5", "16.1-49")
    assert citation.short() == "AISC 360-22 §F2.2 Eq. F2-5"


def test_AISCClauseReference_short_string_without_equation() -> None:
    citation = AISCClauseReference("AISC 341-22", "D1.2b", None, "9.1-21")
    assert citation.short() == "AISC 341-22 §D1.2b"


def test_Report_default_values_are_safe() -> None:
    report = Report()
    assert report.cited_clauses == ()
    assert report.governing_limit_state == ""
    assert report.phi_LRFD == 1.0
    assert report.omega_ASD == 1.0
    assert report.nominal_strength == 0.0


def test_Report_format_renders_citation_list() -> None:
    citations: tuple[AISCClauseReference, ...] = (
        AISCClauseReference("AISC 360-22", "F2.2", "F2-5", "16.1-49"),
        AISCClauseReference("AISC 341-22", "D1.2b", "D1-2", "9.1-21"),
    )
    report = Report(
        cited_clauses=citations,
        governing_limit_state="yielding",
        phi_LRFD=0.90,
        omega_ASD=1.67,
        nominal_strength=425.7 * u.MOMENT_DISPLAY_UNIT_kN_m,
        phi_strength_LRFD=0.90 * 425.7 * u.MOMENT_DISPLAY_UNIT_kN_m,
        omega_strength_ASD=425.7 * u.MOMENT_DISPLAY_UNIT_kN_m / 1.67,
    )
    rendered = report.format()
    assert "yielding" in rendered
    assert "AISC 360-22" in rendered
    assert "AISC 341-22" in rendered
    assert "F2-5" in rendered
    assert "D1-2" in rendered


def test_Report_is_frozen() -> None:
    report = Report()
    with pytest.raises(FrozenInstanceError):
        report.governing_limit_state = "elastic_LTB"  # type: ignore[misc]
