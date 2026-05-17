"""AISC 360-22 §E5 - single-angle compression members.

When the §E5 conditions hold (concentric end load delivered through one
leg, attached by welds or >= 2 bolts, no intermediate transverse load,
member slenderness ``L/rx <= ...``), eccentricity may be neglected and
the angle designed as an axially loaded member per §E3 using a
**modified effective slenderness** ``Lc/r`` in place of the geometric
ratio.  ``rx`` is the radius of gyration about the geometric axis
parallel to the connected leg.

Case (a) - equal-leg, or unequal-leg connected through the longer leg,
single members or web members of planar trusses with adjacent web
members attached to the same side of the gusset:

* Eq. E5-1  ``L/rx <= 80`` : ``Lc/r = 72 + 0.75 (L/rx)``
* Eq. E5-2  ``L/rx >  80`` : ``Lc/r = 32 + 1.25 (L/rx) <= 200``

Case (b) - members of box or space trusses with adjacent web members
attached to the same side of the gusset:

* Eq. E5-3  ``L/rx <= 75`` : ``Lc/r = 60 + 0.8 (L/rx)``
* Eq. E5-4  ``L/rx >  75`` : ``Lc/r = 45 + (L/rx) <= 200``

These reproduce the source spreadsheet's ``E99`` (case a) and ``E107``
(case b) exactly.

References
----------
.. [1] AISC 360-22 §E5 "Single-Angle Compression Members", Eq. E5-1 -
       E5-4, p. 16.1-41.
"""

from __future__ import annotations

from typing import Literal

#: §E5 connection / framing case selector.
SingleAngleE5Case = Literal["a", "b"]

#: Eq. E5-2 / E5-4 cap on the modified effective slenderness.
E5_MODIFIED_SLENDERNESS_CAP: float = 200.0


def compute_modified_slenderness_E5(
    geometric_slenderness_L_over_rx: float,
    case: SingleAngleE5Case,
) -> float:
    """Return the §E5 modified effective slenderness ``Lc/r``.

    Parameters
    ----------
    geometric_slenderness_L_over_rx : float
        ``L / rx`` where ``rx`` is the radius of gyration about the
        geometric axis parallel to the connected leg.
    case : {"a", "b"}
        ``"a"`` -> Eq. E5-1 / E5-2; ``"b"`` -> Eq. E5-3 / E5-4.

    Returns
    -------
    float
        The modified ``Lc/r`` to feed into §E3 (dimensionless).
    """
    lr: float = geometric_slenderness_L_over_rx
    if case == "a":
        if lr <= 80.0:
            return 72.0 + 0.75 * lr  # Eq. E5-1
        return min(32.0 + 1.25 * lr, E5_MODIFIED_SLENDERNESS_CAP)  # Eq. E5-2
    # case "b"
    if lr <= 75.0:
        return 60.0 + 0.8 * lr  # Eq. E5-3
    return min(45.0 + lr, E5_MODIFIED_SLENDERNESS_CAP)  # Eq. E5-4


__all__ = [
    "E5_MODIFIED_SLENDERNESS_CAP",
    "SingleAngleE5Case",
    "compute_modified_slenderness_E5",
]
