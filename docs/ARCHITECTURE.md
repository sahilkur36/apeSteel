# apeSteel — architecture

This document describes the **layered, composition-based** structure of the
`apeSteel` package. It is the contract that every new module must respect.

> **Audience.** A structural engineer who is comfortable with Python and has
> the AISC code at hand. The doc names the AISC equations directly; it does
> not re-explain them.

---

## 1. Layering at a glance

```
┌──────────────────────────────────────────────────────────────────────┐
│  apeSteel.checks                                                     │
│    BeamCheck (facade) — orchestrates calculators, owns no math       │
└─────────────▲────────────────────────────────────────────────────────┘
              │ uses
┌─────────────┴────────────────────────────────────────────────────────┐
│  apeSteel.flexure      apeSteel.shear      apeSteel.serviceability   │
│  apeSteel.classification        apeSteel.seismic                     │
│  → each returns a typed `Report` frozen dataclass                    │
└─────────────▲────────────────────────────────────────────────────────┘
              │ consumes
┌─────────────┴────────────────────────────────────────────────────────┐
│  apeSteel.sections                                                   │
│    .geometry      — pure shape (no Fy involved)                      │
│    .properties    — SectionProperties (Ag, Ix, Sx, Zx, rts, J, Cw…)  │
│    .catalog       — AISC v16, IPE/IPEA/HE adapters                   │
└─────────────▲────────────────────────────────────────────────────────┘
              │ depends on
┌─────────────┴────────────────────────────────────────────────────────┐
│  apeSteel.core                                                       │
│    .units        — baseUnits re-export + BASE assertion              │
│    .materials    — SteelMaterial, A992, A572Gr50, S355, …            │
│    .result_types — AISCClauseReference + Report base                 │
└──────────────────────────────────────────────────────────────────────┘
```

Each layer depends **only on the layers strictly below it**. Tests enforce
this by inspecting imports.

---

## 2. The composition spine

Every analysis pipeline is the same chain:

```
SectionGeometry  ──►  SectionProperties  ──►  Member  ──►  Report
              user OR catalog              + material   = compute step
                                           + lengths
                                           + Cb
```

- `SectionGeometry` (protocol) — anything that can answer: "what are my plates
  and what are their dimensions?" Concrete: `DoublySymmetricISection`,
  `BuiltUpPlateGirder`, future `Channel`, `HSSRectangular`, etc.
- `SectionProperties` (frozen dataclass) — the universal currency. Every
  calculator below this point talks to `SectionProperties`, never to a
  specific shape class. This is the key abstraction.
- `SteelMaterial` (frozen dataclass) — `Fy, Fu, E, G, density_rho, Ry, Rt`.
- `Member` (frozen dataclass) — bundles `(SectionProperties, SteelMaterial,
  unbraced_length_top_flange_Lb_top, unbraced_length_bot_flange_Lb_bot,
  lateral_torsional_buckling_modification_factor_Cb)`.
- `Report` (frozen dataclass, one per calculator) — `phi`, `nominal_strength`,
  `phi_strength_LRFD`, `omega_strength_ASD`, `governing_limit_state`, full
  intermediate quantities echoed, and `cited_clauses: tuple[AISCClauseReference, ...]`.

No calculator owns a `Beam`. No `Beam` owns a calculator. The `BeamCheck`
facade owns *neither* — it owns a `Member` and a strategy for which
calculators to run.

---

## 3. Why composition, not inheritance

The old `to_review/sectionProperties.py` mixes geometry, material, and check
logic into one `WSection` class. That couples three orthogonal concerns and
makes it hard to:

- swap a catalog section in (it doesn't have plate dimensions `bf, tf, h, tw`,
  it has `Ix, Zx, ry, rts` directly),
- reuse the F2 calculator from an HSS or Channel context,
- run the same flexural check with different Cb values without rebuilding the
  whole section,
- unit-test the calculator independently of the geometry.

The composition split fixes all four. There is **no abstract base class** for
`SteelSection`. Polymorphism happens at the `SectionProperties` boundary;
upstream of it the concrete shape classes share a Protocol; downstream of it
every calculator works on the same frozen dataclass.

---

## 4. Module map

### `apeSteel.core`

```python
# units.py
import baseUnits as u
assert u.BASE == "N-mm-tonne-s", f"apeSteel requires N-mm-tonne-s base, got {u.BASE!r}"
# re-export the names we use most often
from baseUnits import (
    mm, m, cm, inches, ksi, MPa, kPa, kN, N, kN_m, ...
)
```

```python
# materials.py
@dataclass(frozen=True, slots=True)
class SteelMaterial:
    name: str
    yield_stress_Fy:        float   # in u.MPa (i.e. base units)
    tensile_stress_Fu:      float
    elastic_modulus_E:      float
    shear_modulus_G:        float
    density_rho:            float
    expected_yield_ratio_Ry:    float   # AISC 341 Table A3.1
    expected_tensile_ratio_Rt:  float

A992      = SteelMaterial(name="ASTM A992",     Fy=345*u.MPa, Fu=450*u.MPa, ...)
A572_Gr50 = SteelMaterial(name="ASTM A572 Gr.50", Fy=345*u.MPa, ...)
S355      = SteelMaterial(name="EN S355",       Fy=355*u.MPa, ...)
```

```python
# result_types.py
@dataclass(frozen=True, slots=True)
class AISCClauseReference:
    specification: str       # "AISC 360-22" | "AISC 341-22"
    section: str             # "F2.2"
    equation: str | None     # "F2-5" or None for a paragraph
    page: str | None         # "16.1-49"

@dataclass(frozen=True, slots=True)
class Report:                # base — every concrete report extends it
    cited_clauses: tuple[AISCClauseReference, ...]
    def format(self) -> str: ...
```

### `apeSteel.sections.geometry`

Pure plate dimensions. No `Fy` here. Each concrete class has a
`compute_section_properties() -> SectionProperties` method.

```python
class SectionGeometry(Protocol):
    def compute_section_properties(self) -> SectionProperties: ...

@dataclass(frozen=True, slots=True)
class DoublySymmetricISection:
    flange_width_bf:        float   # u.mm
    flange_thickness_tf:    float
    web_clear_height_hw:    float
    web_thickness_tw:       float
    def compute_section_properties(self) -> SectionProperties: ...

@dataclass(frozen=True, slots=True)
class BuiltUpPlateGirder:
    # for AISC F5 — distinct from F2/F3 so the slender-web policy
    # is selected by *type*, not by a runtime branch.
    ...
```

### `apeSteel.sections.properties`

```python
@dataclass(frozen=True, slots=True)
class SectionProperties:
    # Gross section
    gross_area_Ag:                  float
    # Strong axis (x)
    moment_of_inertia_Ix:           float
    elastic_section_modulus_Sx:     float
    plastic_section_modulus_Zx:     float
    radius_of_gyration_rx:          float
    # Weak axis (y)
    moment_of_inertia_Iy:           float
    elastic_section_modulus_Sy:     float
    plastic_section_modulus_Zy:     float
    radius_of_gyration_ry:          float
    # LTB-specific
    torsional_constant_J:           float
    warping_constant_Cw:            float
    distance_between_flange_centroids_ho: float
    effective_radius_of_gyration_for_LTB_rts: float
    # Web/flange for classification
    flange_width_to_thickness_ratio_bf_2tf:    float
    web_height_to_thickness_ratio_h_tw:         float
    # Bookkeeping
    source: SectionGeometry | CatalogRow   # for trace
```

### `apeSteel.sections.catalog`

```python
class AISCv16Catalog:
    """Wraps the AISC v16 pickle. Returns CatalogRow (pydantic v2)
    rows, and adapts them to SectionProperties."""
    def get(self, manual_label: str) -> CatalogRow: ...
    def get_geometry(self, manual_label: str) -> SectionGeometry: ...

class EuropeanIPECatalog:    ...
class EuropeanIPEACatalog:   ...
class EuropeanHECatalog:     ...
```

Pydantic v2 is used **only** here: to validate that a pickle row has all the
fields we need (with the right type). Once validated, we leave the pydantic
world and hand a `SectionProperties` frozen dataclass downstream.

### `apeSteel.classification`

```python
def classify_flexural_compactness_B4(
    section_properties: SectionProperties,
    material: SteelMaterial,
) -> FlexuralCompactnessReport: ...   # AISC 360 Table B4.1b

def classify_seismic_compactness_341_D1(
    section_properties: SectionProperties,
    material: SteelMaterial,
    ductility_level: Literal["highly_ductile", "moderately_ductile"],
    axial_demand_ratio_Ca: float = 0.0,
) -> SeismicCompactnessReport: ...    # AISC 341 Table D1.1
```

### `apeSteel.flexure`

One module per F-chapter section:

- `F2_compact_doubly_symmetric.py`
- `F3_noncompact_flange.py`
- `F4_singly_symmetric.py`
- `F5_slender_web_plate_girder.py`
- `lateral_torsional_buckling.py` — shared `Lp`, `Lr`, `Mn(Lb)` machinery.

The doubly-symmetric flexural facade (inside `flexure/`, not yet the global
facade) decides which F-section applies based on the
`FlexuralCompactnessReport` and the geometry type. **Both flanges** are
checked: `Lb_top` and `Lb_bot` are first-class inputs.

### `apeSteel.shear`

`G2_doubly_symmetric.py` — `Cv1`, `Cv2`, `kv` for unstiffened vs stiffened
webs, tension-field eligibility per F5/G2.

### `apeSteel.serviceability`

`simple_beam_deflections.py` — closed-form UDL, point-load, cantilever
deflections; L/360 and L/240 comparisons; camber as 1.5×δ_DL.

### `apeSteel.seismic`

`panel_zone_341.py` — column-flange tension check (`1.8·bf·tf·Ry·Fy`),
`tcf` limit, etc. Future: SMF/IMF/OMF system checks, BRBF, EBF, SPSW.

### `apeSteel.checks`

`doubly_symmetric_i_beam_check.py` — the **single class a casual user
constructs**. Bundles a `Member` plus the strategy for which calculators to
run, and returns one `BeamCheckReport` that aggregates every sub-report.

---

## 5. Data-flow example

```
DoublySymmetricISection(bf, tf, hw, tw)              ← user input
        │
        │ .compute_section_properties()
        ▼
SectionProperties(Ag, Ix, Sx, Zx, ry, rts, J, Cw…)   ← canonical currency
        │
        ├─► classify_flexural_compactness_B4(props, A992)      → FlexuralCompactnessReport
        ├─► classify_seismic_compactness_341_D1(props, A992)   → SeismicCompactnessReport
        ├─► F2_compute_Mn(props, A992, Lb_top, Cb)             → FlexureF2Report  (top)
        ├─► F2_compute_Mn(props, A992, Lb_bot, Cb)             → FlexureF2Report  (bot)
        └─► G2_compute_Vn(props, A992, kv)                     → ShearG2Report
        │
        ▼
BeamCheck.run() aggregates ───► BeamCheckReport
```

No global state. Every step is a pure function of its inputs.

---

## 6. Rules of the road

1. **Every module top:**
   ```python
   import baseUnits as u
   assert u.BASE == "N-mm-tonne-s", f"apeSteel needs N-mm-tonne-s, got {u.BASE!r}"
   ```
2. **No `print` in `src/apeSteel/`.** Reports format themselves via
   `__str__` and `.format()`. Logging is allowed via the standard `logging`
   module, never `print`.
3. **No mutation.** Every dataclass is `frozen=True, slots=True`.
4. **No `Any`.** pyright strict will fail the build.
5. **No bare numbers in calculators.** Every magic constant gets a name and
   a citation, e.g. `LATERAL_TORSIONAL_BUCKLING_REDUCED_STRESS_FACTOR_0p7 = 0.7  # AISC F2-2 (defines 0.7Fy)`.
6. **Tests are golden.** For every equation we port from the spreadsheet,
   there is one CSV in `tests/golden/` that pins the exact value the
   spreadsheet produces for a representative input.

---

## 7. What is intentionally *not* in this design

- No global "Project" or "Model" object. apeSteel is a library, not a CAE.
- No dynamic dispatch by string. Picking F2 vs F3 vs F5 is done by *type* of
  the `SectionGeometry` and by inspecting the `FlexuralCompactnessReport` —
  never by a `match section_type:` on a string.
- No mixed unit input. The facade rejects raw numbers; everything that
  enters must already be multiplied by a `baseUnits` constant.
- No I/O coupling. The library never touches a file outside
  `sections/catalog/data/`. ETABS/Robot/manual load extraction belongs in
  the user's notebook, not in `apeSteel`.
