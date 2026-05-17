# Design note 09 — Combined forces per AISC 360-22 Chapter H

> **Status:** H-0 scaffold + independent oracle done (stubs raise
> `NotImplementedError`; `tests/golden/_chapterH_aisc_oracle.py` complete;
> design note + ROADMAP Phase H landed). Engine phases H-1..H-7 follow.
> **Drives:** `apeSteel.combined.*` and the thin `apeSteel.tension.*` slice.
> **Spreadsheet source:** the engineer's Chapter-H Excel workbook (filename
> to be confirmed before extraction — see §5; edition AISC 360-16, with the
> usual 360-22 vs 360-16 testing consequence).

Chapter H is a **consumer** chapter: it composes available strengths that
Chapters D / E / F / G already produced. The combined layer therefore
follows the same pure-function / frozen-`Report` / two-anchor validation
pattern as the compression layer, but its calculators take *available
strengths* (`Pc`, `Mc`, `Vc`, `Tc`) as inputs rather than re-deriving
member strength.

---

## 1. Scope

AISC 360-22 Chapter H, "Design of Members for Combined Forces and Torsion"
(pp. 16.1-83 – 16.1-88). apeSteel covers the **full chapter**:

| Clause | What | Status |
| --- | --- | --- |
| §H1.1 | Doubly/singly-symmetric, flexure + **compression** (Eq. H1-1a/1b) | H-1 |
| §H1.2 | Doubly/singly-symmetric, flexure + **tension** (H1-1a/1b w/ `Pc=φt·Pn`, `Cb` amplifier) | H-2 |
| §H1.3 | DS rolled compact, single-axis flexure + compression (in-plane H1-1 + out-of-plane Eq. H1-2) | H-3 |
| §H2 | Unsymmetric / other members, flexure + axial (Eq. H2-1, elastic stress) | H-4 |
| §H3.1 | Round / rectangular HSS torsion (`Tn=Fcr·C`, Eq. H3-1..H3-5) | H-5 |
| §H3.2 | HSS combined torsion/shear/flexure/axial (Eq. H3-6) | H-5 |
| §H3.3 | Non-HSS torsion — code-level limiting `Fn` only (Eq. H3-7/8/9) | H-5 |

**Explicit out-of-scope (documented, not hidden):**

- **Open-section warping torsion (Design Guide 9).** §H3.3 here re-derives
  only the code-level limiting nominal stresses `Fn` (`Fy` / `0.6Fy` /
  `Fcr`). The actual warping (`σw`) and St-Venant shear stresses for a
  W-shape under torsion require DG 9; the calculator accepts caller-
  supplied required stresses and performs the limiting-stress check. A
  W-shape with significant torsion must be evaluated with DG 9 — flagged
  by the calculator.
- **Net-section rupture (Eq. D2-2) and block shear (§J4).** §H1.2 needs an
  axial-tension `Pc`. apeSteel does not yet implement Chapter D; the thin
  `apeSteel.tension.yielding_D2` slice provides **only** gross-section
  yielding `Pn = Fy·Ag` (Eq. D2-1). The caller must separately verify
  rupture; `compute_combined_strength_H1_2` documents this in its API.
- **Appendix 8 (B1/B2 amplifiers).** Per the scoping decision the caller
  supplies *second-order* `Mrx`/`Mry` (Direct Analysis Method). No B1/B2
  machinery is implemented; `Mr` is taken as already amplified.

---

## 2. AISC 360-22 Chapter H equation map

Resistance factors: §H1/§H2 carry **no extra φ** — they are pure
interaction checks; the factors live inside the supplied `Pc = φc·Pn`,
`Mc = φb·Mn`, `Vc = φv·Vn`. The only factor that *originates* in
Chapter H is `φT = 0.90` / `ΩT = 1.67` for §H3.1 HSS torsion.

### §H1.1 — flexure + compression

```
Pr/Pc ≥ 0.2:  Pr/Pc      + 8/9·(Mrx/Mcx + Mry/Mcy) ≤ 1.0   (Eq. H1-1a, p. 16.1-83)
Pr/Pc < 0.2:  Pr/(2·Pc)  +     (Mrx/Mcx + Mry/Mcy) ≤ 1.0   (Eq. H1-1b, p. 16.1-83)
```

`Pc = φc·Pn` (Chapter E), `Mc = φb·Mn` (Chapter F), `Pr`/`Mr` =
required *second-order* strengths.

### §H1.2 — flexure + tension

Same Eq. H1-1a/H1-1b, but `Pc = φt·Pn` (tension; here D2-1 yielding only).
For doubly-symmetric members, `Cb` in Chapter F **may** be multiplied by

```
√(1 + α·Pr/Pey)        Pey = π²·E·Iy / Lb²        (§H1.2, p. 16.1-84)
α = 1.0 (LRFD), 1.6 (ASD)
```

The amplified `Cb` increases the LTB strength but `Mn ≤ Mp` still caps it.
**Layering decision:** to keep §H1.2 a pure consumer of a numeric `Mc`,
`compute_combined_strength_H1_2` does *not* re-run Chapter F. It exposes
`compute_Cb_amplification_factor_H1_2(...)`; the caller (or the H-7
`Element` facade) re-evaluates Chapter F with `Cb' = Cb·√(1+α·Pr/Pey)`
and passes the resulting `Mcx` back in. The interaction kernel is shared
with §H1.1.

### §H1.3 — DS rolled compact, single-axis flexure + compression

Applicability: doubly-symmetric, rolled, compact, single-axis (major)
bending, `KLz ≤ KLy`, `Mry = 0`. Two independent checks:

```
(a) in-plane:      Eq. H1-1 with Pc, Mcx in the plane of bending
(b) out-of-plane:  Pr/Pcy·(1.5 − 0.5·Pr/Pcy) + (Mrx/(Cb·Mcx))² ≤ 1.0   (Eq. H1-2, p. 16.1-84)
```

`Pcy` = available compressive strength out of plane; `Mcx` = available
LTB strength for `Cb = 1.0`. The product `Cb·Mcx` in the denominator is
capped at `φb·Mp` (the amplified term need not exceed plastic strength) —
implemented as `min(Cb·Mcx, φb·Mp)`; flagged in code and bounded against
the workbook.

### §H2 — unsymmetric / other members

```
|fra/Fca + frbw/Fcbw + frbz/Fcbz| ≤ 1.0          (Eq. H2-1, p. 16.1-85)
```

Required stresses are *signed*; available stresses positive
(`Fca = φc·Fcr`, `Fcbw = φb·Mnw/Sw`, …). The worst point governs (caller
supplies the point's stresses).

### §H3.1 — HSS torsion

```
Tn = Fcr·C                                        (Eq. H3-1, p. 16.1-86)

Round HSS  (C = π·(D−t)²·t/2):
  Fcr = max(  1.23·E / (√(L/D)·(D/t)^{5/4}) ,     (Eq. H3-2a)
              0.60·E / (D/t)^{3/2}           )     (Eq. H3-2b)
  Fcr ≤ 0.6·Fy

Rect HSS  (h/t = larger flat-wall ratio; C tabulated):
  h/t ≤ 2.45√(E/Fy):                Fcr = 0.6·Fy
  2.45√(E/Fy) < h/t ≤ 3.07√(E/Fy):  Fcr = 0.6·Fy·2.45√(E/Fy)/(h/t)   (Eq. H3-4)
  3.07√(E/Fy) < h/t ≤ 260:          Fcr = 0.458·π²·E/(h/t)²          (Eq. H3-5)
```

`φT = 0.90`, `ΩT = 1.67`.

### §H3.2 — HSS combined torsion/shear/flexure/axial

```
Tr ≤ 0.2·Tc:  torsion neglected → check by §H1
Tr > 0.2·Tc:  (Pr/Pc + Mr/Mc) + (Vr/Vc + Tr/Tc)² ≤ 1.0   (Eq. H3-6, p. 16.1-87)
```

### §H3.3 — non-HSS torsion (limiting stresses only)

```
Eq. H3-7  yielding under normal stress:  Fn = Fy
Eq. H3-8  shear yielding under shear:    Fn = 0.6·Fy
Eq. H3-9  buckling:                      Fn = Fcr
```

(governing = lowest applicable). Stress demands → DG 9 (out of scope).

---

## 3. Module layout

```
src/apeSteel/
├── combined/
│   ├── __init__.py
│   ├── _common.py                # φT/ΩT, all Chapter-H literal coeffs, CombinedLimitState, citations
│   ├── flexure_axial_H1_1.py     # §H1.1  Eq. H1-1a / H1-1b   → CombinedH1Report
│   ├── flexure_tension_H1_2.py   # §H1.2  Cb amplifier + H1-1 (Pc=φt·Pn)
│   ├── single_axis_H1_3.py       # §H1.3  in-plane H1-1 + out-of-plane Eq. H1-2
│   ├── unsymmetric_H2.py         # §H2    Eq. H2-1            → CombinedH2Report
│   ├── torsion_H3.py             # §H3.1/3.2/3.3              → TorsionH3Report
│   └── combined_strength.py      # orchestrator / Element entry points
└── tension/
    ├── __init__.py
    └── yielding_D2.py            # thin D2-1 Pn=Fy·Ag, φt=0.90 (D2-2 out of scope)
```

`apeSteel.tension` is a deliberately minimal slice so §H1.2 has an
upstream `φt·Pn` without pulling in a full (unscoped) Chapter D. A future
dedicated Chapter-D phase supersedes it (D2-2 rupture, §J4 block shear).

### Report dataclasses

Frozen `Report` subclasses, identical convention to the compression
layer. Chapter-H interaction reports headline a **demand/capacity ratio**
rather than a nominal strength; because the φ already lives in the
supplied `Pc`/`Mc`, the report's own `phi_LRFD = 1.0` (documented on the
class). `TorsionH3Report` (§H3.1) *does* carry `φT = 0.90` and a real
`Tn`.

```python
@dataclass(frozen=True, slots=True)
class CombinedH1Report(Report):
    governing_equation: CombinedLimitState        # "H1-1a" | "H1-1b" | "H1-2"
    required_axial_Pr: float
    available_axial_Pc: float
    axial_ratio_Pr_Pc: float
    required_moment_x_Mrx: float
    available_moment_x_Mcx: float
    required_moment_y_Mry: float
    available_moment_y_Mcy: float
    moment_ratio_term: float
    demand_capacity_ratio: float
    unity_check_passes: bool
    cited_clauses: tuple[AISCClauseReference, ...]
```

`CombinedH2Report` (stress terms + signed sum) and `TorsionH3Report`
(`Fcr`, `C`, `Tn`, `φT·Tn`, governing limit state, the Eq. H3-6 terms)
follow the same shape.

---

## 4. Public API

```python
def compute_combined_strength_H1_1(
    required_axial_Pr, available_axial_Pc,
    required_moment_x_Mrx, available_moment_x_Mcx,
    required_moment_y_Mry=0.0, available_moment_y_Mcy=0.0,
) -> CombinedH1Report: ...

def compute_combined_strength_H1_2(...) -> CombinedH1Report: ...          # Pc = φt·Pn
def compute_Cb_amplification_factor_H1_2(Pr, E, Iy, Lb, alpha=1.0) -> float: ...
def compute_combined_strength_H1_3(...) -> CombinedH13Report: ...        # (a)+(b)
def compute_combined_strength_H2(...) -> CombinedH2Report: ...
def compute_torsional_strength_round_HSS_H3_1(Fy, E, D, t, L) -> TorsionH3Report: ...
def compute_torsional_strength_rect_HSS_H3_1(Fy, E, h_t, C) -> TorsionH3Report: ...
def compute_combined_strength_H3_2(...) -> CombinedH3_2Report: ...
```

`Element` integration (phase H-7): `Element.combined_strength_H1(Pr, Mrx,
Mry, *, Kx, Lx, Ky, Ly, Kz, Lz, ...)` resolves `Pc` from
`Element.compression_strength(...)` (Chapter E) and `Mc` from the routed
`flexural_strength_*` (Chapter F), then calls the pure calculator. No
changes to the compression / flexure modules — H1 is a pure consumer
(confirmed by design note 08 §7).

---

## 5. Edition decision and testing consequence

The engineer's workbook implements AISC **360-16**; apeSteel implements
**360-22**. For Chapter H the two editions are **largely identical** — the
H1 interaction equations, the §H2 stress interaction, and the §H3 HSS
torsion expressions are unchanged 360-16 → 360-22. The divergence risk is
*downstream*: the supplied `Pc`/`Mc` may differ between editions when the
member has slender elements (the §E7 360-16-vs-360-22 gap documented in
design note 08 §5) or a slender-web girder. The Chapter-H *composition*
itself is edition-independent.

Two independent anchors (unchanged doctrine):

1. **Independent stdlib oracle** — `tests/golden/_chapterH_aisc_oracle.py`,
   imports only `math`, re-derives every Chapter-H equation from the
   printed spec. The facade must match it **bit-exact** (`rel_tol=1e-9`).
   This is the ground truth.
2. **Excel anchor** — a faithful dump of the engineer's Chapter-H
   workbook to `tests/golden/data/`. Edition-independent quantities
   (the H1 DCR, the H2 stress sum, the §H3.1 HSS `Fcr`/`Tn`) are
   bit-matched at workbook precision (~2e-3, kgf-cm-tonne, `Fy = ksi·70.3`).
   Any 360-22-vs-360-16 difference traceable to a slender `Pc`/`Mc` is
   documented and bounded, never hidden. **The exact workbook filename is
   confirmed with the engineer before extraction (phase H-6).**

Plus reviewer-signable hand calcs in `tests/unit/`.

---

## 6. Phased delivery

| Phase | Deliverable | Gate |
| --- | --- | --- |
| **H-0** ✅ | `combined/` + `tension/` scaffold (stubs raise `NotImplementedError`); stdlib oracle covering §H1.1/1.2/1.3/§H2/§H3.1/3.2/3.3; this design note; ROADMAP Phase H. | ruff + ruff-format + pyright strict + pytest green |
| **H-1** | §H1.1 Eq. H1-1a/1b + `CombinedH1Report`. | oracle bit-exact (both regimes, biaxial) + hand calc |
| **H-2** | `tension/yielding_D2.py` (D2-1) + §H1.2 (Cb amplifier, `Mp` cap, `Pc=φt·Pn`). | oracle + hand calc |
| **H-3** | §H1.3 in-plane + out-of-plane Eq. H1-2 + applicability guards. | oracle + hand calc |
| **H-4** | §H2 Eq. H2-1 elastic-stress interaction. | oracle + hand calc |
| **H-5** | §H3.1 round/rect HSS `Tn`; §H3.2 Eq. H3-6; §H3.3 limiting `Fn`. | oracle + hand calc |
| **H-6** | Excel anchor — workbook dump + edition-independent bit-match; divergence documented/bounded. | anchor suite green |
| **H-7** | `Element.combined_strength_H1/_H1_3/_H2/_H3` consuming Chapter-E φPn + Chapter-F φMn; `apeSteel` re-exports; ROADMAP tick; this note → done. | full suite green on 3.11/3.12/3.13 |

Each phase is a green-gated commit verified locally exactly as CI does
(`ruff check . && ruff format --check . && pyright && pytest --cov=apeSteel`,
confirming the explicit `All checks passed!` line). A phase cannot import
from a later-phase module (ARCHITECTURE.md §1) — Chapter H importing
Chapters D/E/F/G is legal (all are earlier layers).

---

## 7. Forward notes

- **App. 8 B1/B2.** If a later phase needs hand-amplified second-order
  moments (Effective-Length Method users), an optional Appendix-8 helper
  can be added as a *separate* pure module that produces `Mr` before it
  reaches the H1 calculator. The H1 calculator stays a pure consumer.
- **Full Chapter D.** When tension members get a dedicated phase, the
  thin `tension/yielding_D2.py` is absorbed (D2-2 rupture with shear-lag
  `U`, §J4 block shear); §H1.2's `Pc` source is swapped with no change to
  the interaction kernel.
- **Seismic.** AISC 341 capacity-design demands (amplified `Pr` with
  overstrength, `Ω0`) feed the same H1 calculator from the seismic facade
  layer; not a Chapter-H concern.

---

## 8. Open questions

1. **§H1.3 `Cb·Mcx` cap.** Implemented as `min(Cb·Mcx, φb·Mp)`. Confirm
   against the workbook's H1.3 example in phase H-6; if the workbook
   omits the cap, document the (conservative) divergence rather than
   matching the workbook.
2. **§H2 critical point.** Eq. H2-1 must be checked at the point of
   maximum combined stress. apeSteel takes the point's stresses as
   inputs (no automatic extreme-fibre search); the facade documents that
   the caller supplies the governing point.
3. **§H3.3 / DG 9.** The non-HSS torsion path produces only the
   code-level limiting `Fn`. Whether apeSteel should ever implement the
   DG 9 warping-stress derivation is deferred to a future torsion design
   note; for now the calculator raises an explanatory pointer if asked
   for an open-section combined-stress result without caller-supplied
   stresses.
