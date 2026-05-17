"""AISC 360-22 §H1.2 - doubly/singly-symmetric flexure + axial tension.

H-0 scaffold stub.  The real calculator (Eq. H1-1a/H1-1b with
``Pc = phi_t*Pn`` and the ``Cb`` amplifier ``sqrt(1 + alpha*Pr/Pey)``)
lands in phase H-2; see ``docs/design_notes/09_combined_H.md`` §4.

It consumes the thin Chapter-D yielding strength
:mod:`apeSteel.tension.yielding_D2` (D2-1).  Net-section rupture
(D2-2) requires shear-lag / connection data and is **out of scope** -
the caller verifies rupture separately (documented in the design note).
"""

from __future__ import annotations

from typing import NoReturn

_DESIGN_NOTE = "docs/design_notes/09_combined_H.md"


def compute_combined_strength_H1_2(
    required_tension_Pr: float,
    available_tension_Pc: float,
    required_moment_x_Mrx: float,
    available_moment_x_Mcx: float,
    required_moment_y_Mry: float = 0.0,
    available_moment_y_Mcy: float = 0.0,
) -> NoReturn:
    """Not yet implemented - lands in phase H-2."""
    raise NotImplementedError(
        f"AISC 360-22 §H1.2 (flexure + tension) is scheduled for phase H-2; see {_DESIGN_NOTE}."
    )


def compute_Cb_amplification_factor_H1_2(
    required_tension_Pr: float,
    elastic_modulus_E: float,
    moment_of_inertia_y_Iy: float,
    unbraced_length_Lb: float,
    alpha: float = 1.0,
) -> NoReturn:
    """Not yet implemented - lands in phase H-2."""
    raise NotImplementedError(
        f"AISC 360-22 §H1.2 Cb amplification is scheduled for phase H-2; see {_DESIGN_NOTE}."
    )


__all__ = [
    "compute_Cb_amplification_factor_H1_2",
    "compute_combined_strength_H1_2",
]
