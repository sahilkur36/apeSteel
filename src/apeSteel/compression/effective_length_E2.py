"""AISC 360-22 §E2 - effective length and member slenderness.

``Lc = K * L`` (the effective length); the member slenderness is
``Lc / r`` for the relevant radius of gyration.

Per §E2 and the §E2 user note, ``K = 1.0`` is the correct default when
stability is handled by the Direct Analysis Method (Chapter C); the
alignment-chart / effective-length method is an alternative the caller
opts into by passing ``K != 1.0``.  apeSteel does not choose ``K`` for
you - it is an explicit per-axis input, exactly as in the source
spreadsheet (Kx, Ky, Kz).

``Lc / r <= 200`` is an advisory preferred limit (§E2 user note), not a
strength limit; it is reported, never enforced.

References
----------
.. [1] AISC 360-22 §E2 "Effective Length", p. 16.1-37.
"""

from __future__ import annotations

from apeSteel.compression._common import SLENDERNESS_ADVISORY_LIMIT


def compute_effective_length_Lc(
    effective_length_factor_K: float,
    unbraced_length_L: float,
) -> float:
    """Return ``Lc = K * L`` per AISC 360-22 §E2.

    Parameters
    ----------
    effective_length_factor_K : float
        ``K`` for this axis.  Use ``1.0`` with the Direct Analysis
        Method (the recommended default).
    unbraced_length_L : float
        Unbraced length for this axis (mm).  Must be > 0.

    Returns
    -------
    float
        Effective length ``Lc`` (mm).

    Raises
    ------
    ValueError
        If ``unbraced_length_L <= 0`` or ``effective_length_factor_K <= 0``.
    """
    if unbraced_length_L <= 0.0:
        raise ValueError(f"unbraced_length_L must be positive, got {unbraced_length_L!r}")
    if effective_length_factor_K <= 0.0:
        raise ValueError(
            f"effective_length_factor_K must be positive, got {effective_length_factor_K!r}"
        )
    return effective_length_factor_K * unbraced_length_L


def compute_member_slenderness_Lc_over_r(
    effective_length_Lc: float,
    radius_of_gyration_r: float,
) -> float:
    """Return the member slenderness ``Lc / r`` for one buckling axis.

    Parameters
    ----------
    effective_length_Lc : float
        Effective length about this axis (mm).
    radius_of_gyration_r : float
        Radius of gyration about this axis (mm).  Must be > 0.

    Returns
    -------
    float
        ``Lc / r`` (dimensionless).

    Raises
    ------
    ValueError
        If ``radius_of_gyration_r <= 0``.
    """
    if radius_of_gyration_r <= 0.0:
        raise ValueError(f"radius_of_gyration_r must be positive, got {radius_of_gyration_r!r}")
    return effective_length_Lc / radius_of_gyration_r


def is_within_slenderness_advisory(member_slenderness_Lc_over_r: float) -> bool:
    """True iff ``Lc/r <= 200`` (the §E2 preferred advisory limit).

    This is informational only - AISC does not prohibit ``Lc/r > 200``;
    it merely advises against it for practical/handling reasons.
    """
    return member_slenderness_Lc_over_r <= SLENDERNESS_ADVISORY_LIMIT


__all__ = [
    "compute_effective_length_Lc",
    "compute_member_slenderness_Lc_over_r",
    "is_within_slenderness_advisory",
]
