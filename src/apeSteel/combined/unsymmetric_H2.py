"""AISC 360-22 §H2 - unsymmetric / other members, flexure + axial.

H-0 scaffold stub.  The real Eq. H2-1 elastic-stress interaction
``|fra/Fca + frbw/Fcbw + frbz/Fcbz| <= 1.0`` (signed required stresses,
positive available stresses, worst point governs) lands in phase H-4;
see ``docs/design_notes/09_combined_H.md`` §6.
"""

from __future__ import annotations

from typing import NoReturn

_DESIGN_NOTE = "docs/design_notes/09_combined_H.md"


def compute_combined_strength_H2(
    required_axial_stress_fra: float,
    available_axial_stress_Fca: float,
    required_flexural_stress_w_frbw: float,
    available_flexural_stress_w_Fcbw: float,
    required_flexural_stress_z_frbz: float,
    available_flexural_stress_z_Fcbz: float,
) -> NoReturn:
    """Not yet implemented - lands in phase H-4."""
    raise NotImplementedError(
        f"AISC 360-22 §H2 (Eq. H2-1) is scheduled for phase H-4; see {_DESIGN_NOTE}."
    )


__all__ = ["compute_combined_strength_H2"]
