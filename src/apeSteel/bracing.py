"""Bracing - lateral bracing data for a structural-steel element.

`Bracing` owns the domain of "how is this member laterally supported,
and what's the effective moment-diagram modification factor?":

* `unbraced_length_top_flange_Lb_top`  - distance between lateral
  braces of the top flange (mm).
* `unbraced_length_bot_flange_Lb_bot`  - same for the bottom flange.
* `lateral_torsional_buckling_modification_factor_Cb` - Cb per
  AISC F1-1.

Why a separate object?
    Bracing is its own conceptual entity in design.  A given Element
    may be re-evaluated under several bracing scenarios (e.g. ASD vs
    LRFD different load patterns, code-mandated check at multiple
    points along a span, before/after a stiffener detail change), and
    factoring those parameters into a named object makes that
    workflow first-class instead of dragging Lb / Cb through every
    method call.  It also positions us cleanly for future additions
    (transverse stiffener spacing for shear with tension-field action,
    bracing-as-system in DG-25 stability, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Bracing:
    """Frozen description of a member's lateral bracing scenario.

    All lengths in apeSteel base units (mm); Cb dimensionless.

    Attributes
    ----------
    unbraced_length_top_flange_Lb_top : float
        Distance between lateral braces of the top flange (mm).  Use a
        small positive value (e.g. ``0.001 * u.m``) when the top
        flange is continuously braced by a slab; do NOT pass zero, as
        the F2-5 regime check expects a positive Lb.
    unbraced_length_bot_flange_Lb_bot : float
        Distance between lateral braces of the bottom flange (mm).
    lateral_torsional_buckling_modification_factor_Cb : float
        Cb per AISC F1-1, dimensionless.  Defaults to 1.0
        (conservative; recommended only when no moment diagram is
        available).
    """

    unbraced_length_top_flange_Lb_top: float
    unbraced_length_bot_flange_Lb_bot: float
    lateral_torsional_buckling_modification_factor_Cb: float = 1.0


__all__ = ["Bracing"]
