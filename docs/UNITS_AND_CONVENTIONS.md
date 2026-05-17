# Units and conventions

`apeSteel` runs in a **single canonical base system**:

> **N-mm-tonne-s** (force = N, length = mm, mass = tonne, time = s,
> derived stress = MPa, derived energy = N·mm, derived moment = N·mm).

This system is the default of [`baseUnits`](https://github.com/nmorabowen/baseUnits).
All internal storage, every dataclass attribute, every function argument, and
every return value inside the library is a `float` already expressed in this
base. Conversion to or from human units (kN, m, ksi, in, kN·m, etc.) happens
**only at the boundary** — in user code, in catalog loaders, and in `Report.format()`.

This convention is the most important rule in the library. The rest of this
document explains why and how to live with it.

---

## 1. The one rule

```python
import baseUnits as u
assert u.BASE == "N-mm-tonne-s", f"apeSteel requires N-mm-tonne-s base, got {u.BASE!r}"
```

Every module in `src/apeSteel/` starts with these two lines. They live at
the top of the file, after the docstring, before any other imports from
within apeSteel. If `baseUnits` is ever switched at the project scope (e.g.
someone imports `from baseUnits.systems.kip_in_s import *`), the assert
fails fast at import time. That is by design.

---

## 2. Inputs: multiply on the way in

A user constructs a section like this:

```python
import baseUnits as u
from apeSteel.sections.geometry import DoublySymmetricISection

section_geometry = DoublySymmetricISection(
    flange_width_bf       = 300 * u.mm,
    flange_thickness_tf   = 22  * u.mm,
    web_clear_height_hw   = 350 * u.mm,
    web_thickness_tw      = 12  * u.mm,
)
```

`u.mm` is `1.0` in this base, so `300 * u.mm == 300.0`. `u.m` is `1000.0`,
so `4 * u.m == 4000.0`. `u.kN` is `1000.0`, so `1.2 * u.kN_m == 1.2`
(since `u.kN_m = 1000 N · 1000 mm = 1e6` and the moment we just multiplied
gives N·mm — confirm this on first encounter; the unit tests pin it).

The constructor stores the multiplied float and never sees the unit symbol
again. The dataclass attribute `flange_width_bf` is `300.0`, full stop. There
is no `Quantity` wrapper.

---

## 3. Outputs: divide on the way out

```python
report = beam_check.run()
phi_Mn_in_kN_m = report.flexure_top.phi_nominal_flexural_strength_phi_Mn_LRFD / u.kN_m
print(f"φMn = {phi_Mn_in_kN_m:.1f} kN·m")
```

Or use the built-in formatter, which knows the canonical display units:

```python
print(report.flexure_top.format())
# →
# AISC 360 §F2.2 — Lateral-torsional buckling (top flange)
#   Lb       = 1.00 m       (input)
#   Lp       = 1.84 m       (Eq. F2-5)
#   Lr       = 5.23 m       (Eq. F2-6)
#   Mp       = 425.7 kN·m   (Fy · Zx)
#   φMn      = 383.1 kN·m   (φ = 0.90, LRFD)
#   Governing limit state: yielding (Lb < Lp)
```

The library is responsible for choosing display units that round to a sane
number of significant figures for a structural engineer:

| Quantity | Display unit |
| --- | --- |
| Length (member) | `u.m` |
| Length (plate, section) | `u.mm` |
| Force | `u.kN` |
| Moment | `u.kN_m` |
| Stress | `u.MPa` |
| Stiffness | `u.kN_m / u.rad` |

This table lives as a constant `CANONICAL_DISPLAY_UNITS` in
`apeSteel.core.units` and is the only place display units are coupled in.

---

## 4. AISC-symbol-suffix naming

Public attributes and function parameters follow this pattern:

```
<full_english_description>_<AISC_symbol>
```

Examples:

| Verbose name | AISC symbol |
| --- | --- |
| `flange_width_bf` | `bf` |
| `web_thickness_tw` | `tw` |
| `yield_stress_Fy` | `Fy` |
| `expected_yield_ratio_Ry` | `Ry` |
| `lateral_torsional_buckling_modification_factor_Cb` | `Cb` |
| `limiting_length_plastic_Lp` | `Lp` |
| `limiting_length_inelastic_LTB_Lr` | `Lr` |
| `plastic_moment_Mp` | `Mp` |
| `nominal_flexural_strength_Mn` | `Mn` |
| `effective_radius_of_gyration_for_LTB_rts` | `rts` |
| `distance_between_flange_centroids_ho` | `ho` |
| `web_shear_strength_coefficient_Cv1` | `Cv1` |
| `web_plate_buckling_coefficient_kv` | `kv` |
| `radius_of_gyration_strong_axis_rx` | `rx` |

Rules:

1. Public-facing — verbose name **always** carries the symbol suffix.
2. Inside a short calculator function (≤ ~40 lines, single AISC paragraph),
   you may rebind the symbol locally for readability:
   ```python
   def compute_limiting_length_plastic_Lp(
       radius_of_gyration_weak_axis_ry: float,
       elastic_modulus_E: float,
       yield_stress_Fy: float,
   ) -> float:
       # AISC 360 Eq. F2-5: Lp = 1.76 · ry · sqrt(E / Fy)
       ry = radius_of_gyration_weak_axis_ry
       E  = elastic_modulus_E
       Fy = yield_stress_Fy
       Lp = 1.76 * ry * math.sqrt(E / Fy)
       return Lp
   ```
   The local rebinds make the formula match the code text 1:1. They are
   allowed only when the function is short enough that the rebind block is
   in eye-shot of the formula.
3. **Never** invent a new symbol. If AISC calls it `rts`, we call it `rts`,
   even where ASCE/SCI calls it something else.

---

## 5. The `Report` dataclass family

Every calculator returns one. Common fields:

```python
@dataclass(frozen=True, slots=True)
class Report:
    cited_clauses: tuple[AISCClauseReference, ...]
    governing_limit_state: str            # "yielding" | "inelastic_LTB" | …
    phi_LRFD:               float
    omega_ASD:              float
    nominal_strength:       float         # Mn, Vn, Pn — base units
    phi_strength_LRFD:      float         # phi · nominal
    omega_strength_ASD:     float         # nominal / omega
```

Subclasses add the specific intermediate quantities (`Lp`, `Lr`, `Cv1` …) so
the user can introspect every step. They are all `float` in base units.

---

## 6. Sign conventions

- Positive moment causes tension on the **bottom** fibre (sagging is positive).
- Positive axial force is **compression**.
- `Lb_top` and `Lb_bot` are positive lengths.
- `Cb` is dimensionless ≥ 1.0; we never silently substitute `Cb = 1` —
  the caller must pass it.

---

## 7. Catalog rows: the only pydantic boundary

`apeSteel.sections.catalog` loads the AISC v16 pickle into pydantic v2
models. That is the only place pydantic appears.

```python
class CatalogRowAISCv16(BaseModel):
    AISC_Manual_Label:  str
    Ag:  float = Field(..., description="gross area, in (in^2) per AISC v16")
    Ix:  float
    Sx:  float
    Zx:  float
    ry:  float
    rts: float
    J:   float
    Cw:  float
    ho:  float
    # … etc
    model_config = ConfigDict(frozen=True, extra="forbid")
```

The catalog loader **converts the pickle's imperial values to base units
on load** (multiplies by the right unit constants) and stores the result.
After that, no calculator in the rest of the library cares that AISC v16
originally shipped in inches and ksi.

---

## 8. The `Cb` debate (not really a debate, just a policy)

The original spreadsheet leaves `Cb = 1` implicit. We won't:

- `Cb = 1.0` is conservative for many cases but unconservative for some
  (e.g. inflection-point regions inside seismic frames). The user has to
  state the assumption explicitly.
- The library exposes a helper `compute_Cb_from_quarter_point_moments(Mmax,
  MA, MB, MC) -> float` (AISC 360 Eq. F1-1) so the user can compute it
  rigorously when the moment diagram is known.

---

## 9. What "verbose" does **not** mean

- It does **not** mean replacing well-known math symbols with English
  inside formulas. We don't write `pi_constant * radius_squared`. `math.pi`,
  `r**2`, and friends are fine.
- It does **not** mean wrapping numpy or pandas. They handle plain floats.
- It does **not** mean docstring-only typing. Type hints are real, not
  decorative.
