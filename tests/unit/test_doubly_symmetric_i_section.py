"""Unit tests for DoublySymmetricISection.

Three layers of validation:

1. Hand-computed values for the spreadsheet's default
   100 mm x 6 mm / 300 mm x 4 mm plate-built I.  Every section property
   is pinned to the analytic value we worked out by hand and that the
   spreadsheet also produces.
2. Algebraic identity checks that hold for any doubly-symmetric I (e.g.
   Sx = Ix / (d/2), rx = sqrt(Ix/Ag)).
3. Numerical-integration cross-check against a uniform grid sampling of
   the I-shape, for Ix, Iy, Zx, Zy.  Catches a class of bugs that pure
   algebraic checks miss.
"""

from __future__ import annotations

import math
from dataclasses import FrozenInstanceError

import numpy as np
import pytest

from apeSteel.core import units as u
from apeSteel.sections.geometry import DoublySymmetricISection
from apeSteel.sections.properties import SectionProperties

# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------
SPREADSHEET_DEFAULT_FLANGE_WIDTH_BF: float = 100.0 * u.mm
SPREADSHEET_DEFAULT_FLANGE_THICKNESS_TF: float = 6.0 * u.mm
SPREADSHEET_DEFAULT_WEB_CLEAR_HEIGHT_HW: float = 300.0 * u.mm
SPREADSHEET_DEFAULT_WEB_THICKNESS_TW: float = 4.0 * u.mm


@pytest.fixture
def spreadsheet_default_section() -> DoublySymmetricISection:
    return DoublySymmetricISection(
        flange_width_bf=SPREADSHEET_DEFAULT_FLANGE_WIDTH_BF,
        flange_thickness_tf=SPREADSHEET_DEFAULT_FLANGE_THICKNESS_TF,
        web_clear_height_hw=SPREADSHEET_DEFAULT_WEB_CLEAR_HEIGHT_HW,
        web_thickness_tw=SPREADSHEET_DEFAULT_WEB_THICKNESS_TW,
    )


# ---------------------------------------------------------------------------
# Dataclass plumbing
# ---------------------------------------------------------------------------
def test_doubly_symmetric_i_section_is_frozen(
    spreadsheet_default_section: DoublySymmetricISection,
) -> None:
    with pytest.raises(FrozenInstanceError):
        spreadsheet_default_section.flange_width_bf = 999.0  # type: ignore[misc]


def test_compute_section_properties_returns_section_properties_instance(
    spreadsheet_default_section: DoublySymmetricISection,
) -> None:
    props = spreadsheet_default_section.compute_section_properties()
    assert isinstance(props, SectionProperties)


# ---------------------------------------------------------------------------
# Hand-computed values for the spreadsheet defaults
# ---------------------------------------------------------------------------
# 100x6 / 300x4 default, worked out by hand for traceability:
#   d  = hw + 2*tf       = 312
#   ho = hw + tf         = 306
#   Ag = 2*bf*tf + hw*tw = 2_400
#   Ix = 2*(bf*tf^3/12 + bf*tf*(ho/2)^2) + tw*hw^3/12
#      = 2*(1_800 + 600*23_409) + 9_000_000
#      = 28_094_400 + 9_000_000 = 37_094_400
#   Sx = 2*Ix/d          = 237_784.6153846154
#   Zx = bf*tf*ho + tw*hw^2/4 = 273_600
#   Iy = 2*tf*bf^3/12 + hw*tw^3/12 = 1_001_600
#   Sy = 2*Iy/bf         = 20_032
#   Zy = tf*bf^2/2 + hw*tw^2/4 = 31_200
#   J  = (2*bf*tf^3 + ho*tw^3)/3 = 20_928
#   Cw = ho^2 * bf^3 * tf / 24 = 23_409_000_000
EXPECTED_FOR_DEFAULTS: dict[str, float] = {
    "overall_depth_d": 312.0,
    "gross_area_Ag": 2_400.0,
    "moment_of_inertia_strong_axis_Ix": 37_094_400.0,
    "elastic_section_modulus_strong_axis_Sx": 237_784.6153846154,
    "plastic_section_modulus_strong_axis_Zx": 273_600.0,
    "moment_of_inertia_weak_axis_Iy": 1_001_600.0,
    "elastic_section_modulus_weak_axis_Sy": 20_032.0,
    "plastic_section_modulus_weak_axis_Zy": 31_200.0,
    "torsional_constant_J": 20_928.0,
    "warping_constant_Cw": 23_409_000_000.0,
    "distance_between_flange_centroids_ho": 306.0,
    "flange_width_to_thickness_ratio_bf_2tf": 8.333333333333334,
    "web_height_to_thickness_ratio_h_tw": 75.0,
}


@pytest.mark.parametrize(
    ("attribute_name", "expected_value"),
    list(EXPECTED_FOR_DEFAULTS.items()),
)
def test_spreadsheet_default_matches_hand_computed(
    spreadsheet_default_section: DoublySymmetricISection,
    attribute_name: str,
    expected_value: float,
) -> None:
    props = spreadsheet_default_section.compute_section_properties()
    actual = getattr(props, attribute_name)
    assert math.isclose(actual, expected_value, rel_tol=1e-9, abs_tol=1e-9), (
        f"{attribute_name}: {actual} != {expected_value}"
    )


def test_spreadsheet_default_rx_and_ry(
    spreadsheet_default_section: DoublySymmetricISection,
) -> None:
    props = spreadsheet_default_section.compute_section_properties()
    rx_expected = math.sqrt(37_094_400.0 / 2_400.0)
    ry_expected = math.sqrt(1_001_600.0 / 2_400.0)
    assert math.isclose(props.radius_of_gyration_strong_axis_rx, rx_expected, rel_tol=1e-12)
    assert math.isclose(props.radius_of_gyration_weak_axis_ry, ry_expected, rel_tol=1e-12)


def test_spreadsheet_default_rts_matches_aisc_F2_7(
    spreadsheet_default_section: DoublySymmetricISection,
) -> None:
    # AISC 360 Eq. F2-7: rts^2 = sqrt(Iy * Cw) / Sx.
    props = spreadsheet_default_section.compute_section_properties()
    rts_squared_expected = math.sqrt(1_001_600.0 * 23_409_000_000.0) / 237_784.6153846154
    rts_expected = math.sqrt(rts_squared_expected)
    assert math.isclose(props.effective_radius_of_gyration_for_LTB_rts, rts_expected, rel_tol=1e-12)


# ---------------------------------------------------------------------------
# Algebraic identities
# ---------------------------------------------------------------------------
ALGEBRAIC_CASES: list[tuple[float, float, float, float]] = [
    (300.0, 22.0, 350.0, 12.0),
    (150.0, 12.0, 600.0, 8.0),
    (200.0, 15.0, 400.0, 8.0),
    (100.0, 6.0, 300.0, 4.0),
    (50.0, 8.0, 200.0, 6.0),
]


@pytest.mark.parametrize(("bf", "tf", "hw", "tw"), ALGEBRAIC_CASES)
def test_sx_equals_ix_over_half_depth(bf: float, tf: float, hw: float, tw: float) -> None:
    section = DoublySymmetricISection(
        flange_width_bf=bf * u.mm,
        flange_thickness_tf=tf * u.mm,
        web_clear_height_hw=hw * u.mm,
        web_thickness_tw=tw * u.mm,
    )
    p = section.compute_section_properties()
    sx_expected = p.moment_of_inertia_strong_axis_Ix / (p.overall_depth_d / 2.0)
    assert math.isclose(p.elastic_section_modulus_strong_axis_Sx, sx_expected, rel_tol=1e-12)


@pytest.mark.parametrize(("bf", "tf", "hw", "tw"), ALGEBRAIC_CASES)
def test_radii_of_gyration_match_definition(bf: float, tf: float, hw: float, tw: float) -> None:
    section = DoublySymmetricISection(
        flange_width_bf=bf * u.mm,
        flange_thickness_tf=tf * u.mm,
        web_clear_height_hw=hw * u.mm,
        web_thickness_tw=tw * u.mm,
    )
    p = section.compute_section_properties()
    assert math.isclose(
        p.radius_of_gyration_strong_axis_rx,
        math.sqrt(p.moment_of_inertia_strong_axis_Ix / p.gross_area_Ag),
        rel_tol=1e-12,
    )
    assert math.isclose(
        p.radius_of_gyration_weak_axis_ry,
        math.sqrt(p.moment_of_inertia_weak_axis_Iy / p.gross_area_Ag),
        rel_tol=1e-12,
    )


def test_plastic_modulus_is_at_least_elastic_modulus(
    spreadsheet_default_section: DoublySymmetricISection,
) -> None:
    p = spreadsheet_default_section.compute_section_properties()
    assert p.plastic_section_modulus_strong_axis_Zx >= p.elastic_section_modulus_strong_axis_Sx
    assert p.plastic_section_modulus_weak_axis_Zy >= p.elastic_section_modulus_weak_axis_Sy


# ---------------------------------------------------------------------------
# Numerical-integration cross-check
# ---------------------------------------------------------------------------
def _build_numerical_grid_for_doubly_symmetric_i(
    section: DoublySymmetricISection,
    n_y: int = 4001,
    n_x: int = 1001,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    bf = section.flange_width_bf
    tf = section.flange_thickness_tf
    hw = section.web_clear_height_hw
    tw = section.web_thickness_tw
    d = hw + 2.0 * tf
    y = np.linspace(-d / 2.0, d / 2.0, n_y)
    x = np.linspace(-bf / 2.0, bf / 2.0, n_x)
    X, Y = np.meshgrid(x, y, indexing="xy")
    dy = float(y[1] - y[0])
    dx = float(x[1] - x[0])
    inside_flange = (np.abs(Y) > hw / 2.0) & (np.abs(X) <= bf / 2.0)
    inside_web = (np.abs(Y) <= hw / 2.0) & (np.abs(X) <= tw / 2.0)
    inside_section = inside_flange | inside_web
    cell_area = np.where(inside_section, dx * dy, 0.0)
    return X, Y, cell_area


def _numerical_integration_of_section_properties(
    section: DoublySymmetricISection,
) -> dict[str, float]:
    X, Y, dA = _build_numerical_grid_for_doubly_symmetric_i(section)
    return {
        "Ag": float(np.sum(dA)),
        "Ix": float(np.sum(Y * Y * dA)),
        "Iy": float(np.sum(X * X * dA)),
        "Zx": float(np.sum(np.abs(Y) * dA)),
        "Zy": float(np.sum(np.abs(X) * dA)),
    }


@pytest.mark.parametrize(
    ("bf", "tf", "hw", "tw"),
    [
        (100.0, 6.0, 300.0, 4.0),
        (300.0, 22.0, 350.0, 12.0),
        (150.0, 12.0, 600.0, 8.0),
    ],
)
def test_numerical_integration_matches_closed_form(
    bf: float, tf: float, hw: float, tw: float
) -> None:
    section = DoublySymmetricISection(
        flange_width_bf=bf * u.mm,
        flange_thickness_tf=tf * u.mm,
        web_clear_height_hw=hw * u.mm,
        web_thickness_tw=tw * u.mm,
    )
    closed_form = section.compute_section_properties()
    numerical = _numerical_integration_of_section_properties(section)
    # The grid is finite; boundary cells produce ~0.5% relative error
    # on strong-axis quantities and ~1.5% on weak-axis quantities (the
    # narrow web makes fewer cells contribute). This test is a sanity
    # check that the closed-form algebra hasn't silently flipped a
    # factor of 2 or swapped a dimension - not a validation to 12 sig
    # figs (the golden CSV does that).
    assert math.isclose(numerical["Ag"], closed_form.gross_area_Ag, rel_tol=2e-2)
    assert math.isclose(numerical["Ix"], closed_form.moment_of_inertia_strong_axis_Ix, rel_tol=2e-2)
    assert math.isclose(numerical["Iy"], closed_form.moment_of_inertia_weak_axis_Iy, rel_tol=3e-2)
    assert math.isclose(
        numerical["Zx"],
        closed_form.plastic_section_modulus_strong_axis_Zx,
        rel_tol=2e-2,
    )
    assert math.isclose(
        numerical["Zy"],
        closed_form.plastic_section_modulus_weak_axis_Zy,
        rel_tol=3e-2,
    )
