# Design note 07 — Panel-zone column-flange tension check (AISC 341 §E3)

> **Status:** design, not yet implemented.
> **Drives:** `apeSteel.seismic.panel_zone_341`.
> **Spreadsheet source:** none directly in the LTB workbook, but the
> existing `to_review/sectionProperties.py` has a `panelZone` class that
> performs the column-flange tension check. This note specifies how to
> port it cleanly.

---

## 1. Scope

For a beam-to-column moment connection in a special moment frame (SMF),
AISC 341-22 §E3.6e (and AISC 358 prequalification chapters) requires that
the **column flange** be thick enough to resist the demand from the
beam-flange tension.

### Demand (full-plastic beam flange in tension, amplified)

```
Tu = 1.8 · bf,beam · tf,beam · Fy,beam · Ry,beam      (probable beam-flange tension)
```

The 1.8 captures both Ry and a strain-hardening factor — the spreadsheet's
existing `panelZone` class uses the same expression.

### Column flange capacity (concentrated tension force, §J10.1)

```
Rn = 6.25 · tcf² · Fy,col · Ry,col

φRn = 0.90 · Rn                                       (LRFD)
```

### `tcf` minimum thickness (two governing equations)

The existing `panelZone` uses two limits and takes the larger:

```
tcf_limit_1 = bf,beam / 6                              (geometric, AISC 358)

tcf_limit_2 = 0.40 · √( (1.8 · bf,beam · tf,beam · Fy,beam · Ry,beam) /
                       (Fy,col · Ry,col) )            (capacity-based)
```

A column that satisfies `tcf ≥ max(tcf_limit_1, tcf_limit_2)` and
`φRn ≥ Tu` passes the check.

---

## 2. Public API

```python
from apeSteel.core.materials import SteelMaterial
from apeSteel.sections.properties import SectionProperties


@dataclass(frozen=True, slots=True)
class PanelZoneColumnFlangeTensionReport(Report):
    # demand
    beam_flange_tension_demand_Tu:     float
    # capacity
    column_flange_thickness_tcf:       float
    column_flange_tension_capacity_Rn: float
    phi_column_flange_tension_capacity_phi_Rn_LRFD: float
    # minimum thickness limits
    minimum_column_flange_thickness_geometric_tcf_min_1: float
    minimum_column_flange_thickness_capacity_tcf_min_2:  float
    minimum_column_flange_thickness_required_tcf_min:    float
    # outcome
    is_thickness_acceptable: bool
    is_demand_to_capacity_acceptable: bool
    demand_to_capacity_ratio: float


def check_column_flange_tension_341(
    beam_section_properties:   SectionProperties,
    beam_material:             SteelMaterial,
    column_section_properties: SectionProperties,
    column_material:           SteelMaterial,
) -> PanelZoneColumnFlangeTensionReport: ...
```

---

## 3. Citations

```python
cited_clauses = (
    AISCClauseReference("AISC 341-22", "E3.6e", None, "9.1-46"),
    AISCClauseReference("AISC 358-22", "5.3.1",  None, None),
    AISCClauseReference("AISC 360-22", "J10.1", "J10-2", "16.1-129"),
)
```

---

## 4. What this note **does not** cover

- The **panel-zone shear capacity** (`Rn = 0.6·Fy·dc·tw·(1 + ...)`) per
  §E3.6e and §J10.6. That belongs in a separate function in the same
  module and will be added in a follow-up.
- Doubler-plate design.
- Continuity-plate design.

These are companion checks that round out the panel-zone story. They share
the same `Member`-style input set, so the future module will look like:

```python
def check_panel_zone_shear_341(...): ...
def design_doubler_plate(...): ...
def design_continuity_plates(...): ...
```

---

## 5. Difference from the legacy `panelZone` class

| Aspect | Legacy `panelZone` | Ported `check_column_flange_tension_341` |
| --- | --- | --- |
| Inputs | beam + column object with mixed responsibilities | `SectionProperties` + `SteelMaterial`, twice |
| Output | dict + `print` | typed frozen `PanelZoneColumnFlangeTensionReport` |
| Units | implicit, with manual `unit` dict | explicit base units (N-mm-tonne-s) |
| Ry source | column object | `SteelMaterial.expected_yield_ratio_Ry` |
| `tcf_limit_1` interpretation | half of `bf/6` (likely a bug) | `bf/6` per AISC 358 |
| Citations | none | full `cited_clauses` tuple |
| Logging | `print` | nothing — facade can log if desired |
| Mutation | mutable | frozen |

The legacy class has a subtle bug worth flagging during the port: it
computes `tcf_limit.append(self.beam.bf/6)` but does not divide later, and
its second limit uses `0.40 · sqrt(...)` which is a reasonable
capacity-based formula not directly stated in §E3 — verify against AISC
358 before considering the port "the same."
