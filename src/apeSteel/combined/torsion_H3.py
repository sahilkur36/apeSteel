"""AISC 360-22 §H3 - torsion and combined torsion/flexure/shear/axial.

H-0 scaffold stub.  Lands in phase H-5; see
``docs/design_notes/09_combined_H.md`` §7.

* §H3.1 - round HSS ``Fcr`` (Eq. H3-2a/2b) and rectangular HSS ``Fcr``
  (Eq. H3-3..H3-5); ``Tn = Fcr*C`` (Eq. H3-1); ``phi_T = 0.90``.
* §H3.2 - HSS combined Eq. H3-6
  ``(Pr/Pc + Mr/Mc) + (Vr/Vc + Tr/Tc)^2 <= 1.0``; when
  ``Tr <= 0.2*Tc`` torsion is neglected (revert to §H1).
* §H3.3 - non-HSS limiting nominal stresses (Eq. H3-7/8/9).  The
  warping / St-Venant stress demands (Design Guide 9) are out of
  scope; only the code-level limiting stresses are produced.
"""

from __future__ import annotations

from typing import NoReturn

_DESIGN_NOTE = "docs/design_notes/09_combined_H.md"


def compute_torsional_strength_round_HSS_H3_1(
    yield_stress_Fy: float,
    elastic_modulus_E: float,
    outside_diameter_D: float,
    wall_thickness_t: float,
    member_length_L: float,
) -> NoReturn:
    """Not yet implemented - lands in phase H-5."""
    raise NotImplementedError(
        f"AISC 360-22 §H3.1 round-HSS torsion is scheduled for phase H-5; see {_DESIGN_NOTE}."
    )


def compute_torsional_strength_rect_HSS_H3_1(
    yield_stress_Fy: float,
    elastic_modulus_E: float,
    flat_width_to_thickness_h_over_t: float,
    torsional_constant_C: float,
) -> NoReturn:
    """Not yet implemented - lands in phase H-5."""
    raise NotImplementedError(
        f"AISC 360-22 §H3.1 rect-HSS torsion is scheduled for phase H-5; see {_DESIGN_NOTE}."
    )


def compute_combined_strength_H3_2(
    required_axial_Pr: float,
    available_axial_Pc: float,
    required_moment_Mr: float,
    available_moment_Mc: float,
    required_shear_Vr: float,
    available_shear_Vc: float,
    required_torsion_Tr: float,
    available_torsion_Tc: float,
) -> NoReturn:
    """Not yet implemented - lands in phase H-5."""
    raise NotImplementedError(
        f"AISC 360-22 §H3.2 (Eq. H3-6) is scheduled for phase H-5; see {_DESIGN_NOTE}."
    )


__all__ = [
    "compute_combined_strength_H3_2",
    "compute_torsional_strength_rect_HSS_H3_1",
    "compute_torsional_strength_round_HSS_H3_1",
]
