# AISC 341-22 — Seismic Provisions

apeSteel implements the joint-level and member-level seismic checks
that sit on top of AISC 360-22 plus the AISC 358-22 prequalification
provisions, all returning frozen `Report` subclasses.

## What's covered

| AISC clause | What | apeSteel function |
| --- | --- | --- |
| **341 §D1.1** Table D1.1 (*p. 9.1-19*) | Highly- / moderately-ductile member compactness (flange + web + length limits) | `classify_seismic_compactness_341_D1` |
| **341 §D1.2b** Eq. D1-1 / D1-2 | Seismic `Lb_max` (LTB length limit) | (carried as the `length` field of the §D1.1 report) |
| **341 §E3.6e** column-flange tension (*p. 9.1-46*) | `Tu = 1.8 bf,beam tf,beam Fy,beam Ry,beam` vs `Rn = 6.25 tcf^2 Fy,col Ry,col` | `check_column_flange_tension_341` |
| **341 §E3.6e** doubler-plate sizing (*p. 9.1-46*) | Shop-practical `t_dp` recommendation handling shear deficit + local buckling | `recommend_doubler_plate_thickness_341` |
| **341 §E3.6e(2)** doubler local buckling | `t_dp >= (dz + wz) / 90` limit | (carried inside the doubler report) |
| **358 §2.4.4** continuity-plate need + §J10.8 minimum dimensions | Need check + plate sizing | `check_continuity_plates_required_358` |
| **360 §J10.6** panel-zone shear (*p. 16.1-128*) | All four equations **J10-9 / J10-10 / J10-11 / J10-12**, capacity-amplified by `Ry,col` | `check_panel_zone_shear_341` |

`code_edition` parameter on `classify_seismic_compactness_341_D1`
accepts `"AISC 341-22"` (default), `"AISC 341-16"`, and
`"AISC 341-10"` so legacy projects can be checked against the
appropriate coefficient table; the per-edition coefficients are
isolated in the module-level constants of
`apeSteel.classification.seismic_compactness_341_D1`.

The `BeamColumnConnection` composite aggregates a **beam** `Element`
and a **column** `Element` and exposes every joint-level check as a
method:

| `BeamColumnConnection` method | AISC clause |
| --- | --- |
| `check_panel_zone_column_flange_tension()` | 341 §E3.6e |
| `check_panel_zone_shear(...)` | 360 §J10.6 (capacity-amplified per 341 §E3.6e) |
| `recommend_doubler_plate(...)` | 341 §E3.6e + §E3.6e(2) |
| `check_continuity_plates(...)` | 358 §2.4.4 + 360 §J10.8 |

The composite is built via `beam.connected_to(column)` or
`BeamColumnConnection(beam=beam, column=column)`.

## Quick example

```python
--8<-- "examples/aisc_seismic_341.py"
```

Output for a small built-up rolled W beam (`bf = 200`, `tf = 16`,
`hw = 400`, `tw = 10` mm) framing into a stockier column
(`bf = 300`, `tf = 25`, `hw = 350`, `tw = 14` mm), both A992,
`Lb = 2.0 m`:

```text
Highly-ductile flange OK?   : acceptable
Highly-ductile web    OK?   : acceptable
Section seismically compact?: True
Column-flange tension DCR   : 1.638
Column-flange thickness OK? : False
Panel-zone governing eqn    : J10-9
Panel-zone DCR              : 1.524
```

The DCR > 1 at the joint signals that this column flange is too thin
to take the amplified beam-flange tension demand (`Tu = 1.8 bf,beam
tf,beam Fy,beam Ry,beam` per AISC 341 §E3.6e) and that the panel-zone
shear demand exceeds the §J10.6 capacity — both fixable with a
heavier column section or doubler / continuity plates (call
`joint.recommend_doubler_plate(...)`).

## How it routes

The seismic layer follows two independent flows:

**Member-level ductility classification (§341 D1.1)**

1. `Element.classify_seismic(ductility_level, axial_demand_ratio_Ca,
   code_edition)` calls `classify_seismic_compactness_341_D1` with the
   element's `SectionProperties`, `SteelMaterial`, the requested
   ductility (`"highly_ductile"` / `"moderately_ductile"`), the axial
   demand ratio `Ca = Pu / (phi_c Py)`, and the code edition (the
   default is the element's `code_edition_for_seismic`, set at
   construction time and overridable with `with_code_edition_for_seismic`).
2. The classifier compares the actual `bf/(2 tf)` and `h/tw` against
   the per-edition `lambda_hd` / `lambda_md` coefficients (e.g. AISC
   341-22 Case BH1: flange `0.30 sqrt(E/Fy)`, web
   `2.57 sqrt(E/Fy) (1 - 1.04 Ca)` for highly ductile) and reports
   `acceptable` / `unacceptable` per plate.
3. It also evaluates the seismic LTB length limit
   `Lb_max = 0.086 ry E / Fy` (Eq. D1-2, highly ductile) or
   `0.19 ry E / Fy` (Eq. D1-1, moderately ductile) and reports
   `is_seismic_length_acceptable`.
4. `is_seismically_compact_section` is the AND of all three element
   checks (flange, web, length).

**Joint-level capacity-design checks**

1. `BeamColumnConnection.check_panel_zone_column_flange_tension()` —
   amplifies the beam-flange tension by `1.8` (AISC 341 §E3.6e captures
   both `Ry,beam` and a strain-hardening factor) and compares against
   `phi Rn` where `Rn = 6.25 tcf^2 Fy,col Ry,col` (AISC 360 §J10.1
   Eq. J10-2). Two minimum-thickness rules are reported:
   `tcf_min_geometric = bf,beam / 6` (AISC 358) and the capacity-based
   `tcf_min_capacity = 0.40 sqrt(Tu / (Fy,col Ry,col))`. The required
   `tcf_min` is the max of the two.
2. `BeamColumnConnection.check_panel_zone_shear(...)` — runs the
   AISC 360 §J10.6 panel-zone shear check. The demand is the AISC 358
   capacity-design force `Vu,pz = sum(Mpr / db) - Vu,col`, where
   `Mpr = Cpr Ry Fy Zx`; the capacity is one of **Eq. J10-9 .. J10-12**
   depending on whether panel-zone deformation is considered in frame
   stability (the `consider_panel_zone_deformation_in_frame_stability`
   flag). Additional doubler-plate thickness can be credited via
   `additional_doubler_plate_thickness_t_dp`.
3. `BeamColumnConnection.recommend_doubler_plate(...)` — given a shear
   deficit, returns the shop-practical doubler thickness satisfying
   both the deficit and the §E3.6e(2) local-buckling limit
   `t_dp >= (dz + wz) / 90`.
4. `BeamColumnConnection.check_continuity_plates(...)` — applies AISC
   358 §2.4.4 to decide if continuity (stiffener) plates are needed,
   and if so returns the AISC 360 §J10.8 minimum width / thickness.

## Related

- [Design note 03 — Seismic compactness §341](../design_notes/03_seismic_compactness_341.md)
- [Design note 07 — Panel-zone §341](../design_notes/07_panel_zone_341.md)
- [API: Seismic](../api/seismic.md)
- [API: Beam-Column Connections](../api/beam_column_connection.md)
- [User Guide: The Element Composite](../user_guide/element.md)
