"""AISC 360-22 §D2(a) - tensile yielding on the gross section.

The single Chapter-D limit state apeSteel currently implements - the
upstream ``phi_t*Pn`` that §H1.2 (flexure + axial tension) consumes.

* Eq. D2-1  ``Pn = Fy*Ag``
* ``phi_t = 0.90``  (``Omega_t = 1.67``)

Scope: **gross-section yielding only**.  Net-section rupture
(Eq. D2-2, ``Pn = Fu*Ae`` with the shear-lag factor ``U``) and §J4
block shear are out of scope and the caller verifies them separately;
see ``docs/design_notes/09_combined_H.md`` §1/§4.  The equation is a
single multiplication, so the reviewer-signable hand calc in
``tests/unit/test_tension_yielding_D2.py`` is itself the independent
check (there is no composition to re-derive).

References
----------
.. [1] AISC 360-22 §D2(a) "Tensile Yielding in the Gross Section",
       Eq. D2-1, p. 16.1-31.
"""

from __future__ import annotations

from dataclasses import dataclass

from apeSteel.core.result_types import Report
from apeSteel.tension._common import (
    CITATIONS_AISC_360_D2_YIELDING,
    OMEGA_TENSION_YIELDING_ASD,
    PHI_TENSION_YIELDING_LRFD,
)


@dataclass(frozen=True, slots=True)
class TensionYieldingD2Report(Report):
    """AISC 360-22 §D2(a) gross-section tensile-yielding strength.

    Attributes
    ----------
    yield_stress_Fy : float
        Specified minimum yield stress ``Fy`` (MPa).
    gross_area_Ag : float
        Gross cross-sectional area ``Ag`` (mm^2).
    nominal_tensile_strength_Pn : float
        ``Pn = Fy*Ag`` (N) - also mirrored into
        :attr:`Report.nominal_strength`.
    """

    yield_stress_Fy: float = 0.0
    gross_area_Ag: float = 0.0
    nominal_tensile_strength_Pn: float = 0.0


def compute_tension_yielding_strength_D2(
    yield_stress_Fy: float,
    gross_area_Ag: float,
) -> TensionYieldingD2Report:
    """Return the AISC 360-22 §D2(a) gross-section yielding report.

    Parameters
    ----------
    yield_stress_Fy : float
        ``Fy`` (MPa).  Must be > 0.
    gross_area_Ag : float
        ``Ag`` (mm^2).  Must be > 0.

    Returns
    -------
    TensionYieldingD2Report

    Raises
    ------
    ValueError
        If ``Fy <= 0`` or ``Ag <= 0``.
    """
    if yield_stress_Fy <= 0.0:
        raise ValueError(f"yield_stress_Fy must be positive, got {yield_stress_Fy!r}")
    if gross_area_Ag <= 0.0:
        raise ValueError(f"gross_area_Ag must be positive, got {gross_area_Ag!r}")

    pn: float = yield_stress_Fy * gross_area_Ag  # Eq. D2-1
    phi_pn: float = PHI_TENSION_YIELDING_LRFD * pn
    pn_over_omega: float = pn / OMEGA_TENSION_YIELDING_ASD

    return TensionYieldingD2Report(
        cited_clauses=CITATIONS_AISC_360_D2_YIELDING,
        governing_limit_state="tension_yielding_D2",
        phi_LRFD=PHI_TENSION_YIELDING_LRFD,
        omega_ASD=OMEGA_TENSION_YIELDING_ASD,
        nominal_strength=pn,
        phi_strength_LRFD=phi_pn,
        omega_strength_ASD=pn_over_omega,
        yield_stress_Fy=yield_stress_Fy,
        gross_area_Ag=gross_area_Ag,
        nominal_tensile_strength_Pn=pn,
    )


__all__ = [
    "TensionYieldingD2Report",
    "compute_tension_yielding_strength_D2",
]
