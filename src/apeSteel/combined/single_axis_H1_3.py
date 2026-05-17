"""AISC 360-22 §H1.3 - DS rolled compact, single-axis flexure + compression.

H-0 scaffold stub.  The real two-check calculator (in-plane Eq. H1-1
plus out-of-plane Eq. H1-2 ``Pr/Pcy*(1.5 - 0.5*Pr/Pcy) +
(Mrx/(Cb*Mcx))^2 <= 1.0``) lands in phase H-3; see
``docs/design_notes/09_combined_H.md`` §5.

Applicability guard (enforced in H-3): doubly-symmetric, rolled,
compact, single-axis (major) bending, ``KLz <= KLy``.
"""

from __future__ import annotations

from typing import NoReturn

_DESIGN_NOTE = "docs/design_notes/09_combined_H.md"


def compute_combined_strength_H1_3(
    required_axial_Pr: float,
    available_axial_in_plane_Pc: float,
    available_axial_out_of_plane_Pcy: float,
    required_moment_x_Mrx: float,
    available_moment_x_in_plane_Mcx: float,
    available_moment_x_ltb_Cb1_Mcx: float,
    lateral_torsional_modification_Cb: float,
    available_plastic_moment_phi_b_Mp: float,
) -> NoReturn:
    """Not yet implemented - lands in phase H-3."""
    raise NotImplementedError(
        f"AISC 360-22 §H1.3 (single-axis flexure + compression) is scheduled "
        f"for phase H-3; see {_DESIGN_NOTE}."
    )


__all__ = ["compute_combined_strength_H1_3"]
