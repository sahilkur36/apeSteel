"""AISC 360-22 §H2 - unsymmetric / other members, flexure + axial.

For members not covered by §H1 (unsymmetric sections, or members where
the §H1 form is inappropriate), the limit state is an *elastic stress*
interaction evaluated at the point of maximum combined stress:

    | fra/Fca + frbw/Fcbw + frbz/Fcbz | <= 1.0          (Eq. H2-1)

* ``fra``  - required axial stress at the point (signed).
* ``frbw``, ``frbz`` - required flexural stresses at the point about
  the principal ``w`` / ``z`` axes (signed).
* ``Fca``  - available axial stress (``phi_c*Fcr`` comp. or
  ``phi_t*Fy`` tension), positive.
* ``Fcbw``, ``Fcbz`` - available flexural stresses (``phi_b*Mn/S`` at
  the point), positive.

The required stresses carry their own sign so the worst-case
combination is captured; the absolute value of the signed sum is the
DCR.  The calculator is *point-wise* - the caller supplies the
stresses at the governing point (no automatic extreme-fibre search;
design note 09 §8).

References
----------
.. [1] AISC 360-22 §H2 "Unsymmetric and Other Members Subject to
       Flexure and Axial Force", Eq. H2-1, p. 16.1-85.
"""

from __future__ import annotations

from dataclasses import dataclass

from apeSteel.combined._common import CITATIONS_AISC_360_CHAPTER_H
from apeSteel.core.result_types import AISCClauseReference, Report

_CITATIONS_H2: tuple[AISCClauseReference, ...] = (
    *CITATIONS_AISC_360_CHAPTER_H,
    AISCClauseReference("AISC 360-22", "H2", "H2-1", "16.1-85"),
)


@dataclass(frozen=True, slots=True)
class CombinedH2Report(Report):
    """AISC 360-22 §H2 elastic-stress interaction result (Eq. H2-1).

    Attributes
    ----------
    required_axial_stress_fra : float
        ``fra`` (MPa, signed).
    available_axial_stress_Fca : float
        ``Fca`` (MPa, > 0).
    required_flexural_stress_w_frbw, required_flexural_stress_z_frbz : float
        ``frbw`` / ``frbz`` (MPa, signed).
    available_flexural_stress_w_Fcbw, available_flexural_stress_z_Fcbz : float
        ``Fcbw`` / ``Fcbz`` (MPa, > 0).
    axial_stress_ratio, flexural_stress_ratio_w, flexural_stress_ratio_z : float
        The three signed term ratios.
    signed_interaction_sum : float
        ``fra/Fca + frbw/Fcbw + frbz/Fcbz`` (signed, before abs).
    demand_capacity_ratio : float
        ``|signed_interaction_sum|`` (the Eq. H2-1 left-hand side).
    unity_check_passes : bool
        ``demand_capacity_ratio <= 1.0``.
    """

    required_axial_stress_fra: float = 0.0
    available_axial_stress_Fca: float = 0.0
    required_flexural_stress_w_frbw: float = 0.0
    available_flexural_stress_w_Fcbw: float = 0.0
    required_flexural_stress_z_frbz: float = 0.0
    available_flexural_stress_z_Fcbz: float = 0.0
    axial_stress_ratio: float = 0.0
    flexural_stress_ratio_w: float = 0.0
    flexural_stress_ratio_z: float = 0.0
    signed_interaction_sum: float = 0.0
    demand_capacity_ratio: float = 0.0
    unity_check_passes: bool = True


def compute_combined_strength_H2(
    required_axial_stress_fra: float,
    available_axial_stress_Fca: float,
    required_flexural_stress_w_frbw: float,
    available_flexural_stress_w_Fcbw: float,
    required_flexural_stress_z_frbz: float,
    available_flexural_stress_z_Fcbz: float,
) -> CombinedH2Report:
    """Return the AISC 360-22 §H2 (Eq. H2-1) elastic-stress report.

    Parameters
    ----------
    required_axial_stress_fra : float
        ``fra`` (MPa) at the point of consideration - signed.
    available_axial_stress_Fca : float
        ``Fca`` (MPa) - available axial stress.  Must be > 0.
    required_flexural_stress_w_frbw, required_flexural_stress_z_frbz : float
        ``frbw`` / ``frbz`` (MPa) at the point - signed.
    available_flexural_stress_w_Fcbw, available_flexural_stress_z_Fcbz : float
        ``Fcbw`` / ``Fcbz`` (MPa) - available flexural stresses.
        Must be > 0.

    Returns
    -------
    CombinedH2Report

    Raises
    ------
    ValueError
        If any available stress (``Fca``/``Fcbw``/``Fcbz``) <= 0.
    """
    for name, val in (
        ("available_axial_stress_Fca", available_axial_stress_Fca),
        ("available_flexural_stress_w_Fcbw", available_flexural_stress_w_Fcbw),
        ("available_flexural_stress_z_Fcbz", available_flexural_stress_z_Fcbz),
    ):
        if val <= 0.0:
            raise ValueError(f"{name} (available stress) must be positive, got {val!r}")

    axial_ratio: float = required_axial_stress_fra / available_axial_stress_Fca
    flex_ratio_w: float = required_flexural_stress_w_frbw / available_flexural_stress_w_Fcbw
    flex_ratio_z: float = required_flexural_stress_z_frbz / available_flexural_stress_z_Fcbz
    signed_sum: float = axial_ratio + flex_ratio_w + flex_ratio_z  # Eq. H2-1
    dcr: float = abs(signed_sum)

    return CombinedH2Report(
        cited_clauses=_CITATIONS_H2,
        governing_limit_state="H2-1",
        phi_LRFD=1.0,
        omega_ASD=1.0,
        nominal_strength=0.0,
        phi_strength_LRFD=0.0,
        omega_strength_ASD=0.0,
        required_axial_stress_fra=required_axial_stress_fra,
        available_axial_stress_Fca=available_axial_stress_Fca,
        required_flexural_stress_w_frbw=required_flexural_stress_w_frbw,
        available_flexural_stress_w_Fcbw=available_flexural_stress_w_Fcbw,
        required_flexural_stress_z_frbz=required_flexural_stress_z_frbz,
        available_flexural_stress_z_Fcbz=available_flexural_stress_z_Fcbz,
        axial_stress_ratio=axial_ratio,
        flexural_stress_ratio_w=flex_ratio_w,
        flexural_stress_ratio_z=flex_ratio_z,
        signed_interaction_sum=signed_sum,
        demand_capacity_ratio=dcr,
        unity_check_passes=dcr <= 1.0,
    )


__all__ = [
    "CombinedH2Report",
    "compute_combined_strength_H2",
]
