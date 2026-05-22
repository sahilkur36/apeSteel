# AISC 360-22 §E — Compression

apeSteel implements the **full AISC 360-22 Chapter E** for compression
members. The pure-function calculators live in `apeSteel.compression`
and are orchestrated by `compute_compression_strength` (the
`section_kind`-driven facade) and by `Element.compression_strength` (the
doubly-symmetric I convenience that sits on the `Element` composite
spine). LRFD `phi_c = 0.90`, ASD `Omega_c = 1.67`.

## What's covered

| §E clause | Equations | apeSteel module |
| --- | --- | --- |
| **§E2** effective length, `Lc/r <= 200` advisory | *p. 16.1-37* | `apeSteel.compression.effective_length_E2` |
| **§E3** flexural buckling | **Eq. E3-1 .. E3-4**, *p. 16.1-37 .. 16.1-38* | `apeSteel.compression.flexural_buckling_E3.compute_flexural_buckling_critical_stress_E3` |
| **§E4** torsional / flexural-torsional | **Eq. E4-2 / E4-3 / E4-4 / E4-5**, *p. 16.1-39 .. 16.1-40* | `apeSteel.compression.torsional_flexural_E4` |
| **§E5** single-angle modified slenderness | **Eq. E5-1 / E5-3**, *p. 16.1-41* | `apeSteel.compression.single_angle_E5.compute_modified_slenderness_E5` |
| **§E7** slender-element effective area | **Eq. E7-1 / E7-2**, *p. 16.1-42 .. 16.1-43* | `apeSteel.compression.slender_elements_E7.compute_effective_area_Ae` |

Section families currently routed by the facade:

- **Doubly-symmetric I** (rolled W and welded built-up) — §E3 + §E4
  torsion + §E7 if any plate slender.
- **Singly-symmetric I**, **tee**, **channel**, **double angle** —
  §E4 flexural-torsional plus §E7 where applicable.
- **Rectangular** and **round HSS / Pipe** — §E3 + §E7.
- **Single angle** — §E5 modified slenderness fed back into §E3.

Out of scope: built-up sections with non-snug-tight lacing
(§E6.2b), cruciform sections, tapered members.

## Quick example

```python
--8<-- "examples/aisc_E_compression.py"
```

Output for a welded W-style section, `bf = 300 mm`, `tf = 20 mm`,
`hw = 400 mm`, `tw = 16 mm`, A992, with `Kx Lx = Ky Ly = Kz Lz = 4.0 m`:

```text
Governing limit state : flexural_buckling
Lc/r (governing)      :  57.15
Fcr (governing)       : 271.50 MPa
Pn                    :   4995.6 kN
phi*Pn (LRFD)         :   4496.1 kN
```

## How it routes

The orchestrator (`compute_compression_strength`) is a single entry
point that dispatches on `CompressionSectionProperties.section_kind`
— no string `match` on a shape name; the field is a `Literal` union
that the type checker enforces. Inside the orchestrator:

1. **§E2** computes `Lcx = Kx Lx`, `Lcy = Ky Ly`, `Lcz = Kz Lz`, and
   the per-axis `Lc/r` ratios. `Lc/r > 200` flips
   `within_slenderness_advisory_200` to `False` but does not raise
   (per Commentary §E2 the limit is an advisory).
2. **§E3** evaluates the elastic flexural-buckling stress `Fe` from
   **Eq. E3-4** about each axis and applies the **Eq. E3-2** (inelastic,
   `Lc/r <= 4.71 sqrt(E/Fy)`) or **Eq. E3-3** (elastic, `0.877 Fe`)
   regime.
3. **§E4** is invoked when the section has a non-zero shear-center
   offset or is otherwise eligible (tee, channel, singly-symmetric I,
   double angle): the **Eq. E4-2** torsional `Fe` (doubly-symmetric)
   or the **Eq. E4-5 / E4-7** flexural-torsional `Fe` (singly-
   symmetric / point-symmetric) is min-combined with the §E3 axis
   values.
4. **§E5** is taken for single angles: the **modified slenderness**
   (Eq. E5-1 with no end restraint, Eq. E5-3 with restraint at both
   ends) is substituted directly into the §E3 `Fcr` equations.
5. **§E7** runs when any plate is slender per Table B4.1a (set by the
   upstream `classify_axial_compression_B4_1a`): the effective width
   `be` from **Eq. E7-2** is iterated until `f` converges, then
   `Pn = Fcr * Ae` from **Eq. E7-1** replaces `Pn = Fcr * Ag`.

`Element.compression_strength(Kx, Lx, Ky, Ly, Kz, Lz)` is the
doubly-symmetric I convenience: it pulls
`section.compute_compression_properties(material, construction)` and
calls `compute_compression_strength_from_K_L`. Non-I geometries (tee,
channel, HSS, angle) call `compute_compression_strength` directly.

For a parameter sweep, `Element.phi_Pn_vs_length(lengths_L, Kx, Ky, Kz)`
returns a tuple of `CapacityCurvePoint`s (one `phi*Pn` per length),
which `Element.plot_compression_curve(...)` consumes to draw the
column-buckling curve.

## Related

- [Design note 08 — Compression §E](../design_notes/08_compression_E.md)
- [Design note 02 — Classification §B4](../design_notes/02_classification_B4.md) (§B4.1a feeds §E7)
- [API: Compression](../api/compression.md)
- [§H — Combined Forces](H_combined.md) (consumes `phi_c * Pn`)
- [Plotting: capacity curves](../plotting/capacity_curves.md)
