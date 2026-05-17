"""AISC 360-22 §H1.3 - DS rolled compact, single-axis flexure + compression.

For a **doubly-symmetric, rolled, compact** member subject to
single-axis (major-axis) flexure and compression with ``KLz <= KLy``,
§H1.3 permits - as an alternative to §H1.1 - addressing the in-plane
and out-of-plane limit states *separately*:

* (a) **in-plane instability**: Eq. H1-1 (H1-1a/H1-1b) evaluated with
  ``Pc`` and ``Mcx`` both determined *in the plane of bending*
  (``Pcx`` from the in-plane effective length; ``Mcx`` with no LTB
  reduction - it may reach ``phi_b*Mp``).
* (b) **out-of-plane buckling + LTB** (Eq. H1-2):

      Pr/Pcy*(1.5 - 0.5*Pr/Pcy) + (Mrx/(Cb*Mcx))^2 <= 1.0

  ``Pcy`` = available compressive strength out of plane; ``Cb`` = the
  Chapter-F LTB modification factor; ``Mcx`` = available LTB strength
  for strong-axis flexure determined with ``Cb = 1.0``.  Per the spec
  note the product ``Cb*Mcx`` need not exceed ``phi_b*Mp`` - applied
  here as ``min(Cb*Mcx, phi_b*Mp)``.

The member is adequate only if **both** checks pass; the governing
(controlling) check is the one with the larger demand/capacity ratio.

Applicability (DS / rolled / compact / single-axis / ``KLz<=KLy``) is
an engineering precondition the *caller* establishes; the pure
calculator here is numeric.  :func:`ensure_h1_3_applicable` is provided
for the H-7 ``Element`` facade (and tested) to enforce it.

References
----------
.. [1] AISC 360-22 §H1.3 "Doubly Symmetric Rolled Compact Members
       Subject to Single-Axis Flexure and Compression", Eq. H1-1 /
       Eq. H1-2, p. 16.1-84.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from apeSteel.combined._common import (
    CITATIONS_AISC_360_CHAPTER_H,
    H1_2_OUT_OF_PLANE_LEAD,
    H1_2_OUT_OF_PLANE_QUAD,
    CombinedLimitState,
)
from apeSteel.combined.flexure_axial_H1_1 import (
    CombinedH1Report,
    compute_combined_strength_H1_1,
)
from apeSteel.core.result_types import AISCClauseReference, Report

H13GoverningCheck = Literal["in_plane", "out_of_plane"]

_CITATIONS_H1_3: tuple[AISCClauseReference, ...] = (
    *CITATIONS_AISC_360_CHAPTER_H,
    AISCClauseReference("AISC 360-22", "H1.3", "H1-1a", "16.1-84"),
    AISCClauseReference("AISC 360-22", "H1.3", "H1-1b", "16.1-84"),
    AISCClauseReference("AISC 360-22", "H1.3", "H1-2", "16.1-84"),
)


@dataclass(frozen=True, slots=True)
class CombinedH13Report(Report):
    """AISC 360-22 §H1.3 two-check single-axis interaction result.

    Attributes
    ----------
    in_plane : CombinedH1Report
        The §H1.3(a) in-plane Eq. H1-1 sub-report (uniaxial, in-plane
        ``Pcx``/``Mcx``).
    out_of_plane_demand_capacity_ratio : float
        Left-hand side of Eq. H1-2.
    axial_ratio_out_of_plane_Pr_Pcy : float
        ``Pr / Pcy``.
    out_of_plane_capped_Cb_Mcx : float
        ``min(Cb*Mcx, phi_b*Mp)`` - the effective Eq. H1-2 denominator.
    governing_check : {"in_plane", "out_of_plane"}
        Which limit state controls (larger DCR).
    governing_equation : {"H1-1a", "H1-1b", "H1-2"}
        Equation of the controlling check.  Mirrored into
        :attr:`Report.governing_limit_state`.
    demand_capacity_ratio : float
        ``max(in_plane DCR, out-of-plane DCR)``.
    unity_check_passes : bool
        True iff *both* checks are <= 1.0.
    """

    in_plane: CombinedH1Report = field(default_factory=CombinedH1Report)
    out_of_plane_demand_capacity_ratio: float = 0.0
    axial_ratio_out_of_plane_Pr_Pcy: float = 0.0
    out_of_plane_capped_Cb_Mcx: float = 0.0
    governing_check: H13GoverningCheck = "in_plane"
    governing_equation: CombinedLimitState = "H1-1a"
    demand_capacity_ratio: float = 0.0
    unity_check_passes: bool = True


def ensure_h1_3_applicable(
    *,
    is_doubly_symmetric: bool,
    is_rolled: bool,
    is_compact_for_flexure: bool,
    effective_length_torsional_KLz: float,
    effective_length_minor_KLy: float,
) -> None:
    """Raise ``ValueError`` if §H1.3 is not permitted for the member.

    §H1.3 applies only to doubly-symmetric, rolled, compact members in
    single-axis bending with ``KLz <= KLy``.  The H-7 ``Element``
    facade calls this before offering the §H1.3 alternative.
    """
    if not is_doubly_symmetric:
        raise ValueError("§H1.3 requires a doubly-symmetric section")
    if not is_rolled:
        raise ValueError("§H1.3 requires a rolled (not built-up) section")
    if not is_compact_for_flexure:
        raise ValueError("§H1.3 requires a flexurally compact section")
    if effective_length_torsional_KLz > effective_length_minor_KLy:
        raise ValueError(
            "§H1.3 requires KLz <= KLy "
            f"(got KLz={effective_length_torsional_KLz!r}, KLy={effective_length_minor_KLy!r})"
        )


def compute_combined_strength_H1_3(
    required_axial_Pr: float,
    available_axial_in_plane_Pcx: float,
    available_axial_out_of_plane_Pcy: float,
    required_moment_x_Mrx: float,
    available_moment_x_in_plane_Mcx: float,
    available_moment_x_ltb_Cb1_Mcx: float,
    lateral_torsional_modification_Cb: float,
    available_plastic_moment_phi_b_Mp: float,
) -> CombinedH13Report:
    """Return the AISC 360-22 §H1.3 two-check single-axis report.

    Parameters
    ----------
    required_axial_Pr : float
        Required second-order axial compressive strength ``Pr`` (N).
    available_axial_in_plane_Pcx : float
        ``Pcx`` (N) - available axial strength using the in-plane
        (axis-of-bending) effective length.  Must be > 0.
    available_axial_out_of_plane_Pcy : float
        ``Pcy`` (N) - available axial strength out of the plane of
        bending.  Must be > 0.
    required_moment_x_Mrx : float
        Required second-order major-axis flexural strength (N*mm).
    available_moment_x_in_plane_Mcx : float
        ``Mcx`` (N*mm) for the in-plane check - no LTB reduction
        (typically ``phi_b*Mp``).  Must be > 0 if ``Mrx`` is non-zero.
    available_moment_x_ltb_Cb1_Mcx : float
        ``Mcx`` (N*mm) - available LTB strength from Chapter F using
        ``Cb = 1.0`` (the Eq. H1-2 base).  Must be > 0.
    lateral_torsional_modification_Cb : float
        Chapter-F ``Cb``.
    available_plastic_moment_phi_b_Mp : float
        ``phi_b*Mp`` (N*mm) - the cap on ``Cb*Mcx`` in Eq. H1-2.

    Returns
    -------
    CombinedH13Report

    Raises
    ------
    ValueError
        If ``Pcx <= 0``, ``Pcy <= 0``, or the capped ``Cb*Mcx <= 0``.
    """
    if available_axial_in_plane_Pcx <= 0.0:
        raise ValueError(
            f"available_axial_in_plane_Pcx must be positive, got {available_axial_in_plane_Pcx!r}"
        )
    if available_axial_out_of_plane_Pcy <= 0.0:
        raise ValueError(
            f"available_axial_out_of_plane_Pcy must be positive, "
            f"got {available_axial_out_of_plane_Pcy!r}"
        )

    # (a) in-plane instability - Eq. H1-1 with in-plane Pcx, Mcx, Mry=0.
    in_plane: CombinedH1Report = compute_combined_strength_H1_1(
        required_axial_Pr=required_axial_Pr,
        available_axial_Pc=available_axial_in_plane_Pcx,
        required_moment_x_Mrx=required_moment_x_Mrx,
        available_moment_x_Mcx=available_moment_x_in_plane_Mcx,
        required_moment_y_Mry=0.0,
        available_moment_y_Mcy=0.0,
        citations=_CITATIONS_H1_3,
    )

    # (b) out-of-plane buckling + LTB - Eq. H1-2.
    cb_mcx: float = min(
        lateral_torsional_modification_Cb * available_moment_x_ltb_Cb1_Mcx,
        available_plastic_moment_phi_b_Mp,
    )
    if cb_mcx <= 0.0:
        raise ValueError("Eq. H1-2 denominator min(Cb*Mcx, phi_b*Mp) must be positive")
    rp: float = required_axial_Pr / available_axial_out_of_plane_Pcy
    oop_dcr: float = (
        rp * (H1_2_OUT_OF_PLANE_LEAD - H1_2_OUT_OF_PLANE_QUAD * rp)
        + (required_moment_x_Mrx / cb_mcx) ** 2
    )

    in_plane_dcr: float = in_plane.demand_capacity_ratio
    if oop_dcr >= in_plane_dcr:
        governing_check: H13GoverningCheck = "out_of_plane"
        governing_equation: CombinedLimitState = "H1-2"
        overall_dcr: float = oop_dcr
    else:
        governing_check = "in_plane"
        governing_equation = in_plane.governing_equation
        overall_dcr = in_plane_dcr

    return CombinedH13Report(
        cited_clauses=_CITATIONS_H1_3,
        governing_limit_state=governing_equation,
        phi_LRFD=1.0,
        omega_ASD=1.0,
        nominal_strength=0.0,
        phi_strength_LRFD=0.0,
        omega_strength_ASD=0.0,
        in_plane=in_plane,
        out_of_plane_demand_capacity_ratio=oop_dcr,
        axial_ratio_out_of_plane_Pr_Pcy=rp,
        out_of_plane_capped_Cb_Mcx=cb_mcx,
        governing_check=governing_check,
        governing_equation=governing_equation,
        demand_capacity_ratio=overall_dcr,
        unity_check_passes=(in_plane_dcr <= 1.0) and (oop_dcr <= 1.0),
    )


__all__ = [
    "CombinedH13Report",
    "H13GoverningCheck",
    "compute_combined_strength_H1_3",
    "ensure_h1_3_applicable",
]
