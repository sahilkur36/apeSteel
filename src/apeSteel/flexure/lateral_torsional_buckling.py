"""LTB primitives shared by AISC 360 §F2, §F3, and §F5.

Each function here is a pure, single-equation port of one AISC LTB
formula.  The F-section facades (F2, F3, F5) call these in sequence to
build their report.  Splitting the equations out lets each be tested
in isolation against a hand-computed value or a golden CSV.

The constant `c` in F2-6 and F2-4 equals 1.0 for doubly-symmetric I
shapes (default of every public function here).  For singly-symmetric
channels, `c = (h_o / 2) * sqrt(I_y / C_w)` per AISC 360 §F2.2
commentary; callers can pass a non-default `c` when needed.

References
----------
.. [1] AISC 360-22 §F2.2 - LTB of compact doubly-symmetric I-shapes.
       Eq. F2-1 through F2-7.
"""

from __future__ import annotations

import math


# ---------------------------------------------------------------------------
# AISC F2-5 - limiting unbraced length for the yielding plateau (Lp)
# ---------------------------------------------------------------------------
def compute_limiting_length_plastic_Lp(
    radius_of_gyration_weak_axis_ry: float,
    elastic_modulus_E: float,
    yield_stress_Fy: float,
) -> float:
    """Return Lp per AISC 360 Eq. F2-5.

    Lp = 1.76 * ry * sqrt(E / Fy)

    Below this unbraced length, the section can develop its full plastic
    moment Mp before any lateral-torsional buckling occurs.

    Parameters
    ----------
    radius_of_gyration_weak_axis_ry : float
        Weak-axis radius of gyration ry (mm).
    elastic_modulus_E : float
        Steel elastic modulus E (MPa).
    yield_stress_Fy : float
        Steel specified yield stress Fy (MPa).

    Returns
    -------
    float
        Lp in apeSteel base units (mm).
    """
    ry = radius_of_gyration_weak_axis_ry
    E = elastic_modulus_E
    Fy = yield_stress_Fy
    return 1.76 * ry * math.sqrt(E / Fy)


# ---------------------------------------------------------------------------
# AISC F2-6 - limiting unbraced length for inelastic LTB (Lr)
# ---------------------------------------------------------------------------
def compute_limiting_length_inelastic_LTB_Lr(
    effective_radius_of_gyration_rts: float,
    distance_between_flange_centroids_ho: float,
    torsional_constant_J: float,
    elastic_section_modulus_strong_axis_Sx: float,
    elastic_modulus_E: float,
    yield_stress_Fy: float,
    section_constant_c: float = 1.0,
) -> float:
    """Return Lr per AISC 360 Eq. F2-6.

    Lr = 1.95 * rts * E / (0.7*Fy)
         * sqrt(J*c / (Sx*ho))
         * sqrt(1 + sqrt(1 + 6.76 * ( 0.7*Fy*Sx*ho / (E*J*c) )^2))

    Above this length, LTB is fully elastic (Eq. F2-3 / F2-4).
    Between Lp and Lr it is inelastic (Eq. F2-2).

    Parameters
    ----------
    effective_radius_of_gyration_rts : float
        rts per Eq. F2-7 (mm).
    distance_between_flange_centroids_ho : float
        ho = hw + tf for built-up I, the distance between flange
        centroids (mm).
    torsional_constant_J : float
        Saint-Venant torsion constant (mm^4).
    elastic_section_modulus_strong_axis_Sx : float
        Sx about the bending axis (mm^3).
    elastic_modulus_E : float
        E (MPa).
    yield_stress_Fy : float
        Fy (MPa).
    section_constant_c : float, optional
        AISC c constant.  1.0 for doubly-symmetric I (default).

    Returns
    -------
    float
        Lr in apeSteel base units (mm).
    """
    rts = effective_radius_of_gyration_rts
    ho = distance_between_flange_centroids_ho
    J = torsional_constant_J
    Sx = elastic_section_modulus_strong_axis_Sx
    E = elastic_modulus_E
    Fy = yield_stress_Fy
    c = section_constant_c

    Jc_over_Sxho: float = (J * c) / (Sx * ho)
    inverse_ratio: float = (0.7 * Fy * Sx * ho) / (E * J * c)
    inner_root: float = math.sqrt(1.0 + 6.76 * inverse_ratio**2)
    outer_root: float = math.sqrt(1.0 + inner_root)
    return 1.95 * rts * (E / (0.7 * Fy)) * math.sqrt(Jc_over_Sxho) * outer_root


# ---------------------------------------------------------------------------
# AISC F2-4 - elastic LTB critical moment Mcr (= Fcr * Sx, written
# in moment form so callers don't have to multiply)
# ---------------------------------------------------------------------------
def compute_elastic_LTB_critical_moment_Mcr(
    lateral_torsional_buckling_modification_factor_Cb: float,
    unbraced_length_Lb: float,
    effective_radius_of_gyration_rts: float,
    elastic_section_modulus_strong_axis_Sx: float,
    distance_between_flange_centroids_ho: float,
    torsional_constant_J: float,
    elastic_modulus_E: float,
    section_constant_c: float = 1.0,
) -> float:
    """Return Mcr per AISC 360 Eq. F2-4 (elastic LTB regime).

    Fcr = (Cb * pi^2 * E) / (Lb/rts)^2
          * sqrt(1 + 0.078 * (J*c / (Sx*ho)) * (Lb/rts)^2)
    Mcr = Fcr * Sx

    Used only when Lb > Lr; the caller is responsible for routing.

    Parameters
    ----------
    lateral_torsional_buckling_modification_factor_Cb : float
        Cb per AISC F1-1.  Dimensionless, >= 1.0 by definition for
        practical moment diagrams.
    unbraced_length_Lb : float
        Unbraced length of the compression flange (mm).
    effective_radius_of_gyration_rts : float
        rts (mm).
    elastic_section_modulus_strong_axis_Sx : float
        Sx (mm^3).
    distance_between_flange_centroids_ho : float
        ho (mm).
    torsional_constant_J : float
        J (mm^4).
    elastic_modulus_E : float
        E (MPa).
    section_constant_c : float, optional
        c constant. 1.0 for doubly-symmetric I.

    Returns
    -------
    float
        Mcr in apeSteel base units (N*mm).
    """
    Cb = lateral_torsional_buckling_modification_factor_Cb
    Lb = unbraced_length_Lb
    rts = effective_radius_of_gyration_rts
    Sx = elastic_section_modulus_strong_axis_Sx
    ho = distance_between_flange_centroids_ho
    J = torsional_constant_J
    E = elastic_modulus_E
    c = section_constant_c

    Lb_over_rts_squared: float = (Lb / rts) ** 2
    Fcr: float = (
        (Cb * math.pi**2 * E)
        / Lb_over_rts_squared
        * math.sqrt(1.0 + 0.078 * (J * c / (Sx * ho)) * Lb_over_rts_squared)
    )
    return Fcr * Sx


# ---------------------------------------------------------------------------
# Plastic moment Mp - the yielding plateau
# ---------------------------------------------------------------------------
def compute_plastic_moment_Mp(
    yield_stress_Fy: float,
    plastic_section_modulus_strong_axis_Zx: float,
) -> float:
    """Return Mp = Fy * Zx, the plastic-moment plateau used by F2-1.

    Parameters
    ----------
    yield_stress_Fy : float
        Fy (MPa).
    plastic_section_modulus_strong_axis_Zx : float
        Zx (mm^3).

    Returns
    -------
    float
        Mp in apeSteel base units (N*mm).
    """
    return yield_stress_Fy * plastic_section_modulus_strong_axis_Zx


# ---------------------------------------------------------------------------
# Inelastic-LTB linear interpolation between (Lp, Mp) and (Lr, 0.7*Fy*Sx)
# ---------------------------------------------------------------------------
def compute_inelastic_LTB_moment_Mn_F2_2(
    plastic_moment_Mp: float,
    yield_stress_Fy: float,
    elastic_section_modulus_strong_axis_Sx: float,
    lateral_torsional_buckling_modification_factor_Cb: float,
    unbraced_length_Lb: float,
    limiting_length_plastic_Lp: float,
    limiting_length_inelastic_LTB_Lr: float,
) -> float:
    """Return Mn per AISC 360 Eq. F2-2 (inelastic LTB regime).

    Mn = Cb * (Mp - (Mp - 0.7*Fy*Sx) * (Lb - Lp)/(Lr - Lp))

    The caller is responsible for verifying Lp < Lb <= Lr.  The output
    is NOT capped at Mp here; the facade caps the final Mn.
    """
    Mp = plastic_moment_Mp
    Fy = yield_stress_Fy
    Sx = elastic_section_modulus_strong_axis_Sx
    Cb = lateral_torsional_buckling_modification_factor_Cb
    Lb = unbraced_length_Lb
    Lp = limiting_length_plastic_Lp
    Lr = limiting_length_inelastic_LTB_Lr

    reduced_stress_moment: float = 0.7 * Fy * Sx
    interpolation_fraction: float = (Lb - Lp) / (Lr - Lp)
    return Cb * (Mp - (Mp - reduced_stress_moment) * interpolation_fraction)


__all__ = [
    "compute_elastic_LTB_critical_moment_Mcr",
    "compute_inelastic_LTB_moment_Mn_F2_2",
    "compute_limiting_length_inelastic_LTB_Lr",
    "compute_limiting_length_plastic_Lp",
    "compute_plastic_moment_Mp",
]
