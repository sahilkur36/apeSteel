"""Type stubs for the dynamic attributes exported by :mod:`baseUnits`.

baseUnits builds its named-unit constants at import time by populating a
``types.SimpleNamespace`` and shadowing the package globals with that
namespace's attributes. Static type checkers (pyright, mypy) cannot
introspect that pattern, which produces a flood of
``reportAttributeAccessIssue`` and ``reportUnknownVariableType`` errors
across every consumer of baseUnits.

This stub declares the public attribute surface that apeSteel relies on,
typed as :class:`float`. It is loaded automatically when pyright is
configured with ``stubPath: "typings"`` (see ``pyrightconfig.json``).

The stub mirrors the **N-mm-tonne-s** default system. apeSteel asserts
that this system is active before it starts using these symbols (see
:mod:`apeSteel.core.units`); using the stub for any other system would
type-check but produce wrong numerical values at runtime.

Source of truth at runtime:
- :mod:`baseUnits._factors` (unit factors in absolute SI)
- :mod:`baseUnits._make_system` (factory that derives the consistent set)
- :mod:`baseUnits.systems.N_mm_s` (the active default system)
"""

# ---------------------------------------------------------------------------
# Active-system metadata
# ---------------------------------------------------------------------------
BASE: str
g: float

# ---------------------------------------------------------------------------
# Lengths
# ---------------------------------------------------------------------------
mm: float
cm: float
m: float
km: float
inches: float
ft: float
yard: float
mile: float

# ---------------------------------------------------------------------------
# Forces
# ---------------------------------------------------------------------------
N: float
kN: float
MN: float
dyne: float
kgf: float
tf: float
lbf: float
kip: float

# ---------------------------------------------------------------------------
# Mass
# ---------------------------------------------------------------------------
kg: float
tonne: float
gram: float
gr: float
mg: float
lb: float
oz: float

# ---------------------------------------------------------------------------
# Time
# ---------------------------------------------------------------------------
s: float
minutes: float
h: float
day: float
week: float
month: float
year: float

# ---------------------------------------------------------------------------
# Pressure / stress
# ---------------------------------------------------------------------------
Pa: float
kPa: float
MPa: float
GPa: float
kgf_cm2: float
ksi: float
psi: float
bar: float
atm: float

# ---------------------------------------------------------------------------
# Energy
# ---------------------------------------------------------------------------
J: float
kJ: float
mJ: float
cal: float
kcal: float
eV: float
Wh: float
kWh: float

# ---------------------------------------------------------------------------
# Power
# ---------------------------------------------------------------------------
W: float
kW: float
MW: float
HP: float
mJ_s: float

# ---------------------------------------------------------------------------
# Density / unit weight
# ---------------------------------------------------------------------------
kg_per_m3: float
gr_per_cm3: float
tonne_per_m3: float
tonne_per_mm3: float
lb_per_ft3: float

N_per_m3: float
kN_per_m3: float
kgf_per_m3: float
N_per_mm3: float

# ---------------------------------------------------------------------------
# Angle (dimensionless)
# ---------------------------------------------------------------------------
radian: float
rad: float
degree: float

# ---------------------------------------------------------------------------
# Temperature (deltas only)
# ---------------------------------------------------------------------------
K: float
C: float
F: float
