# Getting Started

`apeSteel` is a composition-based, strictly-typed Python library for
structural-steel member design per **AISC 360-22**, **AISC 341-22**, and
**AISC 358-22**, with parallel support for **EN 10365** rolled IPE
shapes. Every check returns a frozen `Report` dataclass whose `phi*Mn`,
`phi*Pn`, `phi*Vn`, and limit-state fields are anchored to a concrete
AISC clause citation.

## Installation

```bash
pip install apeSteel
```

Optional plotting (matplotlib-backed capacity curves and interaction
diagrams) is gated behind an extra:

```bash
pip install "apeSteel[plot]"
```

`apeSteel` declares a runtime dependency on
[`baseUnits`](https://github.com/nmorabowen/baseUnits); installation
pulls it in automatically.

## The unit-system invariant

`apeSteel` runs in a **single canonical base system** — `N-mm-tonne-s`
— supplied by `baseUnits`. Every internal float (every dataclass field,
every function argument, every return value) is already expressed in
that base. Human-facing values are converted only at the boundary:

| Boundary | Pattern |
| --- | --- |
| Construction | `flange_width_bf = 300 * u.mm` |
| Comparison | `if Mr > 0.8 * 250 * u.kN * u.m: ...` |
| Display | `phi_Mn / (u.kN * u.m)` |

A module-level assertion in `apeSteel.core.units` fails fast at import
time if the active `baseUnits` system is not `N-mm-tonne-s`, so a
unit-system swap cannot silently corrupt downstream numbers. The deep
dive lives in [Units & Conventions](UNITS_AND_CONVENTIONS.md).

## A worked end-to-end example

The example below builds a welded plate-built I-section in **ASTM
A992**, binds a `Bracing` scenario, and drives the §B4 classification,
§F2 lateral-torsional buckling, §G2 web shear, and Chapter-E
compression checks through the `Element` facade.

```python
--8<-- "examples/getting_started_end_to_end.py"
```

Sample output:

```text
Flange class : compact
Web class    : compact
phi*Mn (F2)  :   458.0 kN.m   governing flange: bot
phi*Vn (G2)  :   695.0 kN
phi*Pn (Ch E):  1612.0 kN
```

(Numbers will track AISC 360-22 exactly; treat the values above as
illustrative of the output shape, not as a code-conformance test.)

## Where to next

- **[Sections & Catalogs](user_guide/sections.md)** — plate-built
  geometry classes (`DoublySymmetricISection`, `ChannelSection`,
  `RectangularHSS`, ...) and the `AISCv16Catalog` /
  `EuropeanIPECatalog` lookups.
- **[Materials & Units](user_guide/materials.md)** — `SteelMaterial`,
  the pre-built grades (`A36`, `A992`, `S355`, ...), and how to express
  values at the boundary.
- **[The Element Composite](user_guide/element.md)** — the
  section + material + construction + bracing composite and the AISC
  checks it exposes.
- **[Bracing](user_guide/bracing.md)** — the `Lb_top` / `Lb_bot` / `Cb`
  contract.
- **[AISC Chapters](aisc/E_compression.md)** — chapter-by-chapter
  reference for the §B / §E / §F / §G / §H checks.
- **[API Reference](api/element.md)** — full type signatures generated
  from the docstrings.
