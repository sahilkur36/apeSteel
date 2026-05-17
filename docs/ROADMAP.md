# apeSteel — roadmap

The port from the original Excel spreadsheet (`Vigas - Seccion I -
Diseno LTB.xlsx`) plus the `to_review/steelProperties/` Python prototype
is broken into **eight phases**. Each phase ends with a green golden-test
file pinning the spreadsheet's exact numerical output.

The phases are ordered so that each one can stand on its own: at the end
of phase N the library has a working public API for the topics ≤ N and
nothing else.

---

## Legend

- 🟦 `[scaffolding]` — pure plumbing, no engineering.
- 🟧 `[engine]` — AISC equation port; produces a `Report` dataclass.
- 🟩 `[facade]` — orchestration layer (`BeamCheck`).
- ⬛ `[catalog]` — section database integration.

---

## Phase 0 — Scaffolding 🟦

**Goal:** the repo can install, type-check, lint, and run an empty test
suite. No engineering yet.

Deliverables:

- `pyproject.toml` with deps (`numpy`, `pandas`, `pydantic>=2`,
  `rapidfuzz`, `baseUnits @ git+https://github.com/nmorabowen/baseUnits.git`),
  dev extras, ruff and pytest config sections.
- `pyrightconfig.json` (strict mode).
- `ruff.toml` (rules per `CODING_STYLE.md`).
- Empty `src/apeSteel/__init__.py` exposing `__version__ = "0.0.0"`.
- `apeSteel.core.units` — re-export of baseUnits + the BASE assertion.
- `apeSteel.core.materials.SteelMaterial` (frozen dataclass) +
  `A992`, `A572_Gr50`, `S355` instances.
- `apeSteel.core.result_types.AISCClauseReference` + `Report` base.
- `tests/test_smoke.py` — imports the package, asserts `u.BASE`, asserts
  `A992.yield_stress_Fy / u.MPa == 345.0`.
- CI: GitHub Actions workflow running `ruff`, `pyright`, `pytest`.

**Done when:** `pip install -e .[dev] && pyright && ruff check && pytest`
all pass on a fresh clone.

---

## Phase 1 — Section geometry & properties (user-defined) 🟧

**Goal:** reproduce cells `B39` – `B56` of the `Seccion Tipo I` sheet for
the spreadsheet's default `100×6 / 300×4` plate-built I.

Deliverables:

- `apeSteel.sections.properties.SectionProperties` (frozen dataclass).
- `apeSteel.sections.geometry.DoublySymmetricISection` with
  `.compute_section_properties()`.
- Closed-form formulas for `Ag, Ix, Iy, Sx, Sy, Zx, Zy, ry, rx, J, Cw,
  ho, rts`, with each one constant-named and AISC-cited (DG 9 for `J` /
  `Cw` of welded I).
- Unit tests in `tests/unit/test_doubly_symmetric_i_section.py`.
- Golden test `tests/golden/section_properties_doubly_symmetric_i.csv`
  with the spreadsheet's exact output for at least four (bf, tf, hw, tw)
  combinations.
- Cross-check: numerical integration via `scipy.integrate` over the plate
  cross-section, agreeing to `rel_tol = 1e-9`.

**Done when:** the golden CSV passes; the cross-check passes; pyright +
ruff are green.

**Cells reproduced:** `B39` – `B56`.

---

## Phase 2 — Classification 🟧

**Goal:** reproduce cells `B57` – `B68` of `Seccion Tipo I`.

Deliverables:

- `apeSteel.classification.flexural_compactness_B4.classify_flexural_compactness_B4`
  → `FlexuralCompactnessReport`.
- `apeSteel.classification.seismic_compactness_341_D1.classify_seismic_compactness_341_D1`
  → `SeismicCompactnessReport`.
- Unit + golden tests.

**Cells reproduced:** `B57` – `B68`, `B71`, `B85`.

---

## Phase 3 — Flexure §F2 (compact doubly-symmetric I, both flanges) 🟧

**Goal:** reproduce the LTB strength block `B69` – `B82` + `B83` – `B96`.

Deliverables:

- `apeSteel.flexure.lateral_torsional_buckling` with the three primitive
  functions (`Lp`, `Lr`, `Mcr`).
- `apeSteel.flexure.F2_compact_doubly_symmetric.compute_flexural_strength_F2_compact_doubly_symmetric`.
- `apeSteel.flexure.cb.compute_Cb_from_quarter_point_moments`
  (helper for Eq. F1-1).
- Reports include the regime label (`"yielding" | "inelastic_LTB" |
  "elastic_LTB"`).
- Golden CSV pins the spreadsheet's `Mn` for both top and bottom flanges
  across the three regimes.

**Cells reproduced:** `B69` – `B96` (both flanges).

---

## Phase 4 — Flexure §F3 (non-compact / slender flange) 🟧

**Goal:** reproduce `B97` – `B99`.

Deliverables:

- `apeSteel.flexure.F3_noncompact_flange.compute_flexural_strength_F3_noncompact_or_slender_flange`.
- Optional `kc` welded-flange path (off by default for v1 parity).

**Cells reproduced:** `B97` – `B99`.

---

## Phase 5 — Shear §G2 (unstiffened, then stiffened, then TFA) 🟧

**Goal:** reproduce `B100` – `B107` and the relevant Plate-Girders TFA
block.

Deliverables:

- `apeSteel.shear.G2_doubly_symmetric.compute_shear_strength_G2_doubly_symmetric`.
- TFA eligibility checker that raises with a descriptive error when one
  of the four conditions fails.

**Cells reproduced:** `B100` – `B107` of `Seccion Tipo I`; `B79` – `B82`
of `Plate Girders`.

---

## Phase 6 — Section catalog ⬛  ✅ DONE

**Goal:** port the `to_review` `AISCDatabase` and add the European IPE
table embedded in the spreadsheet at `R44:V88`.

Deliverables (all shipped):

- ✅ `apeSteel.sections.catalog.AISCv16Catalog` with RapidFuzz fallback
  and a typed `CatalogRowAISCv16` (pydantic v2). All 13 AISC v16
  section types (W, M, S, HP, C, MC, L, 2L, WT, MT, ST, HSS, PIPE) load
  through the same model.
- ✅ `apeSteel.sections.catalog.EuropeanIPECatalog` shipping an EN
  10365-verified subset (IPE 200, 300, 400, 500, 600). Eurocode-to-
  AISC axis renaming handled inside the adapter. Users extend by
  editing `data/european_IPE_subset.csv` or pointing the catalog at
  their own CSV.
- ✅ Both catalogs implement `get_section_properties` →
  `SectionProperties` and `get_doubly_symmetric_i_geometry` →
  plate-built `DoublySymmetricISection`.
- ✅ Catalog-derived golden test (`tests/golden/test_catalog_flexure_F2_golden.py`,
  pinning W24X94 + A992/S355 across the three LTB regimes).
- ✅ Plate-built vs catalog cross-check baked into unit tests
  (`TestGetDoublySymmetricIGeometry`, `TestPlateBuiltReconstruction`):
  rolled-vs-plate-built gap is < 2 % for W shapes, < 7 % for IPE
  (k-radii contribute proportionally more in IPE sections).
- ✅ Data ingestion: `tools/build_aisc_v16_csv.py` generates the
  shipped `data/AISC_v16_shapes.csv` from the legacy pickle in
  `to_review/`. CSV preserves AISC v16 SI Manual mixed-prefix units
  exactly (mm, kg/m, 10⁶ mm⁴, 10³ mm³, 10⁹ mm⁶) so a row can be
  diffed against a printed page; per-column scaling to
  `N-mm-tonne-s` base happens in `_unit_conversion.py` at load time.

Test impact: +86 tests (1085 → 1171 passing).

---

## Phase 7 — BeamCheck facade 🟩

**Goal:** the user-facing API.

Deliverables:

- `apeSteel.checks.doubly_symmetric_i_beam_check.DoublySymmetricIBeamCheck`
  bundling Phase 1 – 5 + Phase 6 catalog access.
- `BeamCheckReport` aggregating every sub-report and producing a
  human-readable `format()` matching the spreadsheet's "Resumen" block
  (cells `L1` – `L23`).
- End-to-end test reproducing the full default section and Fy in the
  spreadsheet (`100×6 / 300×4` at A992) and comparing `φMn`, `φVn`, and
  the deflection block.

---

## Phase 8 — Plate-girder §F5, serviceability, panel zone 🟧 🟧 🟧

**Goal:** complete the original spreadsheet coverage.

Deliverables (in order):

1. ✅ `apeSteel.flexure.F5_slender_web_plate_girder` (RPG, F5-1 to F5-8).
2. ✅ `apeSteel.serviceability.simple_beam_deflections` (Phase 8b).
   Four cases: simply-supported UDL, simply-supported PL at mid-span,
   simply-supported PL at arbitrary `a` (returns mid-span + max
   deflection + location of max), and cantilever UDL + tip load.
   Camber recommendation via `recommend_camber_from_dead_load_deflection`
   (0.8 × δ_dead, no rounding — caller picks shop-practice rounding).
   Composite API on `Element`: `element.serviceability_simply_supported_udl(...)`
   and three sibling methods. Golden test in
   `tests/golden/serviceability.csv` pins 11 representative cases.
3. ✅ `apeSteel.seismic.panel_zone_341.check_column_flange_tension_341`
   (Phase 8c). Port + fix of `to_review` `panelZone` class. Adds
   `PanelZoneColumnFlangeTensionReport` with Tu / Rn / phi*Rn / two
   tcf_min limits / DCR / acceptance flags; cites AISC 341-22 §E3.6e,
   AISC 358-22 §5.3.1, and AISC 360-22 §J10.1 Eq. J10-2. New top-level
   composite `BeamColumnConnection` aggregates (beam: Element,
   column: Element) and exposes
   `joint.check_panel_zone_column_flange_tension()`. Builder
   `element.connected_to(column_element)` chains both. Phase 1
   `SectionProperties` extended with `flange_width_bf` and
   `flange_thickness_tf` (defaults 0.0); the plate-built geometry,
   AISC v16 catalog, and European IPE catalog all populate them.
   Test impact: +33 tests (25 unit + 8 golden).

   **Phase 8c companions** (panel-zone shear + doubler-plate
   sizing + continuity-plate need-check):

   - ✅ `apeSteel.seismic.panel_zone_shear_J10_6.check_panel_zone_shear_341`
     - all four AISC 360 §J10.6 nominal-strength equations
     (J10-9 through J10-12), one-sided and two-sided beam
     attachments, column-axial reduction, panel-zone-deformation
     boost, doubler-plate contribution via
     `additional_doubler_plate_thickness_t_dp`.  Demand uses
     `Mpr = Cpr * Ry * Fy * Zx` with `Cpr = (Fy+Fu)/(2Fy) <= 1.2`
     (fallback 1.15 when `Fu` not on the material).
   - ✅ `apeSteel.seismic.doubler_plate_design.recommend_doubler_plate_thickness_341`
     - solves the shear and the local-buckling
     `(tw + tdp) >= (db + dc)/90` constraints simultaneously and
     rounds up to a shop-practical increment (default 2 mm).
   - ✅ `apeSteel.seismic.continuity_plate_design.check_continuity_plates_required_358`
     - AISC 358 §2.4.4 need-check + AISC 360 §J10.8 minimum
     `(t_cp, b_cp)` dimensions, 1-sided vs 2-sided aware.
   - All three exposed on `BeamColumnConnection`:
     `joint.check_panel_zone_shear(...)`,
     `joint.recommend_doubler_plate(...)`,
     `joint.check_continuity_plates(...)`.
   - Test impact: +49 tests (43 unit + 6 golden);
     project total 1243 -> 1292.
4. ✅ `BeamCheck` facade routes to F5 when geometry is a slender-web
   plate girder.

**Cells reproduced:** the full `Plate Girders` sheet (Phase 8); the
right-side serviceability block of `Seccion Tipo I` (Phase 8b); the
panel-zone block from the legacy `panelZone` class is the remaining
work (Phase 8c).

---

## Phase E — AISC 360-22 Chapter E (Compression) 🟧

**Goal:** a complete, section-family-by-section-family compression-strength
calculator anchored to an independent AISC 360-22 oracle and (for
edition-independent quantities) to the engineer's AISC 360-16 Excel workbook.
Mirrors the flexure-layer architecture: pure functions, frozen Reports, two
independent correctness anchors.

Design note: `docs/design_notes/08_compression_E.md`.

Sub-items:

- ✅ **E-0 — Scaffold.** `CompressionSectionProperties` input contract;
  `compression/` module stubs; standalone stdlib oracle
  (`tests/golden/_chapterE_aisc_oracle.py`). pyright/ruff clean.

- ✅ **E-1 — W-shape (doubly-symmetric I).** `flexural_buckling_E3.py`,
  `torsional_flexural_E4.py` (torsional path, Eq. E4-2),
  `slender_elements_E7.py` (effective-width §E7.2, Eq. E7-2),
  `compression_strength.py` W-shape orchestrator.
  Test impact: +13 tests (10 oracle bit-exact + 3 Excel anchor; Fe / Fe,torsion
  / Pn non-slender all edition-independent; §E7 divergence from 360-16 is
  bounded, documented, expected).
  Project total: **1398 tests passing**; pyright strict clean; ruff clean.

- ✅ **E-2 — Tee and channel.** `TeeSection` / `ChannelSection`
  plate-built geometries (properties transcribed verbatim from the
  validated workbook); §E4 singly-symmetric flexural–torsional path
  (Eq. E4-3 / E4-7, axis-of-symmetry selection: tee→Fey, channel→Fex).
  Test impact: +12 tests (10 oracle bit-exact incl. FT-governing across
  4 grades + 2 Excel geometry anchors: Ag/Ix/Iy/rx/ry/J/Cw/xo·yo/H all
  bit-match the workbook). Project total: **1410 tests passing**;
  pyright strict clean; ruff clean.

- ✅ **E-3 — Rectangular and round HSS.** `RectangularHSS` / `RoundHSS`
  geometries; facade + oracle skip §E4 for closed HSS (§E3-only).
  §E7.2 rect-HSS-wall effective width (Table E7.1 HSS-wall c1/c2);
  §E7.2(c) round-HSS reduced area (Eq. E7-6/E7-7, retained from
  360-16). +10 tests: 8 oracle bit-exact (incl. slender HSS); 2 Excel
  anchors bit-match the workbook's **full governing φPn** (non-slender
  ⇒ 360-16 == 360-22 — the strongest external anchor).

- ✅ **E-4 — Single and double angle.** `SingleAngleSection` (equal-leg,
  principal-axis Mohr rotation) with §E5 modified `Lc/r`
  (Eq. E5-1…E5-4) and §E3+§E4; `DoubleAngleSection` (back-to-back) with
  §E6 modified slenderness (Eq. E6-1/E6-2) wired through the facade.
  +21 tests: 11 oracle bit-exact (E5 cases a/b, E6 snug/welded across
  grades); 2 Excel geometry anchors (the Excel caught & fixed a
  back-to-back built-up-Iy convention error). Project total: **1433
  tests passing**; pyright strict 0 errors; ruff/format clean.

- ✅ **E-5 — Element integration + φPn-vs-length curve.**
  `compression/capacity_curve.py` (`compute_phi_Pn_vs_length` →
  `CapacityCurvePoint` tuple, the workbook's Data-Table column as a
  pure function); `Element.compression_strength(Kx,Lx,Ky,Ly,Kz,Lz)` and
  `Element.phi_Pn_vs_length(...)` for doubly-symmetric I (SS-I guarded
  with `NotImplementedError`, as F2/F3/F5); top-level `apeSteel`
  re-exports. Tee/channel/HSS/angle compression use the dedicated
  geometries with `apeSteel.compression.compute_compression_strength`.
  +4 tests (Element≡free-function, curve monotone & point-consistent,
  SS-I guard, non-positive-length guard).

**Done when:** all five sub-items green; oracle + Excel-anchor suites pass;
pyright + ruff clean; coverage ≥ 90 %.  **DONE** — 1437 tests passing;
pyright strict 0 errors; ruff + ruff-format clean; coverage 95 %.

---

## Phase H — AISC 360-22 Chapter H (Combined forces + torsion) 🟧

**Goal:** the **full** Chapter H — §H1.1, §H1.2, §H1.3, §H2, and
§H3.1/3.2/3.3 — anchored to an independent AISC 360-22 oracle and (for
edition-independent quantities) to the engineer's Chapter-H Excel
workbook. Chapter H is a *consumer* layer: §H1/§H2 compose the existing
Chapter-E `φ·Pn` and Chapter-F `φ·Mn` (no changes to those layers);
the only nominal strength that originates here is the §H3.1 HSS
torsional `Tn`. Second-order `Mr` is caller-supplied (DAM) — no
Appendix-8 B1/B2. §H1.2 consumes a thin `apeSteel.tension` slice
(D2-1 gross-section yielding only; D2-2 rupture out of scope).

Design note: `docs/design_notes/09_combined_H.md`.

Sub-items:

- ✅ **H-0 — Scaffold + oracle.** `combined/` + `tension/` module stubs
  (every calculator raises `NotImplementedError` pointing at the design
  note); standalone stdlib oracle
  (`tests/golden/_chapterH_aisc_oracle.py`) re-deriving §H1.1/1.2/1.3,
  §H2, §H3.1/3.2/3.3; design note 09; this ROADMAP section.
  pyright strict / ruff / ruff-format clean; suite green.

- ⏳ **H-1 — §H1.1.** Eq. H1-1a/H1-1b calculator + `CombinedH1Report`;
  oracle bit-exact across both regimes + biaxial; reviewer hand calc.

- ⏳ **H-2 — §H1.2.** `tension/yielding_D2.py` (Eq. D2-1, `φt=0.90`) +
  flexure+tension interaction (`Pc=φt·Pn`) + `Cb` amplifier
  `√(1+α·Pr/Pey)` with `Mn≤Mp` cap.

- ⏳ **H-3 — §H1.3.** In-plane Eq. H1-1 + out-of-plane Eq. H1-2
  (`Cb·Mcx` capped at `φb·Mp`) + applicability guards (DS / rolled /
  compact / single-axis / `KLz≤KLy`).

- ⏳ **H-4 — §H2.** Eq. H2-1 signed elastic-stress interaction.

- ⏳ **H-5 — §H3.** Round/rect HSS `Tn=Fcr·C` (Eq. H3-1..H3-5,
  `φT=0.90`); Eq. H3-6 HSS combined (with `Tr≤0.2·Tc` neglect path);
  §H3.3 limiting `Fn` (Eq. H3-7/8/9; DG 9 warping out of scope).

- ⏳ **H-6 — Excel anchor.** Faithful workbook dump to
  `tests/golden/data/`; edition-independent quantities bit-matched at
  workbook precision; any slender-`Pc`/`Mc` 360-22-vs-360-16 divergence
  documented and bounded.

- ⏳ **H-7 — Element/facade integration.** `Element.combined_strength_*`
  consuming Chapter-E φPn + Chapter-F φMn; `apeSteel` re-exports;
  ROADMAP tick; design note status → done.

**Done when:** all sub-items green; oracle + Excel-anchor suites pass;
pyright + ruff clean; coverage ≥ 90 %.

---

## After v1 — explicit non-goals (for later phases)

- AISC §E (compression) — **done (Phase E above)**.
- AISC §H (combined loading) — **underway (Phase H above)**.
- AISC §D (tension) — full chapter (D2-2 net-section rupture, §J4 block
  shear) for braces / hangers; Phase H ships only the thin D2-1 slice
  that §H1.2 consumes.
- AISC §I (composite construction).
- AISC §J / §K (connections — bolts, welds, plate-element checks).
- AISC 358 prequalified moment connections (RBS, BFP, BUEEP, …).
- AISC 341 system-level checks (SMF/IMF/OMF criteria,
  capacity-design Vu, doubler/continuity plates).
- AISC Design Guide 11 floor vibrations.

Each of these will get its own design note and roadmap update when we
start it.

---

## Bookkeeping rules

- Every PR that closes a phase line item updates this file (ticks the
  box, attaches the golden-test row count).
- A phase is "done" only when its golden tests + unit tests are green,
  pyright is green, ruff is green, and coverage on the touched code is
  ≥ 90 %.
- A phase **cannot be merged** if it imports from a module belonging to
  a later phase (the layer-dependency rule from `ARCHITECTURE.md` §1).
