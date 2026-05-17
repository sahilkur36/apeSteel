# apeSteel

Structural-steel design library for **AISC 360** and **AISC 341 (seismic)**,
written in modern Python with an emphasis on:

- Composition over inheritance.
- Verbose, fully typed public API (pyright strict, Python 3.11+).
- One canonical internal unit system (`N-mm-tonne-s`) via
  [`baseUnits`](https://github.com/nmorabowen/baseUnits).
- Every calculator returns a typed, frozen `Report` dataclass — no `print`
  inside the engine, ever.
- Citations baked into every result: section, equation, page in AISC.

`apeSteel` is the structural-engineering complement to
[`apeGmsh`](../apeGmsh) (FEM meshing) and the broader `ape*` toolchain.

---

## Scope (v0.x)

| Area | AISC ref | Implemented |
| --- | --- | --- |
| Section geometry (doubly-symmetric I, plate girder) | — | planned |
| AISC v16 catalog (W, M, S, HP, C, MC, L, WT, MT, ST, HSS, Pipe) | Manual Tables 1-1 … 1-14 | planned |
| European catalog (IPE, IPEA, HE-A/B/M) | EN 10365 | planned |
| Flexural classification | 360 §B4.1b | planned |
| Seismic compactness | 341 §D1.1 | planned |
| Flexure — compact doubly-symmetric I | 360 §F2 | planned |
| Flexure — non-compact / slender flange | 360 §F3 | planned |
| Flexure — singly-symmetric I | 360 §F4 | planned |
| Flexure — slender web plate girder | 360 §F5 | planned |
| Shear (incl. tension-field action) | 360 §G2 | planned |
| Serviceability deflections | — | planned |
| Panel-zone column-flange tension check | 341 §E3.6e | planned |

Out of scope (for now): compression (E), tension (D), combined loading (H),
composite members (I), connections (J/K) — these will be added in later
phases. The design accommodates them; the chapters above are just what the
port from the original Excel sheets covers first.

---

## Design philosophy

1. **Layered composition.** A `Member` is `Geometry + Material + UnbracedLengths
   + Cb`. Each calculator (`F2`, `F3`, `G2`, `B4`, `D1`, …) takes the smallest
   possible slice of that data and returns a frozen `Report`. The high-level
   `BeamCheck` facade simply orchestrates the calculators — it owns no math.

2. **Geometry knows nothing about material.** The same `DoublySymmetricISection`
   computes `Ix`, `Iy`, `J`, `Cw`, `rts` regardless of whether you'll later
   pair it with A992 or S355. Catalog sections and user-defined plate-built
   sections both produce a `SectionProperties` frozen dataclass; downstream
   code only sees that type.

3. **Verbose names + AISC symbol suffix.** Public attributes are spelled out
   (`flange_width_bf`, `limiting_length_plastic_Lp`, `nominal_flexural_strength_Mn`).
   Inside short calculator functions, the bare AISC symbol (`Lp`, `Mp`, `Fy`)
   is allowed because that's what the code citation says.

4. **Static-typing first.** pyright in strict mode. No `Any`. No implicit
   `Optional`. Frozen dataclasses with `slots=True` for every result.

5. **Citation discipline.** Every calculator carries a list of
   `AISCClauseReference(spec="AISC 360-22", section="F2.2", equation="F2-5",
   page=16.1-49)` so that the produced report can be traced back to the
   exact code paragraph.

---

## Install (development)

```bash
git clone https://github.com/nmorabowen/apeSteel.git
cd apeSteel
pip install -e .[dev]
```

Requires Python ≥ 3.11. The `dev` extra pulls pyright, ruff, pytest,
pytest-cov, and the `baseUnits` package from GitHub.

---

## Example

```python
import baseUnits as u
from apeSteel import (
    A992,
    Bracing,
    DoublySymmetricISection,
)

# 1. Three primary domain objects (nodes in the model graph).
section = DoublySymmetricISection(
    flange_width_bf     = 300 * u.mm,
    flange_thickness_tf = 22  * u.mm,
    web_clear_height_hw = 350 * u.mm,
    web_thickness_tw    = 12  * u.mm,
)
material = A992
bracing = Bracing(
    unbraced_length_top_flange_Lb_top  = 0.001 * u.m,   # slab-braced
    unbraced_length_bot_flange_Lb_bot  = 4.0   * u.m,
    lateral_torsional_buckling_modification_factor_Cb = 1.0,
)

# 2. Compose them into an Element.
element = section.element(
    material=material, construction="welded", bracing=bracing,
)

# 3. Every AISC check is a method on the composite.
flex_class = element.classify_flexural()            # AISC 360 §B4.1b
axial      = element.classify_axial_compression()   # AISC 360 §B4.1a
seismic    = element.classify_seismic("highly_ductile")     # AISC 341 §D1.1
F2         = element.flexural_strength_F2_both_flanges()    # AISC 360 §F2

print(f"section classification : {flex_class.section_classification}")
print(f"governing flange       : {F2.governing_flange}")
print(f"governing phi*Mn       : {F2.governing_report.phi_strength_LRFD / (u.kN * u.m):.2f} kN·m")
print(f"governing limit state  : {F2.governing_report.governing_limit_state}")
```

Rebind any primary object without recomputing the others — section
properties are cached on the Element:

```python
from apeSteel import S355
element_S355 = element.with_material(S355)
tighter      = element.with_bracing(
    Bracing(0.001 * u.m, 1.5 * u.m, lateral_torsional_buckling_modification_factor_Cb=1.2),
)
```

---

## Pure-function form

For parametric studies, FEM post-processing, or porting from procedural
spreadsheets, every AISC equation is also importable as a free function:

```python
from apeSteel import (
    classify_flexural_compactness_B4_1b,
    compute_flexural_strength_F2_compact_doubly_symmetric,
)

props = section.compute_section_properties()
classification_report = classify_flexural_compactness_B4_1b(
    props, A992, construction="welded",
)
flexure_report = compute_flexural_strength_F2_compact_doubly_symmetric(
    section_properties=props, material=A992,
    unbraced_length_Lb=4.0 * u.m,
    lateral_torsional_buckling_modification_factor_Cb=1.0,
)
```

The `Element` methods are one-line wrappers around these functions; both
APIs are first-class and stay in sync.

---

## Status

Phases 0 – 3 of the roadmap shipped (scaffolding, section geometry +
properties, classification, F2 flexural strength).  Phase 4+ (F3 / F5,
shear, serviceability, panel zone) is upcoming — see
[`docs/ROADMAP.md`](docs/ROADMAP.md) for the phased port plan.

## License

MIT (to be added).
