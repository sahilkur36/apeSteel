"""AISC 360-22 Chapter D - tension members (thin slice).

apeSteel does not yet implement the full Chapter D.  This package
ships only the single limit state that AISC 360-22 §H1.2 (flexure +
axial tension) consumes: gross-section yielding ``Pn = Fy*Ag``
(Eq. D2-1).  Net-section rupture (Eq. D2-2) and block shear (§J4) are
deliberately out of scope and tracked for a future dedicated Chapter-D
phase; see ``docs/design_notes/09_combined_H.md`` §4.
"""

from apeSteel.tension.yielding_D2 import compute_tension_yielding_strength_D2

__all__ = ["compute_tension_yielding_strength_D2"]
