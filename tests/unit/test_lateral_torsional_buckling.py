"""Unit tests for the LTB primitives (Lp, Lr, Mcr, Mp, F2-2)."""

from __future__ import annotations

import math

import pytest

from apeSteel import A992, DoublySymmetricISection, SectionProperties
from apeSteel.core import units as u
from apeSteel.flexure import (
    compute_elastic_LTB_critical_moment_Mcr,
    compute_inelastic_LTB_moment_Mn_F2_2,
    compute_limiting_length_inelastic_LTB_Lr,
    compute_limiting_length_plastic_Lp,
    compute_plastic_moment_Mp,
)


@pytest.fixture
def default_props() -> SectionProperties:
    sec = DoublySymmetricISection(100.0 * u.mm, 6.0 * u.mm, 300.0 * u.mm, 4.0 * u.mm)
    return sec.compute_section_properties()


# ---------------------------------------------------------------------------
# Lp - AISC Eq. F2-5
# ---------------------------------------------------------------------------
def test_Lp_matches_F2_5(default_props: SectionProperties) -> None:
    Fy = A992.yield_stress_Fy
    E = A992.elastic_modulus_E
    ry = default_props.radius_of_gyration_weak_axis_ry
    expected = 1.76 * ry * math.sqrt(E / Fy)
    actual = compute_limiting_length_plastic_Lp(
        radius_of_gyration_weak_axis_ry=ry,
        elastic_modulus_E=E,
        yield_stress_Fy=Fy,
    )
    assert math.isclose(actual, expected, rel_tol=1e-12)


def test_Lp_for_default_section_is_about_866mm_at_A992() -> None:
    sec = DoublySymmetricISection(100.0 * u.mm, 6.0 * u.mm, 300.0 * u.mm, 4.0 * u.mm)
    p = sec.compute_section_properties()
    Lp = compute_limiting_length_plastic_Lp(
        p.radius_of_gyration_weak_axis_ry,
        A992.elastic_modulus_E,
        A992.yield_stress_Fy,
    )
    # Hand calc: 1.76 * 20.4287 * sqrt(199948/344.74) = 866 mm
    assert math.isclose(Lp / u.mm, 866.0, rel_tol=5e-3)


# ---------------------------------------------------------------------------
# Lr - AISC Eq. F2-6
# ---------------------------------------------------------------------------
def test_Lr_is_greater_than_Lp(default_props: SectionProperties) -> None:
    Lp = compute_limiting_length_plastic_Lp(
        default_props.radius_of_gyration_weak_axis_ry,
        A992.elastic_modulus_E,
        A992.yield_stress_Fy,
    )
    Lr = compute_limiting_length_inelastic_LTB_Lr(
        effective_radius_of_gyration_rts=default_props.effective_radius_of_gyration_for_LTB_rts,
        distance_between_flange_centroids_ho=default_props.distance_between_flange_centroids_ho,
        torsional_constant_J=default_props.torsional_constant_J,
        elastic_section_modulus_strong_axis_Sx=default_props.elastic_section_modulus_strong_axis_Sx,
        elastic_modulus_E=A992.elastic_modulus_E,
        yield_stress_Fy=A992.yield_stress_Fy,
    )
    assert Lr > Lp


def test_Lr_for_default_section_is_about_2_4m_at_A992(default_props: SectionProperties) -> None:
    Lr = compute_limiting_length_inelastic_LTB_Lr(
        default_props.effective_radius_of_gyration_for_LTB_rts,
        default_props.distance_between_flange_centroids_ho,
        default_props.torsional_constant_J,
        default_props.elastic_section_modulus_strong_axis_Sx,
        A992.elastic_modulus_E,
        A992.yield_stress_Fy,
    )
    # The smoke test confirmed Lr = 2.404 m.
    assert math.isclose(Lr / u.m, 2.404, rel_tol=5e-3)


def test_Lr_with_c_equal_to_one_is_default() -> None:
    # Explicitly passing c=1.0 produces the same Lr.
    sec = DoublySymmetricISection(100.0 * u.mm, 6.0 * u.mm, 300.0 * u.mm, 4.0 * u.mm)
    p = sec.compute_section_properties()
    Lr_default = compute_limiting_length_inelastic_LTB_Lr(
        p.effective_radius_of_gyration_for_LTB_rts,
        p.distance_between_flange_centroids_ho,
        p.torsional_constant_J,
        p.elastic_section_modulus_strong_axis_Sx,
        A992.elastic_modulus_E,
        A992.yield_stress_Fy,
    )
    Lr_c1 = compute_limiting_length_inelastic_LTB_Lr(
        p.effective_radius_of_gyration_for_LTB_rts,
        p.distance_between_flange_centroids_ho,
        p.torsional_constant_J,
        p.elastic_section_modulus_strong_axis_Sx,
        A992.elastic_modulus_E,
        A992.yield_stress_Fy,
        section_constant_c=1.0,
    )
    assert math.isclose(Lr_default, Lr_c1, rel_tol=1e-12)


# ---------------------------------------------------------------------------
# Mp
# ---------------------------------------------------------------------------
def test_Mp_equals_Fy_times_Zx(default_props: SectionProperties) -> None:
    Mp = compute_plastic_moment_Mp(
        A992.yield_stress_Fy,
        default_props.plastic_section_modulus_strong_axis_Zx,
    )
    expected = A992.yield_stress_Fy * default_props.plastic_section_modulus_strong_axis_Zx
    assert math.isclose(Mp, expected, rel_tol=1e-12)


def test_Mp_for_default_section_is_about_94kN_m(default_props: SectionProperties) -> None:
    Mp = compute_plastic_moment_Mp(
        A992.yield_stress_Fy,
        default_props.plastic_section_modulus_strong_axis_Zx,
    )
    Mp_kN_m = Mp / u.MOMENT_DISPLAY_UNIT_kN_m
    # Hand calc: 344.7378 * 273_600 / 1e6 = 94.32 kN.m
    assert math.isclose(Mp_kN_m, 94.32, rel_tol=5e-3)


# ---------------------------------------------------------------------------
# Mcr - AISC Eq. F2-4
# ---------------------------------------------------------------------------
def test_Mcr_decreases_with_increasing_Lb(default_props: SectionProperties) -> None:
    Mcr_3m = compute_elastic_LTB_critical_moment_Mcr(
        1.0,
        3.0 * u.m,
        default_props.effective_radius_of_gyration_for_LTB_rts,
        default_props.elastic_section_modulus_strong_axis_Sx,
        default_props.distance_between_flange_centroids_ho,
        default_props.torsional_constant_J,
        A992.elastic_modulus_E,
    )
    Mcr_5m = compute_elastic_LTB_critical_moment_Mcr(
        1.0,
        5.0 * u.m,
        default_props.effective_radius_of_gyration_for_LTB_rts,
        default_props.elastic_section_modulus_strong_axis_Sx,
        default_props.distance_between_flange_centroids_ho,
        default_props.torsional_constant_J,
        A992.elastic_modulus_E,
    )
    assert Mcr_5m < Mcr_3m


def test_Mcr_scales_linearly_with_Cb(default_props: SectionProperties) -> None:
    common_kwargs = dict(
        unbraced_length_Lb=3.0 * u.m,
        effective_radius_of_gyration_rts=default_props.effective_radius_of_gyration_for_LTB_rts,
        elastic_section_modulus_strong_axis_Sx=default_props.elastic_section_modulus_strong_axis_Sx,
        distance_between_flange_centroids_ho=default_props.distance_between_flange_centroids_ho,
        torsional_constant_J=default_props.torsional_constant_J,
        elastic_modulus_E=A992.elastic_modulus_E,
    )
    Mcr_Cb1 = compute_elastic_LTB_critical_moment_Mcr(
        lateral_torsional_buckling_modification_factor_Cb=1.0,
        **common_kwargs,
    )
    Mcr_Cb2 = compute_elastic_LTB_critical_moment_Mcr(
        lateral_torsional_buckling_modification_factor_Cb=2.0,
        **common_kwargs,
    )
    assert math.isclose(Mcr_Cb2, 2.0 * Mcr_Cb1, rel_tol=1e-12)


# ---------------------------------------------------------------------------
# Inelastic LTB Mn (F2-2)
# ---------------------------------------------------------------------------
def test_F2_2_at_Lb_equal_to_Lp_returns_Cb_times_Mp(default_props: SectionProperties) -> None:
    Fy = A992.yield_stress_Fy
    E = A992.elastic_modulus_E
    Sx = default_props.elastic_section_modulus_strong_axis_Sx
    Zx = default_props.plastic_section_modulus_strong_axis_Zx
    ry = default_props.radius_of_gyration_weak_axis_ry
    Lp = compute_limiting_length_plastic_Lp(ry, E, Fy)
    Lr = compute_limiting_length_inelastic_LTB_Lr(
        default_props.effective_radius_of_gyration_for_LTB_rts,
        default_props.distance_between_flange_centroids_ho,
        default_props.torsional_constant_J,
        Sx,
        E,
        Fy,
    )
    Mp = Fy * Zx
    # At Lb = Lp, interpolation_fraction = 0 -> Mn = Cb * Mp.
    Mn_raw = compute_inelastic_LTB_moment_Mn_F2_2(
        plastic_moment_Mp=Mp,
        yield_stress_Fy=Fy,
        elastic_section_modulus_strong_axis_Sx=Sx,
        lateral_torsional_buckling_modification_factor_Cb=1.5,
        unbraced_length_Lb=Lp,
        limiting_length_plastic_Lp=Lp,
        limiting_length_inelastic_LTB_Lr=Lr,
    )
    assert math.isclose(Mn_raw, 1.5 * Mp, rel_tol=1e-12)


def test_F2_2_at_Lb_equal_to_Lr_returns_Cb_times_0p7_Fy_Sx(
    default_props: SectionProperties,
) -> None:
    Fy = A992.yield_stress_Fy
    E = A992.elastic_modulus_E
    Sx = default_props.elastic_section_modulus_strong_axis_Sx
    Zx = default_props.plastic_section_modulus_strong_axis_Zx
    ry = default_props.radius_of_gyration_weak_axis_ry
    Lp = compute_limiting_length_plastic_Lp(ry, E, Fy)
    Lr = compute_limiting_length_inelastic_LTB_Lr(
        default_props.effective_radius_of_gyration_for_LTB_rts,
        default_props.distance_between_flange_centroids_ho,
        default_props.torsional_constant_J,
        Sx,
        E,
        Fy,
    )
    Mp = Fy * Zx
    # At Lb = Lr, interpolation_fraction = 1 -> Mn = Cb * 0.7*Fy*Sx.
    Mn_raw = compute_inelastic_LTB_moment_Mn_F2_2(
        Mp,
        Fy,
        Sx,
        1.0,
        Lr,
        Lp,
        Lr,
    )
    assert math.isclose(Mn_raw, 0.7 * Fy * Sx, rel_tol=1e-9)
