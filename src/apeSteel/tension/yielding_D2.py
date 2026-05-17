"""AISC 360-22 §D2(a) - tensile yielding on the gross section.

H-0 scaffold stub.  The thin Chapter-D yielding calculator
``Pn = Fy*Ag`` (Eq. D2-1), ``phi_t = 0.90`` / ``Omega_t = 1.67``, plus
``TensionYieldingD2Report``, lands in phase H-2; see
``docs/design_notes/09_combined_H.md`` §4.

Scope: **gross-section yielding only** (Eq. D2-1).  Net-section
rupture (Eq. D2-2, ``Pn = Fu*Ae``) needs the shear-lag factor ``U``
and connection geometry; it is intentionally out of scope and the
caller verifies rupture separately (documented in the design note).
This module exists so §H1.2 (flexure + tension) has an upstream
``phi_t*Pn`` to consume without depending on a future full Chapter D.
"""

from __future__ import annotations

from typing import NoReturn

_DESIGN_NOTE = "docs/design_notes/09_combined_H.md"


def compute_tension_yielding_strength_D2(
    yield_stress_Fy: float,
    gross_area_Ag: float,
) -> NoReturn:
    """Not yet implemented - lands in phase H-2."""
    raise NotImplementedError(
        f"AISC 360-22 §D2(a) gross-section yielding is scheduled for phase H-2; see {_DESIGN_NOTE}."
    )


__all__ = ["compute_tension_yielding_strength_D2"]
