# Design note 08 — Compression per AISC 360-22 Chapter E

> **Status:** E-0 scaffold done; E-1 W-shape done & validated (1398 tests passing;
> +13 from compression; independent oracle + Excel anchor green; pyright/ruff clean).
> **Drives:** `apeSteel.compression.*`.
> **Spreadsheet source:** engineer's AISC 360-16 Excel workbook (edition ≠ 360-22;
> see §5 below for the testing consequence).

The compression layer follows the same pure-function / frozen-Report / two-anchor
validation pattern established by the flexure layer.

---

## 1. Scope

AISC 360-22 Chapter E applies to members subject to axial compression.
apeSteel covers the following section families:

| Family | Cross-section type | Governing E-section(s) |
| --- | --- | --- |
| W-shape (doubly-symmetric I) | rolled wide-flange | E3 + E7 when slender |
| Tee (WT / MT / ST) | singly-symmetric I | E4 (flexural–torsional) + E7 |
| Channel (C / MC) | singly-symmetric | E4 (flexural–torsional) + E7 |
| Rectangular HSS | closed box | E3 + E7 |
| Round HSS / pipe | closed circular | E3 + E7 |
| Single equal-leg angle | L | E5 |
| Double angle (2L) | 2L | E4 (flexural–torsional) |

Out of scope for v1: built-up I-shapes with non-snug-tight fastened lacing
(§E6.2b), cruciform sections, and any section not listed above.

---

## 2. AISC 360-22 Chapter E equation map

All equations below are from AISC 360-22 Chapter E (pp. 16.1-37 – 16.1-43).
Resistance factor `φ_c = 0.90` (LRFD); safety factor `Ω_c = 1.67` (ASD).

### §E2 — Slenderness limit

```
KL/r ≤ 200                                                       (§E2, p. 16.1-37)
```

Checked for every axis and for every characteristic radius of gyration.
Violations raise a warning; the calculator proceeds (per Commentary §E2, the
limit is not a hard prohibitor).

### §E3 — Flexural buckling of members without slender elements

Applies when all elements are compact or non-compact in compression (Table B4.1a).

```
Fe = π²·E / (KL/r)²                                              (Eq. E3-4, p. 16.1-38)
```

Two regimes based on `KL/r` (equivalently on `Fy/Fe`):

```
KL/r ≤ 4.71·√(E/Fy)   [i.e. Fy/Fe ≤ 2.25]:
    Fcr = [0.658^(Fy/Fe)] · Fy                                   (Eq. E3-2, p. 16.1-38)

KL/r > 4.71·√(E/Fy)   [elastic]:
    Fcr = 0.877·Fe                                                (Eq. E3-3, p. 16.1-38)
```

Nominal strength:

```
Pn = Fcr · Ag                                                     (Eq. E3-1, p. 16.1-38)
φ·Pn = 0.90·Pn    (LRFD)
Pn/Ω = Pn/1.67   (ASD)
```

### §E4 — Torsional and flexural–torsional buckling

Applies to singly-symmetric sections (tee, channel, double angle) and
asymmetric sections. The effective elastic buckling stress is the smaller root
of the three-equation system (Eq. E4-5 / E4-6 for doubly-symmetric, Eq. E4-7
for singly-symmetric, Eq. E4-8 for point-symmetric).

For **doubly-symmetric I-shapes** (torsional buckling governs when KL/r_y is
large relative to KL/r_z):

```
Fe,torsion = (π²·E·Cw / (KL_z)²  +  G·J) / (Ix + Iy)           (Eq. E4-2, p. 16.1-39)
```

For **singly-symmetric I, tee, channel** (flexural–torsional buckling):

```
Fe = ((Fex + Fez) / (2·H)) · [1 − √(1 − 4·Fex·Fez·H / (Fex + Fez)²)]
                                                                  (Eq. E4-5, p. 16.1-39)
H  = 1 − (xo² + yo²) / ro²
ro² = xo² + yo² + Ix/Ag + Iy/Ag                                  (Eq. E4-7, p. 16.1-40)
```

where `xo, yo` are shear-center coordinates relative to the centroid, and
`Fex, Fey, Fez` are the elastic buckling stresses for the three axes (§E4).
The resulting `Fe` replaces `Fe` from §E3-4 in the §E3 Fcr expressions.

### §E5 — Single-angle compression members

Single angles use the modified slenderness ratio:

```
Without lateral or rotational end restraint:
    (KL/r)_eff = 72 + 0.75·(L/r_z)                              (Eq. E5-1, p. 16.1-41)

With lateral restraint at both ends:
    (KL/r)_eff = 60 + 0.8·(L/r_z)                               (Eq. E5-3, p. 16.1-41)
```

The modified `(KL/r)_eff` is substituted directly into the §E3 Fcr equations.
Slender-element reduction (§E7) still applies.

### §E6 — Built-up members

Applies to built-up I-shapes with separated elements (lacing, battens).
The effective slenderness is modified by `(KL/r)_o`:

```
(KL/r)_m² = (KL/r)_o² + (a/r_i)²                               (Eq. E6-1, p. 16.1-42)
```

`a/r_i` is the slenderness of the individual component between fasteners.
The full §E6.2 procedure for snug-tight vs non-snug-tight fasteners is
out of scope for E-1 through E-4; only the §E6.1 welded (or snug-tight)
path is implemented.

### §E7 — Members with slender elements

When any element (flange, web, wall) is slender in compression per Table
B4.1a, the nominal strength is reduced:

```
Pn = Fcr · Aeff                                                   (Eq. E7-1, p. 16.1-42)
```

where `Aeff` is the effective cross-sectional area computed using the
**effective width** of each slender element:

```
be = 1.92·t · √(E/f) · [1 − (0.34 / (b/t)·√(E/f))] ≤ b         (Eq. E7-2, p. 16.1-43)

f = Pn_no_slender / Ag    (iterative — §E7 Commentary)
```

For round HSS / pipe with slender walls, `Aeff` uses the Q-factor approach
(§E7.2(c)), which **differs from the 360-16 Q-factor method** applied across
all slender elements in that edition. This is the primary source of divergence
between apeSteel (360-22) and the Excel anchor (360-16); see §5.

---

## 3. Module layout

```
src/apeSteel/
├── compression/
│   ├── __init__.py
│   ├── _common.py                   # shared φ_c, Ω_c, slenderness limit helpers
│   ├── effective_length_E2.py       # KL/r check + warning; no Fcr here
│   ├── flexural_buckling_E3.py      # Fe (Eq. E3-4), Fcr (Eq. E3-2/E3-3), Pn (Eq. E3-1)
│   ├── torsional_flexural_E4.py     # Fe_torsion, Fe_flexural_torsional (Eq. E4-2 / E4-5)
│   ├── single_angle_E5.py           # modified KL/r (Eq. E5-1 / E5-3)
│   ├── built_up_E6.py               # (KL/r)_m modifier (Eq. E6-1); snug-tight path only
│   ├── slender_elements_E7.py       # effective width be (Eq. E7-2), Aeff, Pn (Eq. E7-1)
│   └── compression_strength.py      # orchestrator: routes by section type, applies E3–E7
└── sections/
    └── compression_properties.py    # CompressionSectionProperties (universal input contract)
```

### `CompressionSectionProperties`

The universal input contract for all compression calculators. Mirrors the role
that `SectionProperties` plays in the flexure layer — every calculator below
this point talks to `CompressionSectionProperties`, never to a concrete
shape class.

```python
@dataclass(frozen=True, slots=True)
class CompressionSectionProperties:
    # Gross section
    gross_area_Ag:                                   float   # mm²
    # Radii of gyration for flexural buckling
    radius_of_gyration_x_rx:                         float   # mm
    radius_of_gyration_y_ry:                         float   # mm
    radius_of_gyration_min_r:                        float   # mm (min of rx, ry)
    # Torsional properties (needed for §E4 / §E6)
    torsional_constant_J:                            float   # mm⁴
    warping_constant_Cw:                             float   # mm⁶
    # Shear-center coordinates (for §E4 singly-symmetric)
    shear_center_xo:                                 float   # mm (0 for doubly-sym)
    shear_center_yo:                                 float   # mm (0 for doubly-sym)
    polar_radius_of_gyration_ro:                     float   # mm (§E4-7)
    # Elements — per flange + web (or per wall for HSS)
    flange_width_to_thickness_ratio_b_t_flange:      float   # dimensionless
    web_height_to_thickness_ratio_h_tw:              float   # dimensionless
    # Effective-width inputs for §E7 (one per slender element pair)
    slender_flange_width_b_flange:                   float | None   # mm
    slender_flange_thickness_t_flange:               float | None   # mm
    slender_web_clear_height_h:                      float | None   # mm
    slender_web_thickness_tw:                        float | None   # mm
    # Moment-of-inertia terms (for §E4 torsional Fe)
    moment_of_inertia_Ix:                            float   # mm⁴
    moment_of_inertia_Iy:                            float   # mm⁴
    # Bookkeeping
    section_type: Literal[
        "doubly_symmetric_I", "tee", "channel",
        "rect_HSS", "round_HSS", "single_angle", "double_angle"
    ]
    source: object   # SectionGeometry | CatalogRow — for trace
```

`compression_properties.py` lives in `apeSteel.sections` rather than in
`apeSteel.compression` so that the sections layer can populate it from any
geometry source (plate-built, catalog, or user-supplied) without creating a
circular dependency.

### Report dataclasses

Each module returns a frozen `Report`. The orchestrator returns
`CompressionStrengthReport`, which aggregates the sub-reports:

```python
@dataclass(frozen=True, slots=True)
class CompressionStrengthReport(Report):
    # governing effective slenderness
    governing_KL_r:                              float
    governing_axis:  Literal["x", "y", "z", "modified"]
    # intermediate stresses
    elastic_buckling_stress_Fe:                  float   # MPa
    critical_stress_Fcr:                         float   # MPa
    # slender-element reduction
    effective_area_Aeff:                         float | None  # mm² (None if no slender element)
    # strengths
    nominal_compression_strength_Pn:             float   # N
    phi_compression_strength_phi_Pn_LRFD:        float   # N
    compression_strength_Pn_over_Omega_ASD:      float   # N
    # governing limit state
    governing_limit_state: Literal[
        "flexural_buckling_E3",
        "torsional_buckling_E4",
        "flexural_torsional_buckling_E4",
        "single_angle_E5",
        "slender_element_reduction_E7",
    ]
    # sub-reports retained for audit
    slender_elements_report: SlenderElementsE7Report | None
    cited_clauses: tuple[AISCClauseReference, ...]
```

---

## 4. Public API

```python
def compute_compression_strength(
    section_properties: CompressionSectionProperties,
    material: SteelMaterial,
    effective_length_KL_x: float,          # mm (KL about strong axis)
    effective_length_KL_y: float,          # mm (KL about weak axis)
    effective_length_KL_z: float | None,   # mm (KL for torsion); None → same as KL_y
) -> CompressionStrengthReport: ...
```

The orchestrator inside `compression_strength.py`:

1. Calls `effective_length_E2.check_slenderness(...)` — warning if > 200.
2. Calls `flexural_buckling_E3.compute_Fe_flexural(...)` for x and y axes.
3. If `section_type` is singly-symmetric or has a non-zero shear center:
   calls `torsional_flexural_E4.compute_Fe_torsional_or_flexural_torsional(...)`.
4. If `section_type == "single_angle"`: delegates to `single_angle_E5`.
5. Takes `Fe = min(Fe_x, Fe_y, Fe_torsional)` as the governing elastic
   buckling stress.
6. Computes `Fcr` via §E3-2 or §E3-3 (using the governing `Fe`).
7. If any element is slender: calls `slender_elements_E7.compute_Aeff(...)` and
   replaces `Pn = Fcr·Ag` with `Pn = Fcr·Aeff`.
8. Returns `CompressionStrengthReport`.

No caller-visible branching; the route is determined entirely by the
`section_type` field of `CompressionSectionProperties`.

### Citations carried in every report

```python
cited_clauses = (
    AISCClauseReference("AISC 360-22", "E2",   None,   "16.1-37"),
    AISCClauseReference("AISC 360-22", "E3",   "E3-1", "16.1-38"),
    AISCClauseReference("AISC 360-22", "E3",   "E3-2", "16.1-38"),
    AISCClauseReference("AISC 360-22", "E3",   "E3-3", "16.1-38"),
    AISCClauseReference("AISC 360-22", "E3",   "E3-4", "16.1-38"),
    # E4 citations appended when torsional path is taken
    # E7 citations appended when slender elements are present
)
```

---

## 5. Edition decision and testing consequence

### 360-22 vs 360-16

The engineer's Excel workbook implements AISC **360-16**. apeSteel implements
AISC **360-22**. The two editions differ materially only in §E7:

| Aspect | 360-16 | 360-22 |
| --- | --- | --- |
| Slender element reduction | Q-factor (`Qa·Qs`) applied to `Ag` globally | Effective-width `Aeff` (§E7.2) per element |
| Round HSS slender wall | Q factor from §E7.2(b) | Separate `Aeff` expression, §E7.2(c) |
| §E3 / §E4 / §E5 / §E6 | Identical to 360-22 (Fe expressions, Fcr, Pn) | — |

**§E3/E4 are edition-independent.** The `Fe` expressions (Eq. E3-4, E4-2,
E4-5) and the `Fcr` expressions (Eq. E3-2/E3-3) are unchanged between the
two editions.

### Testing architecture

Two independent anchors validate the implementation:

**1. Independent stdlib oracle** (`tests/golden/_chapterE_aisc_oracle.py`)

A self-contained, dependency-free Python module that implements AISC 360-22
§E3/E4/E5/E7 from first principles using only Python stdlib `math`. It serves
as the primary correctness anchor. For the non-slender path the oracle agrees
with apeSteel to full floating-point precision (bit-exact within `rel_tol=1e-9`).
For the slender path (§E7) the oracle also implements 360-22 effective-width,
so agreement is again bit-exact. This oracle **is the ground truth**; the
Excel is a secondary check only.

**2. Excel anchor** (`tests/golden/test_compression_excel_anchor.py`)

Hard-coded against the engineer's 360-16 Excel workbook for a set of
representative sections. The anchor verifies:

- `Fe` flexural (Eq. E3-4): edition-independent — must agree to `rel_tol=1e-6`
  (limited by Excel's display precision).
- `Fe,torsion` (Eq. E4-2): edition-independent — same tolerance.
- `Fcr` and `Pn` for **non-slender** sections: edition-independent — anchored.
- `Pn` for **slender** sections (§E7 path): legitimately diverges between 360-16
  (Q-factor) and 360-22 (effective width). The test documents the expected
  divergence band (typ. < 5 % for lightly slender sections) with an explicit
  comment and an `assertAlmostEqual` with a generous tolerance annotated
  `# 360-22 vs 360-16 divergence — expected, not a bug`.

**Bottom line:** if the oracle and apeSteel agree (bit-exact), the implementation
is correct per 360-22. If the Excel differs only on slender elements, that is
a known, bounded, documented edition difference — not a defect.

---

## 6. Phased delivery

### E-0 — Scaffold ✅ done

- `src/apeSteel/compression/__init__.py` + `_common.py` (φ_c, Ω_c constants).
- `src/apeSteel/sections/compression_properties.py` (`CompressionSectionProperties`
  frozen dataclass).
- Placeholder module stubs raising `NotImplementedError` with design-note
  pointers for E3 through E7.
- `tests/golden/_chapterE_aisc_oracle.py` — standalone oracle (no apeSteel
  imports); covers W-shape E3, tee E4, rect/round HSS E3/E7.
- pyright / ruff clean.

### E-1 — W-shape (doubly-symmetric I) ✅ done

Deliverables (all shipped):

- `flexural_buckling_E3.py`: `compute_Fe_flexural`, `compute_Fcr`, `compute_Pn`.
- `torsional_flexural_E4.py`: `compute_Fe_torsion_doubly_symmetric` (Eq. E4-2).
- `slender_elements_E7.py`: `compute_be_E7_2` (Eq. E7-2), `compute_Aeff_I_shape`.
- `compression_strength.py`: W-shape orchestration path complete.
- `CompressionSectionProperties` populated from `AISCv16Catalog` and from
  `DoublySymmetricISection.compute_section_properties()`.

Test impact: **+13 tests** (10 oracle bit-exact + 3 Excel anchor):

- 10 oracle tests: W8×31, W14×48, W14×145 × three KL values each; §E3
  inelastic + elastic regimes; one §E7 slender-flange case (W6×9 surrogate).
- 3 Excel anchor tests: `Fe` flexural, `Fe,torsion`, `Pn` non-slender — all
  edition-independent, `rel_tol=1e-6`; §E7 divergence documented.
- Project total: 1398 tests passing; pyright strict clean; ruff clean.

### E-2 — Tee and channel (planned)

- `torsional_flexural_E4.py`: `compute_Fe_flexural_torsional_singly_symmetric`
  (Eq. E4-5 / E4-7).
- `CompressionSectionProperties` populated from `AISCv16Catalog` for WT, C, MC
  section types.
- `slender_elements_E7.py`: tee stem and channel web effective-width paths.
- Additional oracle tests (WT8×25, C12×20.7 × two KL).

### E-3 — Rectangular and round HSS (planned)

- Rect HSS: §E3 + §E7.2(a) effective-width for slender walls.
- Round HSS: §E3 + §E7.2(c) reduced area for slender walls.
- `CompressionSectionProperties` populated from `AISCv16Catalog` HSS and PIPE
  types.
- Oracle tests: HSS6×6×¼, HSS8×4×3/16, PIPE 4 STD.

### E-4 — Single and double angle (planned)

- `single_angle_E5.py`: modified `(KL/r)_eff` (Eq. E5-1 / E5-3); feeds Fcr
  via §E3.
- `torsional_flexural_E4.py`: double-angle flexural–torsional path (Eq. E4-5
  with Fex based on x-axis KL/r, Fez from §E4).
- `CompressionSectionProperties` populated from `AISCv16Catalog` L and 2L types.
- Oracle tests: L4×4×½, 2L3×3×¼ (LLBB) × two restraint conditions.

### E-5 — Facade routing, Element methods, φPn-vs-length curve (planned)

- `apeSteel.checks.column_check.ColumnCheck` facade: accepts a catalog label or
  plate-built geometry + material + KL values, routes to the correct
  `compute_compression_strength(...)`, returns `CompressionStrengthReport`.
- `Element.compute_phi_Pn(KL_x, KL_y)` convenience method on the existing
  `Element` class.
- `Element.phi_Pn_vs_length(KL_range)` → `pd.DataFrame` for column-curve
  plots.
- End-to-end test: W14×82 / A992 at KL = 3 m, 6 m, 9 m; oracle-anchored.

---

## 7. Forward note — Chapter H (combined flexure + axial)

AISC 360-22 Chapter H (H1 interaction) requires both `φ·Pn` (from this
chapter) and `φ·Mn` (from Chapter F, already implemented). When Chapter H
is added, the `CompressionStrengthReport.phi_compression_strength_phi_Pn_LRFD`
field and the flexure layer's `phi_flexural_strength_phi_Mn_LRFD` will be
consumed by a new `beam_column_H1_interaction.py` module following the same
pure-function pattern. No changes to the compression or flexure modules will
be required; the H1 module is a pure consumer.

The interaction equations are:

```
Pr/Pc ≥ 0.2:
    Pr/Pc + (8/9)·(Mrx/Mcx + Mry/Mcy) ≤ 1.0             (Eq. H1-1a, p. 16.1-88)

Pr/Pc < 0.2:
    Pr/(2·Pc) + (Mrx/Mcx + Mry/Mcy) ≤ 1.0               (Eq. H1-1b, p. 16.1-88)
```

where `Pc = φ·Pn` from Chapter E and `Mcx = φ·Mnx` from Chapter F.

---

## 8. Open questions

1. **Effective length for torsion.** `KL_z` defaults to `KL_y` when not
   supplied. For singly-symmetric sections in moment frames the torsional
   effective length can differ. Require the caller to supply it explicitly
   (no silent default) to avoid unsafe conservatism masking.

2. **Tapered members / variable KL.** Out of scope for v1; flag with a
   `NotImplementedError` in the orchestrator if the caller attempts a
   variable-section route.

3. **Seismic compactness interplay.** AISC 341-22 §D1.1 requires highly-ductile
   compression members to satisfy λhd limits stricter than Table B4.1a. Should
   the compression calculator silently enforce §341 λhd? Recommendation: no —
   the §E calculator reports the §360 strength. The `ColumnCheck` facade calls
   `classify_seismic_compactness_341_D1` separately and refuses to proceed if
   the element fails.

4. **Interaction with panel-zone capacity design.** Chapter H columns in an SMF
   must also pass the AISC 341 §E3.4a column-strength check
   (`Pr ≤ 0.3·φ·Pn` or capacity-design demand). This belongs in the seismic
   facade layer (design note 07 follow-on), not in the §E calculator.
