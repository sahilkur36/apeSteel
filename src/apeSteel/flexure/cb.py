"""Cb - lateral-torsional buckling modification factor (AISC 360 Eq. F1-1).

Cb captures the effect of a non-uniform moment diagram on the LTB
strength of a beam.  For a uniform moment along the unbraced segment
(constant Mmax), Cb = 1.0.  For a moment diagram that varies along the
segment, Cb > 1.0 (the strength is higher than the constant-moment case
because not every fibre is at peak stress simultaneously).

AISC 360 Eq. F1-1 gives Cb from the maximum absolute moment in the
unbraced segment plus the absolute moments at the quarter, midspan, and
three-quarter points:

    Cb = 12.5 * Mmax / (2.5*Mmax + 3*MA + 4*MB + 3*MC) * Rm

where Rm is the cross-section monosymmetry parameter (1.0 for
doubly-symmetric sections and singly-symmetric sections in single
curvature).

A conservative default of Cb = 1.0 is always allowed; the helper here
is for users who have the actual moment diagram (e.g. from an ETABS /
SAP / Robot run) and want to take credit for the non-uniformity.

References
----------
.. [1] AISC 360-22 §F1, Eq. F1-1, p. 16.1-48.
"""

from __future__ import annotations


def compute_Cb_from_quarter_point_moments(
    maximum_absolute_moment_Mmax: float,
    absolute_moment_at_quarter_point_MA: float,
    absolute_moment_at_midspan_MB: float,
    absolute_moment_at_three_quarter_point_MC: float,
    cross_section_monosymmetry_parameter_Rm: float = 1.0,
) -> float:
    """Return Cb per AISC 360 Eq. F1-1.

    Parameters
    ----------
    maximum_absolute_moment_Mmax : float
        Maximum of |M(x)| over the unbraced segment.  All quantities
        in apeSteel base units (N*mm).
    absolute_moment_at_quarter_point_MA : float
        |M(L/4)| in the unbraced segment.
    absolute_moment_at_midspan_MB : float
        |M(L/2)|.
    absolute_moment_at_three_quarter_point_MC : float
        |M(3L/4)|.
    cross_section_monosymmetry_parameter_Rm : float, optional
        Rm per AISC F1-1 commentary.  1.0 for doubly-symmetric and
        singly-symmetric beams in single curvature (default).  Use a
        smaller value for singly-symmetric beams in reverse curvature
        (see AISC commentary for the explicit form).

    Returns
    -------
    float
        Cb, dimensionless.  Typically in [1.0, 3.0] for realistic
        moment diagrams; the AISC commentary suggests capping Cb at
        3.0 in practice though F1-1 itself does not.

    Raises
    ------
    ValueError
        If `maximum_absolute_moment_Mmax` is zero (Cb is undefined).
    """
    Mmax = maximum_absolute_moment_Mmax
    MA = absolute_moment_at_quarter_point_MA
    MB = absolute_moment_at_midspan_MB
    MC = absolute_moment_at_three_quarter_point_MC
    Rm = cross_section_monosymmetry_parameter_Rm

    denominator: float = 2.5 * Mmax + 3.0 * MA + 4.0 * MB + 3.0 * MC
    if denominator == 0.0:
        raise ValueError(
            "Cb is undefined when the four moments are all zero (meaningless unbraced segment)."
        )
    return (12.5 * Mmax / denominator) * Rm


__all__ = ["compute_Cb_from_quarter_point_moments"]
