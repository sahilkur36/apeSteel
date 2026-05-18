# Design note 10 — Full AISC 360-22 Chapter F (all section families)

> **Status: COMPLETE (F-0 … F-8 shipped).**  The entire AISC 360-22
> Chapter F (§F2–§F12, all section families) is implemented, anchored
> (independent stdlib oracle bit-exact `rel_tol=1e-9` + AISC Manual
> v15.1 worked-example cross-checks where staged), and gated.  Phase
> **F-8** integrated the section-kind facade
> (`apeSteel.checks.flexure_dispatch`), the AISC v16 catalog flexural
> path (`AISCv16Catalog.get_flexural_section_properties`), the channel
> §F2(major)/§F6(minor) wiring, the `Element.combined_strength_H1`
> auto-`Mcy` (design-note-09 H-7 gap closed), and the F9-EC-1
> resolution (§F9.2(b)(2) 2L web-leg LTB → exact §F10 Eq. F10-2/F10-3).
> The shipped I-shape `Element`/`run_full_beam_check`/§F2–§F5 path and
> every prior golden/oracle/Manual/catalog/Chapter-H anchor are
> bit-unchanged; the non-I §F dispatch is purely additive.  Scope and
> architecture were locked by the engineer (senior-engineer-
> orchestrated build; one agent per phase against this contract).
> **Drives:** `apeSteel.flexure.*`, `apeSteel.sections.flexural_properties`,
> `apeSteel.classification.*`, and the geometry classes' new
> `compute_section_properties()` flexure path.
> **Extends:** design note 04 (§F2–§F5, shipped, I-shapes only).
> **Citation source-of-truth:** `docs/design_notes/_chapterF_citation_reference.md`
> — every §F equation number, Table B4.1b case, λ_p / λ_r, and AISC
> Manual v15.1 worked-example ID/page is transcribed there verbatim from
> `a360-22w.pdf` / `v15.1_vol-1_design-examples.pdf` /
> `v15.1_vol-2_design-tables.pdf` (an F-0 deliverable). Code and oracle
> cite *that* file; nothing in this note is pinned from memory.

---

## 1. Scope

AISC 360-22 Chapter F, "Design of Members for Flexure" (pp. 16.1-48 –
16.1-72). apeSteel currently ships only the major-axis I-shape suite
(§F2–§F5, doubly-symmetric; §F4 also singly-symmetric). This phase
completes the **entire chapter**.

| Clause | What | apeSteel today | Phase |
| --- | --- | --- | --- |
| §F1 | General — `Cb` (Eq. F1-1) | ✅ `flexure/cb.py` | — |
| §F2 | DS compact I **& channels**, major axis | ✅ I only — channel `c` (Eq. F2-8b) missing | F-1 |
| §F3 | DS I, compact web, NC/slender flange | ✅ | F-1 (refactor only) |
| §F4 | Other I (DS NC-web + SS I), major axis | ✅ DS+SS | F-1 (refactor only) |
| §F5 | DS **& SS** I, slender web | ✅ DS only — SS raises `NotImplementedError` | F-1 |
| §F6 | I-shapes **& channels, minor axis** | ❌ | F-4 |
| §F7 | Square/rectangular HSS & box | ❌ | F-3 |
| §F8 | Round HSS / Pipe | ❌ | F-2 |
| §F9 | Tees & double angles, plane of symmetry | ❌ | F-5 |
| §F10 | Single angles | ❌ | F-6 |
| §F11 | Rectangular bars & rounds | ❌ | F-7 |
| §F12 | Unsymmetrical shapes | ❌ | F-7 |
| §F13 | Proportion limits (holes F13.1, proportioning F13.2) | partial (F5 uses some) | F-1 / per-phase |

**Explicit out-of-scope (documented, not hidden):**

- **§F13.1 tension-flange-hole rupture reduction** is implemented only
  where a §F section invokes it; a standalone net-flexural-rupture
  calculator (full §F13.1 with `Afn`, `Yt`) is a per-phase add, not a
  separate chapter port. Flagged in each report where it could apply.
- **§F13.3 cover-plated and §F13.4 built-up proportioning** geometry
  helpers are not in scope; the calculators accept the resulting
  `FlexuralSectionProperties` and do not synthesise cover plates.
- **Lateral bracing design (§F1(2), App. 6)** — strength only; brace
  sizing is not Chapter F.
- **Edition delta.** AISC Manual v15.1 worked examples are 360-16-based.
  Chapter F equations F2–F12 are materially unchanged 360-16 → 360-22;
  any per-section delta found during F-0 transcription is documented in
  `_chapterF_citation_reference.md` and the Manual anchor is taken on
  edition-independent quantities only (the Phase E precedent for §E7).

---

## 2. Why a new currency, and why F2–F5 move onto it

The shipped flexure layer is I-shape-locked at the **data model**, not
just the calculators:

- `SectionProperties` (`sections/properties.py`) is I-centric:
  `flange_width_to_thickness_ratio_bf_2tf`,
  `web_height_to_thickness_ratio_h_tw`,
  `distance_between_flange_centroids_ho`,
  `effective_radius_of_gyration_for_LTB_rts`. No `Z`/`S` minor-axis
  flexural path, no HSS-wall / round-`D/t` / angle-leg / tee-stem
  slenderness, no per-element classification list.
- `classify_flexural_compactness_B4_1b` only does Table B4.1b Cases
  10/11 (I flange) + 15/16 (I web).
- The non-I geometries (`RectangularHSS`, `RoundHSS`, `TeeSection`,
  `ChannelSection`, `SingleAngleSection`, `DoubleAngleSection`) exist
  but emit only `CompressionSectionProperties` (Phase E) — no flexure
  path.

Phase E already established the correct pattern: a section-kind-
discriminated currency (`CompressionSectionProperties` with a
`section_kind` literal + a `CompressionPlateElement` list) that the
facade routes on by *type*, not by string `match`. Flexure adopts the
same pattern. **F2–F5 are refactored onto it** (the engineer's locked
decision), but the refactor is **internal and signature-preserving**:
the existing public functions keep their `SectionProperties` parameters,
adapt internally via `FlexuralSectionProperties.from_legacy(...)`, and
must reproduce every shipped golden / oracle / Excel-anchor value
**bit-for-bit** (`rel_tol=1e-9`). The verified path's *numbers* do not
move; only the data it flows through is generalised.

---

## 3. The generalized model — `apeSteel.sections.flexural_properties`

New module, precisely analogous to `compression_properties.py`. Kept
separate from `SectionProperties` (same rationale Phase E gave: "keep it
separate, leave the verified path untouched"); F2–F5 consume it via an
adapter; new sections consume it natively; the catalog and geometry
classes grow a `compute_section_properties()` that returns it.

```python
FlexuralSectionKind = Literal[
    "doubly_symmetric_I", "singly_symmetric_I", "channel",
    "rectangular_HSS", "round_HSS",
    "tee", "double_angle", "single_angle",
    "rectangular_bar", "round_bar", "unsymmetric",
]

BendingAxis = Literal["major", "minor"]   # flexure is axis-specific

@dataclass(frozen=True, slots=True)
class FlexuralPlateElement:
    name: str                       # "flange" | "web" | "wall" | "stem" | "leg"
    role: Literal["compression_flange", "tension_flange", "web",
                  "stem", "leg", "hss_flange", "hss_web"]
    aisc_b4_1b_case: str            # "10","11","12","14","15","16","17","19","20"
    slenderness_ratio_lambda: float
    compact_limit_lambda_p: float
    noncompact_limit_lambda_r: float
    @property
    def classification(self) -> FlexuralPlateClass: ...   # compact|non_compact|slender

@dataclass(frozen=True, slots=True)
class FlexuralSectionProperties:
    section_kind: FlexuralSectionKind
    symmetry: SectionSymmetry                       # reuse Phase E literal
    # gross / both axes (flexure is axis-specific — carry both)
    overall_depth_d: float
    gross_area_Ag: float
    moment_of_inertia_Ix: float; elastic_modulus_Sx: float
    plastic_modulus_Zx: float;    radius_of_gyration_rx: float
    moment_of_inertia_Iy: float; elastic_modulus_Sy: float
    plastic_modulus_Zy: float;    radius_of_gyration_ry: float
    torsional_constant_J: float = 0.0
    warping_constant_Cw: float = 0.0
    distance_between_flange_centroids_ho: float = 0.0          # I / channel
    effective_radius_of_gyration_for_LTB_rts: float = 0.0      # I / channel
    section_constant_c: float = 1.0                            # Eq. F2-8a/8b
    # singly-symmetric / tee (carried over from SectionProperties optionals)
    Sxc: float = 0.0; Sxt: float = 0.0; Iyc: float = 0.0
    hc: float = 0.0; hp: float = 0.0
    # round HSS / Pipe (§F8 uses D/t directly)
    diameter_D: float = 0.0; wall_thickness_t: float = 0.0
    # single angle (§F10 principal-axis)
    principal_I_major_Iw: float = 0.0; principal_I_minor_Iz: float = 0.0
    min_principal_radius_rz: float = 0.0
    equal_leg: bool = True; geometric_axis_bending: bool = False
    # §F12 elastic Fn·S — extreme-fibre elastic moduli to each corner
    extreme_fibre_moduli: tuple[float, ...] = ()
    plate_elements: tuple[FlexuralPlateElement, ...] = ()

    @classmethod
    def from_legacy(cls, sp: SectionProperties, *, kind, symmetry,
                    construction) -> "FlexuralSectionProperties": ...
```

`from_legacy` is the bit-exactness lever for F-1: it lifts the shipped
I-shape `SectionProperties` (including the Phase 9b SS optionals and the
`resolved_*` fallbacks) into the new model with zero numerical change.

---

## 4. Generalized classifier

`classify_flexural_compactness` (new name; `_B4_1b` kept as a thin
shim for back-compat) dispatches Table B4.1b by `section_kind` and emits
the `FlexuralPlateElement` list. All case numbers / λ_p / λ_r come from
`_chapterF_citation_reference.md` §2. Cases required by scope:

| Kind | Elements → B4.1b case |
| --- | --- |
| doubly_symmetric_I | flange 10/11, web 15 |
| singly_symmetric_I | flange 10/11, web 16 |
| channel | flange 10/11, web 15 |
| rectangular_HSS | flange (flexural compression) + web — HSS-flexure cases |
| round_HSS | round-HSS-flexure case (D/t) |
| tee | flange 10/11, stem case |
| single_angle / double_angle | leg case |
| rectangular_bar / round_bar | n/a (compact by inspection; §F11 ductility check) |
| unsymmetric | per element; §F12 is elastic so classification is informational |

Exact case numbers (12 leg, 14 stem, 17/19 HSS, 20 round HSS, …) are
**not** asserted here — they are the first thing F-0 pins from the PDF.

---

## 5. Phases

Priority order is the engineer's selection. Critical path is **serial
through F-1**; F-2…F-7 parallelise (isolated worktrees) once F-1 is
bit-exact; F-8 integrates.

Every phase, like Phases E/H: an independent **stdlib oracle** that
re-derives `Mn` from the 360-22 PDF with no `apeSteel.flexure` import
(bit-exact `rel_tol=1e-9` primary anchor) + a **golden** snapshot +,
for §F6–§F12, an **AISC Manual v15.1 worked-example cross-check**
(catalog properties, Manual printed sig-figs — see §6). Reviewer hand
calcs only where the Manual prints no intermediate worth pinning.

### F-0 — Generalized model + full classifier + oracle scaffold 🟦🟧
- `_chapterF_citation_reference.md` (Ch F eqns/pages, B4.1b cases,
  Manual Ch F example index) — verified against the PDFs.
- `sections/flexural_properties.py` (model above) + `from_legacy`.
- `classify_flexural_compactness` covering **every** case F2–F12 needs.
- `tests/golden/_chapterF_full_aisc_oracle.py` skeleton (extends the
  existing `_chapterF_aisc_oracle.py`).
- **No behaviour change.** Done when: pyright 0 / ruff / suite green;
  classifier unit-anchored to hand-derived λ for one shape per kind.

### F-1 — Refactor §F2–§F5 onto the model; close I-shape gaps 🟧
- F2–F5 consume `FlexuralSectionProperties` via `from_legacy`; public
  signatures unchanged.
- Add channel `c` (Eq. F2-8b) to §F2; add **SS slender-web §F5**
  (delete the `NotImplementedError` in `run_full_beam_check` and
  `Element.flexural_strength_F5_*`).
- **Gate (hardest):** every shipped golden + `test_chapterF_independent`
  + `test_flexure_F2/F3/F4_golden` + `test_catalog_flexure_F2_golden`
  + the §F2 Excel anchor must pass **unchanged** at `rel_tol=1e-9`.
  Any delta = the refactor is wrong. I review the diff personally.

### F-2 — §F8 round HSS / Pipe 🟧
- `RoundHSS.compute_section_properties`; classifier round-HSS case.
- Eq. F8-1 (yielding) / F8-2 (NC, FLB) / F8-3 (slender) / F8-4 (`Fcr`).
  No LTB. Cheapest section in the chapter.
- Anchor: oracle + Manual v15.1 §F8 example (Pipe/round HSS).

### F-3 — §F7 square/rectangular HSS & box 🟧
- `RectangularHSS.compute_section_properties` (Zx, Zy, Sx, Sy, J);
  classifier HSS flange + web flexure cases; **both axes**.
- Eq. F7-1 (yield), F7-2..F7-5 (FLB, compact/NC/slender flange),
  F7-6..F7-9 (WLB), F7-10/F7-11 (LTB). §F13.1 hole check flagged.
- Anchor: oracle + Manual v15.1 §F7 example.

### F-4 — §F6 minor-axis I 🟧
- Reuse existing I geometry / `from_legacy`; populate `Zy/Sy` +
  minor-axis flange classification. **I-shapes only** (DS & SS).
- Eq. F6-1 (`Mn=Mp=Fy·Zy ≤ 1.6·Fy·Sy`), F6-2/F6-3/F6-4 (FLB NC/slender).
- Anchor: oracle + Manual v15.1 §F6 example (W weak-axis).
- **Scope moved to F-8 (orchestrator decision, post-F-2):** (a) wiring
  `Element.combined_strength_H1` to auto-resolve `Mcy` — `element.py`
  is an orchestrator-owned seam, all Element/facade work consolidated
  in F-8; (b) **channel** minor-axis §F6 — channel flexure currency is
  not wired until the F-8 catalog step (same deferral as F-1's channel
  §F2 Manual anchor). F-4 stays a pure, parallel-safe engine phase.

### F-5 — §F9 tees & double angles (plane of symmetry) 🟧
- `TeeSection` / `DoubleAngleSection.compute_section_properties`.
- Yielding (stem-tension vs stem-compression, `1.6My` / `My` caps),
  LTB (Eq. F9-4..F9-6, `B` factor; sign by stem state), flange FLB
  (Eq. F9-10..), stem / double-angle-leg local buckling (Eq. F9-16..).
- Stem-in-compression low-ductility flag in the report.
- Anchor: oracle + Manual v15.1 §F9 examples (WT, 2L).

### F-6 — §F10 single angles 🟧
- `SingleAngleSection.compute_section_properties` (principal axes
  `Iw/Iz/rz`; equal- vs unequal-leg; geometric-axis option).
- Eq. F10-1 (yield), F10-2/3 (LTB via `Me` F10-4/5/6), F10-7/8/9
  (leg local buckling). Most code-intensive section.
- Anchor: oracle + Manual v15.1 §F10 example.

### F-7 — §F11 bars/rounds + §F12 unsymmetrical 🟧
- New `RectangularBar` / `RoundBar` geometry; Eq. F11-1..F11-4
  (yield + LTB for rect bars; rounds = `Mp`).
- §F12 elastic catch-all: `Mn = Fn·S`, `Fn = min(yield, LTB, LB)` over
  `extreme_fibre_moduli` (Eq. F12-1..). Closes Chapter F.
- Anchor: oracle + Manual v15.1 §F11/§F12 examples.

### F-8 — Facade + catalog + element integration 🟩⬛
- `section_kind` dispatch in `run_full_beam_check` / `Element`
  (mirror the compression facade switch). Both-flange / both-axis
  routing where applicable.
- `AISCv16Catalog.get_section_properties` → `FlexuralSectionProperties`
  for HSS / PIPE / WT / MT / ST / C / MC / L / 2L wired to the right §F.
- ROADMAP Phase F ticked; README scope table + design note 04 status
  cross-linked; this note's Status set to complete.

---

## 6. Two-tier anchor (the Phase E pattern, made explicit)

1. **Primary, bit-exact (`rel_tol=1e-9`):** the independent stdlib
   oracle (`_chapterF_full_aisc_oracle.py`) re-derives `Mn` from the
   360-22 spec with no `apeSteel.flexure` import. This is the
   regression pin for every phase.
2. **External authority (Manual printed sig-figs):** a golden test
   feeds **AISC v16 catalog** properties (NOT plate-built — the
   documented 2–7 % k-radius gap would swamp the comparison) for the
   exact shape in a Manual v15.1 Chapter-F worked example, and asserts
   apeSteel's `φMn` *and the printed intermediates* (`Lp`, `Lr`, `Mp`,
   governing `Mn`) match the Manual to its sig-figs. No §F section in
   scope lacks a published external anchor — superseding the
   "oracle + hand-calc only" fallback proposed earlier.

CI gates every phase: `ruff` + `ruff format` + `pyright` strict (0
errors) + `pytest` (coverage ≥ 90 % on touched code) + the layer rule
(no import from a later phase's module).

---

## 7. Senior-engineer orchestration

- The **contract** (this note + ROADMAP Phase F) is authored and owned
  by the orchestrator, not delegated.
- One Opus-4.7 agent implements each phase against this contract, in an
  isolated git worktree. The orchestrator reviews every phase against
  the §6 gates **before** the next phase starts; F-1's bit-exactness
  diff is reviewed line-by-line.
- The orchestrator owns all shared seams: the frozen model (after F-0),
  the classifier (must be complete in F-0 so F-2…F-7 stay additive),
  and every `__init__.py` / `apeSteel/__init__.py` / ROADMAP / README
  merge. Agents create new files; the orchestrator integrates seams.
- Sequencing: F-0 → F-1 (serial, gated). Then F-2/F-3/F-4 may run
  concurrently (independent section files; shared surface frozen);
  F-5/F-6/F-7 next wave; F-8 last, by the orchestrator.

---

## 9. Tooling & citation provenance (resolved at design time)

PDF access was de-risked before any phase started:

- Subagents are sandbox-denied on the SeaDrive AISC library; the **main
  process** can read it and has `fitz` (PyMuPDF) + `pypdf`. The
  environment has **no `pdftoppm`**, so the `Read` tool cannot render
  PDFs — extraction is via PyMuPDF text only.
- The needed source pages are **staged inside the workspace** at
  `docs/design_notes/_aisc_src_extract/` (gitignore this dir — it holds
  copyrighted excerpts):
  - `spec_chapterF.txt` — AISC 360-22 Chapter F spec body, printed
    16.1-53 … 16.1-74 (F2 → F13 equation forms, numbers, page labels).
  - `spec_B4_1b.txt` — only printed 16.1-19 text-extracts; **Table
    B4.1b case rows are image-rendered** in the spec PDF and do not
    text-extract.
  - `manual_v1_chapterF_index.txt` — Manual v15.1 Vol.1 Chapter-F
    worked-example headers + PDF pages (the primary external anchor).
  - `manual_v2_part3_index.txt` — Vol.2 is image-rendered; **secondary
    anchor deferred**, engineer-confirmed if ever used (oracle + Vol.1
    already satisfy the §6 two-tier requirement; Vol.2 was only the
    coarse extra).
- **B4.1b new-case provenance (12 leg, 14 stem, 17/19 HSS, 20 round
  HSS):** λ_p / λ_r formulas are taken from the authoritative
  `aisc-steel-design` skill reference `references/aisc360_members.md`
  (a curated standard reference, not model memory). The exact **Case
  numbers and `16.1-NN` page labels** for these rows are set
  `equation="Case ?"/page=None` and **flagged for engineer confirmation
  at the F-0 review gate** — never invented. The independent oracle
  re-derives the λ limits numerically regardless, so correctness does
  not depend on the case-number label.

`_chapterF_citation_reference.md` is produced as the **first F-0 task**
from the staged extracts + the skill reference + the existing in-repo
citations — not from a separate pre-phase agent (avoids a reconciliation
seam).

---

## 8. Bookkeeping

Per the ROADMAP rules: every phase PR ticks its ROADMAP box with the
golden-test row count; a phase is "done" only when its oracle + golden
(+ Manual anchor where applicable) + unit tests are green, pyright is
green, ruff is green, coverage ≥ 90 %; a phase cannot merge if it
imports from a later phase's module.
