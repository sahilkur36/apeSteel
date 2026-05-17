"""Flange-local-buckling (FLB) primitives for AISC 360 §F3 / §F4.

Two pure single-equation functions:

* `compute_flange_local_buckling_moment_Mn_F3_1` - non-compact flange,
  linear interpolation between Mp at the compact limit and 0.7*Fy*Sx at
  the non-compact limit (AISC 360 Eq. F3-1).
* `compute_flange_local_buckling_moment_Mn_F3_2` - slender flange,
  closed-form 0.9*E*kc*Sx/lambda^2 (AISC 360 Eq. F3-2).

The caller is responsible for selecting which equation applies based on
the AISC §B4.1b flange classification (compact / non-compact / slender).

References
----------
.. [1] AISC 360-22 §F3.2 "Compression Flange Local Buckling",
       Eq. F3-1 and F3-2.  Steel Construction Manual, 16th ed., p. 16.1-50.
"""

from __future__ import annotations

# AISC 360 §F3.2 / §F2.2 (Eq. F2-2 background): the "reduced stress" the
# section can develop in the regime above Lp / above lambda_pf is 0.7 * Fy,
# corresponding to a residual-stress-reduced first-yield level.
AISC_F3_REDUCED_STRESS_FACTOR_0p7: float = 0.7

# AISC 360 §F3.2 Eq. F3-2 coefficient.
AISC_F3_2_ELASTIC_BUCKLING_COEFFICIENT_0p9: float = 0.9


def compute_flange_local_buckling_moment_Mn_F3_1(
    plastic_moment_Mp: float,
    yield_stress_Fy: float,
    elastic_section_modulus_strong_axis_Sx: float,
    flange_slenderness_ratio_lambda_f: float,
    flange_compact_limit_lambda_pf: float,
    flange_noncompact_limit_lambda_rf: float,
) -> float:
    """Return Mn per AISC Eq. F3-1 (non-compact flange, linear interpolation).

    Mn_FLB = Mp - (Mp - 0.7*Fy*Sx) * (lambda_f - lambda_pf)/(lambda_rf - lambda_pf)

    Applies only when lambda_pf < lambda_f <= lambda_rf.  The caller must
    verify the flange falls in the non-compact range before calling.

    Parameters
    ----------
    plastic_moment_Mp : float
        Mp = Fy * Zx (N*mm).
    yield_stress_Fy : float
        Fy (MPa).
    elastic_section_modulus_strong_axis_Sx : float
        Sx (mm^3).
    flange_slenderness_ratio_lambda_f : float
        bf/(2*tf) for an I-shape, dimensionless.
    flange_compact_limit_lambda_pf : float
        lambda_p for the flange from AISC Table B4.1b.
    flange_noncompact_limit_lambda_rf : float
        lambda_r for the flange from AISC Table B4.1b.

    Returns
    -------
    float
        Mn for the FLB limit state in base units (N*mm).  Not capped at
        Mp here; the caller is responsible for the final cap.
    """
    Mp = plastic_moment_Mp
    Fy = yield_stress_Fy
    Sx = elastic_section_modulus_strong_axis_Sx
    lam = flange_slenderness_ratio_lambda_f
    lam_p = flange_compact_limit_lambda_pf
    lam_r = flange_noncompact_limit_lambda_rf

    reduced_stress_moment: float = AISC_F3_REDUCED_STRESS_FACTOR_0p7 * Fy * Sx
    interpolation_fraction: float = (lam - lam_p) / (lam_r - lam_p)
    return Mp - (Mp - reduced_stress_moment) * interpolation_fraction


def compute_flange_local_buckling_moment_Mn_F3_2(
    elastic_section_modulus_strong_axis_Sx: float,
    elastic_modulus_E: float,
    flange_plate_buckling_coefficient_kc: float,
    flange_slenderness_ratio_lambda_f: float,
) -> float:
    """Return Mn per AISC Eq. F3-2 (slender flange, elastic buckling).

    Mn_FLB = 0.9 * E * kc * Sx / lambda_f^2

    Applies only when lambda_f > lambda_rf.  The caller must verify the
    flange is slender before calling.  `kc` is computed via
    :func:`apeSteel.classification.compute_kc_for_built_up_flange` for
    welded I-shapes, or taken implicitly as 1.0 in the equation for
    rolled (Table B4.1b note [c] applies to built-up sections only).
    For rolled sections, AISC has no Eq. F3-2 slender-flange path; the
    caller should not invoke this function for a rolled I.

    Parameters
    ----------
    elastic_section_modulus_strong_axis_Sx : float
        Sx (mm^3).
    elastic_modulus_E : float
        E (MPa).
    flange_plate_buckling_coefficient_kc : float
        kc per Table B4.1b note [c], bounded 0.35 <= kc <= 0.76.
    flange_slenderness_ratio_lambda_f : float
        bf/(2*tf), dimensionless.

    Returns
    -------
    float
        Mn for the slender-flange FLB limit state in base units (N*mm).
        Not capped at Mp here; caller caps.
    """
    Sx = elastic_section_modulus_strong_axis_Sx
    E = elastic_modulus_E
    kc = flange_plate_buckling_coefficient_kc
    lam = flange_slenderness_ratio_lambda_f
    return AISC_F3_2_ELASTIC_BUCKLING_COEFFICIENT_0p9 * E * kc * Sx / (lam**2)


__all__ = [
    "AISC_F3_2_ELASTIC_BUCKLING_COEFFICIENT_0p9",
    "AISC_F3_REDUCED_STRESS_FACTOR_0p7",
    "compute_flange_local_buckling_moment_Mn_F3_1",
    "compute_flange_local_buckling_moment_Mn_F3_2",
]
