"""AISC 360-22 §E7 - members with slender elements (effective width).

360-22 replaced the 360-16 ``Q = Qs*Qa`` stress knock-down with an
**effective-width** method.  The critical stress ``Fcr`` is computed
from §E3 / §E4 on the *gross* section with the full ``Fy`` (no Q); the
*area* is then reduced:

    Pn = Fcr * Ae                                            (Eq. E7-1)

For each plate element with ``lambda = b/t``:

* Eq. E7-2  if ``lambda <= lambda_r * sqrt(Fy/Fcr)``  -> ``be = b``
* Eq. E7-3  else
  ``be = b * (1 - c1*sqrt(Fel/Fcr)) * sqrt(Fel/Fcr)``  (and ``be <= b``)
* Eq. E7-5  ``Fel = (c2 * lambda_r / lambda)^2 * Fy``

``c1, c2`` from Table E7.1 by element kind.  Then
``Ae = Ag - sum( (b - be) * t )`` over the slender elements.

Round HSS use §E7.2(c) (Eq. E7-6 / E7-7) on ``D/t`` directly - that
provision was *retained unchanged* from 360-16, so it coincides with
the source spreadsheet's ``Qa_3``.

References
----------
.. [1] AISC 360-22 §E7 "Members with Slender Elements", Eq. E7-1 -
       E7-7 and Table E7.1, pp. 16.1-42 - 16.1-43.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from apeSteel.compression._common import (
    B4_1A_ROUND_HSS_DT_COEFF,
    E7_HSS_WALL_C1,
    E7_HSS_WALL_C2,
    E7_STIFFENED_C1,
    E7_STIFFENED_C2,
    E7_UNSTIFFENED_C1,
    E7_UNSTIFFENED_C2,
)

if TYPE_CHECKING:
    from apeSteel.sections.compression_properties import (
        CompressionPlateElement,
        CompressionSectionProperties,
    )

#: Round-HSS upper D/t limit for compression (§E7.2(c)): 0.45 * E/Fy.
#: Above this, a round HSS is not permitted as a compression member.
ROUND_HSS_MAX_DT_COEFF: float = 0.45
#: Round-HSS effective-area constant (Eq. E7-7): 0.038.
ROUND_HSS_EA_COEFF_0p038: float = 0.038
#: Round-HSS effective-area constant (Eq. E7-7): 2/3.
ROUND_HSS_EA_CONST_2_3: float = 2.0 / 3.0


def _table_E7_1_constants(kind: str) -> tuple[float, float]:
    """Return ``(c1, c2)`` from AISC 360-22 Table E7.1 by element kind."""
    if kind == "unstiffened":
        return E7_UNSTIFFENED_C1, E7_UNSTIFFENED_C2
    if kind == "hss_wall":
        return E7_HSS_WALL_C1, E7_HSS_WALL_C2
    # "stiffened" - any stiffened element except a square/rect HSS wall.
    return E7_STIFFENED_C1, E7_STIFFENED_C2


def compute_effective_width_be(
    element: CompressionPlateElement,
    yield_stress_Fy: float,
    critical_stress_Fcr: float,
) -> float:
    """Return the §E7 effective width ``be`` of one plate element (mm).

    Eq. E7-2 / E7-3 / E7-5.  ``be == element.width_b`` when the element
    is not slender or does not reach the Eq. E7-3 threshold; otherwise
    the reduced width, clamped to ``[0, b]``.

    Parameters
    ----------
    element : CompressionPlateElement
        Carries ``b``, ``t``, ``lambda = b/t`` and the Table B4.1a
        ``lambda_r``.
    yield_stress_Fy : float
        ``Fy`` (MPa).
    critical_stress_Fcr : float
        Governing ``Fcr`` (MPa) from §E3 / §E4 on the gross section.
    """
    b: float = element.width_b
    if not element.is_slender:
        return b

    lam: float = element.slenderness_ratio_lambda
    lam_r: float = element.nonslender_limit_lambda_r

    # Eq. E7-2: fully effective when slender but lightly loaded.
    if lam <= lam_r * math.sqrt(yield_stress_Fy / critical_stress_Fcr):
        return b

    c1, c2 = _table_E7_1_constants(element.kind)
    f_el: float = (c2 * lam_r / lam) ** 2 * yield_stress_Fy  # Eq. E7-5
    ratio: float = math.sqrt(f_el / critical_stress_Fcr)
    be: float = b * (1.0 - c1 * ratio) * ratio  # Eq. E7-3
    # be is physically bounded by [0, b].
    return max(0.0, min(be, b))


def compute_effective_area_Ae(
    section_properties: CompressionSectionProperties,
    yield_stress_Fy: float,
    elastic_modulus_E: float,
    critical_stress_Fcr: float,
) -> float:
    """Return the §E7 effective area ``Ae`` (mm^2).

    Round HSS use §E7.2(c) (Eq. E7-6 / E7-7) on ``D/t``.  All other
    sections use the plate-element effective-width summation:
    ``Ae = Ag - sum( (b - be) * t )`` over slender elements.

    Parameters
    ----------
    section_properties : CompressionSectionProperties
    yield_stress_Fy : float
        ``Fy`` (MPa).
    elastic_modulus_E : float
        ``E`` (MPa) - only used by the round-HSS path.
    critical_stress_Fcr : float
        Governing ``Fcr`` (MPa) on the gross section.

    Returns
    -------
    float
        ``Ae`` (mm^2).  Equals ``Ag`` when nothing is slender.

    Raises
    ------
    ValueError
        Round HSS with ``D/t > 0.45 E/Fy`` (not a permitted compression
        member per §E7.2(c)).
    """
    ag: float = section_properties.gross_area_Ag

    if section_properties.section_kind == "round_HSS":
        d_over_t: float = section_properties.diameter_D / section_properties.wall_thickness_t
        limit_nonslender: float = B4_1A_ROUND_HSS_DT_COEFF * elastic_modulus_E / yield_stress_Fy
        limit_max: float = ROUND_HSS_MAX_DT_COEFF * elastic_modulus_E / yield_stress_Fy
        if d_over_t <= limit_nonslender:
            return ag
        if d_over_t > limit_max:
            raise ValueError(
                f"round HSS D/t = {d_over_t:.3f} exceeds the §E7.2(c) limit "
                f"0.45 E/Fy = {limit_max:.3f}; not permitted in compression."
            )
        # Eq. E7-6 / E7-7: Ae = (0.038 E / (Fy (D/t)) + 2/3) * Ag.
        factor: float = (
            ROUND_HSS_EA_COEFF_0p038 * elastic_modulus_E / (yield_stress_Fy * d_over_t)
            + ROUND_HSS_EA_CONST_2_3
        )
        return factor * ag

    area_removed: float = 0.0
    for pe in section_properties.plate_elements:
        be: float = compute_effective_width_be(
            element=pe,
            yield_stress_Fy=yield_stress_Fy,
            critical_stress_Fcr=critical_stress_Fcr,
        )
        area_removed += (pe.width_b - be) * pe.thickness_t
    return ag - area_removed


@dataclass(frozen=True, slots=True)
class EffectiveAreaResult:
    """Outcome of the §E7 area reduction.

    Attributes
    ----------
    gross_area_Ag : float
    effective_area_Ae : float
    section_has_slender_element : bool
        True iff §E7 actually reduced the area (``Ae < Ag``).
    """

    gross_area_Ag: float
    effective_area_Ae: float
    section_has_slender_element: bool


def resolve_effective_area(
    section_properties: CompressionSectionProperties,
    yield_stress_Fy: float,
    elastic_modulus_E: float,
    critical_stress_Fcr: float,
) -> EffectiveAreaResult:
    """Convenience wrapper returning ``Ag``, ``Ae`` and a slender flag."""
    ag: float = section_properties.gross_area_Ag
    ae: float = compute_effective_area_Ae(
        section_properties=section_properties,
        yield_stress_Fy=yield_stress_Fy,
        elastic_modulus_E=elastic_modulus_E,
        critical_stress_Fcr=critical_stress_Fcr,
    )
    return EffectiveAreaResult(
        gross_area_Ag=ag,
        effective_area_Ae=ae,
        section_has_slender_element=ae < ag,
    )


__all__ = [
    "ROUND_HSS_EA_CONST_2_3",
    "ROUND_HSS_MAX_DT_COEFF",
    "EffectiveAreaResult",
    "ROUND_HSS_EA_COEFF_0p038",
    "compute_effective_area_Ae",
    "compute_effective_width_be",
    "resolve_effective_area",
]
