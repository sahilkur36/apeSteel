# Design note 06 — Serviceability deflections

> **Status:** design, not yet implemented.
> **Drives:** `apeSteel.serviceability.simple_beam_deflections`.
> **Spreadsheet rows ported:** the right-side blocks in `Seccion Tipo I`
> (`R9` – `R23`, `R26` – `R38`) and the camber line `R33` / `R34` / `R37`.

This module is not in AISC 360 — it implements the elastic-beam formulas
that the spreadsheet uses to check live-load and total deflection against
`L/360` and `L/240` (or whatever the user wants), plus a camber
recommendation.

---

## 1. Cases supported

| Case | Formula (mid-span deflection δ) |
| --- | --- |
| Simply-supported, UDL `w` | `δ = (5·w·L⁴) / (384·E·Ix)` |
| Simply-supported, point load `P` at mid-span | `δ = (P·L³) / (48·E·Ix)` |
| Simply-supported, point load `P` at distance `a` | (closed form) |
| Cantilever, UDL `w` | `δ = (w·L⁴) / (8·E·Ix)` |
| Cantilever, tip load `P` | `δ = (P·L³) / (3·E·Ix)` |

The spreadsheet handles the simply-supported UDL case for the secondary
beam check and a cantilever UDL+tip-load case for cantilevers
(cells `R33` and `R34`).

---

## 2. Limits

```
delta_max_live  = L / live_load_limit_ratio      # often L/360
delta_max_total = L / total_load_limit_ratio     # often L/240
```

The spreadsheet uses `L/360` for live and `L/240` for total (cells `R12`
and `R13`). We expose the ratios as parameters with the spreadsheet's
defaults.

---

## 3. Camber

The spreadsheet's camber rule (cells `R33`, `R34`, `R37`) is essentially:

```
camber = 1.5 × δ_dead   (rounded to the nearest 1/4 inch in US practice)
```

Specifically, the spreadsheet computes the deflection under unfactored
dead load and recommends a camber equal to ~80% of it. We will expose this
as a separate function with a `camber_factor` argument (default 0.8),
because shop practice varies.

---

## 4. Public API

```python
@dataclass(frozen=True, slots=True)
class SimplyBeamUDLDeflectionReport(Report):
    elastic_modulus_E:        float
    moment_of_inertia_Ix:     float
    span_length_L:            float
    distributed_load_live_w_live:    float
    distributed_load_dead_w_dead:    float
    distributed_load_superdead_w_sd: float
    deflection_under_live_load_delta_live:   float
    deflection_under_total_load_delta_total: float
    deflection_limit_live_L_over_360:        float
    deflection_limit_total_L_over_240:       float
    is_live_load_deflection_acceptable:      bool
    is_total_load_deflection_acceptable:     bool


def compute_deflections_simply_supported_UDL(
    section_properties: SectionProperties,
    material: SteelMaterial,
    span_length_L: float,
    distributed_load_dead_w_dead:       float,
    distributed_load_superdead_w_sd:    float,
    distributed_load_live_w_live:       float,
    live_load_limit_denominator:        float = 360.0,
    total_load_limit_denominator:       float = 240.0,
) -> SimplyBeamUDLDeflectionReport: ...


def recommend_camber_from_dead_load_deflection(
    deflection_under_dead_load: float,
    camber_factor:               float = 0.8,
    rounding_increment_inches:   float = 0.25,
) -> float: ...
```

---

## 5. Where the loads come from

`apeSteel` does **not** ingest ETABS or Robot output. That's a notebook
concern. The original spreadsheet has dedicated `etabs` and `Robot`
sheets that pull min/max moments and shears; the equivalent in Python is
a thin helper script in `examples/` that reads the ETABS export and
constructs the function arguments.

---

## 6. Open questions

1. **Continuous beams.** The spreadsheet handles only the simply-supported
   case; for continuous beams the user manually adjusts `w·L⁴/384EI`. We
   could ship a separate helper for the equal-span continuous case in v2.
2. **Vibrations (DG 11).** Out of scope for v1. Worth a separate design
   note when we tackle floor systems.
