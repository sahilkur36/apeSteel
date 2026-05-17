"""Shared primitives for the thin AISC 360-22 Chapter-D slice.

apeSteel ships only §D2(a) gross-section yielding (the single limit
state §H1.2 consumes).  This module centralises the §D2 resistance /
safety factors and the citation block, mirroring the ``_common.py`` of
every other chapter package.

References
----------
.. [1] AISC 360-22 §D2 "Tensile Strength", Eq. D2-1, p. 16.1-31.
"""

from __future__ import annotations

from apeSteel.core.result_types import AISCClauseReference

#: AISC 360-22 §D2(a) LRFD resistance factor for tensile yielding.
PHI_TENSION_YIELDING_LRFD: float = 0.90

#: AISC 360-22 §D2(a) ASD safety factor for tensile yielding.
OMEGA_TENSION_YIELDING_ASD: float = 1.67

#: Citation block for the §D2(a) gross-section-yielding limit state.
CITATIONS_AISC_360_D2_YIELDING: tuple[AISCClauseReference, ...] = (
    AISCClauseReference("AISC 360-22", "D2", "D2-1", "16.1-31"),
)


__all__ = [
    "CITATIONS_AISC_360_D2_YIELDING",
    "OMEGA_TENSION_YIELDING_ASD",
    "PHI_TENSION_YIELDING_LRFD",
]
