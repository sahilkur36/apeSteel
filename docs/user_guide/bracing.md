# Bracing

`Bracing` owns the domain of "how is this member laterally supported,
and what is the effective moment-diagram modification factor?". It is
a frozen dataclass with `slots=True`; three fields, all positional:

| Field | Symbol | Units | Default |
| --- | --- | --- | --- |
| `unbraced_length_top_flange_Lb_top` | $L_{b,\text{top}}$ | mm | — |
| `unbraced_length_bot_flange_Lb_bot` | $L_{b,\text{bot}}$ | mm | — |
| `lateral_torsional_buckling_modification_factor_Cb` | $C_b$ | — | `1.0` |

## Why a separate domain object?

Bracing is its own conceptual entity in design. A given `Element` is
frequently re-evaluated under several bracing scenarios:

- LRFD vs ASD under different load patterns.
- Code-mandated checks at multiple points along a span.
- Before / after a stiffener detail change.

Factoring `Lb_top`, `Lb_bot`, and `Cb` into a named object makes that
workflow first-class instead of dragging three parameters through every
method signature. Re-binding is one call:

```python
new_element = element.with_bracing(updated_bracing)
```

## `Lb_top` vs `Lb_bot` — which flange is in compression?

AISC 360-22 Chapter F speaks of "the unbraced length" — singular —
because Chapter F assumes the compression flange is identified by the
loading direction. `apeSteel` exposes **both** flanges explicitly so
the same `Bracing` instance covers positive *and* negative bending.

| Bending direction | Compression flange | `Element` method | Lb used |
| --- | --- | --- | --- |
| Positive (sagging) | Top | `flexural_strength_Fx_top_flange()` | `Lb_top` |
| Negative (hogging) | Bottom | `flexural_strength_Fx_bot_flange()` | `Lb_bot` |
| Either | Governing | `flexural_strength_Fx_both_flanges()` | min φ*Mn over both |

The `_both_flanges` variant runs both and returns a
`BothFlangesFlexureFxReport` carrying `top`, `bot`, `governing_flange`,
and `governing_report` so the worst case is one attribute access away.

### The fully-braced-flange convention

When a flange is **continuously** restrained by a composite slab or a
deep deck, use a small positive value — **not zero** — for that
flange's unbraced length:

```python
Bracing(
    unbraced_length_top_flange_Lb_top=0.001 * u.m,   # composite slab
    unbraced_length_bot_flange_Lb_bot=4.0   * u.m,   # actual bot Lb
    lateral_torsional_buckling_modification_factor_Cb=1.0,
)
```

The §F2-5 regime check expects a positive `Lb`; passing `0.0` is
rejected. `0.001 * u.m` (one micrometre) places the check deep in the
plastic-yielding regime ($L_b \ll L_p$) so the result is the bare $M_p$
(or $M_p / \Omega$ for ASD) with no LTB knock-down.

## $C_b$ — the moment-diagram modification factor

$C_b$ multiplies $M_n$ in the inelastic and elastic LTB regions to
account for non-uniform moment along the unbraced length (AISC F1-1):

$$
C_b = \frac{12.5\,M_{\max}}{2.5\,M_{\max} + 3\,M_A + 4\,M_B + 3\,M_C}
$$

Common values:

| Moment diagram | $C_b$ |
| --- | --- |
| Constant (the conservative default) | 1.00 |
| Simply supported, uniformly distributed load | 1.14 |
| Simply supported, mid-span point load | 1.32 |
| Cantilever, tip point load | 2.05 |
| Cantilever, uniformly distributed | 2.05 |

When the moment diagram is available in code form (e.g. from a
finite-element output),
`apeSteel.compute_Cb_from_quarter_point_moments(M_max, M_A, M_B, M_C)`
returns $C_b$ from the F1-1 quarter-point formula directly. Passing a
fitted value through the `Bracing` constructor is otherwise a one-line
call.

## Example — two bracing scenarios on the same section

```python
--8<-- "examples/bracing_scenarios.py"
```

The same `DoublySymmetricISection` is bound to two `Bracing` instances
in turn; the resulting `phi*Mn` from `flexural_strength_F2_both_flanges`
changes by the expected $C_b$ and $L_b$ dependency. Because `Bracing`
is frozen, swapping scenarios cannot mutate the previous result —
`element.with_bracing(...)` always returns a new `Element`.

## What `Bracing` does **not** include

By design, `Bracing` is the *flange-LTB* domain. It does not carry:

- Transverse stiffener spacing for shear with tension-field action —
  that is a per-call argument to
  `Element.shear_strength_G2(transverse_stiffener_spacing_a=...)`.
- Effective length factors $K_x$, $K_y$, $K_z$ for Chapter-E
  compression — those are per-call arguments to
  `Element.compression_strength(...)` and `Element.combined_strength_H1(...)`.
- Bracing-as-system stiffness / strength requirements (Appendix 6 of
  AISC 360 — a future-phase addition).
