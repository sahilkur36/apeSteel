"""Unit-system contract for apeSteel.

apeSteel runs in a single canonical base system,
**N-mm-tonne-s**, provided by :mod:`baseUnits`. All internal storage,
every dataclass attribute, every function argument, and every return value
inside the library is a :class:`float` already expressed in this base.

This module:

1. Asserts at import time that :data:`baseUnits.BASE` is the expected
   ``"N-mm-tonne-s"`` so that an accidental system swap fails fast.
2. Re-exports the unit names we use most often, with explicit names so
   :mod:`pyright` resolves them without having to chase a star-import.
3. Defines the compound display units that :mod:`baseUnits` does not ship
   (moment in kN·m, flexural / lateral stiffness in kN/mm, etc.) as
   uppercase module-level constants suitable for division at the boundary
   (``value / MOMENT_DISPLAY_UNIT_kN_m``).
4. Publishes :data:`CANONICAL_DISPLAY_UNITS`, the table the formatter
   uses when rendering a :class:`~apeSteel.core.result_types.Report`.

Every module that depends on units in apeSteel should import
:mod:`apeSteel.core.units` rather than reaching for :mod:`baseUnits`
directly — that way the BASE assertion runs in one place and stays in
one place.

Notes
-----
The BASE assertion is intentionally an :class:`AssertionError` (not a
custom exception) so that it cannot be silenced by Python's ``-O`` flag
inside production runs of structural-engineering software, where unit
mismatches are a hard fault, not a warning. This is reinforced by the
companion test ``tests/test_smoke.py``.
"""

from __future__ import annotations

import baseUnits as _u

# ---------------------------------------------------------------------------
# 1. BASE assertion
# ---------------------------------------------------------------------------
EXPECTED_BASE: str = "N-mm-tonne-s"
ACTIVE_BASE: str = _u.BASE

if ACTIVE_BASE != EXPECTED_BASE:  # pragma: no cover - guarded at import time
    raise AssertionError(
        f"apeSteel requires baseUnits in the {EXPECTED_BASE!r} system, "
        f"but the active system is {ACTIVE_BASE!r}. Did some module "
        f"import `from baseUnits.systems.<other>_<other>_s import *` "
        f"before apeSteel was imported? See docs/UNITS_AND_CONVENTIONS.md."
    )


# ---------------------------------------------------------------------------
# 2. Explicit re-exports of the units apeSteel touches.
# ---------------------------------------------------------------------------
# Lengths (base = mm)
mm: float = _u.mm
cm: float = _u.cm
m: float = _u.m
inches: float = _u.inches
ft: float = _u.ft

# Forces (base = N)
N: float = _u.N
kN: float = _u.kN
MN: float = _u.MN
kgf: float = _u.kgf
tf: float = _u.tf
lbf: float = _u.lbf
kip: float = _u.kip

# Mass (base = tonne)
kg: float = _u.kg
tonne: float = _u.tonne
gram: float = _u.gram

# Time (base = s)
s: float = _u.s

# Stress / pressure (base = MPa)
Pa: float = _u.Pa
kPa: float = _u.kPa
MPa: float = _u.MPa
GPa: float = _u.GPa
ksi: float = _u.ksi
psi: float = _u.psi
kgf_cm2: float = _u.kgf_cm2

# Angle
radian: float = _u.radian
rad: float = _u.rad
degree: float = _u.degree

# Gravity in the active system (mm / s^2)
g: float = _u.g


# ---------------------------------------------------------------------------
# 3. Compound display units that baseUnits does not ship with a name.
# ---------------------------------------------------------------------------
# Moment (force * length). Divide a stored moment by these to display.
MOMENT_DISPLAY_UNIT_N_mm: float = N * mm
MOMENT_DISPLAY_UNIT_kN_m: float = kN * m
MOMENT_DISPLAY_UNIT_kip_ft: float = kip * ft

# Flexural stiffness (force per length).
STIFFNESS_DISPLAY_UNIT_N_per_mm: float = N / mm
STIFFNESS_DISPLAY_UNIT_kN_per_mm: float = kN / mm
STIFFNESS_DISPLAY_UNIT_kN_per_m: float = kN / m

# Rotational stiffness (moment per angle).
ROTATIONAL_STIFFNESS_DISPLAY_UNIT_kN_m_per_rad: float = MOMENT_DISPLAY_UNIT_kN_m / rad

# Line load (force per length, e.g. UDL on a beam).
LINE_LOAD_DISPLAY_UNIT_kN_per_m: float = kN / m
LINE_LOAD_DISPLAY_UNIT_N_per_mm: float = N / mm

# Area load (force per area, e.g. floor pressure).
AREA_LOAD_DISPLAY_UNIT_kPa: float = kPa
AREA_LOAD_DISPLAY_UNIT_kN_per_m2: float = kN / (m * m)


# ---------------------------------------------------------------------------
# 4. Canonical display-unit table used by Report.format().
# ---------------------------------------------------------------------------
# The keys are physical-quantity tags (free strings); the value pair is
# `(display_unit_value, display_unit_label)`. The formatter divides the
# stored base-units float by the value, then prints the rounded number
# followed by the label.
CANONICAL_DISPLAY_UNITS: dict[str, tuple[float, str]] = {
    "length_member": (m, "m"),
    "length_plate": (mm, "mm"),
    "force": (kN, "kN"),
    "moment": (MOMENT_DISPLAY_UNIT_kN_m, "kN·m"),
    "stress": (MPa, "MPa"),
    "stiffness_lateral": (STIFFNESS_DISPLAY_UNIT_kN_per_mm, "kN/mm"),
    "stiffness_axial": (STIFFNESS_DISPLAY_UNIT_kN_per_mm, "kN/mm"),
    "line_load": (LINE_LOAD_DISPLAY_UNIT_kN_per_m, "kN/m"),
    "area_load": (AREA_LOAD_DISPLAY_UNIT_kPa, "kPa"),
    "angle": (degree, "°"),
}


__all__ = [
    "ACTIVE_BASE",
    "CANONICAL_DISPLAY_UNITS",
    "EXPECTED_BASE",
    "MN",
    "AREA_LOAD_DISPLAY_UNIT_kN_per_m2",
    "AREA_LOAD_DISPLAY_UNIT_kPa",
    "GPa",
    "LINE_LOAD_DISPLAY_UNIT_N_per_mm",
    "LINE_LOAD_DISPLAY_UNIT_kN_per_m",
    "MOMENT_DISPLAY_UNIT_N_mm",
    "MOMENT_DISPLAY_UNIT_kN_m",
    "MOMENT_DISPLAY_UNIT_kip_ft",
    "MPa",
    "N",
    "Pa",
    "ROTATIONAL_STIFFNESS_DISPLAY_UNIT_kN_m_per_rad",
    "STIFFNESS_DISPLAY_UNIT_N_per_mm",
    "STIFFNESS_DISPLAY_UNIT_kN_per_m",
    "STIFFNESS_DISPLAY_UNIT_kN_per_mm",
    "cm",
    "degree",
    "ft",
    "g",
    "gram",
    "inches",
    "kN",
    "kPa",
    "kg",
    "kgf",
    "kgf_cm2",
    "kip",
    "ksi",
    "lbf",
    "m",
    "mm",
    "psi",
    "rad",
    "radian",
    "s",
    "tf",
    "tonne",
]
