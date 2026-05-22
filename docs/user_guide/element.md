# The Element Composite

`Element` is the central composite in `apeSteel`. It aggregates the
three primary domain objects — `section`, `material`, and `bracing` —
plus the `construction` discriminator (`"welded"` or `"rolled"`), and
exposes every AISC member-level check as a method.

## Composition spine

```text
DoublySymmetricISection            SteelMaterial            Bracing
        |                                |                     |
        +-------------- Element ---------+---------------------+
                          |
                          +-- classify_flexural()         # AISC §B4.1b
                          +-- classify_axial_compression()# AISC §B4.1a
                          +-- classify_seismic(...)       # AISC 341 §D1.1
                          +-- flexural_strength_F2_*()    # §F2 LTB
                          +-- flexural_strength_F3_*()    # §F3 LTB + FLB
                          +-- flexural_strength_F4_*()    # §F4 doubly/singly sym
                          +-- flexural_strength_F5_*()    # §F5 slender web
                          +-- shear_strength_G2(...)      # §G2 web shear
                          +-- compression_strength(...)   # Chapter E
                          +-- combined_strength_H1(...)   # §H1.1
                          +-- run_full_check(...)         # B4 + Ch F + G2 facade
                          +-- serviceability_*(...)       # elastic deflections
```

`Element` is a frozen dataclass: every check returns a fresh `Report`,
and field-replacement is done with `with_*` builders that return a new
`Element`.

## The four construction paths

```python
--8<-- "examples/element_composite.py"
```

The four constructors are equivalent (and asserted as such by the unit
suite):

1. **`section.element(material=..., bracing=...)`** — the section
   shortcut, used in 90 % of code.
2. **`Element(section=..., material=..., construction=..., bracing=...)`** —
   the explicit constructor; passes through any field.
3. **`Element.from_section(section, material, construction, bracing)`** —
   the classmethod factory; equivalent to (2).
4. **`with_*` builders** — `with_material(...)`, `with_construction(...)`,
   `with_bracing(...)`, `with_code_edition_for_seismic(...)` — each
   returns a new `Element` with one field replaced.

The `section` field is typed as the `ISection` union
(`DoublySymmetricISection | SinglySymmetricISection`). Singly-symmetric
sections route through §F4 / §F5 only; the F2 / F3 / G2 / Chapter-E /
§H1.1 paths raise `NotImplementedError` (they assume doubly-symmetric
geometry).

## The check surface

### Classification (no bracing required)

| Method | AISC clause | Returns |
| --- | --- | --- |
| `classify_flexural()` | §B4.1b | `FlexuralCompactnessReport` |
| `classify_axial_compression()` | §B4.1a | `AxialCompressionClassificationReport` |
| `classify_seismic(ductility_level, axial_demand_ratio_Ca=0.0)` | AISC 341-22 §D1.1 | `SeismicCompactnessReport` |

### Flexural strength (bracing required)

For each Chapter-F clause `Fx` (where `x` is 2 / 3 / 4 / 5), the
`Element` exposes a triple:

- `flexural_strength_Fx_top_flange()` — top flange in compression, uses
  `bracing.unbraced_length_top_flange_Lb_top`.
- `flexural_strength_Fx_bot_flange()` — bottom flange in compression,
  uses `bracing.unbraced_length_bot_flange_Lb_bot`.
- `flexural_strength_Fx_both_flanges()` — runs both, returns a
  `BothFlangesFlexureFxReport` with `top`, `bot`, `governing_flange`,
  and `governing_report`.

For a parameter study over `Lb`, use `phi_Mn_vs_Lb(unbraced_lengths_Lb,
lateral_torsional_buckling_modification_factor_Cb=1.0,
flange="governing")`. The classifier runs **once** to pick the routed
engine (F2 / F3 / F4 / F5); that engine is then evaluated at every
`Lb` in the sweep.

### Shear and compression

| Method | Signature | AISC clause |
| --- | --- | --- |
| `shear_strength_G2(transverse_stiffener_spacing_a=None)` | One web check (no top / bot distinction) | §G2 |
| `compression_strength(effective_length_factor_Kx, unbraced_length_Lx, ...Ky, ...Ly, ...Kz, ...Lz)` | Six explicit `K`, `L` arguments | Chapter E (§E2 / §E3 / §E4 / §E7) |

### Combined forces and full beam check

| Method | Purpose |
| --- | --- |
| `combined_strength_H1(required_axial_Pr, required_moment_x_Mrx, *, Kx, Lx, Ky, Ly, Kz, Lz, required_moment_y_Mry=0.0, available_moment_y_Mcy=0.0)` | §H1.1 beam-column unity check. `Pc` is resolved from `compression_strength`, `Mcx` from `run_full_check`; biaxial `Mcy` auto-resolves from §F6 when `Mry != 0`. |
| `run_full_check(transverse_stiffener_spacing_a=None)` | Classify per §B4.1b, route flexure to F2 / F3 / F4 / F5 accordingly, and run G2 shear. Returns a `BeamCheckReport`. |

### Serviceability

The `serviceability_*` methods cover elastic deflections for the four
canonical patterns (simply-supported UDL, simply-supported point load
at mid-span and at arbitrary location, cantilever UDL + tip load). Each
takes loads in base units (`100 * u.kN`, `12 * u.kN / u.m`) and returns
a report with the predicted deflection plus the load-pattern-specific
limit-state check.

## Immutability and value identity

`Element` is `@dataclass(frozen=True)`; field assignment raises
`FrozenInstanceError`. Two `Element` instances built from the same
section / material / construction / bracing compare equal (the test
suite pins this), so they slot directly into sets, dict keys, and
caching layers.
