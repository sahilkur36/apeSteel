# Materials & Units

A `SteelMaterial` is the immutable description of a steel grade as
needed by AISC 360 and AISC 341 strength formulas. It is a frozen
dataclass with `slots=True`; mutation raises
`dataclasses.FrozenInstanceError`. Every numeric attribute is stored
in the canonical `N-mm-tonne-s` base.

## Attributes

| Field | Symbol | Units (base) |
| --- | --- | --- |
| `name` | — | `str` |
| `yield_stress_Fy` | $F_y$ | MPa |
| `tensile_stress_Fu` | $F_u$ | MPa |
| `elastic_modulus_E` | $E$ | MPa |
| `shear_modulus_G` | $G$ | MPa |
| `density_rho` | $\rho$ | tonne / mm³ |
| `expected_yield_ratio_Ry` | $R_y$ | — |
| `expected_tensile_ratio_Rt` | $R_t$ | — |

`Ry` and `Rt` follow **AISC 341-22 Table A3.1** (expected material
properties); they are pinned on each pre-built grade so capacity-design
demand (e.g. $M_{pr} = R_y\,F_y\,Z_x$) is internally consistent.

## Pre-built grades

`apeSteel` ships five canonical grades, all importable from the
top-level package:

| Grade | $F_y$ | $F_u$ | $R_y$ | $R_t$ |
| --- | --- | --- | --- | --- |
| `A36` | 36 ksi | 58 ksi | 1.5 | 1.2 |
| `A992` | 50 ksi | 65 ksi | 1.1 | 1.1 |
| `A572_Gr50` | 50 ksi | 65 ksi | 1.1 | 1.1 |
| `S275` | 275 MPa | 430 MPa | 1.25 | 1.20 |
| `S355` | 355 MPa | 510 MPa | 1.25 | 1.20 |
| `S460` | 460 MPa | 550 MPa | 1.20 | 1.15 |

All six share the AISC canonical moduli: $E = 29\,000\ \mathrm{ksi}$
($\approx 199\,948\ \mathrm{MPa}$), $G = 11\,200\ \mathrm{ksi}$
($\approx 77\,211\ \mathrm{MPa}$), $\rho = 7.85\ \mathrm{tonne/m^3}$.

## Expressing values at the boundary

`apeSteel` does **not** wrap values in a `Quantity` type. Instead, the
boundary contract is *multiply on the way in, divide on the way out*.
The unit constants live in `apeSteel.core.units` (re-exported from
`baseUnits`):

```python
from apeSteel.core import units as u

flange_width   = 300 * u.mm          #  300.0 mm in the base
yield_stress   = 50  * u.ksi         #  ~344.74 MPa in the base
axial_force    = 1.2 * u.kN          #  1200.0 N in the base
moment_demand  = 250 * u.kN * u.m    #  2.5e8 N.mm in the base
```

The constants are simple floats (`u.mm == 1.0`, `u.m == 1000.0`,
`u.kN == 1000.0`, `u.MPa == 1.0`, ...), so the arithmetic is just
float multiplication — no overloads, no surprises.

For display, divide by the same unit constants:

```python
print(f"phi*Mn = {report.phi_strength_LRFD / (u.kN * u.m):.1f} kN.m")
```

## Working example

```python
--8<-- "examples/materials_grades.py"
```

## Customising a grade

`SteelMaterial` is just a frozen dataclass — there is no registry, no
side effect at construction. A custom grade is one constructor call:

```python
from apeSteel import SteelMaterial
from apeSteel.core import units as u

Q420 = SteelMaterial(
    name="Custom Q420",
    yield_stress_Fy=420 * u.MPa,
    tensile_stress_Fu=540 * u.MPa,
    elastic_modulus_E=200_000 * u.MPa,
    shear_modulus_G=77_200 * u.MPa,
    density_rho=7.85 * u.tonne / (u.m**3),
    expected_yield_ratio_Ry=1.20,
    expected_tensile_ratio_Rt=1.15,
)
```

Every downstream `Element.classify_*`, `Element.flexural_strength_*`,
and `Element.compression_strength` call accepts this `Q420` instance
verbatim.

## See also

For the full rationale (the BASE assertion, the
multiply-at-the-boundary contract, the
[`CANONICAL_DISPLAY_UNITS`](https://github.com/nmorabowen/apeSteel/blob/main/src/apeSteel/core/units.py)
formatter table, and the test suite that pins it), see the
[Units & Conventions](../UNITS_AND_CONVENTIONS.md) reference page.
