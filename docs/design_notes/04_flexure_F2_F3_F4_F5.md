# Design note 04 — Flexure per AISC 360 §F2–F5

> **Status:** design, not yet implemented.
> **Drives:** `apeSteel.flexure.*`.
> **Spreadsheet rows ported:** cells `B69` – `B99` of `Seccion Tipo I`,
> plus the entire `Plate Girders` sheet (F5).

The flexure layer is the meat of the library. Four AISC sections, each
with its own slenderness regime and limit-state structure.

---

## 1. Which §F section applies?

The classifier decides:

| Section | Geometry | Flange | Web |
| --- | --- | --- | --- |
| **F2** | doubly-symmetric I | compact | compact |
| **F3** | doubly-symmetric I | non-compact or slender | compact |
| **F4** | singly-symmetric I (incl. channel) | any | compact or non-compact (not slender) |
| **F5** | doubly- or singly-symmetric I | any | slender |
| **F6** | I-shape bent about weak axis | — | (out of scope for v1) |
| **F7** | square / rectangular HSS | any | any | (out of scope for v1) |

The user-built `DoublySymmetricISection` always routes to F2/F3/F5 (never
F4). The `BuiltUpPlateGirder` type **always** routes to F5 because that's
the only reason to instantiate it. The classification report selects
F2 vs F3 within the doubly-symmetric branch.

---

## 2. AISC §F2 — compact doubly-symmetric I

The simplest and most common branch. Three states:

```
Lb ≤ Lp         Mn = Mp                         (yielding plateau)
Lp < Lb ≤ Lr   Mn = Cb·(Mp − (Mp − 0.7·Fy·Sx)·((Lb − Lp)/(Lr − Lp)))   (inelastic LTB)
Lb > Lr         Mn = Cb · Mcr   (elastic LTB, Eq. F2-4)
```

In **all** cases, `Mn ≤ Mp`.

### Lp, Lr — limiting unbraced lengths

```
Lp = 1.76 · ry · √(E / Fy)                                        (Eq. F2-5)

Lr = 1.95 · rts · (E / (0.7 · Fy)) ·
     √( (J · c) / (Sx · ho) ) ·
     √( 1 + √( 1 + 6.76 · ((0.7·Fy · Sx · ho) / (E · J · c))² ) ) (Eq. F2-6)
```

where `c = 1` for doubly-symmetric I-shapes (`c = ho/2 · √(Iy/Cw)` for
channels, F2 commentary).

### Elastic critical moment Mcr (Eq. F2-4)

```
Mcr = (Cb · π² · E / (Lb / rts)²) · √(1 + 0.078 · (J·c) / (Sx · ho) · (Lb/rts)²)
```

The spreadsheet formulates `Fcr` (stress) instead of `Mcr` (moment) and
then multiplies by `Sx`; both are equivalent. We will store `Mcr` directly
in the report.

### Cb — moment modification factor (Eq. F1-1)

```
Cb = (12.5 · Mmax) / (2.5·Mmax + 3·MA + 4·MB + 3·MC) · Rm
```

`Rm = 1.0` for doubly-symmetric beams. The library exposes a helper that
takes the four moments at quarter-points and returns `Cb`. Where the user
doesn't have them, they pass `Cb = 1.0` explicitly.

### Both flanges checked separately

The spreadsheet does this and so do we. The top-flange and bottom-flange
unbraced lengths can differ:

- Composite floor beams: top flange continuously braced by the slab
  (`Lb_top → 0`); bottom flange braced only at intermediate beams or
  at supports.
- Cantilever moment reversal under uplift.
- Beams in moment frames under cyclic seismic demand — both flanges go
  into compression alternately.

Two `FlexureF2Report`s are produced (one per flange) and the controlling
one is highlighted in the `BeamCheckReport`.

---

## 3. AISC §F3 — non-compact / slender flange

When the flange is non-compact (compact web), `Mn` is the lesser of LTB
(same §F2 machinery) and **flange local buckling (FLB)**:

```
Non-compact flange (Eq. F3-1):
  Mn = Mp − (Mp − 0.7·Fy·Sx) · ((λ_f − λ_pf) / (λ_rf − λ_pf))

Slender flange (Eq. F3-2):
  Mn = 0.9 · E · kc · Sx / λ_f²
```

with `kc = 4 / √(h/tw)`, bounded `0.35 ≤ kc ≤ 0.76` (Table B4.1b
footnote `[c]`).

The spreadsheet only implements the **non-compact** branch (cell `B98`).
We'll port both for completeness.

---

## 4. AISC §F4 — singly-symmetric I-shapes

Out of scope for v1 of the LTB port (the spreadsheet doesn't touch it). We
*will* expose the module skeleton so that a future user can plug in a tee
or a channel without restructuring. The skeleton just raises
`NotImplementedError` with a pointer to the design note.

---

## 5. AISC §F5 — slender-web plate girder

The `Plate Girders` sheet of the spreadsheet does this. Key additions
beyond §F2/F3:

### Web bend-buckling reduction factor `Rpg` (Eq. F5-6)

```
Rpg = 1 − (aw / (1200 + 300·aw)) · (hc/tw − 5.7·√(E/Fy)) ≤ 1.0

aw = (hc · tw) / (bfc · tfc)        but aw ≤ 10
```

The spreadsheet implements this exactly (cells `B87`–`B88`).

### Compression-flange yielding (Eq. F5-1)

```
Mn = Rpg · Fy · Sxc
```

### Lateral-torsional buckling (Eq. F5-2 to F5-4)

Same three-regime structure as §F2 but with different Lp, Lr, and Fcr
formulas (involving the compression-flange-only radius of gyration
`rt = bfc / √(12·(1 + aw/6))`).

```
Lp = 1.1 · rt · √(E/Fy)
Lr = π · rt · √(E / (0.7·Fy))
Fcr = (Cb · π² · E) / (Lb/rt)²    (elastic, ≤ Fy)
```

### Compression-flange local buckling (Eq. F5-7 / F5-8)

Same machinery as §F3 but multiplied by `Rpg`.

### Vertical web-pandling limit (proportioning, §F13.2)

```
h/tw ≤ smaller of  (260, 11.7·√(E/Fy))     when a/h ≤ 1.5
h/tw ≤ smaller of  (260, 0.42·E/Fy)        when a/h > 1.5
```

Cell `B71` of the `Plate Girders` sheet.

### Tension-field action (§G2.2)

The web shear capacity is enhanced if TFA is allowed:

```
TFA permitted only if:
  - panel is not an end panel
  - a/h ≤ 3 and a/h ≤ (260 / (h/tw))²
  - 2·Aw / (Afc + Aft) ≤ 2.5
  - h/bfc ≤ 6  and  h/bft ≤ 6
```

The spreadsheet checks this in cell `B82`.

---

## 6. Public API

```python
@dataclass(frozen=True, slots=True)
class FlexureF2Report(Report):
    Cb_used:                          float
    unbraced_length_Lb:               float
    limiting_length_plastic_Lp:       float
    limiting_length_inelastic_LTB_Lr: float
    plastic_moment_Mp:                float
    elastic_LTB_moment_Mcr:           float
    governing_regime: Literal["yielding", "inelastic_LTB", "elastic_LTB"]
    nominal_flexural_strength_Mn:     float
    phi_flexural_strength_phi_Mn_LRFD: float


def compute_flexural_strength_F2_compact_doubly_symmetric(
    section_properties: SectionProperties,
    material: SteelMaterial,
    unbraced_length_Lb: float,
    lateral_torsional_buckling_modification_factor_Cb: float,
) -> FlexureF2Report: ...


def compute_flexural_strength_F3_noncompact_or_slender_flange(
    section_properties: SectionProperties,
    flange_classification: PlateClassification,
    material: SteelMaterial,
    unbraced_length_Lb: float,
    lateral_torsional_buckling_modification_factor_Cb: float,
    construction: Literal["rolled", "welded"] = "rolled",
) -> FlexureF3Report: ...


def compute_flexural_strength_F5_slender_web_plate_girder(
    section_properties: SectionProperties,
    flange_classification: PlateClassification,
    material: SteelMaterial,
    unbraced_length_Lb: float,
    lateral_torsional_buckling_modification_factor_Cb: float,
) -> FlexureF5Report: ...
```

### Shared LTB machinery

The `Lp`, `Lr`, `Mcr` formulas are reused. They live in
`apeSteel.flexure.lateral_torsional_buckling` and each take their geometry
ingredients explicitly:

```python
def compute_limiting_length_plastic_Lp(
    radius_of_gyration_weak_axis_ry: float,
    elastic_modulus_E: float,
    yield_stress_Fy: float,
) -> float: ...

def compute_limiting_length_inelastic_LTB_Lr(
    effective_radius_of_gyration_rts: float,
    distance_between_flange_centroids_ho: float,
    torsional_constant_J: float,
    elastic_section_modulus_Sx: float,
    elastic_modulus_E: float,
    yield_stress_Fy: float,
    section_constant_c: float = 1.0,
) -> float: ...

def compute_elastic_LTB_moment_Mcr(
    elastic_section_modulus_Sx: float,
    effective_radius_of_gyration_rts: float,
    distance_between_flange_centroids_ho: float,
    torsional_constant_J: float,
    elastic_modulus_E: float,
    unbraced_length_Lb: float,
    lateral_torsional_buckling_modification_factor_Cb: float,
    section_constant_c: float = 1.0,
) -> float: ...
```

This keeps each function short, named, and individually testable. The
public `compute_flexural_strength_F2_...` is a 30-line orchestrator.

---

## 7. Citations carried in every report

```python
cited_clauses = (
    AISCClauseReference("AISC 360-22", "F2",   "F2-1", "16.1-49"),
    AISCClauseReference("AISC 360-22", "F2.2", "F2-2", "16.1-49"),
    AISCClauseReference("AISC 360-22", "F2.2", "F2-3", "16.1-49"),
    AISCClauseReference("AISC 360-22", "F2.2", "F2-4", "16.1-49"),
    AISCClauseReference("AISC 360-22", "F2.2", "F2-5", "16.1-49"),
    AISCClauseReference("AISC 360-22", "F2.2", "F2-6", "16.1-50"),
)
```

---

## 8. Golden tests

`tests/golden/flexure_F2.csv` — six rows spanning the three regimes for
each flange, including the spreadsheet's default `100×6 / 300×4`
plate-built section at `Fy = 345 MPa`.

`tests/golden/flexure_F3.csv` — three rows for non-compact flange.

`tests/golden/flexure_F5.csv` — five rows from the `Plate Girders` sheet
defaults.

Each row pins:

```
Lb, Lp, Lr, Mp, Mcr, regime, Mn, phi_Mn
```

with `math.isclose(rel_tol=1e-9)`.

---

## 9. Open questions

1. **`c` for channels in F2-6.** The spreadsheet only handles
   doubly-symmetric I. We default `c = 1.0` and document; channels come
   later via the F4 module.
2. **`Cb` default.** Do we accept `Cb = 1.0` silently as a default arg, or
   require the caller to pass it? Recommendation: require it. Conservative
   default behaviour is a sin in code-of-record software.
3. **Seismic limit interplay.** §F2 says `Mn = Mp` for `Lb ≤ Lp`. §341
   says the beam must additionally satisfy `Lb ≤ Lb_max_hd`. Should §F2
   silently apply both? Recommendation: no — §F2 reports the static §F2
   strength. The seismic-compactness report is separate. The `BeamCheck`
   facade is the place to refuse a seismic detail that satisfies §F2 but
   fails §D1.2b.
