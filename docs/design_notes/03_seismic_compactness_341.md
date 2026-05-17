# Design note 03 — Seismic compactness per AISC 341 §D1

> **Status:** design, not yet implemented.
> **Drives:** `apeSteel.classification.seismic_compactness_341_D1`.
> **Spreadsheet rows ported:** cells `B59`, `B63`, `B68`, `B71`, `B85` of
> `Seccion Tipo I`.

Seismic compactness is the second classifier sitting next to §B4. Where
§B4 asks *"will the section reach Mp before local buckling under static
demand?"*, AISC 341 asks *"can the section sustain Mp through the cyclic
demand expected of a ductile fuse?"* — a stricter bar.

---

## 1. Scope

For a doubly-symmetric I-shape used as a fuse element (beam in SMF, brace
in BRBF, link in EBF, etc.), AISC 341-22 §D1.1 imposes element slenderness
limits parameterised by ductility level:

| Ductility | Flange `bf/(2·tf)` ≤ | Web `h/tw` ≤ |
| --- | --- | --- |
| **Moderately ductile** (`λ_md`) | `0.40 · √(E/Fy)` | function of `Ca = Pu/(φc·Py)` |
| **Highly ductile** (`λ_hd`) | `0.30 · √(E/Fy)` | function of `Ca` |

For beams in moment frames with negligible axial demand (`Ca ≈ 0`):

| Ductility | Flange | Web (Case BH1, Ca = 0) |
| --- | --- | --- |
| Highly ductile | `λ_hd_f = 0.30 · √(E/Fy)` | `λ_hd_w = 2.57 · √(E/Fy) · (1 − 1.04·Ca)` ≈ `2.57 · √(E/Fy)` |
| Moderately ductile | `λ_md_f = 0.40 · √(E/Fy)` | `λ_md_w = 3.96 · √(E/Fy) · (1 − 3.04·Ca)` ≈ `3.96 · √(E/Fy)` |

The spreadsheet uses:

- `0.30 · √(E/Fy)` for the flange (cell `B59`) — matches `λ_hd`.
- `2.45 · √(E/Fy)` for the web (cell `B63`) — close to but not exactly
  AISC 341-22 (which is `2.57` for highly ductile, `Ca = 0`). The
  spreadsheet appears to be referencing an older edition of AISC 341
  (possibly 2010 or 2016, which used different coefficients). The Python
  port will **default to AISC 341-22** values but expose the older
  coefficients via a `code_edition` keyword.

---

## 2. The seismic LTB length limit `Lb,max`

In addition to local slenderness, AISC 341-22 §D1.2b restricts the
unbraced length of beams in moderate-and-higher-ductility systems:

```
Lb_max_hd = 0.086 · ry · (E / Fy)        # highly ductile  (Eq. D1-2)
Lb_max_md = 0.19  · ry · (E / Fy)        # moderately ductile (Eq. D1-1)
```

The spreadsheet uses `0.086 · ry · (E/Fy)` (cell `B71`/`B85`) — matches
the highly-ductile limit.

These limits are not the §F2 `Lp` (yielding plateau) — they are *stricter*.
A beam can satisfy `Lb ≤ Lp` (no LTB strength penalty) and still violate
`Lb ≤ Lb_max_hd` (insufficient cyclic ductility).

---

## 3. Public API

```python
from typing import Literal
from dataclasses import dataclass

DuctilityLevel = Literal["highly_ductile", "moderately_ductile"]


@dataclass(frozen=True, slots=True)
class SeismicPlateLimit:
    slenderness_ratio_lambda: float
    seismic_compact_limit_lambda_seismic: float
    is_seismically_compact: bool


@dataclass(frozen=True, slots=True)
class SeismicLengthLimit:
    unbraced_length_Lb:           float
    seismic_limit_Lb_max:         float
    is_seismic_length_acceptable: bool


@dataclass(frozen=True, slots=True)
class SeismicCompactnessReport(Report):
    ductility_level: DuctilityLevel
    flange:  SeismicPlateLimit
    web:     SeismicPlateLimit
    length:  SeismicLengthLimit
    is_seismically_compact_section: bool   # all three checks


def classify_seismic_compactness_341_D1(
    section_properties: SectionProperties,
    material:           SteelMaterial,
    ductility_level:    DuctilityLevel,
    unbraced_length_Lb: float,
    axial_demand_ratio_Ca: float = 0.0,
    code_edition: Literal["AISC 341-22", "AISC 341-16", "AISC 341-10"] = "AISC 341-22",
) -> SeismicCompactnessReport: ...
```

Defaults:

- `axial_demand_ratio_Ca = 0.0` is reasonable for a pure beam. For columns,
  the caller must pass `Ca = Pu / (φc · Py)` (or the ASD equivalent).
- `code_edition = "AISC 341-22"` is the current default. The user can
  override to the 2016 or 2010 edition for legacy projects.

---

## 4. Coefficients per edition (table)

The actual numeric coefficients live in one place: a module-level dict in
`apeSteel.classification.seismic_compactness_341_D1`:

```python
_FLANGE_LIMIT_COEFF_HD: Mapping[str, float] = {
    "AISC 341-22": 0.30,
    "AISC 341-16": 0.30,
    "AISC 341-10": 0.30,
}
_FLANGE_LIMIT_COEFF_MD: Mapping[str, float] = {
    "AISC 341-22": 0.40,
    "AISC 341-16": 0.38,
    "AISC 341-10": 0.38,
}
_WEB_LIMIT_COEFF_HD_BASE: Mapping[str, float] = {
    "AISC 341-22": 2.57,
    "AISC 341-16": 2.57,
    "AISC 341-10": 2.45,        # matches the spreadsheet
}
_WEB_LIMIT_COEFF_HD_CA: Mapping[str, float] = {
    "AISC 341-22": 1.04,
    "AISC 341-16": 1.04,
    "AISC 341-10": 0.0,         # legacy: no Ca dependence
}
# … etc.
```

The base coefficient `2.45` for the 2010 edition is what lets the v1 port
reproduce the spreadsheet to the digit while still supporting modern code.

---

## 5. Citations carried in the report

```python
cited_clauses = (
    AISCClauseReference(
        specification="AISC 341-22",
        section="D1.1",
        equation=None,
        page="9.1-19",
    ),
    AISCClauseReference(
        specification="AISC 341-22",
        section="Table D1.1",
        equation=None,
        page="9.1-20",
    ),
    AISCClauseReference(
        specification="AISC 341-22",
        section="D1.2b",
        equation="D1-1, D1-2",
        page="9.1-21",
    ),
)
```

---

## 6. Golden test

`tests/golden/seismic_compactness_341.csv` covers six combinations:

| section | code_edition | duct | Fy | Ca | Lb [m] | passes_flange | passes_web | passes_length | is_seismically_compact |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| user 300×22 / 350×12 | 341-10 | highly_ductile | 345 | 0.0 | 1.0 | true | true | … | … |
| user 300×22 / 350×12 | 341-22 | highly_ductile | 345 | 0.0 | 1.0 | true | true | … | … |
| W24X94 (catalog)     | 341-22 | highly_ductile | 345 | 0.0 | 1.5 | … | … | … | … |
| W24X94 (catalog)     | 341-22 | moderately_ductile | 345 | 0.0 | 2.5 | … | … | … | … |

The legacy 341-10 row is the one that must reproduce the spreadsheet to
the digit, because that's the edition the spreadsheet was built against.

---

## 7. Open questions

1. **What does AISC 341 require for *built-up* welded I-shapes?** The
   answer (§D1.1 commentary) is the same `λ` limits, but with the web
   height taken between flange-to-web welds rather than fillet radius.
   For user-built sections we use the full `hw` (the user-supplied
   web clear height); for rolled W shapes we use `T = d − 2·kdes`. The
   `SectionProperties.web_height_to_thickness_ratio_h_tw` field already
   distinguishes these because the geometry vs catalog adapters compute
   it differently. The classifier just trusts what it's given.
2. **Should we surface the seismic LTB limit `Lb_max` even when the user
   didn't ask for a seismic check?** Recommendation: no — keep the §D1
   classifier separate. The flexure facade can call both classifiers and
   merge.
