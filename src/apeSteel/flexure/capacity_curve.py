"""φMn-vs-Lb capacity curve (mirror of the §E capacity curve).

Pure data record consumed by :meth:`Element.phi_Mn_vs_Lb` and the
plotting helpers.  The Element method owns the F2/F3/F4/F5 routing
(classification is geometry-based, so it runs once and the same engine
evaluates every Lb); this module just defines the per-point record.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

RoutedFlexureChapterCurve = Literal["F2", "F3", "F4", "F5"]
"""The Chapter-F engine selected by B4.1b classification."""

GoverningFlangeCurve = Literal["top", "bot"]


@dataclass(frozen=True, slots=True)
class FlexuralCurvePoint:
    """One point on the φMn-vs-Lb curve.

    Attributes
    ----------
    unbraced_length_Lb : float
        Sweep Lb (mm), applied to both flanges symmetrically.
    nominal_strength_Mn : float
        Governing ``Mn`` at this Lb (N*mm).
    design_strength_phi_Mn : float
        ``phi_b * Mn`` (N*mm).
    routed_chapter : str
        Which Chapter-F engine produced the value
        (``"F2"``/``"F3"``/``"F4"``/``"F5"``).
    governing_flange : str
        ``"top"`` or ``"bot"`` — the flange whose check governed.
    governing_limit_state : str
        Limit-state tag from the governing F-report
        (``"yielding"`` / ``"inelastic_LTB"`` / ``"elastic_LTB"`` /
        ``"flange_local_buckling"`` / ...).
    limiting_length_plastic_Lp : float
        Lp landmark (mm).  All four routed engines expose Lp.
    limiting_length_inelastic_LTB_Lr : float
        Lr landmark (mm).
    """

    unbraced_length_Lb: float
    nominal_strength_Mn: float
    design_strength_phi_Mn: float
    routed_chapter: RoutedFlexureChapterCurve
    governing_flange: GoverningFlangeCurve
    governing_limit_state: str
    limiting_length_plastic_Lp: float
    limiting_length_inelastic_LTB_Lr: float


__all__ = [
    "FlexuralCurvePoint",
    "GoverningFlangeCurve",
    "RoutedFlexureChapterCurve",
]
