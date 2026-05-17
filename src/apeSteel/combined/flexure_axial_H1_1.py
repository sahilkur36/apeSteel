"""AISC 360-22 §H1.1 - doubly/singly-symmetric flexure + compression.

H-0 scaffold stub.  The real Eq. H1-1a / H1-1b calculator and
``CombinedH1Report`` land in phase H-1; see
``docs/design_notes/09_combined_H.md`` §3.

Eq. H1-1a (Pr/Pc >= 0.2):  Pr/Pc + 8/9*(Mrx/Mcx + Mry/Mcy) <= 1.0
Eq. H1-1b (Pr/Pc <  0.2):  Pr/(2*Pc) + (Mrx/Mcx + Mry/Mcy) <= 1.0
"""

from __future__ import annotations

from typing import NoReturn

_DESIGN_NOTE = "docs/design_notes/09_combined_H.md"


def compute_combined_strength_H1_1(
    required_axial_Pr: float,
    available_axial_Pc: float,
    required_moment_x_Mrx: float,
    available_moment_x_Mcx: float,
    required_moment_y_Mry: float = 0.0,
    available_moment_y_Mcy: float = 0.0,
) -> NoReturn:
    """Not yet implemented - lands in phase H-1."""
    raise NotImplementedError(
        f"AISC 360-22 §H1.1 (Eq. H1-1a/H1-1b) is scheduled for phase H-1; see {_DESIGN_NOTE}."
    )


__all__ = ["compute_combined_strength_H1_1"]
