# Recipe — Full Beam Check

**Question.** Given a welded built-up I-section in A992 steel and a
known bracing layout, what is the design flexural strength `φMn`
(governing flange, governing limit state) and design shear strength
`φVn` per AISC 360-22?

**Answer.** Compose the section, attach the material, construction,
and `Bracing`, then call `Element.run_full_check`. The returned `BeamCheckReport` carries the classification, the routed §F chapter (F2/F3/F4/F5), the
governing-flange flexural result, the §G2 shear result, and the AISC
clause citations.

```python
--8<-- "examples/recipe_beam_check.py"
```

## Step-by-step

### 1. Build the section

Use a plate-built `DoublySymmetricISection` directly, or pull a rolled
shape from the catalog:

```python
from apeSteel import AISCv16Catalog
section = AISCv16Catalog().get_doubly_symmetric_i_geometry("W14X90")
```

### 2. Compose the `Element`

```python
element = section.element(
    material=A992,
    construction="welded",
    bracing=Bracing(
        unbraced_length_top_flange_Lb_top=0.001 * u.m,   # continuous top brace
        unbraced_length_bot_flange_Lb_bot=3.0 * u.m,
        lateral_torsional_buckling_modification_factor_Cb=1.14,
    ),
)
```

`Bracing` is required for the §F2/F3/F4/F5 LTB methods. `construction`
(`"rolled"` or `"welded"`) drives the residual-stress assumption that
sets `λr` for the flange-classifier and the §F4 / §F5 plate-girder
factors.

### 3. Run the facade

```python
report = element.run_full_check()
```

`run_full_check` is the `Element` delegate for `run_full_beam_check`.
It chains:

1. **Classification** per AISC Table B4.1b (flange + web).
2. **Routing** to §F2/F3/F4/F5 based on web compactness, flange
   compactness, and symmetry.
3. The routed §F engine for both flanges; the governing flange is the
   one with the lower `φMn`.
4. **§G2 shear** (doubly-symmetric I only; singly-symmetric yields
   `shear = None` because §G2 SS is not yet shipped).

### 4. Read the report

| Field | Meaning |
| --- | --- |
| `routed_flexure_chapter` | `"F2" / "F3" / "F4" / "F5"` |
| `flexural_classification` | `FlexuralCompactnessReport` (flange + web) |
| `flexure_both_flanges` | the `BothFlanges...Report` for the routed §F |
| `governing_flexural_flange` | `"top"` or `"bot"` |
| `governing_flexural_phi_Mn` | `min(top φMn, bot φMn)` (N·mm) |
| `shear` | `ShearG2Report` with `phi_strength_LRFD` (N) |
| `cited_clauses` | the AISC clause references for every step |

The inner `flexure_both_flanges.governing_report.governing_limit_state`
names the controlling limit state (e.g. `"yielding"`, `"inelastic_LTB"`,
`"flange_local_buckling"`).

## See also

- [Beam-Column (H1.1)](beam_column_H1.md) — extend this with axial
  demand.
- [Plotting → Capacity Curves](../plotting/capacity_curves.md) — plot
  `φMn` against `Lb` for sizing.
