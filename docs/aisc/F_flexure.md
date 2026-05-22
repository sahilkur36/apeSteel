# AISC 360-22 §F — Flexure

apeSteel implements the **full AISC 360-22 Chapter F** (§F2 through
§F12). Every calculator is a pure function returning a frozen
`FlexureF<n>Report`, every report carries `AISCClauseReference`
citations, and the geometry-class dispatch is `section_kind`-typed
rather than string-matched. LRFD `phi_b = 0.90`, ASD `Omega_b = 1.67`.

## What's covered

| §F clause | Section family | apeSteel function |
| --- | --- | --- |
| **§F2**, Eq. F2-1 .. F2-8b (*p. 16.1-48*) | DS compact I & channels (major) | `compute_flexural_strength_F2_compact_doubly_symmetric` |
| **§F3**, Eq. F3-1 / F3-2 (*p. 16.1-50*) | DS I, compact web, NC / slender flange | `compute_flexural_strength_F3_noncompact_or_slender_flange` |
| **§F4**, Eq. F4-1 .. F4-15 (*p. 16.1-51*) | DS NC-web I + SS I (compact / NC web) | `compute_flexural_strength_F4` |
| **§F5**, Eq. F5-1 .. F5-10 (*p. 16.1-56*) | DS *and* SS I with slender web (plate girder) | `compute_flexural_strength_F5_slender_web_plate_girder` |
| **§F6**, Eq. F6-1 .. F6-4 (*p. 16.1-60*) | I-shapes & channels, minor axis | `compute_flexural_strength_F6_minor_axis` / `_channel` |
| **§F7**, Eq. F7-1 .. F7-13 (*p. 16.1-61*) | Square / rectangular HSS & box | `compute_flexural_strength_F7_rect_hss` |
| **§F8**, Eq. F8-1 .. F8-4 (*p. 16.1-64*) | Round HSS / Pipe | `compute_flexural_strength_F8_round_hss` |
| **§F9**, Eq. F9-1 .. F9-19 (*p. 16.1-65*) | Tees & double angles in plane of symmetry | `compute_flexural_strength_F9_tee_double_angle` |
| **§F10**, Eq. F10-1 .. F10-6 (*p. 16.1-68*) | Single angles | `compute_flexural_strength_F10_single_angle` |
| **§F11**, Eq. F11-1 .. F11-4 (*p. 16.1-70*) | Rectangular bars and rounds | `compute_flexural_strength_F11_bar` |
| **§F12**, Eq. F12-1 (*p. 16.1-71*) | Unsymmetric shapes (elastic `Fn Smin`) | `compute_flexural_strength_F12_unsymmetric` |

Shared primitives (`Lp`, `Lr`, `Mp`, `Mcr`, `Cb` via
`compute_Cb_from_quarter_point_moments`, `Rpc`, `Rpt`, `Rpg`, the F2-2
interpolation, the F3-1/F3-2 FLB equations, the F4-13/14 CFLB
equations) are exported from `apeSteel.flexure` for direct reuse.

## Quick example

```python
--8<-- "examples/aisc_F_flexure.py"
```

Output for a welded W-style section (`bf = 300 mm`, `tf = 20 mm`,
`hw = 400 mm`, `tw = 16 mm`, A992) with `Lb_top = 0.001 m` (top flange
continuously braced), `Lb_bot = 4.0 m`, `Cb = 1.0`:

```text
Routed to             : F2
Governing flange      : bot
phi*Mn (governing)    :   924.4 kN.m
F2 governing limit    : inelastic_LTB
F2 phi*Mn             :   924.4 kN.m
```

## How it routes

The I-shape facade `run_full_beam_check` (also reachable as
`Element.run_full_check`) embodies the routing rule. After calling
`classify_flexural_compactness_B4_1b`, it reads
`(section_classification, flange.classification, web.classification)`
and dispatches:

| Geometry | Web class | Flange class | Routed engine |
| --- | --- | --- | --- |
| Singly-symmetric I | compact or non-compact | (any) | **§F4** |
| Singly-symmetric I | slender | (any) | **§F5** *(F5 covers DS *and* SS)* |
| Doubly-symmetric I | slender | (any) | **§F5** *(plate girder)* |
| Doubly-symmetric I | non-compact | (any) | **§F4** |
| Doubly-symmetric I | compact | compact | **§F2** |
| Doubly-symmetric I | compact | non-compact or slender | **§F3** |

Each routed engine is run **twice** — once per compression flange (top
and bottom) — and the **governing flange** is the one with the lower
`phi * Mn`. The result is a `BothFlangesFlexureF<n>Report` whose
`governing_report` carries the standard `Report` interface
(`nominal_strength`, `phi_strength_LRFD`, `governing_limit_state`).

For non-I geometries, the `apeSteel.checks.flexure_dispatch` facade
exposes per-family entry points
(`compute_flexural_strength_channel`, `_rectangular_hss`,
`_round_hss`, `_tee_or_double_angle`, `_single_angle`,
`_bar`, `_unsymmetric_F12`) that take the concrete geometry object
and route to the §F engine that owns it. The dispatch is by *type*,
not by string match (ARCHITECTURE.md §7).

Element methods relevant to Chapter F:

- `Element.flexural_strength_F2_top_flange()` / `_bot_flange()` /
  `_both_flanges()` — F2 LTB-only (compact DS I).
- `Element.flexural_strength_F3_*` — F3 LTB + FLB (NC/slender flange).
- `Element.flexural_strength_F4_*` — F4 (DS NC web, SS compact / NC web).
- `Element.flexural_strength_F5_*` — F5 (DS or SS slender web).
- `Element.phi_Mn_vs_Lb(unbraced_lengths_Lb, ...)` — parameter sweep
  that classifies once, picks the routed engine, and evaluates the
  capacity curve at each `Lb`.
- `Element.run_full_check()` — classification + F-routing + G2 shear,
  one `BeamCheckReport`.

## Related

- [Design note 04 — Flexure §F2-F5](../design_notes/04_flexure_F2_F3_F4_F5.md) (I-shape detail)
- [Design note 10 — Full Flexure §F](../design_notes/10_flexure_full_F.md) (the full chapter port)
- [API: Flexure](../api/flexure.md)
- [§B — Classification](B_classification.md) (drives the routing)
- [§H — Combined Forces](H_combined.md) (consumes `phi_b * Mn`)
- [Plotting: capacity curves](../plotting/capacity_curves.md)
