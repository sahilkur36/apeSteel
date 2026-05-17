"""AISC 360-22 §H3 - torsion and combined torsion/flexure/shear/axial.

* **§H3.1** - round and rectangular HSS in torsion.  ``Tn = Fcr*C``
  (Eq. H3-1), ``phi_T = 0.90`` / ``Omega_T = 1.67``.

  Round HSS (``C = pi*(D-t)^2*t/2``): ``Fcr`` = the larger of
  Eq. H3-2a ``1.23*E/(sqrt(L/D)*(D/t)^{5/4})`` and Eq. H3-2b
  ``0.60*E/(D/t)^{3/2}``, but not greater than ``0.6*Fy``.

  Rectangular HSS (``h/t`` = larger flat-wall ratio; ``C`` is the
  tabulated HSS torsional constant - a section property, supplied):
  ``Fcr = 0.6*Fy`` for ``h/t <= 2.45*sqrt(E/Fy)``; Eq. H3-4 for
  ``2.45*sqrt(E/Fy) < h/t <= 3.07*sqrt(E/Fy)``; Eq. H3-5 for
  ``3.07*sqrt(E/Fy) < h/t <= 260``.

* **§H3.2** - HSS under combined torsion, shear, flexure, axial.
  When ``Tr <= 0.2*Tc`` torsion may be neglected (check by §H1);
  otherwise Eq. H3-6 ``(Pr/Pc + Mr/Mc) + (Vr/Vc + Tr/Tc)^2 <= 1.0``.

* **§H3.3** - non-HSS members in torsion: the code-level limiting
  nominal stress ``Fn`` = lowest of ``Fy`` (Eq. H3-7), ``0.6*Fy``
  (Eq. H3-8), ``Fcr`` (Eq. H3-9).  The warping / St-Venant *stress
  demand* for an open section requires Design Guide 9 and is out of
  scope (design note 09 §1/§8); only the limiting stress is produced.

References
----------
.. [1] AISC 360-22 §H3, Eq. H3-1, H3-2a, H3-2b, H3-3 .. H3-9,
       pp. 16.1-86 - 16.1-88.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from apeSteel.combined._common import (
    CITATIONS_AISC_360_CHAPTER_H,
    H3_2_TORSION_NEGLECT_RATIO,
    H3_3_SHEAR_YIELD_FRACTION,
    H3_FCR_SHEAR_YIELD_FRACTION,
    H3_RECT_H3_5_COEFF,
    H3_RECT_HT_ABSOLUTE_MAX,
    H3_RECT_HT_LIMIT_1_COEFF,
    H3_RECT_HT_LIMIT_2_COEFF,
    H3_ROUND_H3_2A_COEFF,
    H3_ROUND_H3_2B_COEFF,
    OMEGA_TORSION_ASD,
    PHI_TORSION_LRFD,
    CombinedLimitState,
)
from apeSteel.core.result_types import AISCClauseReference, Report

TorsionH3GoverningState = Literal["shear_yielding_0p6Fy", "H3-2a", "H3-2b", "H3-4", "H3-5"]
NonHSSGoverningState = Literal["H3-7", "H3-8", "H3-9"]

_CITATIONS_H3_1: tuple[AISCClauseReference, ...] = (
    *CITATIONS_AISC_360_CHAPTER_H,
    AISCClauseReference("AISC 360-22", "H3.1", "H3-1", "16.1-86"),
    AISCClauseReference("AISC 360-22", "H3.1", "H3-2a", "16.1-86"),
    AISCClauseReference("AISC 360-22", "H3.1", "H3-2b", "16.1-86"),
)
_CITATIONS_H3_1_RECT: tuple[AISCClauseReference, ...] = (
    *CITATIONS_AISC_360_CHAPTER_H,
    AISCClauseReference("AISC 360-22", "H3.1", "H3-1", "16.1-86"),
    AISCClauseReference("AISC 360-22", "H3.1", "H3-4", "16.1-86"),
    AISCClauseReference("AISC 360-22", "H3.1", "H3-5", "16.1-86"),
)
_CITATIONS_H3_2: tuple[AISCClauseReference, ...] = (
    *CITATIONS_AISC_360_CHAPTER_H,
    AISCClauseReference("AISC 360-22", "H3.2", "H3-6", "16.1-87"),
)
_CITATIONS_H3_3: tuple[AISCClauseReference, ...] = (
    *CITATIONS_AISC_360_CHAPTER_H,
    AISCClauseReference("AISC 360-22", "H3.3", "H3-7", "16.1-88"),
    AISCClauseReference("AISC 360-22", "H3.3", "H3-8", "16.1-88"),
    AISCClauseReference("AISC 360-22", "H3.3", "H3-9", "16.1-88"),
)


# ---------------------------------------------------------------------------
# §H3.1 - HSS torsional strength
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class TorsionH3Report(Report):
    """AISC 360-22 §H3.1 HSS torsional strength (Eq. H3-1).

    ``nominal_strength`` carries ``Tn``; ``phi_strength_LRFD`` is
    ``phi_T*Tn`` (``phi_T = 0.90``).

    Attributes
    ----------
    critical_stress_Fcr : float
        ``Fcr`` (MPa).
    torsional_constant_C : float
        HSS torsional constant ``C`` (mm^3).
    nominal_torsional_strength_Tn : float
        ``Tn = Fcr*C`` (N*mm).
    governing_torsion_state : str
        Which branch produced ``Fcr`` ("shear_yielding_0p6Fy",
        "H3-2a", "H3-2b", "H3-4", "H3-5").
    """

    critical_stress_Fcr: float = 0.0
    torsional_constant_C: float = 0.0
    nominal_torsional_strength_Tn: float = 0.0
    governing_torsion_state: TorsionH3GoverningState = "shear_yielding_0p6Fy"


def compute_torsional_strength_round_HSS_H3_1(
    yield_stress_Fy: float,
    elastic_modulus_E: float,
    outside_diameter_D: float,
    wall_thickness_t: float,
    member_length_L: float,
) -> TorsionH3Report:
    """Return the AISC 360-22 §H3.1(a) round-HSS torsional strength.

    Parameters
    ----------
    yield_stress_Fy : float
        ``Fy`` (MPa).  Must be > 0.
    elastic_modulus_E : float
        ``E`` (MPa).
    outside_diameter_D : float
        Outside diameter ``D`` (mm).  Must be > 0.
    wall_thickness_t : float
        Design wall thickness ``t`` (mm).  Must be ``0 < t < D``.
    member_length_L : float
        Length ``L`` (mm) used in Eq. H3-2a.  Must be > 0.

    Returns
    -------
    TorsionH3Report

    Raises
    ------
    ValueError
        On non-physical geometry inputs.
    """
    if yield_stress_Fy <= 0.0:
        raise ValueError(f"yield_stress_Fy must be positive, got {yield_stress_Fy!r}")
    if outside_diameter_D <= 0.0 or wall_thickness_t <= 0.0:
        raise ValueError("outside_diameter_D and wall_thickness_t must be positive")
    if wall_thickness_t >= outside_diameter_D:
        raise ValueError("wall_thickness_t must be less than outside_diameter_D")
    if member_length_L <= 0.0:
        raise ValueError(f"member_length_L must be positive, got {member_length_L!r}")

    dt: float = outside_diameter_D / wall_thickness_t
    fcr_2a: float = (
        H3_ROUND_H3_2A_COEFF
        * elastic_modulus_E
        / (math.sqrt(member_length_L / outside_diameter_D) * dt**1.25)
    )  # Eq. H3-2a
    fcr_2b: float = H3_ROUND_H3_2B_COEFF * elastic_modulus_E / dt**1.5  # Eq. H3-2b
    fcr_buckling: float = max(fcr_2a, fcr_2b)
    cap: float = H3_FCR_SHEAR_YIELD_FRACTION * yield_stress_Fy
    if fcr_buckling >= cap:
        fcr: float = cap
        gov: TorsionH3GoverningState = "shear_yielding_0p6Fy"
    elif fcr_2a >= fcr_2b:
        fcr = fcr_2a
        gov = "H3-2a"
    else:
        fcr = fcr_2b
        gov = "H3-2b"

    c_const: float = math.pi * (outside_diameter_D - wall_thickness_t) ** 2 * wall_thickness_t / 2.0
    tn: float = fcr * c_const  # Eq. H3-1
    return TorsionH3Report(
        cited_clauses=_CITATIONS_H3_1,
        governing_limit_state=gov,
        phi_LRFD=PHI_TORSION_LRFD,
        omega_ASD=OMEGA_TORSION_ASD,
        nominal_strength=tn,
        phi_strength_LRFD=PHI_TORSION_LRFD * tn,
        omega_strength_ASD=tn / OMEGA_TORSION_ASD,
        critical_stress_Fcr=fcr,
        torsional_constant_C=c_const,
        nominal_torsional_strength_Tn=tn,
        governing_torsion_state=gov,
    )


def compute_torsional_strength_rect_HSS_H3_1(
    yield_stress_Fy: float,
    elastic_modulus_E: float,
    flat_width_to_thickness_h_over_t: float,
    torsional_constant_C: float,
) -> TorsionH3Report:
    """Return the AISC 360-22 §H3.1(b) rectangular-HSS torsional strength.

    Parameters
    ----------
    yield_stress_Fy : float
        ``Fy`` (MPa).  Must be > 0.
    elastic_modulus_E : float
        ``E`` (MPa).
    flat_width_to_thickness_h_over_t : float
        The larger flat-wall ``h/t`` ratio.  Must be > 0 and <= 260.
    torsional_constant_C : float
        HSS torsional constant ``C`` (mm^3) - a tabulated section
        property.  Must be > 0.

    Returns
    -------
    TorsionH3Report

    Raises
    ------
    ValueError
        If inputs are non-physical or ``h/t > 260`` (outside §H3.1).
    """
    if yield_stress_Fy <= 0.0:
        raise ValueError(f"yield_stress_Fy must be positive, got {yield_stress_Fy!r}")
    if flat_width_to_thickness_h_over_t <= 0.0:
        raise ValueError("flat_width_to_thickness_h_over_t must be positive")
    if torsional_constant_C <= 0.0:
        raise ValueError("torsional_constant_C must be positive")

    s: float = math.sqrt(elastic_modulus_E / yield_stress_Fy)
    lim_1: float = H3_RECT_HT_LIMIT_1_COEFF * s
    lim_2: float = H3_RECT_HT_LIMIT_2_COEFF * s
    h_t: float = flat_width_to_thickness_h_over_t
    if h_t <= lim_1:
        fcr: float = H3_FCR_SHEAR_YIELD_FRACTION * yield_stress_Fy
        gov: TorsionH3GoverningState = "shear_yielding_0p6Fy"
    elif h_t <= lim_2:
        fcr = H3_FCR_SHEAR_YIELD_FRACTION * yield_stress_Fy * lim_1 / h_t  # Eq. H3-4
        gov = "H3-4"
    elif h_t <= H3_RECT_HT_ABSOLUTE_MAX:
        fcr = H3_RECT_H3_5_COEFF * math.pi**2 * elastic_modulus_E / h_t**2  # Eq. H3-5
        gov = "H3-5"
    else:
        raise ValueError(
            f"rectangular HSS h/t = {h_t!r} exceeds the §H3.1 limit of {H3_RECT_HT_ABSOLUTE_MAX}"
        )

    tn: float = fcr * torsional_constant_C  # Eq. H3-1
    return TorsionH3Report(
        cited_clauses=_CITATIONS_H3_1_RECT,
        governing_limit_state=gov,
        phi_LRFD=PHI_TORSION_LRFD,
        omega_ASD=OMEGA_TORSION_ASD,
        nominal_strength=tn,
        phi_strength_LRFD=PHI_TORSION_LRFD * tn,
        omega_strength_ASD=tn / OMEGA_TORSION_ASD,
        critical_stress_Fcr=fcr,
        torsional_constant_C=torsional_constant_C,
        nominal_torsional_strength_Tn=tn,
        governing_torsion_state=gov,
    )


# ---------------------------------------------------------------------------
# §H3.2 - HSS combined torsion / shear / flexure / axial
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class CombinedH32Report(Report):
    """AISC 360-22 §H3.2 HSS combined-effects result (Eq. H3-6).

    Attributes
    ----------
    torsion_is_negligible : bool
        ``Tr <= 0.2*Tc`` - torsion may be neglected (check by §H1);
        when True the Eq. H3-6 terms are not evaluated.
    axial_flexure_term : float
        ``Pr/Pc + Mr/Mc``.
    shear_torsion_term : float
        ``Vr/Vc + Tr/Tc``  (squared in Eq. H3-6).
    demand_capacity_ratio : float
        ``(Pr/Pc + Mr/Mc) + (Vr/Vc + Tr/Tc)^2`` (0.0 when negligible).
    unity_check_passes : bool
        ``demand_capacity_ratio <= 1.0`` (True when torsion negligible
        - the §H1 check governs and is performed separately).
    """

    torsion_is_negligible: bool = False
    axial_flexure_term: float = 0.0
    shear_torsion_term: float = 0.0
    demand_capacity_ratio: float = 0.0
    unity_check_passes: bool = True


def compute_combined_strength_H3_2(
    required_axial_Pr: float,
    available_axial_Pc: float,
    required_moment_Mr: float,
    available_moment_Mc: float,
    required_shear_Vr: float,
    available_shear_Vc: float,
    required_torsion_Tr: float,
    available_torsion_Tc: float,
) -> CombinedH32Report:
    """Return the AISC 360-22 §H3.2 (Eq. H3-6) HSS combined report.

    When ``Tr <= 0.2*Tc`` torsion is permitted to be neglected and the
    member is checked by §H1 (``torsion_is_negligible=True``, DCR not
    evaluated).  Otherwise Eq. H3-6.

    Parameters
    ----------
    required_axial_Pr, required_moment_Mr, required_shear_Vr,
    required_torsion_Tr : float
        Required second-order strengths (N, N*mm, N, N*mm).
    available_axial_Pc, available_moment_Mc, available_shear_Vc,
    available_torsion_Tc : float
        Available strengths (``phi*Pn`` etc.).  Must be > 0.

    Returns
    -------
    CombinedH32Report

    Raises
    ------
    ValueError
        If any available strength is non-positive.
    """
    for name, val in (
        ("available_axial_Pc", available_axial_Pc),
        ("available_moment_Mc", available_moment_Mc),
        ("available_shear_Vc", available_shear_Vc),
        ("available_torsion_Tc", available_torsion_Tc),
    ):
        if val <= 0.0:
            raise ValueError(f"{name} (available strength) must be positive, got {val!r}")

    if required_torsion_Tr <= H3_2_TORSION_NEGLECT_RATIO * available_torsion_Tc:
        return CombinedH32Report(
            cited_clauses=_CITATIONS_H3_2,
            governing_limit_state="torsion_negligible_H1",
            phi_LRFD=1.0,
            omega_ASD=1.0,
            torsion_is_negligible=True,
            axial_flexure_term=0.0,
            shear_torsion_term=0.0,
            demand_capacity_ratio=0.0,
            unity_check_passes=True,
        )

    axial_flexure_term: float = (
        required_axial_Pr / available_axial_Pc + required_moment_Mr / available_moment_Mc
    )
    shear_torsion_term: float = (
        required_shear_Vr / available_shear_Vc + required_torsion_Tr / available_torsion_Tc
    )
    dcr: float = axial_flexure_term + shear_torsion_term**2  # Eq. H3-6
    governing: CombinedLimitState = "H3-6"
    return CombinedH32Report(
        cited_clauses=_CITATIONS_H3_2,
        governing_limit_state=governing,
        phi_LRFD=1.0,
        omega_ASD=1.0,
        torsion_is_negligible=False,
        axial_flexure_term=axial_flexure_term,
        shear_torsion_term=shear_torsion_term,
        demand_capacity_ratio=dcr,
        unity_check_passes=dcr <= 1.0,
    )


# ---------------------------------------------------------------------------
# §H3.3 - non-HSS limiting nominal stress
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class NonHSSTorsionH33Report(Report):
    """AISC 360-22 §H3.3 limiting nominal torsional stress ``Fn``.

    Only the *code-level limiting stress* is produced; the warping /
    St-Venant stress demand for an open section needs Design Guide 9
    (out of scope - design note 09 §1/§8).

    Attributes
    ----------
    Fn_yielding_H3_7 : float
        ``Fy`` (Eq. H3-7).
    Fn_shear_yielding_H3_8 : float
        ``0.6*Fy`` (Eq. H3-8).
    Fn_buckling_H3_9 : float or None
        ``Fcr`` (Eq. H3-9); ``None`` if buckling not evaluated.
    governing_Fn : float
        Lowest applicable ``Fn`` (MPa).
    nominal_torsional_strength_Tn : float or None
        ``Fn*C`` (N*mm) if a torsional constant ``C`` was supplied.
    """

    Fn_yielding_H3_7: float = 0.0
    Fn_shear_yielding_H3_8: float = 0.0
    Fn_buckling_H3_9: float | None = None
    governing_Fn: float = 0.0
    nominal_torsional_strength_Tn: float | None = None


def compute_nonHSS_torsion_limit_H3_3(
    yield_stress_Fy: float,
    buckling_stress_Fcr: float | None = None,
    torsional_constant_C: float | None = None,
) -> NonHSSTorsionH33Report:
    """Return the AISC 360-22 §H3.3 limiting nominal stress ``Fn``.

    ``Fn`` is the lowest of ``Fy`` (Eq. H3-7), ``0.6*Fy`` (Eq. H3-8)
    and, if supplied, ``Fcr`` (Eq. H3-9).  If ``torsional_constant_C``
    is given, ``Tn = Fn*C`` is also reported (``phi_T = 0.90``).

    Parameters
    ----------
    yield_stress_Fy : float
        ``Fy`` (MPa).  Must be > 0.
    buckling_stress_Fcr : float or None, optional
        ``Fcr`` (MPa) for the Eq. H3-9 buckling limit.
    torsional_constant_C : float or None, optional
        ``C`` (mm^3); when given, ``Tn = Fn*C`` is reported.

    Returns
    -------
    NonHSSTorsionH33Report

    Raises
    ------
    ValueError
        If ``Fy <= 0`` or a supplied ``Fcr``/``C`` is non-positive.
    """
    if yield_stress_Fy <= 0.0:
        raise ValueError(f"yield_stress_Fy must be positive, got {yield_stress_Fy!r}")
    if buckling_stress_Fcr is not None and buckling_stress_Fcr <= 0.0:
        raise ValueError("buckling_stress_Fcr must be positive when supplied")
    if torsional_constant_C is not None and torsional_constant_C <= 0.0:
        raise ValueError("torsional_constant_C must be positive when supplied")

    fn_yield: float = yield_stress_Fy  # Eq. H3-7
    fn_shear: float = H3_3_SHEAR_YIELD_FRACTION * yield_stress_Fy  # Eq. H3-8
    candidates: list[tuple[float, NonHSSGoverningState]] = [
        (fn_yield, "H3-7"),
        (fn_shear, "H3-8"),
    ]
    if buckling_stress_Fcr is not None:  # Eq. H3-9
        candidates.append((buckling_stress_Fcr, "H3-9"))
    fn_gov, label = min(candidates, key=lambda kv: kv[0])

    tn: float | None = None
    phi_tn: float = 0.0
    omega_tn: float = 0.0
    if torsional_constant_C is not None:
        tn = fn_gov * torsional_constant_C
        phi_tn = PHI_TORSION_LRFD * tn
        omega_tn = tn / OMEGA_TORSION_ASD

    return NonHSSTorsionH33Report(
        cited_clauses=_CITATIONS_H3_3,
        governing_limit_state=label,
        phi_LRFD=PHI_TORSION_LRFD,
        omega_ASD=OMEGA_TORSION_ASD,
        nominal_strength=tn if tn is not None else 0.0,
        phi_strength_LRFD=phi_tn,
        omega_strength_ASD=omega_tn,
        Fn_yielding_H3_7=fn_yield,
        Fn_shear_yielding_H3_8=fn_shear,
        Fn_buckling_H3_9=buckling_stress_Fcr,
        governing_Fn=fn_gov,
        nominal_torsional_strength_Tn=tn,
    )


__all__ = [
    "CombinedH32Report",
    "NonHSSGoverningState",
    "NonHSSTorsionH33Report",
    "TorsionH3GoverningState",
    "TorsionH3Report",
    "compute_combined_strength_H3_2",
    "compute_nonHSS_torsion_limit_H3_3",
    "compute_torsional_strength_rect_HSS_H3_1",
    "compute_torsional_strength_round_HSS_H3_1",
]
