# AISC 360-22 §H — Combined Forces and Torsion

apeSteel implements the **full AISC 360-22 Chapter H** as a *consumer*
layer: §H1 / §H2 carry **no extra `phi`** — they are pure interaction
checks; the resistance factors are already embedded inside the supplied
`Pc = phi_c Pn` (Chapter E), `Mc = phi_b Mn` (Chapter F),
`Vc = phi_v Vn` (Chapter G), and `Tc = phi_T Tn` (§H3.1). The only
factor that *originates* in Chapter H is `phi_T = 0.90` /
`Omega_T = 1.67` for **§H3.1** HSS torsion. The literal AISC
coefficients of the chapter (the `0.2` axial-ratio break, the `8/9`
factor of Eq. H1-1a, the `1.5` / `0.5` of Eq. H1-2, the `0.6` shear-
yield fraction, etc.) live in `apeSteel.combined._common` and are
unit-tested against the spec values directly.

## What's covered

| §H clause | Equations | apeSteel function |
| --- | --- | --- |
| **§H1.1** flexure + compression | **Eq. H1-1a / H1-1b**, *p. 16.1-83* | `compute_combined_strength_H1_1` |
| **§H1.2** flexure + tension | **Eq. H1-1a / H1-1b** with `Pc = phi_t Pn` + `Cb` amplifier | `compute_combined_strength_H1_2`, `compute_Cb_amplification_factor_H1_2`, `compute_Pey_H1_2` |
| **§H1.3** DS rolled compact, single-axis (in-plane + out-of-plane) | **Eq. H1-1 + Eq. H1-2**, *p. 16.1-85* | `compute_combined_strength_H1_3`, `ensure_h1_3_applicable` |
| **§H2** unsymmetric / other members | **Eq. H2-1** elastic-stress interaction, *p. 16.1-86* | `compute_combined_strength_H2` |
| **§H3.1** HSS torsion `Tn` | **Eq. H3-1 .. H3-5**, *p. 16.1-87* | `compute_torsional_strength_rect_HSS_H3_1`, `compute_torsional_strength_round_HSS_H3_1` |
| **§H3.2** HSS combined torsion / shear / flexure / axial | **Eq. H3-6**, *p. 16.1-88* | `compute_combined_strength_H3_2` |
| **§H3.3** non-HSS torsion limiting nominal stresses | **Eq. H3-7 / H3-8 / H3-9**, *p. 16.1-88* | `compute_nonHSS_torsion_limit_H3_3` |

### Constants exported from `apeSteel.combined._common`

| Symbol | Value | Role |
| --- | --- | --- |
| `H1_AXIAL_RATIO_BREAK` | `0.2` | Eq. H1-1a vs H1-1b break |
| `H1_1A_MOMENT_FACTOR` | `8/9` | Moment-term coefficient of Eq. H1-1a |
| `H1_1B_AXIAL_DIVISOR` | `2.0` | Axial-term divisor of Eq. H1-1b |
| `H1_2_ALPHA_LRFD` / `H1_2_ALPHA_ASD` | `1.0` / `1.6` | §H1.2 `Cb` amplifier `alpha` |
| `H1_2_OUT_OF_PLANE_LEAD` / `_QUAD` | `1.5` / `0.5` | Coefficients of Eq. H1-2 |
| `H3_ROUND_H3_2A_COEFF` / `_H3_2B_COEFF` | `1.23` / `0.60` | Round-HSS Fcr (Eq. H3-2a/b) |
| `H3_RECT_HT_LIMIT_1_COEFF` / `_2_COEFF` | `2.45` / `3.07` | Rect-HSS Fcr breaks |
| `H3_FCR_SHEAR_YIELD_FRACTION` / `H3_3_SHEAR_YIELD_FRACTION` | `0.6` | Shear-yield cap on `Fcr` |
| `H3_2_TORSION_NEGLECT_RATIO` | `0.2` | `Tr <= 0.2 Tc` reverts to §H1 |
| `PHI_TORSION_LRFD` / `OMEGA_TORSION_ASD` | `0.90` / `1.67` | §H3.1 factors |

### Explicit out-of-scope (documented, not hidden)

- **Open-section warping torsion (Design Guide 9).** §H3.3 here
  re-derives only the *code-level limiting nominal stresses* `Fn`
  (`Fy`, `0.6 Fy`, `Fcr`). A W-shape with significant torsion must be
  analysed with DG 9 — see design note 09 §1.
- **Net-section rupture (Eq. D2-2) and block shear (§J4).** §H1.2
  consumes a caller-supplied tensile `Pc`; apeSteel's `tension.D2`
  slice ships only **Eq. D2-1** gross-section yielding.
- **Appendix 8 B1 / B2 amplifiers.** Per the scoping decision in
  [design note 09](../design_notes/09_combined_H.md), the caller
  supplies *second-order* `Mrx` / `Mry` (Direct Analysis Method); no
  B1 / B2 machinery is implemented.

## Quick example

```python
--8<-- "examples/aisc_H_combined.py"
```

Output for a welded W-style section (`bf = 300 mm`, `tf = 20 mm`,
`hw = 400 mm`, `tw = 16 mm`, A992), `Kx Lx = Ky Ly = Kz Lz = 4.0 m`,
`Cb = 1.0`, `Pr = 600 kN`, `Mrx = 120 kN.m`:

```text
Equation governing    : H1-1b
Pr / Pc               : 0.133
Available Pc          :  4496.1 kN
Available Mcx         :   924.4 kN.m
Unity check (DCR)     : 0.197
Passes?               : True
```

## How it routes

The `Element.combined_strength_H1` facade (the Phase H-7 deliverable)
is a *uniaxial / biaxial* §H1.1 entry point for doubly-symmetric I
beam-columns. It resolves the available strengths internally and feeds
them to the pure §H1.1 kernel:

1. `Pc = phi_c Pn` from `self.compression_strength(Kx, Lx, Ky, Ly,
   Kz, Lz)` (Chapter E).
2. `Mcx = phi_b Mnx` from `self.run_full_check(...)` (the governing
   Chapter-F result after B4.1b routing).
3. **Biaxial Mcy resolution** (Phase F-8): if
   `required_moment_y_Mry != 0` *and* the caller did not supply
   `available_moment_y_Mcy`, `Mcy` is auto-resolved from §F6 via
   `compute_flexural_strength_F6_minor_axis(section_kind="doubly_symmetric_I")`.
   When `Mry == 0` the uniaxial path is byte-identical to the pre-F-8
   behaviour and §F6 is never evaluated.
4. The pure `compute_combined_strength_H1_1` kernel then selects:
   - **Eq. H1-1a** when `Pr / Pc >= 0.2`:
     `Pr/Pc + (8/9) (Mrx/Mcx + Mry/Mcy) <= 1.0`.
   - **Eq. H1-1b** when `Pr / Pc < 0.2`:
     `Pr/(2 Pc) + (Mrx/Mcx + Mry/Mcy) <= 1.0`.

The headline number on the returned `CombinedH1Report` is
`demand_capacity_ratio` (the LHS of the governing equation, *the
unity check*). `unity_check_passes` is the `<= 1.0` flag. Because the
resistance factors are baked into `Pc` / `Mc`, `Report.phi_LRFD` on
this report is `1.0` (the interaction itself carries no factor).

§H1.2 (flexure + tension) reuses the **same kernel** but takes a
tensile `Pc` (yielding only, **Eq. D2-1** in
`apeSteel.tension.yielding_D2`); `compute_Cb_amplification_factor_H1_2`
returns `sqrt(1 + alpha Pr/Pey)` so the caller can re-run Chapter F
with the amplified `Cb` before evaluating the interaction.

§H1.3 wraps two checks — an *in-plane* Eq. H1-1 (sliced to the bent
axis) and an *out-of-plane* Eq. H1-2 — and reports the governing one
via `H13GoverningCheck`.

§H3 splits into three: §H3.1 derives the nominal HSS torsional
strength `Tn = Fcr * C`, §H3.2 combines it with axial/shear/flexure
through Eq. H3-6, and §H3.3 returns only the limiting nominal stresses
for non-HSS sections (the caller supplies the warping/St-Venant
stresses themselves — DG 9 territory).

## Related

- [Design note 09 — Combined §H](../design_notes/09_combined_H.md)
- [API: Combined Forces](../api/combined.md)
- [§E — Compression](E_compression.md) (source of `Pc`)
- [§F — Flexure](F_flexure.md) (source of `Mcx`, `Mcy`)
- [Recipe: Beam-Column (H1.1)](../recipes/beam_column_H1.md)
- [Plotting: interaction diagrams](../plotting/interaction_diagrams.md)
