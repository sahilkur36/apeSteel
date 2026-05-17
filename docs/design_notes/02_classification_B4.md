# Design note 02 — Flexural classification per AISC 360 §B4

> **Status:** design, not yet implemented.
> **Drives:** `apeSteel.classification.flexural_compactness_B4`.
> **Spreadsheet rows ported:** cells `B57` – `B67` of `Seccion Tipo I`.

This is the gatekeeper between F2 (compact), F3 (non-compact flange), F4
(singly-symmetric), and F5 (slender web). Get this wrong and the whole
flexure pipeline picks the wrong code path.

---

## 1. Scope

For a **doubly-symmetric I-shape in flexure** about the strong axis, AISC
360 §B4.1b uses Table B4.1b to classify each plate element:

| Plate element | Case | λ | λ_p | λ_r |
| --- | --- | --- | --- | --- |
| Flange of rolled/welded I (flexure) | 10 (rolled) / 11 (welded) | `bf / (2·tf)` | `0.38 · √(E/Fy)` | `1.0 · √(E/Fy)` (rolled) / `kc·√(E/Fy)` family (welded) |
| Web of doubly-symmetric I (flexure) | 15 | `h / tw` | `3.76 · √(E/Fy)` | `5.70 · √(E/Fy)` |

The element is classified:

- **Compact** if `λ ≤ λ_p`,
- **Non-compact** if `λ_p < λ ≤ λ_r`,
- **Slender** if `λ > λ_r`.

The **section** classification is the *worst* of its plate classifications.

The spreadsheet uses Case 10/15 (rolled) limits even for welded shapes,
which is a known approximation. Our port will:

- Use Case 10/15 for rolled (`Type == "W"`).
- Use Case 11 with `kc = 4 / √(h/tw)`, bounded `0.35 ≤ kc ≤ 0.76`, for
  user-built welded shapes (per AISC §F3.2 footnote).

The original spreadsheet uses `0.38 · √(E/Fy)` and `1.0 · √(E/Fy)` for
the flange in all cases (cells `B60` and `B61`). We will follow the
spreadsheet for the v1 port to pass the golden test, then add the welded
`kc` path behind a keyword argument in v1.1.

---

## 2. Equations to port

From the spreadsheet (renamed to verbose form):

```
flange_slenderness_ratio_lambda_f          =  bf / (2 * tf)             # B58
web_slenderness_ratio_lambda_w             =  hw / tw                   # B62

flange_compact_limit_lambda_pf             =  0.38 * sqrt(E / Fy)       # B60
flange_noncompact_limit_lambda_rf          =  1.00 * sqrt(E / Fy)       # B61

web_compact_limit_lambda_pw                =  3.76 * sqrt(E / Fy)       # B64
web_noncompact_limit_lambda_rw             =  5.70 * sqrt(E / Fy)       # B65
```

The seismic compactness limits `λ_hd` and `λ_md` are **AISC 341**, not §B4,
and live in design note 03. The §B4 layer doesn't know about ductility.

---

## 3. Public API

```python
from typing import Literal
from dataclasses import dataclass

PlateClass = Literal["compact", "non_compact", "slender"]


@dataclass(frozen=True, slots=True)
class PlateClassification:
    slenderness_ratio_lambda: float
    compact_limit_lambda_p:   float
    noncompact_limit_lambda_r: float
    classification:           PlateClass


@dataclass(frozen=True, slots=True)
class FlexuralCompactnessReport(Report):
    flange: PlateClassification
    web:    PlateClassification
    section_classification: PlateClass    # worst of the two


def classify_flexural_compactness_B4(
    section_properties: SectionProperties,
    material: SteelMaterial,
    construction: Literal["rolled", "welded"] = "rolled",
) -> FlexuralCompactnessReport: ...
```

### Inputs vs derived

`section_properties.flange_width_to_thickness_ratio_bf_2tf` and
`web_height_to_thickness_ratio_h_tw` are already in
`SectionProperties` because both the user-defined geometry and the AISC
v16 catalog compute them upstream. The classifier only consumes
`SectionProperties` + `material`; it never inspects plate dimensions.

---

## 4. Citations carried in the report

```python
cited_clauses = (
    AISCClauseReference(
        specification="AISC 360-22",
        section="B4.1b",
        equation=None,
        page="16.1-11",
    ),
    AISCClauseReference(
        specification="AISC 360-22",
        section="Table B4.1b",
        equation="Cases 10 & 15",
        page="16.1-15",
    ),
)
```

---

## 5. Golden test (drives the port)

`tests/golden/classification_B4.csv` will contain the spreadsheet's exact
output for ten section/material combinations spanning compact, non-compact,
and slender in flange and/or web:

| section | construction | Fy [MPa] | λ_f | λ_pf | λ_rf | flange | λ_w | λ_pw | λ_rw | web | section |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| W24X94 (catalog) | rolled | 345 | … | … | … | compact | … | … | … | compact | compact |
| user 300×22 / 350×12 | welded | 345 | … | … | … | … | … | … | … | … | … |
| … | … | … | … | … | … | … | … | … | … | … | … |

The CSV is built by running the spreadsheet once with each input and
copying the cells. The test then re-runs the Python and compares row by
row with `math.isclose(rel_tol=1e-9, abs_tol=1e-12)`.

---

## 6. Open questions

1. **Welded flange `kc` path.** Implement now or postpone? Recommendation:
   port the rolled path first (matches spreadsheet exactly), add `kc` in a
   follow-up PR with its own golden test.
2. **Slender-web routing.** The classifier reports "section is slender,"
   but it's the higher-level facade in `apeSteel.flexure` that picks F5
   instead of F2/F3. The classification module must not import from
   `flexure/` to keep the dependency arrow pointing the right way.
