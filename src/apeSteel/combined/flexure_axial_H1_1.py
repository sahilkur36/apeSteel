"""AISC 360-22 §H1.1 - doubly/singly-symmetric flexure + compression.

Pure single-equation calculator (Eq. H1-1a / H1-1b), mirroring the
Chapter-E / Chapter-F calculators: it returns a frozen
:class:`CombinedH1Report`.

Chapter H is an *interaction* chapter - the resistance factors already
live inside the supplied ``Pc = phi_c*Pn`` (Chapter E) and
``Mc = phi_b*Mn`` (Chapter F).  The unity equation itself carries no
further ``phi`` (the report's ``phi_LRFD`` is 1.0).  ``Pr``/``Mr`` are
the required *second-order* strengths (Direct Analysis Method - the
caller supplies already-amplified moments; no Appendix-8 B1/B2 here).

* Eq. H1-1a  (Pr/Pc >= 0.2):  Pr/Pc + 8/9*(Mrx/Mcx + Mry/Mcy) <= 1.0
* Eq. H1-1b  (Pr/Pc <  0.2):  Pr/(2*Pc) +   (Mrx/Mcx + Mry/Mcy) <= 1.0

References
----------
.. [1] AISC 360-22 §H1.1 "Doubly and Singly Symmetric Members Subject
       to Flexure and Compression", Eq. H1-1a / H1-1b, p. 16.1-83.
"""

from __future__ import annotations

from dataclasses import dataclass

from apeSteel.combined._common import (
    CITATIONS_AISC_360_CHAPTER_H,
    H1_1A_MOMENT_FACTOR,
    H1_1B_AXIAL_DIVISOR,
    H1_AXIAL_RATIO_BREAK,
    CombinedLimitState,
)
from apeSteel.core.result_types import AISCClauseReference, Report


@dataclass(frozen=True, slots=True)
class CombinedH1Report(Report):
    """AISC 360-22 §H1.1 / §H1.2 combined flexure + axial interaction.

    This is an *interaction* report: the headline number is
    :attr:`demand_capacity_ratio` (the left-hand side of Eq. H1-1a /
    H1-1b).  Because the AISC resistance factors are already embedded in
    the supplied ``Pc``/``Mc``, the inherited :attr:`Report.phi_LRFD` is
    ``1.0`` and the nominal/factored-strength fields are not used.

    Attributes
    ----------
    governing_equation : {"H1-1a", "H1-1b"}
        Which interaction equation governed (set by the ``Pr/Pc >= 0.2``
        branch).  Mirrored into :attr:`Report.governing_limit_state`.
    required_axial_Pr : float
        Required second-order axial strength ``Pr`` (N).  Compression
        for §H1.1; tensile for §H1.2.
    available_axial_Pc : float
        Available axial strength ``Pc`` (N) - ``phi_c*Pn`` (§H1.1) or
        ``phi_t*Pn`` (§H1.2).
    axial_ratio_Pr_Pc : float
        ``Pr / Pc``.
    required_moment_x_Mrx, required_moment_y_Mry : float
        Required second-order flexural strengths about x and y (N*mm).
    available_moment_x_Mcx, available_moment_y_Mcy : float
        Available flexural strengths ``phi_b*Mn`` about x and y (N*mm).
    moment_ratio_term : float
        ``Mrx/Mcx + Mry/Mcy`` (the bracketed biaxial moment term).
    demand_capacity_ratio : float
        Left-hand side of the governing equation (the DCR / unity value).
    unity_check_passes : bool
        ``demand_capacity_ratio <= 1.0``.
    """

    governing_equation: CombinedLimitState = "H1-1a"
    required_axial_Pr: float = 0.0
    available_axial_Pc: float = 0.0
    axial_ratio_Pr_Pc: float = 0.0
    required_moment_x_Mrx: float = 0.0
    available_moment_x_Mcx: float = 0.0
    required_moment_y_Mry: float = 0.0
    available_moment_y_Mcy: float = 0.0
    moment_ratio_term: float = 0.0
    demand_capacity_ratio: float = 0.0
    unity_check_passes: bool = True


_CITATIONS_H1_1: tuple[AISCClauseReference, ...] = (
    *CITATIONS_AISC_360_CHAPTER_H,
    AISCClauseReference("AISC 360-22", "H1.1", "H1-1a", "16.1-83"),
    AISCClauseReference("AISC 360-22", "H1.1", "H1-1b", "16.1-83"),
)


def compute_combined_strength_H1_1(
    required_axial_Pr: float,
    available_axial_Pc: float,
    required_moment_x_Mrx: float,
    available_moment_x_Mcx: float,
    required_moment_y_Mry: float = 0.0,
    available_moment_y_Mcy: float = 0.0,
    *,
    citations: tuple[AISCClauseReference, ...] = _CITATIONS_H1_1,
) -> CombinedH1Report:
    """Return the AISC 360-22 §H1.1 combined-strength interaction report.

    Parameters
    ----------
    required_axial_Pr : float
        Required second-order axial *compressive* strength ``Pr`` (N).
    available_axial_Pc : float
        Available axial strength ``Pc = phi_c*Pn`` (N).  Must be > 0.
    required_moment_x_Mrx, required_moment_y_Mry : float
        Required second-order flexural strengths about x / y (N*mm).
    available_moment_x_Mcx, available_moment_y_Mcy : float
        Available flexural strengths ``phi_b*Mn`` about x / y (N*mm).
        Must be > 0 whenever the corresponding ``Mr`` is non-zero.
    citations : tuple of AISCClauseReference, optional
        Override the cited clauses (used by §H1.2, which reuses this
        kernel with the tension ``Pc`` and its own citation block).

    Returns
    -------
    CombinedH1Report

    Raises
    ------
    ValueError
        If ``Pc <= 0``, or an ``Mc`` is non-positive while its ``Mr``
        is non-zero.
    """
    if available_axial_Pc <= 0.0:
        raise ValueError(f"available_axial_Pc must be positive, got {available_axial_Pc!r}")
    if required_moment_x_Mrx != 0.0 and available_moment_x_Mcx <= 0.0:
        raise ValueError(
            "available_moment_x_Mcx must be positive when required_moment_x_Mrx is non-zero"
        )
    if required_moment_y_Mry != 0.0 and available_moment_y_Mcy <= 0.0:
        raise ValueError(
            "available_moment_y_Mcy must be positive when required_moment_y_Mry is non-zero"
        )

    ratio_p: float = required_axial_Pr / available_axial_Pc
    moment_ratio_term: float = (
        required_moment_x_Mrx / available_moment_x_Mcx if required_moment_x_Mrx != 0.0 else 0.0
    ) + (required_moment_y_Mry / available_moment_y_Mcy if required_moment_y_Mry != 0.0 else 0.0)

    if ratio_p >= H1_AXIAL_RATIO_BREAK:  # Eq. H1-1a
        dcr: float = ratio_p + H1_1A_MOMENT_FACTOR * moment_ratio_term
        governing: CombinedLimitState = "H1-1a"
    else:  # Eq. H1-1b
        dcr = ratio_p / H1_1B_AXIAL_DIVISOR + moment_ratio_term
        governing = "H1-1b"

    return CombinedH1Report(
        cited_clauses=citations,
        governing_limit_state=governing,
        phi_LRFD=1.0,
        omega_ASD=1.0,
        nominal_strength=0.0,
        phi_strength_LRFD=0.0,
        omega_strength_ASD=0.0,
        governing_equation=governing,
        required_axial_Pr=required_axial_Pr,
        available_axial_Pc=available_axial_Pc,
        axial_ratio_Pr_Pc=ratio_p,
        required_moment_x_Mrx=required_moment_x_Mrx,
        available_moment_x_Mcx=available_moment_x_Mcx,
        required_moment_y_Mry=required_moment_y_Mry,
        available_moment_y_Mcy=available_moment_y_Mcy,
        moment_ratio_term=moment_ratio_term,
        demand_capacity_ratio=dcr,
        unity_check_passes=dcr <= 1.0,
    )


__all__ = [
    "CombinedH1Report",
    "compute_combined_strength_H1_1",
]
