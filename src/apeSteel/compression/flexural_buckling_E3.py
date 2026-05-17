"""AISC 360-22 §E3 - flexural-buckling critical stress.

Pure single-equation primitives.  The §E7 area reduction and the
governing-mode selection live in the facade, exactly as the Chapter-F
LTB primitives feed the F2/F3 facades.

* Eq. E3-4  ``Fe = pi^2 * E / (Lc/r)^2``           (elastic buckling stress)
* Eq. E3-2  ``Fcr = 0.658^(Fy/Fe) * Fy``           (inelastic regime)
* Eq. E3-3  ``Fcr = 0.877 * Fe``                   (elastic regime)
* Eq. E3-1  ``Pn = Fcr * Ag``  (non-slender; §E7 substitutes Ae)

The inelastic / elastic boundary is ``Lc/r <= 4.71*sqrt(E/Fy)``,
equivalently ``Fy/Fe <= 2.25`` (the two are algebraically identical;
this module uses the ``Fy/Fe`` form so it is exact at the boundary).

Note (360-22 vs 360-16): AISC 360-22 deleted the ``Q = Qs*Qa`` slender-
element knock-down on *stress*.  §E3 here always uses the full ``Fy``;
slender elements are handled by reducing *area* to ``Ae`` in §E7.

References
----------
.. [1] AISC 360-22 §E3 "Flexural Buckling of Members without Slender
       Elements", Eq. E3-1 - E3-4, pp. 16.1-37 - 16.1-38.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from apeSteel.compression._common import (
    BucklingRegime,
    E3_ELASTIC_FACTOR_0p877,
    E3_INELASTIC_BASE_0p658,
)


def compute_elastic_buckling_stress_Fe(
    elastic_modulus_E: float,
    member_slenderness_Lc_over_r: float,
) -> float:
    """Return ``Fe`` per AISC 360-22 Eq. E3-4.

    ``Fe = pi^2 * E / (Lc/r)^2``

    Parameters
    ----------
    elastic_modulus_E : float
        Steel elastic modulus ``E`` (MPa).
    member_slenderness_Lc_over_r : float
        ``Lc / r`` for the governing axis (dimensionless).  Must be > 0.

    Returns
    -------
    float
        Elastic flexural-buckling stress ``Fe`` (MPa).

    Raises
    ------
    ValueError
        If ``member_slenderness_Lc_over_r <= 0``.
    """
    if member_slenderness_Lc_over_r <= 0.0:
        raise ValueError(
            f"member_slenderness_Lc_over_r must be positive, got {member_slenderness_Lc_over_r!r}"
        )
    return (math.pi**2 * elastic_modulus_E) / (member_slenderness_Lc_over_r**2)


@dataclass(frozen=True, slots=True)
class CriticalStressE3:
    """Result of the §E3 (or §E4) critical-stress decision.

    Attributes
    ----------
    elastic_buckling_stress_Fe : float
        ``Fe`` (MPa) - the elastic buckling stress that fed the decision
        (flexural Eq. E3-4, or torsional/FT from §E4).
    critical_stress_Fcr : float
        ``Fcr`` (MPa) per Eq. E3-2 or E3-3.
    regime : {"inelastic", "elastic"}
        Which branch produced ``Fcr``.
    """

    elastic_buckling_stress_Fe: float
    critical_stress_Fcr: float
    regime: BucklingRegime


def compute_critical_stress_from_Fe(
    yield_stress_Fy: float,
    elastic_buckling_stress_Fe: float,
) -> CriticalStressE3:
    """Return ``Fcr`` per AISC 360-22 Eq. E3-2 / E3-3.

    This is the shared "given Fe, get Fcr" kernel used by §E3 (flexural
    buckling) and §E4 (torsional / flexural-torsional buckling) - AISC
    routes the §E4 ``Fe`` through the identical Eq. E3-2 / E3-3 form.

    * ``Fy/Fe <= 2.25``  -> ``Fcr = 0.658^(Fy/Fe) * Fy``   (Eq. E3-2)
    * ``Fy/Fe >  2.25``  -> ``Fcr = 0.877 * Fe``           (Eq. E3-3)

    Parameters
    ----------
    yield_stress_Fy : float
        Specified minimum yield stress ``Fy`` (MPa).
    elastic_buckling_stress_Fe : float
        ``Fe`` (MPa).  Must be > 0.

    Returns
    -------
    CriticalStressE3

    Raises
    ------
    ValueError
        If ``elastic_buckling_stress_Fe <= 0``.
    """
    if elastic_buckling_stress_Fe <= 0.0:
        raise ValueError(
            f"elastic_buckling_stress_Fe must be positive, got {elastic_buckling_stress_Fe!r}"
        )
    fy_over_fe: float = yield_stress_Fy / elastic_buckling_stress_Fe
    if fy_over_fe <= 2.25:
        fcr: float = (E3_INELASTIC_BASE_0p658**fy_over_fe) * yield_stress_Fy
        regime: BucklingRegime = "inelastic"
    else:
        fcr = E3_ELASTIC_FACTOR_0p877 * elastic_buckling_stress_Fe
        regime = "elastic"
    return CriticalStressE3(
        elastic_buckling_stress_Fe=elastic_buckling_stress_Fe,
        critical_stress_Fcr=fcr,
        regime=regime,
    )


def compute_flexural_buckling_critical_stress_E3(
    yield_stress_Fy: float,
    elastic_modulus_E: float,
    member_slenderness_Lc_over_r: float,
) -> CriticalStressE3:
    """Return the §E3 flexural-buckling ``Fcr`` for one axis.

    Composes Eq. E3-4 (``Fe``) then Eq. E3-2 / E3-3 (``Fcr``).

    Parameters
    ----------
    yield_stress_Fy : float
        ``Fy`` (MPa).
    elastic_modulus_E : float
        ``E`` (MPa).
    member_slenderness_Lc_over_r : float
        ``Lc / r`` for this axis (dimensionless).

    Returns
    -------
    CriticalStressE3
    """
    fe: float = compute_elastic_buckling_stress_Fe(
        elastic_modulus_E=elastic_modulus_E,
        member_slenderness_Lc_over_r=member_slenderness_Lc_over_r,
    )
    return compute_critical_stress_from_Fe(
        yield_stress_Fy=yield_stress_Fy,
        elastic_buckling_stress_Fe=fe,
    )


def compute_nominal_compressive_strength_Pn(
    critical_stress_Fcr: float,
    effective_area_Ae: float,
) -> float:
    """Return ``Pn = Fcr * Ae`` per AISC 360-22 Eq. E3-1 / Eq. E7-1.

    For non-slender members ``Ae == Ag`` (Eq. E3-1).  For members with
    slender elements the caller passes the §E7 effective area
    (Eq. E7-1).

    Parameters
    ----------
    critical_stress_Fcr : float
        Governing ``Fcr`` (MPa).
    effective_area_Ae : float
        ``Ae`` (mm^2) - equals ``Ag`` when no element is slender.

    Returns
    -------
    float
        Nominal compressive strength ``Pn`` (N).
    """
    return critical_stress_Fcr * effective_area_Ae


__all__ = [
    "CriticalStressE3",
    "compute_critical_stress_from_Fe",
    "compute_elastic_buckling_stress_Fe",
    "compute_flexural_buckling_critical_stress_E3",
    "compute_nominal_compressive_strength_Pn",
]
