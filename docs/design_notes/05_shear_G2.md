# Design note 05 — Shear per AISC 360 §G2

> **Status:** design, not yet implemented.
> **Drives:** `apeSteel.shear.G2_doubly_symmetric`.
> **Spreadsheet rows ported:** cells `B100` – `B107` of `Seccion Tipo I`,
> plus shear-related rows in `Plate Girders`.

---

## 1. Scope

For a doubly-symmetric I-shape in shear about the strong axis, §G2 gives:

```
Vn = 0.6 · Fy · Aw · Cv1                       (Eq. G2-1, web yielding / inelastic buckling)
Vn = 0.6 · Fy · Aw · Cv1 + tension-field term  (Eq. G2-7, when TFA permitted)
```

with `Aw = d · tw` for rolled W and `Aw = hw · tw` for plate girders.

Three regimes for `Cv1`:

```
λ_w = h/tw

if λ_w ≤ 1.10 · √(kv·E/Fy):
    Cv1 = 1.0                                          (Eq. G2-3, yielding)
elif λ_w ≤ 1.37 · √(kv·E/Fy):
    Cv1 = (1.10 · √(kv·E/Fy)) / λ_w                    (Eq. G2-4, inelastic)
else:
    Cv1 = (1.51 · E · kv) / (λ_w² · Fy)                (Eq. G2-5, elastic)
```

The spreadsheet implements this exactly (cells `B103`, `B104`, `B106`).
`kv = 5.0` for unstiffened webs is hard-coded in cell `B31`.

For stiffened webs (transverse stiffener spacing `a`):

```
kv = 5 + 5 / (a/h)²       when a/h ≤ 3
kv = 5                    when a/h > 3 or a/h > (260/(h/tw))²
```

---

## 2. φ factor

`φv = 0.90` for the doubly-symmetric I-shape webs in §G2.1(a)
**when `h/tw ≤ 2.24·√(E/Fy)`** (rolled). Otherwise `φv = 0.90` still
applies but Cv1 is no longer 1.0. For built-up girders `φv = 0.90`.

---

## 3. Tension-field action (§G2.2)

Permitted when, **simultaneously**:

- The panel is not an end panel.
- `2·Aw / (Afc + Aft) ≤ 2.5`
- `h / bfc ≤ 6` and `h / bft ≤ 6`
- `a/h ≤ 3` and `a/h ≤ (260 / (h/tw))²`

When permitted, the TFA contribution adds to `Vn`. The spreadsheet
implements TFA in cells `B79`–`B82`. We will port it as a separate path
behind `tension_field_action_permitted: bool` so the user makes the
detail decision consciously.

---

## 4. Public API

```python
@dataclass(frozen=True, slots=True)
class ShearG2Report(Report):
    web_slenderness_ratio_lambda_w:   float
    web_plate_buckling_coefficient_kv: float
    yielding_limit_lambda_1:           float    # 1.10·√(kv·E/Fy)
    inelastic_limit_lambda_2:          float    # 1.37·√(kv·E/Fy)
    web_shear_strength_coefficient_Cv1: float
    web_area_Aw:                       float
    nominal_shear_strength_Vn:         float
    phi_shear_strength_phi_Vn_LRFD:    float
    governing_regime: Literal["yielding", "inelastic_buckling", "elastic_buckling"]
    tension_field_action_permitted: bool


def compute_shear_strength_G2_doubly_symmetric(
    section_properties: SectionProperties,
    material: SteelMaterial,
    transverse_stiffener_spacing_a: float | None = None,
    tension_field_action_permitted: bool = False,
) -> ShearG2Report: ...
```

When `transverse_stiffener_spacing_a` is `None`, the web is treated as
unstiffened and `kv = 5`. When TFA is requested, the function checks the
four eligibility conditions and raises if any fail.

---

## 5. Citations

```python
cited_clauses = (
    AISCClauseReference("AISC 360-22", "G2.1", "G2-1", "16.1-65"),
    AISCClauseReference("AISC 360-22", "G2.1", "G2-2", "16.1-65"),
    AISCClauseReference("AISC 360-22", "G2.1", "G2-3", "16.1-66"),
    AISCClauseReference("AISC 360-22", "G2.1", "G2-4", "16.1-66"),
    AISCClauseReference("AISC 360-22", "G2.1", "G2-5", "16.1-66"),
    AISCClauseReference("AISC 360-22", "G2.2", "G2-7 to G2-9", "16.1-67"),
)
```

---

## 6. Golden test

`tests/golden/shear_G2.csv` — four rows: compact web (yielding), inelastic
buckling, elastic buckling, and one stiffened-web case with TFA.

---

## 7. Open questions

1. **What does §G2 expect for `h`?** AISC v16 publishes `h` for catalog
   sections (clear distance between flanges, less fillet). For user-built
   plates we use `hw` (the user-supplied clear web height). Documented in
   `SectionProperties.web_height_to_thickness_ratio_h_tw`.
2. **End panel detection.** The library cannot know whether a panel is an
   end panel; the caller must declare via `is_end_panel: bool` when TFA
   is requested.
