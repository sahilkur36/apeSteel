# AISC 360-22 §B — Classification

apeSteel applies **AISC 360-22 §B4** — *Member Properties* — to every
cross-section before any strength check runs. Two classifiers live in
`apeSteel.classification`, both pure functions returning frozen
`Report` subclasses:

- **`classify_flexural_compactness_B4_1b`** — Table B4.1b (flexure),
  classifies each plate element as **compact** / **non-compact** /
  **slender**. The section class is the *worst* of its elements and
  drives the §F2 / §F3 / §F4 / §F5 routing.
- **`classify_axial_compression_B4_1a`** — Table B4.1a (axial
  compression), classifies each plate element as **non-slender** /
  **slender**. A single slender element triggers the §E7 effective-
  width reduction inside the Chapter-E orchestrator.

The classifiers consume only `SectionProperties` + `SteelMaterial` +
`construction` (`"rolled"` vs `"welded"`); they never inspect plate
dimensions directly. Welded built-up I-shape flanges (Cases 2 and 11)
use the bounded `kc = 4 / sqrt(h/tw)` (`0.35 <= kc <= 0.76`) helper
exposed as `compute_kc_for_built_up_flange`.

## What's covered

- **Table B4.1a Cases 1 / 2** (I-shape flange) and **Case 5** (I-shape
  web) for axial compression — *AISC 360-22, p. 16.1-16*.
- **Table B4.1b Cases 10 / 11** (I-shape flange) and **Case 15** (I-shape
  web) for flexure — *AISC 360-22, p. 16.1-17*. The asymmetric `lambda_p`
  for the singly-symmetric web (Case 16) is supported via the
  `(hc / hp) * sqrt(E/Fy)` form documented in design note 02.
- Per-plate `PlateElementClassification` records carry
  `slenderness_ratio_lambda`, `compact_limit_lambda_p`,
  `noncompact_limit_lambda_r`, and the AISC `aisc_case` tag
  ("B4.1b Case 10", etc.) so reports are self-citing.

| Concern | Module / function |
| --- | --- |
| §B4.1a Table B4.1a | `apeSteel.classification.axial_compression_B4_1a.classify_axial_compression_B4_1a` |
| §B4.1b Table B4.1b | `apeSteel.classification.flexural_compactness_B4_1b.classify_flexural_compactness_B4_1b` |
| `kc` for welded flange | `apeSteel.classification._common.compute_kc_for_built_up_flange` |
| Element facade | `Element.classify_flexural` / `Element.classify_axial_compression` |

## Quick example

```python
--8<-- "examples/aisc_B_classification.py"
```

Output for a welded W-style section, `bf = 300 mm`, `tf = 20 mm`,
`hw = 400 mm`, `tw = 16 mm`, A992:

```text
Flexural section class : compact
  flange  lambda=  7.50  lambda_p=  9.15  lambda_r= 23.84  -> compact
  web     lambda= 25.00  lambda_p= 90.55  lambda_r=137.27  -> compact
Axial: any slender element? False  (flange non_slender, web non_slender)
```

## How it routes

The classifiers are *pure* and *upstream* of every strength engine —
they hold no knowledge of §F or §E. The composition flows downward:

1. `Element.section_properties` computes the geometry-derived
   `SectionProperties` (cached, side-aware for singly-symmetric
   sections via `section_properties_for("top"|"bot")`).
2. `Element.classify_flexural()` calls
   `classify_flexural_compactness_B4_1b` with that
   `SectionProperties`, the bound `SteelMaterial`, and the bound
   `construction`. The resulting `FlexuralCompactnessReport` carries
   `flange`, `web`, and `section_classification` (the worst of the two).
3. The **`run_full_beam_check` facade** (see `Element.run_full_check`)
   reads `section_classification` and routes:
    - web slender ➜ **§F5** (plate girder)
    - web non-compact ➜ **§F4** (DS or SS)
    - web compact + flange compact ➜ **§F2**
    - web compact + flange non-compact or slender ➜ **§F3**
4. For axial compression, `Element.classify_axial_compression()` sets
   `section_has_slender_element` which the §E orchestrator consumes to
   decide whether §E7 effective-width reduction applies.

The classifier itself never imports from `flexure/` or `compression/`,
which keeps the dependency arrow pointing downward (see
[design note 02](../design_notes/02_classification_B4.md) §6 *Open
questions*).

## Related

- [Design note 02 — Classification §B4](../design_notes/02_classification_B4.md)
- [Design note 03 — Seismic compactness §341](../design_notes/03_seismic_compactness_341.md)
- [API: Classification](../api/classification.md)
- [§E — Compression](E_compression.md) (consumer of `B4.1a`)
- [§F — Flexure](F_flexure.md) (consumer of `B4.1b`)
