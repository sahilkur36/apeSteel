"""AISC 360-22 §H1.2 - doubly/singly-symmetric flexure + axial tension.

§H1.2 uses the **same** interaction equations as §H1.1 (Eq. H1-1a /
H1-1b), but with ``Pc`` = the available *tensile* strength
(``phi_t*Pn``; here the §D2(a) gross-section yield from
:mod:`apeSteel.tension.yielding_D2`).  In addition, for doubly-
symmetric members ``Cb`` in Chapter F may be multiplied by

    sqrt(1 + alpha*Pr/Pey)        Pey = pi^2*E*Iy / Lb^2
    alpha = 1.0 (LRFD), 1.6 (ASD)

to recognise the LTB benefit of concurrent axial tension (with the
usual ``Mn <= Mp`` cap).

Layering decision (design note 09 §2/§4): to keep §H1.2 a pure
consumer of a numeric ``Mc``, this module does **not** re-run
Chapter F.  It exposes :func:`compute_Pey_H1_2` and
:func:`compute_Cb_amplification_factor_H1_2`; the caller (or the
H-7 ``Element`` facade) re-evaluates Chapter F with
``Cb' = Cb*sqrt(1+alpha*Pr/Pey)`` (capping ``Mn <= Mp``) and passes the
resulting ``Mcx`` back into :func:`compute_combined_strength_H1_2`,
which shares the §H1.1 unity kernel.

References
----------
.. [1] AISC 360-22 §H1.2 "Doubly and Singly Symmetric Members Subject
       to Flexure and Tension", p. 16.1-84 (Eq. H1-1a/H1-1b reused).
"""

from __future__ import annotations

import math

from apeSteel.combined._common import (
    CITATIONS_AISC_360_CHAPTER_H,
    H1_2_ALPHA_LRFD,
)
from apeSteel.combined.flexure_axial_H1_1 import (
    CombinedH1Report,
    compute_combined_strength_H1_1,
)
from apeSteel.core.result_types import AISCClauseReference

_CITATIONS_H1_2: tuple[AISCClauseReference, ...] = (
    *CITATIONS_AISC_360_CHAPTER_H,
    AISCClauseReference("AISC 360-22", "H1.2", "H1-1a", "16.1-84"),
    AISCClauseReference("AISC 360-22", "H1.2", "H1-1b", "16.1-84"),
)


def compute_Pey_H1_2(
    elastic_modulus_E: float,
    moment_of_inertia_y_Iy: float,
    unbraced_length_Lb: float,
) -> float:
    """Return ``Pey = pi^2*E*Iy / Lb^2`` (AISC 360-22 §H1.2).

    Parameters
    ----------
    elastic_modulus_E : float
        ``E`` (MPa).
    moment_of_inertia_y_Iy : float
        Weak-axis moment of inertia ``Iy`` (mm^4).
    unbraced_length_Lb : float
        Laterally-unbraced length ``Lb`` (mm).  Must be > 0.

    Returns
    -------
    float
        ``Pey`` (N).

    Raises
    ------
    ValueError
        If ``unbraced_length_Lb <= 0``.
    """
    if unbraced_length_Lb <= 0.0:
        raise ValueError(f"unbraced_length_Lb must be positive, got {unbraced_length_Lb!r}")
    return math.pi**2 * elastic_modulus_E * moment_of_inertia_y_Iy / unbraced_length_Lb**2


def compute_Cb_amplification_factor_H1_2(
    required_tension_Pr: float,
    elastic_modulus_E: float,
    moment_of_inertia_y_Iy: float,
    unbraced_length_Lb: float,
    alpha: float = H1_2_ALPHA_LRFD,
) -> float:
    """Return the §H1.2 ``Cb`` amplifier ``sqrt(1 + alpha*Pr/Pey)``.

    For doubly-symmetric members with axial *tension* concurrent with
    bending, ``Cb`` from Chapter F may be multiplied by this factor
    (``alpha = 1.0`` LRFD, ``1.6`` ASD).  The caller applies it to the
    Chapter-F LTB calculation and still caps ``Mn <= Mp``.

    Parameters
    ----------
    required_tension_Pr : float
        Required axial *tensile* strength ``Pr`` (N).  Must be >= 0.
    elastic_modulus_E : float
        ``E`` (MPa).
    moment_of_inertia_y_Iy : float
        ``Iy`` (mm^4).
    unbraced_length_Lb : float
        ``Lb`` (mm).  Must be > 0.
    alpha : float, optional
        ``1.0`` (LRFD, default) or ``1.6`` (ASD).

    Returns
    -------
    float
        The dimensionless ``Cb`` multiplier (>= 1.0).

    Raises
    ------
    ValueError
        If ``Pr < 0`` or ``Lb <= 0``.
    """
    if required_tension_Pr < 0.0:
        raise ValueError(f"required_tension_Pr (tension) must be >= 0, got {required_tension_Pr!r}")
    pey: float = compute_Pey_H1_2(elastic_modulus_E, moment_of_inertia_y_Iy, unbraced_length_Lb)
    return math.sqrt(1.0 + alpha * required_tension_Pr / pey)


def compute_combined_strength_H1_2(
    required_tension_Pr: float,
    available_tension_Pc: float,
    required_moment_x_Mrx: float,
    available_moment_x_Mcx: float,
    required_moment_y_Mry: float = 0.0,
    available_moment_y_Mcy: float = 0.0,
) -> CombinedH1Report:
    """Return the AISC 360-22 §H1.2 flexure + tension interaction report.

    Identical Eq. H1-1a/H1-1b kernel as §H1.1, but ``available_tension_Pc``
    is the available *tensile* strength ``phi_t*Pn`` (e.g. the §D2(a)
    gross-section yield).  Any §H1.2 ``Cb`` amplification must already be
    reflected in the supplied ``available_moment_*`` (see
    :func:`compute_Cb_amplification_factor_H1_2`).

    Parameters
    ----------
    required_tension_Pr : float
        Required second-order axial *tensile* strength ``Pr`` (N).
    available_tension_Pc : float
        Available tensile strength ``Pc = phi_t*Pn`` (N).  Must be > 0.
    required_moment_x_Mrx, required_moment_y_Mry : float
        Required second-order flexural strengths about x / y (N*mm).
    available_moment_x_Mcx, available_moment_y_Mcy : float
        Available flexural strengths ``phi_b*Mn`` about x / y (N*mm).

    Returns
    -------
    CombinedH1Report
        With the §H1.2 citation block.
    """
    return compute_combined_strength_H1_1(
        required_axial_Pr=required_tension_Pr,
        available_axial_Pc=available_tension_Pc,
        required_moment_x_Mrx=required_moment_x_Mrx,
        available_moment_x_Mcx=available_moment_x_Mcx,
        required_moment_y_Mry=required_moment_y_Mry,
        available_moment_y_Mcy=available_moment_y_Mcy,
        citations=_CITATIONS_H1_2,
    )


__all__ = [
    "compute_Cb_amplification_factor_H1_2",
    "compute_Pey_H1_2",
    "compute_combined_strength_H1_2",
]
