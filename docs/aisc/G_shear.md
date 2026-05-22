# AISC 360-22 §G — Shear

apeSteel currently implements **AISC 360-22 §G2.1** — web-shear strength
of doubly-symmetric I-shapes — exposed as
`compute_shear_strength_G2_doubly_symmetric` (pure function) and
`Element.shear_strength_G2(transverse_stiffener_spacing_a=None)`
(`Element` facade). §G3 (tension-field action) and §G4 (rectangular
HSS) are planned but not yet shipped; see
[design note 05](../design_notes/05_shear_G2.md) for the roadmap.

## What's covered

- **§G2.1(a)** — `Vn = 0.6 * Fy * Aw * Cv1`, **Eq. G2-1** (*p. 16.1-65*).
- **§G2.1(b)** — three-regime `Cv1` family, **Eq. G2-3 / G2-4 / G2-5**
  (*p. 16.1-65*).
- **§G2.1(b)** — `kv = 5.34` (unstiffened webs, 360-22) or the
  stiffened-web `kv = 5 + 5/(a/h)^2` family (*p. 16.1-66*).
- **§G2.1(a) exception** — `phi_v = 1.00` for stocky rolled webs
  (`h/tw <= 2.24 sqrt(E/Fy)`), `phi_v = 0.90` otherwise. Both constants
  are exported (`PHI_SHEAR_LRFD_GENERAL`, `PHI_SHEAR_LRFD_STOCKY_ROLLED`).
- Per-regime reporting via `ShearG2Report.governing_shear_regime`
  (`"yielding"`, `"inelastic_buckling"`, `"elastic_buckling"`) — also
  mirrored into the standard `Report.governing_limit_state`.

| Concern | Module / symbol |
| --- | --- |
| Three-regime `Cv1` | `apeSteel.shear.G2_doubly_symmetric.compute_Cv1_three_regime` |
| Stiffened-web `kv` | `apeSteel.shear.G2_doubly_symmetric.compute_kv_for_stiffened_web` |
| Full §G2 strength | `apeSteel.shear.compute_shear_strength_G2_doubly_symmetric` |
| `Element` facade | `Element.shear_strength_G2` |

## Quick example

```python
--8<-- "examples/aisc_G_shear.py"
```

Output for a welded W-style section (`bf = 300 mm`, `tf = 20 mm`,
`hw = 400 mm`, `tw = 16 mm`, A992, unstiffened web):

```text
Regime                : yielding
h/tw                  :  25.00
kv                    : 5.340
Cv1                   : 1.000
Vn                    :  1456.2 kN
phi*Vn (LRFD)         :  1310.6 kN
```

## How it routes

`compute_shear_strength_G2_doubly_symmetric` is a single straight-line
calculator — no per-axis dispatch — but several decisions are folded
into one report:

1. Compute `lambda_w = h / tw` from `SectionProperties`.
2. Pick `kv`:
   - If `transverse_stiffener_spacing_a is None` ➜ **unstiffened**,
     `kv = 5.34` (AISC 360-22).
   - Otherwise call `compute_kv_for_stiffened_web(a, h, tw)`.
3. Classify into the three regimes against
   `lambda_1 = 1.10 sqrt(kv E / Fy)` and
   `lambda_2 = 1.37 sqrt(kv E / Fy)`:
   - `lambda_w <= lambda_1` ➜ **Eq. G2-3**, `Cv1 = 1.0`
     (web-shear yielding).
   - `lambda_1 < lambda_w <= lambda_2` ➜ **Eq. G2-4**, inelastic.
   - `lambda_w > lambda_2` ➜ **Eq. G2-5**, elastic shear buckling.
4. Compute `Vn = 0.6 * Fy * Aw * Cv1` (`Aw = d * tw`).
5. Pick `phi_v`: `1.00` only when `construction == "rolled"` *and*
   `h/tw <= 2.24 sqrt(E/Fy)` *and* the regime is yielding; `0.90`
   otherwise. The flag
   `is_qualified_for_phi_1p00_stocky_rolled_exception` records the
   decision.

The `Element.run_full_check` facade automatically calls
`shear_strength_G2()` and stuffs the result into `BeamCheckReport.shear`
(set to `None` for singly-symmetric I where the G2-SS path is not yet
shipped). For ASD, `omega_strength_ASD = Vn / 1.50` is exposed alongside
the LRFD value.

## Related

- [Design note 05 — Shear §G2](../design_notes/05_shear_G2.md)
- [API: Shear](../api/shear.md)
- [§F — Flexure](F_flexure.md) (paired with shear in `run_full_check`)
- [§H — Combined Forces](H_combined.md) (HSS §H3.2 consumes `phi_v * Vn`)
