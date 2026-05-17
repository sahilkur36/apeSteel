"""AISC 360-22 §E4 - torsional and flexural-torsional buckling.

The §E4 elastic buckling stress ``Fe`` is found from the section's
symmetry, then routed through the *same* Eq. E3-2 / E3-3 kernel as
flexural buckling (``compute_critical_stress_from_Fe``).

* Doubly-symmetric (torsional about the longitudinal axis), Eq. E4-2:
  ``Fe = (pi^2 E Cw / Lcz^2 + G J) / (Ix + Iy)``
* Singly-symmetric (flexural-torsional), Eq. E4-3:
  ``Fe = (Fe_sym + Fez)/(2H) * [1 - sqrt(1 - 4 Fe_sym Fez H/(Fe_sym+Fez)^2)]``
  where ``Fe_sym`` is the elastic flexural-buckling stress about the
  axis of symmetry (Eq. E4-5 / E4-6) and ``Fez`` is Eq. E4-7.
* Unsymmetric, Eq. E4-4: smallest positive root of the cubic in ``Fe``.

Supporting equations:

* Eq. E4-5  ``Fex = pi^2 E / (Lcx/rx)^2``
* Eq. E4-6  ``Fey = pi^2 E / (Lcy/ry)^2``
* Eq. E4-7  ``Fez = (pi^2 E Cw / Lcz^2 + G J) / (Ag * ro_bar^2)``
* Eq. E4-8  ``H   = 1 - (xo^2 + yo^2) / ro_bar^2``
* Eq. E4-9  ``ro_bar^2 = xo^2 + yo^2 + (Ix + Iy)/Ag``

Note (360-22 vs the source spreadsheet): 360-22 forms ``Fe`` from the
*elastic* stresses and only then applies Eq. E3-2 / E3-3.  The Q-factor
(360-16) workbook combines post-knock-down stresses; results coincide
only for the doubly-symmetric Eq. E4-2 path (and any non-slender
member), which is exactly the part used as the Excel anchor.

References
----------
.. [1] AISC 360-22 §E4 "Torsional and Flexural-Torsional Buckling of
       Single Angles and Members without Slender Elements", Eq. E4-1 -
       E4-9, pp. 16.1-39 - 16.1-40.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from apeSteel.compression.flexural_buckling_E3 import (
    CriticalStressE3,
    compute_critical_stress_from_Fe,
)

if TYPE_CHECKING:
    from apeSteel.sections.compression_properties import CompressionSectionProperties


def compute_polar_radius_about_shear_centre_squared_ro_bar2(
    shear_centre_x_xo: float,
    shear_centre_y_yo: float,
    moment_of_inertia_x_Ix: float,
    moment_of_inertia_y_Iy: float,
    gross_area_Ag: float,
) -> float:
    """Return ``ro_bar^2`` per AISC 360-22 Eq. E4-9.

    ``ro_bar^2 = xo^2 + yo^2 + (Ix + Iy)/Ag``  (mm^2).
    """
    return (
        shear_centre_x_xo**2
        + shear_centre_y_yo**2
        + (moment_of_inertia_x_Ix + moment_of_inertia_y_Iy) / gross_area_Ag
    )


def compute_flexural_constant_H(
    shear_centre_x_xo: float,
    shear_centre_y_yo: float,
    polar_radius_about_shear_centre_squared_ro_bar2: float,
) -> float:
    """Return the flexural constant ``H`` per AISC 360-22 Eq. E4-8.

    ``H = 1 - (xo^2 + yo^2) / ro_bar^2``  (dimensionless).
    """
    return 1.0 - (
        (shear_centre_x_xo**2 + shear_centre_y_yo**2)
        / polar_radius_about_shear_centre_squared_ro_bar2
    )


def compute_torsional_Fe_doubly_symmetric(
    elastic_modulus_E: float,
    shear_modulus_G: float,
    warping_constant_Cw: float,
    torsional_constant_J: float,
    effective_length_torsional_Lcz: float,
    moment_of_inertia_x_Ix: float,
    moment_of_inertia_y_Iy: float,
) -> float:
    """Return the torsional-buckling ``Fe`` per AISC 360-22 Eq. E4-2.

    ``Fe = (pi^2 E Cw / Lcz^2 + G J) / (Ix + Iy)``  (MPa).
    """
    euler_warping: float = (
        math.pi**2 * elastic_modulus_E * warping_constant_Cw
    ) / effective_length_torsional_Lcz**2
    saint_venant: float = shear_modulus_G * torsional_constant_J
    return (euler_warping + saint_venant) / (moment_of_inertia_x_Ix + moment_of_inertia_y_Iy)


def compute_Fez(
    elastic_modulus_E: float,
    shear_modulus_G: float,
    warping_constant_Cw: float,
    torsional_constant_J: float,
    effective_length_torsional_Lcz: float,
    gross_area_Ag: float,
    polar_radius_about_shear_centre_squared_ro_bar2: float,
) -> float:
    """Return ``Fez`` per AISC 360-22 Eq. E4-7.

    ``Fez = (pi^2 E Cw / Lcz^2 + G J) / (Ag * ro_bar^2)``  (MPa).
    """
    euler_warping: float = (
        math.pi**2 * elastic_modulus_E * warping_constant_Cw
    ) / effective_length_torsional_Lcz**2
    saint_venant: float = shear_modulus_G * torsional_constant_J
    return (euler_warping + saint_venant) / (
        gross_area_Ag * polar_radius_about_shear_centre_squared_ro_bar2
    )


def compute_flexural_torsional_Fe_singly_symmetric(
    elastic_flexural_stress_about_axis_of_symmetry: float,
    Fez: float,
    flexural_constant_H: float,
) -> float:
    """Return the flexural-torsional ``Fe`` per AISC 360-22 Eq. E4-3.

    ``Fe = (Fe_s + Fez)/(2H) * [1 - sqrt(1 - 4 Fe_s Fez H / (Fe_s+Fez)^2)]``

    Parameters
    ----------
    elastic_flexural_stress_about_axis_of_symmetry : float
        ``Fe`` for flexural buckling about the axis of symmetry
        (Eq. E4-5 or E4-6), MPa.
    Fez : float
        Eq. E4-7 (MPa).
    flexural_constant_H : float
        Eq. E4-8 (dimensionless).
    """
    fes: float = elastic_flexural_stress_about_axis_of_symmetry
    summed: float = fes + Fez
    radical: float = 1.0 - (4.0 * fes * Fez * flexural_constant_H) / summed**2
    # Guard tiny negative round-off under the root.
    radical = max(radical, 0.0)
    return (summed / (2.0 * flexural_constant_H)) * (1.0 - math.sqrt(radical))


def compute_flexural_torsional_Fe_unsymmetric(
    Fex: float,
    Fey: float,
    Fez: float,
    shear_centre_x_xo: float,
    shear_centre_y_yo: float,
    polar_radius_about_shear_centre_squared_ro_bar2: float,
) -> float:
    """Return ``Fe`` for an unsymmetric section per AISC 360-22 Eq. E4-4.

    Smallest positive root of the cubic

    ``(Fe-Fex)(Fe-Fey)(Fe-Fez)
        - Fe^2 (Fe-Fey)(xo/ro_bar)^2
        - Fe^2 (Fe-Fex)(yo/ro_bar)^2 = 0``

    The governing elastic buckling stress is the smallest positive root,
    which lies in ``(0, min(Fex, Fey, Fez)]``.  Solved by bisection on
    that bracket (the cubic is positive at ``Fe -> 0+`` and changes sign
    before the smallest of ``Fex, Fey, Fez``).
    """
    xo2_over_ro2: float = shear_centre_x_xo**2 / polar_radius_about_shear_centre_squared_ro_bar2
    yo2_over_ro2: float = shear_centre_y_yo**2 / polar_radius_about_shear_centre_squared_ro_bar2

    def cubic(fe: float) -> float:
        return (
            (fe - Fex) * (fe - Fey) * (fe - Fez)
            - fe**2 * (fe - Fey) * xo2_over_ro2
            - fe**2 * (fe - Fex) * yo2_over_ro2
        )

    hi: float = min(Fex, Fey, Fez)
    lo: float = 1.0e-9 * hi
    f_lo: float = cubic(lo)
    f_hi: float = cubic(hi)
    # The smallest positive root is bracketed by [lo, hi]; if the sign
    # does not change (degenerate doubly/singly case), fall back to hi.
    if f_lo == 0.0:
        return lo
    if f_lo * f_hi > 0.0:
        return hi
    for _ in range(200):
        mid: float = 0.5 * (lo + hi)
        f_mid: float = cubic(mid)
        if f_mid == 0.0 or (hi - lo) < 1.0e-12 * hi:
            return mid
        if f_lo * f_mid < 0.0:
            hi = mid
        else:
            lo = mid
            f_lo = f_mid
    return 0.5 * (lo + hi)


def compute_E4_critical_stress(
    section_properties: CompressionSectionProperties,
    yield_stress_Fy: float,
    elastic_modulus_E: float,
    shear_modulus_G: float,
    effective_length_x_Lcx: float,
    effective_length_y_Lcy: float,
    effective_length_torsional_Lcz: float,
) -> CriticalStressE3:
    """Return the §E4 ``Fcr`` (via the Eq. E3-2 / E3-3 kernel).

    Routes by ``section_properties.symmetry``.  ``ro_bar`` and ``H`` are
    taken from the section properties when populated, else derived from
    Eq. E4-9 / E4-8.
    """
    ix: float = section_properties.moment_of_inertia_x_Ix
    iy: float = section_properties.moment_of_inertia_y_Iy
    ag: float = section_properties.gross_area_Ag
    cw: float = section_properties.warping_constant_Cw
    j: float = section_properties.torsional_constant_J
    xo: float = section_properties.shear_centre_x_xo
    yo: float = section_properties.shear_centre_y_yo

    ro_bar: float = section_properties.polar_radius_about_shear_centre_ro_bar
    ro_bar2: float = (
        ro_bar**2
        if ro_bar > 0.0
        else compute_polar_radius_about_shear_centre_squared_ro_bar2(xo, yo, ix, iy, ag)
    )
    h: float = (
        section_properties.flexural_constant_H
        if section_properties.symmetry == "doubly_symmetric"
        else compute_flexural_constant_H(xo, yo, ro_bar2)
    )

    if section_properties.symmetry == "doubly_symmetric":
        fe: float = compute_torsional_Fe_doubly_symmetric(
            elastic_modulus_E=elastic_modulus_E,
            shear_modulus_G=shear_modulus_G,
            warping_constant_Cw=cw,
            torsional_constant_J=j,
            effective_length_torsional_Lcz=effective_length_torsional_Lcz,
            moment_of_inertia_x_Ix=ix,
            moment_of_inertia_y_Iy=iy,
        )
        return compute_critical_stress_from_Fe(yield_stress_Fy, fe)

    fez: float = compute_Fez(
        elastic_modulus_E=elastic_modulus_E,
        shear_modulus_G=shear_modulus_G,
        warping_constant_Cw=cw,
        torsional_constant_J=j,
        effective_length_torsional_Lcz=effective_length_torsional_Lcz,
        gross_area_Ag=ag,
        polar_radius_about_shear_centre_squared_ro_bar2=ro_bar2,
    )
    fex: float = (math.pi**2 * elastic_modulus_E) / (
        effective_length_x_Lcx / section_properties.radius_of_gyration_x_rx
    ) ** 2
    fey: float = (math.pi**2 * elastic_modulus_E) / (
        effective_length_y_Lcy / section_properties.radius_of_gyration_y_ry
    ) ** 2

    if section_properties.symmetry == "singly_symmetric":
        # The shear centre lies ON the axis of symmetry, so the
        # perpendicular offset to that axis is zero.  xo == 0 -> the
        # y-axis is the axis of symmetry (tee) -> couple Fey with Fez.
        # yo == 0 -> the x-axis is the axis of symmetry (channel) ->
        # couple Fex with Fez.  (Eq. E4-3.)
        fe_sym: float = fey if abs(xo) <= abs(yo) else fex
        fe = compute_flexural_torsional_Fe_singly_symmetric(
            elastic_flexural_stress_about_axis_of_symmetry=fe_sym,
            Fez=fez,
            flexural_constant_H=h,
        )
        return compute_critical_stress_from_Fe(yield_stress_Fy, fe)

    # Unsymmetric.
    fe = compute_flexural_torsional_Fe_unsymmetric(
        Fex=fex,
        Fey=fey,
        Fez=fez,
        shear_centre_x_xo=xo,
        shear_centre_y_yo=yo,
        polar_radius_about_shear_centre_squared_ro_bar2=ro_bar2,
    )
    return compute_critical_stress_from_Fe(yield_stress_Fy, fe)


__all__ = [
    "compute_E4_critical_stress",
    "compute_Fez",
    "compute_flexural_constant_H",
    "compute_flexural_torsional_Fe_singly_symmetric",
    "compute_flexural_torsional_Fe_unsymmetric",
    "compute_polar_radius_about_shear_centre_squared_ro_bar2",
    "compute_torsional_Fe_doubly_symmetric",
]
