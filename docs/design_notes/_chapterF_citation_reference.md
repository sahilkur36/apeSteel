# Chapter F citation reference — the source-of-truth

> **Status:** F-0 deliverable. This file is the *only* place apeSteel's
> Chapter-F code and oracle take their AISC equation numbers, Table
> B4.1b cases, λ_p / λ_r forms, and Manual v15.1 worked-example IDs.
> Design note `10_flexure_full_F.md` §9 governs provenance.
>
> **Provenance rule (enforced here):**
> 1. Equation FORMS / NUMBERS and `16.1-NN` page labels that appear
>    *verbatim* in `_aisc_src_extract/spec_chapterF.txt` are
>    authoritative — quoted with their printed page.
> 2. Table B4.1b CASE NUMBERS and any page label NOT present in the
>    extracted spec text are written `Case ?` / `page=None` and listed
>    in [`## ENGINEER-CONFIRM`](#engineer-confirm). They are **never
>    invented**. The independent oracle re-derives every λ limit
>    numerically, so correctness does not depend on the case label.
> 3. λ_p / λ_r coefficients come from the curated
>    `_aisc_src_extract/skill_reference_chapterF.md` (the
>    `aisc-steel-design` skill's curated reference — a standard
>    reference, not model memory) cross-checked against the spec body
>    text where the spec prints them.

---

## Part 1 — §F1–§F13 equation map (verbatim from `spec_chapterF.txt`)

Every row below was located in the staged spec extract. The "Spec page"
column is the *printed* `16.1-NN` label shown on that PDF page in the
extract; it is authoritative. Section sub-numbers (e.g. `F2.2`) follow
the spec's own clause numbering.

### §F1 — General provisions

| Item | Section | Eq. | Spec page | Notes |
|---|---|---|---|---|
| Cb modification factor | F1 | F1-1 | None† | Not in `spec_chapterF.txt` (extract starts at 16.1-53 = F2). In-repo `flexure/_common.py` cites §F1 p.16.1-47. See ENGINEER-CONFIRM. |

† `spec_chapterF.txt` begins at printed 16.1-53 (PDF p.121). §F1 and the
F1-1 page label are outside the extract; the existing shipped citation
(`flexure/_common.py`: `AISCClauseReference("AISC 360-22","F1",None,"16.1-47")`)
is retained and flagged, not overwritten.

### §F2 — Doubly-symmetric compact I & channels, major axis

| Item | Section | Eq. | Spec page |
|---|---|---|---|
| Yielding `Mn = Mp = Fy·Zx` | F2.1 | F2-1 | 16.1-53 |
| Inelastic LTB `Mn = Cb[Mp−(Mp−0.7FySx)(Lb−Lp)/(Lr−Lp)] ≤ Mp` | F2.2 | F2-2 | 16.1-53 |
| Elastic LTB `Mn = Fcr·Sx ≤ Mp` | F2.2 | F2-3 | 16.1-53 |
| `Fcr` (Cb·π²E/(Lb/rts)²·√(1+0.078·(Jc/(Sx·ho))·(Lb/rts)²)) | F2.2 | F2-4 | 16.1-53 |
| `Lp = 1.76·ry·√(E/Fy)` | F2.2 | F2-5 | 16.1-54 |
| `Lr` (Eq. F2-6 closed form) | F2.2 | F2-6 | 16.1-54 |
| `rts² = √(Iy·Cw)/Sx` | F2.2 | F2-7 | 16.1-54 |
| `c = 1` (doubly-symmetric I) | F2.2 | F2-8a | 16.1-54 |
| `c = (ho/2)·√(Iy/Cw)` (channels) | F2.2 | F2-8b | 16.1-54 |

### §F3 — DS I, compact web, NC/slender flange, major axis

| Item | Section | Eq. | Spec page |
|---|---|---|---|
| LTB → use §F2.2 | F3.1 | (refers F2-2..F2-6) | 16.1-55 |
| NC-flange FLB `Mn = Mp−(Mp−0.7FySx)(λ−λpf)/(λrf−λpf)` | F3.2 | F3-1 | 16.1-55 |
| Slender-flange FLB `Mn = 0.9·E·kc·Sx/λ²` | F3.2 | F3-2 | 16.1-55 |
| `kc = 4/√(h/tw)`, 0.35 ≤ kc ≤ 0.76 | F3.2 | (defn under F3-2) | 16.1-55 |

### §F4 — Other I (DS NC-web, SS I), major axis

| Item | Section | Eq. | Spec page |
|---|---|---|---|
| CF yielding `Mn = Rpc·Myc` | F4.1 | F4-1 | 16.1-56 |
| Inelastic LTB | F4.2 | F4-2 | 16.1-56 |
| Elastic LTB `Mn = Fcr·Sxc ≤ Rpc·Myc` | F4.2 | F4-3 | 16.1-56 |
| `Myc = Fy·Sxc` | F4.2 | F4-4 | 16.1-56 |
| `Fcr` (F4-5; J=0 when Iyc/Iy ≤ 0.23) | F4.2 | F4-5 | 16.1-57 |
| `FL = 0.7Fy` (Sxt/Sxc ≥ 0.7) | F4.2 | F4-6a | 16.1-57 |
| `FL = Fy·Sxt/Sxc ≥ 0.5Fy` (Sxt/Sxc < 0.7) | F4.2 | F4-6b | 16.1-57 |
| `Lp = 1.1·rt·√(E/Fy)` | F4.2 | F4-7 | 16.1-57 |
| `Lr` (Eq. F4-8 closed form) | F4.2 | F4-8 | 16.1-57 |
| `Rpc = Mp/Myc` (Iyc/Iy>0.23, hc/tw ≤ λpw) | F4.2 | F4-9a | 16.1-57 |
| `Rpc` interpolated (hc/tw > λpw) | F4.2 | F4-9b | 16.1-58 |
| `Rpc = 1.0` (Iyc/Iy ≤ 0.23) | F4.2 | F4-10 | 16.1-58 |
| `rt = bfc/√(12(1+aw/6))` | F4.2 | F4-11 | 16.1-58 |
| `aw = hc·tw/(bfc·tfc)` | F4.2 | F4-12 | 16.1-58 |
| NC-flange FLB | F4.3 | F4-13 | 16.1-59 |
| Slender-flange FLB `Mn = 0.9·E·kc·Sxc/λ²` | F4.3 | F4-14 | 16.1-59 |
| TF yielding `Mn = Rpt·Myt` (Sxt < Sxc) | F4.4 | F4-15 | 16.1-59 |
| `Rpt = Mp/Myt` (Iyc/Iy>0.23, hc/tw ≤ λpw) | F4.4 | F4-16a | 16.1-59 |
| `Rpt` interpolated (hc/tw > λpw) | F4.4 | F4-16b | 16.1-59 |
| `Rpt = 1.0` (Iyc/Iy ≤ 0.23) | F4.4 | F4-17 | 16.1-60 |

### §F5 — DS & SS I, slender web, major axis

| Item | Section | Eq. | Spec page |
|---|---|---|---|
| CF yielding `Mp = Rpg·Fy·Sxc` | F5.1 | F5-1 | 16.1-60 |
| LTB `Mn = Rpg·Fcr·Sxc` | F5.2 | F5-2 | 16.1-60 |
| `Fcr` inelastic (Lp<Lb≤Lr) | F5.2 | F5-3 | 16.1-60 |
| `Fcr` elastic (Lb>Lr) | F5.2 | F5-4 | 16.1-60 |
| `Lr = π·rt·√(E/(0.7Fy))` (Lp per F4-7) | F5.2 | F5-5 | 16.1-60 |
| `Rpg = 1 − aw/(1200+300aw)·(hc/tw − 5.7√(E/Fy)) ≤ 1` | F5.2 | F5-6 | 16.1-61 |
| CFLB `Mn = Rpg·Fcr·Sxc` | F5.3 | F5-7 | 16.1-61 |
| `Fcr` NC flange | F5.3 | F5-8 | 16.1-61 |
| `Fcr` slender flange `0.9·E·kc/(bfc/tfc)²` | F5.3 | F5-9 | 16.1-61 |
| TF yielding `Mn = Fy·Sxt` (Sxt < Sxc) | F5.4 | F5-10 | 16.1-61 |

### §F6 — I-shapes & channels, minor axis

| Item | Section | Eq. | Spec page |
|---|---|---|---|
| Yielding `Mn = Mp = Fy·Zy ≤ 1.6·Fy·Sy` | F6.1 | F6-1 | 16.1-62 |
| NC-flange FLB `Mn = Mp−(Mp−0.70FySy)(λ−λpf)/(λrf−λpf)` | F6.2 | F6-2 | 16.1-62 |
| Slender-flange FLB `Mn = Fcr·Sy` | F6.2 | F6-3 | 16.1-62 |
| `Fcr = 0.70·E/(b/tf)²` | F6.2 | F6-4 | 16.1-62 |

Spec note: `b` = bf/2 for I-shape flanges, full flange width for channels.

### §F7 — Square / rectangular HSS & box, either axis

| Item | Section | Eq. | Spec page |
|---|---|---|---|
| Yielding `Mn = Mp = Fy·Z` | F7.1 | F7-1 | 16.1-63 |
| NC-flange FLB `Mn = Mp−(Mp−FyS)·(…) ≤ Mp` | F7.2 | F7-2 | 16.1-63 |
| Slender-flange FLB `Mn = Fy·Se` | F7.2 | F7-3 | 16.1-63 |
| `be` (HSS) | F7.2 | F7-4 | 16.1-63 |
| `be` (box) | F7.2 | F7-5 | 16.1-63 |
| NC-web WLB `Mn = Mp−(Mp−FyS)·(…) ≤ Mp` | F7.3 | F7-6 | 16.1-63 |
| Slender-web `Mn = Rpg·Fy·S` (Rpg per F5-6, aw=2·h·tw/(b·tf)) | F7.3 | F7-7 | 16.1-64 |
| Inelastic LTB (rect HSS major axis) | F7.4 | F7-10 | 16.1-64 |
| Elastic LTB `Mn = 2E·Cb·√(J·Ag)/(Lb/?) ≤ Mp` | F7.4 | F7-11 | 16.1-64 |
| `Lp = 0.13·E·ry·√(J·Ag)/Mp` | F7.4 | F7-12 | 16.1-64 |
| `Lr = 2·E·ry·√(J·Ag)/(0.7·Fy·Sx)` | F7.4 | F7-13 | 16.1-64 |

**Spec-extract gaps in §F7:** equations **F7-8 and F7-9** are referenced
by the limit-state list but their bodies are not present in the
`spec_chapterF.txt` extract (the WLB slender-web branch jumps F7-7 →
F7-10 in the extracted text). The §F7 phase (F-3) must re-pull F7-8/F7-9
from the source PDF. The exact `(…)` interpolation coefficients in
F7-2 / F7-6 are likewise not legible in the extract (the equation images
did not text-extract cleanly — only the surrounding prose did); the
curated reference gives the conventional `3.57√(Fy/E)−4.0` form for
F7-2 but this is **not** confirmed from the spec body and is flagged.

### §F8 — Round HSS / Pipe

| Item | Section | Eq. | Spec page |
|---|---|---|---|
| Applicability `D/t < 0.45·E/Fy` | F8 | (intro) | 16.1-65 |
| Yielding `Mn = Mp = Fy·Z` | F8.1 | F8-1 | 16.1-65 |
| NC `Mn = (0.021·E/(D/t) + Fy)·S` | F8.2 | F8-2 | 16.1-65 |
| Slender `Mn = Fcr·S` | F8.2 | F8-3 | 16.1-65 |
| `Fcr = 0.33·E/(D/t)` | F8.2 | F8-4 | 16.1-65 |

### §F9 — Tees & double angles in the plane of symmetry

| Item | Section | Eq. | Spec page |
|---|---|---|---|
| Yielding `Mn = Mp` | F9.1 | F9-1 | 16.1-65 |
| Stem/web-leg in tension `Mp = Fy·Zx ≤ 1.6·My` | F9.1 | F9-2 | 16.1-66 |
| `My = Fy·Sx` | F9.1 | F9-3 | 16.1-66 |
| Tee stem in compression `Mp = My` | F9.1 | F9-4 | 16.1-66 |
| 2L web legs in compression `Mp = 1.5·My` | F9.1 | F9-5 | 16.1-66 |
| LTB inelastic (tension stem) | F9.2 | F9-6 | 16.1-66 |
| LTB elastic `Mn = Mcr` | F9.2 | F9-7 | 16.1-66 |
| `Lp = 1.76·ry·√(E/Fy)` | F9.2 | F9-8 | 16.1-66 |
| `Lr` (Eq. F9-9) | F9.2 | F9-9 | 16.1-66 |
| `Mcr = (1.95E/Lb)·√(Iy·J)·(B+√(1+B²))` | F9.2 | F9-10 | 16.1-66 |
| `B = 2.3·(d/Lb)·√(Iy/J)` (tension) | F9.2 | F9-11 | 16.1-66 |
| `B = −2.3·(d/Lb)·√(Iy/J)` (compression) | F9.2 | F9-12 | 16.1-66 |
| Tee-stem-in-compression cap `Mn = Mcr ≤ My` | F9.2 | F9-13 | 16.1-67 |
| Tee NC-flange FLB `Mn = [Mp−(Mp−0.7FySxc)(…)] ≤ 1.6·… ` | F9.3 | F9-14 | 16.1-67 |
| Tee slender-flange FLB `Mn = 0.7·E·Sxc/(bf/2tf)²` | F9.3 | F9-15 | 16.1-67 |
| Tee-stem LB `Mn = Fcr·Sx` | F9.4 | F9-16 | 16.1-67 |
| `Fcr = Fy` (d/tw ≤ 0.84√(E/Fy)) | F9.4 | F9-17 | 16.1-68 |
| `Fcr = (1.43−0.515·(d/tw)·√(Fy/E))·Fy` | F9.4 | F9-18 | 16.1-68 |
| `Fcr = 1.52·E/(d/tw)²` (d/tw > 1.52√(E/Fy)) | F9.4 | F9-19 | 16.1-68 |

### §F10 — Single angles

| Item | Section | Eq. | Spec page |
|---|---|---|---|
| Yielding `Mn = 1.5·My` | F10.1 | F10-1 | None* |
| LTB NC `Mn = (1.92−1.17√(My/Mcr))·My ≤ 1.5My` | F10.2 | F10-2 | None* |
| LTB slender `Mn = (0.92−0.17·Me/My)·Me` | F10.2 | F10-3 | None* |
| `Me` (equal-leg, geometric axis) | F10.2 | F10-4 | None* |
| `Mcr` max compression at heel | F10.2 | F10-5a | None* |
| `Mcr` max tension at toe | F10.2 | F10-5b | 16.1-70 |
| Leg LB NC `Mn = Fy·Sc·(2.43−1.72·(b/t)·√(Fy/E))` | F10.3 | F10-6 | 16.1-70 |
| Leg LB slender `Mn = Fcr·Sc` | F10.3 | F10-7 | 16.1-70 |
| `Fcr = 0.71·E/(b/t)²` | F10.3 | F10-8 | 16.1-70 |

\* §F10 spans printed 16.1-68 … 16.1-71, but **PDF page 16.1-69 is
absent from the `spec_chapterF.txt` extract** (the extract jumps from
16.1-68 to 16.1-70). Equations **F10-1, F10-2, F10-3, F10-4, F10-5a**
and their exact page labels are therefore **not verifiable from the
extract**. The forms above come from the curated reference; the §F10
phase (F-6) must re-pull printed 16.1-69 from the source PDF. Flagged in
ENGINEER-CONFIRM. (`F10-9` in the curated map is the §F10.3 `Sc`
definition prose, not a numbered equation in the extract — treat the
leg-LB equation count as F10-6/7/8 per the extracted 16.1-70 text.)

### §F11 — Rectangular bars & rounds

| Item | Section | Eq. | Spec page |
|---|---|---|---|
| Rect-bar yielding `Mn = Mp = Fy·Z ≤ 1.5·Fy·Sx` | F11.1 | F11-1 | 16.1-71 |
| Round yielding `Mn = Mp = Fy·Z ≤ 1.6·Fy·Sx` | F11.1 | F11-2 | 16.1-71 |
| Rect-bar LTB inelastic | F11.2 | F11-3 | 16.1-71 |
| Rect-bar LTB elastic `Mn = Fcr·Sx ≤ Mp` | F11.2 | F11-4 | 16.1-71 |
| `Fcr = 1.9·E·Cb/(Lb·d/t²)` | F11.2 | F11-5 | 16.1-71 |

### §F12 — Unsymmetrical shapes

| Item | Section | Eq. | Spec page |
|---|---|---|---|
| `Mn = Fn·Smin` | F12 | F12-1 | 16.1-71 |
| Yielding `Fn = Fy` | F12.1 | F12-2 | 16.1-72 |
| LTB `Fn = Fcr ≤ Fy` | F12.2 | F12-3 | 16.1-72 |
| Local buckling `Fn = Fcr ≤ Fy` | F12.3 | F12-4 | 16.1-72 |

### §F13 — Proportions of beams and girders

| Item | Section | Eq. | Spec page |
|---|---|---|---|
| Tension-flange-hole rupture `Mn = (Fu·Afn/Afg)·Sx` | F13.1 | F13-1 | 16.1-72 |
| SS I proportioning `0.1 ≤ Iyc/Iy ≤ 0.9` | F13.2 | F13-2 | 16.1-73 |
| Slender-web `(h/tw)max = 12.0·√(E/Fy)` (a/h ≤ 1.5) | F13.2 | F13-3 | 16.1-73 |
| Slender-web `(h/tw)max = 0.40·E/Fy` (a/h > 1.5) | F13.2 | F13-4 | 16.1-73 |
| Cover-plate `a' = w` | F13.3 | F13-5 | 16.1-73 |
| Cover-plate `a' = 1.5w` | F13.3 | F13-6 | 16.1-74 |
| Cover-plate `a' = 2w` | F13.3 | F13-7 | 16.1-74 |
| Unstiffened-girder limit `h/tw ≤ 260`; `aw ≤ 10` | F13.2 | (prose) | 16.1-73 |
| `Yt = 1.0` (Fy/Fu ≤ 0.8) else `1.1` | F13.1 | (defn) | 16.1-73 |

---

## Part 2 — Table B4.1b flexure λ_p / λ_r (curated forms + case provenance)

λ forms are from `skill_reference_chapterF.md` (curated standard
reference) and, where the spec body prints them, cross-checked against
`spec_chapterF.txt`. **`spec_B4_1b.txt` does NOT contain the Table B4.1b
case rows** — the table is image-rendered in the spec PDF and did not
text-extract (only printed 16.1-19 prose extracted). Therefore *every*
B4.1b case number below is provenance-classified:

- **CONFIRMED** — the case number appears in an authoritative extracted
  source (existing shipped in-repo citation, or the Manual v15.1
  worked-example text in `manual_v1_chapterF_index.txt`).
- **UNVERIFIED** — case number not in any extract; written `Case ?`,
  listed in ENGINEER-CONFIRM. The λ form is still given (oracle re-derives
  it numerically).

| Element (role) | λ | λ_p (compact) | λ_r (noncompact) | B4.1b case | Provenance |
|---|---|---|---|---|---|
| I/channel flange, rolled, flexure | bf/2tf | 0.38·√(E/Fy) | 1.0·√(E/Fy) | Case 10 | CONFIRMED — shipped `flexural_compactness_B4_1b.py` ("B4.1b Case 10"), Manual F.3A text |
| I/channel flange, welded, flexure | bf/2tf | 0.38·√(E/Fy) | 0.95·√(kc·E/FL), FL=0.7Fy (DS) | Case 11 | CONFIRMED — shipped code ("B4.1b Case 11") |
| I/channel web, DS, flexure | h/tw | 3.76·√(E/Fy) | 5.70·√(E/Fy) | Case 15 | CONFIRMED — shipped code ("B4.1b Case 15") |
| I web, SS, flexure | hc/tw | (hc/hp)·√(E/Fy)/(0.54·Mp/My−0.09)² ≤ λ_r | 5.70·√(E/Fy) | Case 16 | CONFIRMED — shipped `compute_singly_symmetric_web_lambda_pw_case16` docstring ("Case 16") |
| Rect-HSS flange, flexure | b/t (flat) | 1.12·√(E/Fy) | 1.40·√(E/Fy) | **Case ?** (~17) | UNVERIFIED — not in extract |
| Rect-HSS web, flexure | h/t (flat) | 2.42·√(E/Fy) | 5.70·√(E/Fy) | **Case ?** (~19) | UNVERIFIED — not in extract |
| Round HSS, flexure | D/t | 0.07·E/Fy | 0.31·E/Fy | Case 20 | CONFIRMED — Manual v15.1 Ex. F.9B text: "AISC Specification Table B4.1b Case 20" (`manual_v1_chapterF_index.txt` PDF p.190) |
| Tee stem, flexure | d/tw | (defined in §F9.4, not B4.1b) | (defined in §F9.4) | **Case ?** (~14) | UNVERIFIED — §F9.4 supplies Fcr breakpoints (Eq. F9-17/18/19) directly |
| Single/double-angle leg, flexure | b/t | (defined in §F10.3, not B4.1b) | (defined in §F10.3) | **Case ?** (~12) | UNVERIFIED — §F10.3 supplies the b/t breakpoints directly |
| Rectangular / round bar | n/a | n/a (compact by inspection) | n/a | — | §F11 has no local-buckling limit state for bars |

Auxiliary, confirmed from `spec_chapterF.txt`:
- `kc = 4/√(h/tw)`, bounded `0.35 ≤ kc ≤ 0.76` — printed under F3-2
  (16.1-55), F4-14 (16.1-59), F5-9 (16.1-61).
- DS-I major-axis `FL = 0.7·Fy` — Eq. F4-6a (16.1-57).

**§F9.4 tee-stem `Fcr` breakpoints (from `spec_chapterF.txt`, 16.1-67/68
— authoritative, used in lieu of a B4.1b stem row):**
- `d/tw ≤ 0.84·√(E/Fy)` → `Fcr = Fy` (Eq. F9-17)
- `0.84·√(E/Fy) < d/tw ≤ 1.52·√(E/Fy)` → `Fcr = (1.43−0.515·(d/tw)·√(Fy/E))·Fy` (Eq. F9-18)
- `d/tw > 1.52·√(E/Fy)` → `Fcr = 1.52·E/(d/tw)²` (Eq. F9-19)

**§F10.3 angle-leg breakpoints (curated; spec page 16.1-70 confirms the
slender/NC equation bodies F10-6/7/8 but the printed compact/NC b/t
limits 0.54√(E/Fy) / 0.91√(E/Fy) are on the absent 16.1-69 — flagged):**
- compact `b/t ≤ 0.54·√(E/Fy)` *(UNVERIFIED — page 16.1-69 absent)*
- noncompact `0.54·√(E/Fy) < b/t ≤ 0.91·√(E/Fy)` *(UNVERIFIED)*
- slender `b/t > 0.91·√(E/Fy)` → `Fcr = 0.71·E/(b/t)²` (Eq. F10-8, 16.1-70 — CONFIRMED)

---

## Part 3 — AISC Manual v15.1 Vol.1 Chapter-F worked-example index

From `_aisc_src_extract/manual_v1_chapterF_index.txt` (the §6 external
anchor for F-2…F-7). "Manual page" is the `F-NN` label printed in the
companion; "PDF page" is the page in `v15.1_vol-1_design-examples.pdf`.
**Edition note:** the Manual companion is 360-16-based; per design note
10 §1 the F2–F12 equations are materially unchanged 360-16 → 360-22, so
each anchor is taken on edition-independent quantities only.

| Example | Shape / topic | §F | Manual pg | PDF pg |
|---|---|---|---|---|
| F.1-1A/1B | W-shape major-axis, continuously braced | F2 | F-6 / F-8 | 153 / 155 |
| F.1-2A/2B | W-shape major-axis, braced at third points | F2 | F-9 / F-10 | 156 / 157 |
| F.1-3A/3B | W-shape major-axis, braced at midspan (elastic LTB) | F2 | F-12 / F-14 | 159 / 161 |
| F.2-1A/1B | Compact channel, continuously braced (C15×33.9, A36) | F2 | F-16 / F-18 | 163 / 165 |
| F.2-2A/2B | Compact channel, ends + fifth points | F2 | F-19 / F-20 | 166 / 167 |
| F.3A/3B | W-shape NC flanges, major axis (A992) | F3 | F-22 / F-24 | 169 / 171 |
| F.4 | W-shape selection by Ix, major axis | F2/F3 | F-26 | 173 |
| F.5 | I-shape **minor-axis** bending | F6 | F-28 | 175 |
| F.6 | **Square HSS**, compact flanges | F7 | F-30 | 177 |
| F.7A/7B | **Rectangular HSS**, NC flanges (A500 Gr.C) | F7 | F-32 / F-34 | 179 / 181 |
| F.8A/8B | **Square HSS**, slender flanges (A500 Gr.C) | F7 | F-37 / F-39 | 184 / 186 |
| F.9A/9B | **Pipe** (round HSS) flexural member | F8 | F-42 / F-43 | 189 / 190 |
| F.10 | **WT-shape** flexural member (stem in compression) | F9 | F-45 | 192 |
| F.11A | **Single angle**, bracing at ends only | F10 | F-48 | 195 |
| F.11B | **Single angle**, ends + midspan | F10 | F-52 | 199 |
| F.11C | **Single angle**, vertical + horizontal loading | F10/H2 | F-55 | 202 |
| F.12 | **Rectangular bar**, major axis | F11 | F-62 | 209 |
| F.13 | **Round bar** in bending | F11 | F-65 | 212 |
| F.14 | **Point-symmetrical Z-shape**, major axis (A36) | F12 | F-67 | 214 |
| F.15 | **Plate girder** (built-up, slender web) | F5 | F-73 | 220 |

Per-phase anchor selection (design note 10 §6, tier 2):
- F-2 §F8 → Ex. F.9A/F.9B (Pipe).
- F-3 §F7 → Ex. F.6 (square HSS compact), F.7A/B (rect HSS NC), F.8A/B (square HSS slender).
- F-4 §F6 → Ex. F.5 (W minor axis).
- F-5 §F9 → Ex. F.10 (WT). (2L example not in Vol.1 index — reviewer hand-calc fallback per §6.)
- F-6 §F10 → Ex. F.11A/B/C (single angle).
- F-7 §F11/§F12 → Ex. F.12 (rect bar), F.13 (round bar), F.14 (Z-shape §F12).
- F-1 §F2/§F3 regression cross-check → Ex. F.1-x (W), F.2-x (channel), F.3x (NC flange), F.15 (plate girder §F5).

---

## ENGINEER-CONFIRM

The following could **not** be verified from the staged extracts and are
written `Case ?` / `page=None` in code & oracle until the engineer
confirms them against the source PDFs at the F-0 review gate. None is
invented; the independent oracle re-derives every λ limit numerically so
correctness does not depend on these labels.

| # | Item | What is unconfirmed | Where it bites | Curated value (NOT authoritative) |
|---|---|---|---|---|
| EC-1 | B4.1b **rect-HSS flange** flexure case number | `spec_B4_1b.txt` has no B4.1b case table (image-rendered). | F-3 §F7 classifier `aisc_b4_1b_case` label | likely "Case 17"; λ_p=1.12√(E/Fy), λ_r=1.40√(E/Fy) |
| EC-2 | B4.1b **rect-HSS web** flexure case number | same | F-3 §F7 classifier label | likely "Case 19"; λ_p=2.42√(E/Fy), λ_r=5.70√(E/Fy) |
| EC-3 | B4.1b **round-HSS** flexure case number | Manual Ex. F.9B says "Case 20" — **CONFIRMED as Case 20**; the **`16.1-NN` page label** for that B4.1b row is still unconfirmed (B4.1b table not in extract). | F-2 §F8 classifier label / page | Case 20 (confirmed); page=None |
| EC-4 | B4.1b **single/double-angle leg** flexure case number | not in extract; §F10.3 gives b/t breakpoints directly | F-6 §F10 / F-5 2L classifier label | likely "Case 12"; compact 0.54√(E/Fy), NC 0.91√(E/Fy) |
| EC-5 | B4.1b **tee-stem** flexure case number | not in extract; §F9.4 gives Fcr breakpoints directly | F-5 §F9 classifier label | likely "Case 14" |
| EC-6 | §F7 equations **F7-8, F7-9** | bodies absent from `spec_chapterF.txt` (extract jumps F7-7 → F7-10) | F-3 §F7 WLB slender/NC branch | curated: F7-8/9 are the slender-web LTB-region forms — re-pull PDF |
| EC-7 | §F7 F7-2 / F7-6 interpolation coefficients | equation images did not text-extract; only prose did | F-3 §F7 FLB/WLB NC interpolation | curated `Mn=Mp−(Mp−FyS)(3.57(b/t)√(Fy/E)−4.0)≤Mp` — re-pull PDF |
| EC-8 | §F7 elastic-LTB F7-11 denominator | extract shows `Mn = 2E·Cb·√(J·Ag)/(Lb/?)` — the `(Lb/ry)` term garbled in extraction | F-3 §F7 LTB elastic branch | curated `2E·Cb·√(J·Ag)/(Lb/ry) ≤ Mp` — re-pull PDF |
| EC-9 | §F10 equations **F10-1, F10-2, F10-3, F10-4, F10-5a** + their pages | **printed 16.1-69 absent from `spec_chapterF.txt`** (extract jumps 16.1-68 → 16.1-70) | F-6 §F10 yield/LTB | curated forms in Part 1 §F10 — re-pull printed 16.1-69 |
| EC-10 | §F10.3 compact/NC **b/t limits** (0.54 / 0.91 √(E/Fy)) | on the absent printed 16.1-69 | F-6 §F10 leg-LB classifier | curated; F10-8 slender form IS confirmed (16.1-70) |
| EC-11 | §F1 / Eq. **F1-1** page label | extract starts at 16.1-53 (F2); §F1 outside it | (F-1, not F-0) Cb citation | shipped code uses p.16.1-47; retained, not overwritten |
| EC-12 | Shipped F2–F5 page labels vs extract | **RESOLVED (orchestrator, F-1 gate).** Shipped `flexure/F*.py` cite F2 @16.1-49, F3 @16.1-50, F5 @16.1-52, F4 @16.1-56; the `spec_chapterF.txt` extract prints F2 @16.1-53, F3 @16.1-55, F4 @16.1-56, F5 @16.1-60. | F-1 (refactor) — resolved, no code change | **The shipped `AISCClauseReference` page labels (F2@16.1-49 / F3@16.1-50 / F5@16.1-52 / F4@16.1-56) are AUTHORITATIVE** and are **left unchanged**. The orchestrator confirmed them against the `aisc-steel-design` skill reference *and* prior-phase verification. The divergent `16.1-NN` labels in this file's Part 1 are an artefact of the staged extract starting **mid-chapter** — `spec_chapterF.txt` was truncated at the first `(Fn-n)` token (≈ printed 16.1-53), so its printed running-header labels are offset from the spec's true §F pagination. Part 1's labels are retained only as the extract's internal cross-reference; **code and oracle cite the shipped (authoritative) labels**. F-1 modifies **no** shipped citation page label (verified: the F2/F3/F4/F5 `_CITATIONS_*` tuples are byte-unchanged by the F-1 data-model refactor). |

**Resolution protocol:** at the F-0 review gate the engineer opens
`a360-22w.pdf` to printed 16.1-15/16 (Table B4.1b) and 16.1-69, fills
EC-1..EC-10, decides EC-11/EC-12. Code written in F-0 (and the F-3/F-5/F-6
phases) emits `aisc_b4_1b_case="Case ?"` for EC-1/EC-2/EC-4/EC-5 and the
*confirmed* `"Case 20"` for round HSS (EC-3), with `page=None` on the
B4.1b row citation until EC-3's page is set.

---

## Confidence & gaps

**High confidence (authoritative from `spec_chapterF.txt`, quoted with
printed page):**
- All §F2–§F13 equation **numbers and forms** for the equations whose
  bodies are present in the extract (F2-1..F2-8b, F3-1/2, F4-1..F4-17,
  F5-1..F5-10, F6-1..F6-4, F7-1..F7-7 + F7-10..F7-13, F8-1..F8-4,
  F9-1..F9-19, F10-5b/6/7/8, F11-1..F11-5, F12-1..F12-4, F13-1..F13-7).
- The §F9.4 tee-stem Fcr breakpoints and F10-8 slender-leg form.
- `kc` definition and bounds; DS-I `FL = 0.7Fy`.
- B4.1b Cases 10/11/15/16 (cross-checked against shipped in-repo code).
- B4.1b Case 20 for round HSS (Manual Ex. F.9B text).

**Medium confidence (curated reference; λ forms reliable, case numbers
flagged):**
- Rect-HSS flange/web λ_p/λ_r (1.12/1.40, 2.42/5.70 √(E/Fy)) — forms
  curated, case numbers EC-1/EC-2 unverified.
- Round-HSS λ_p/λ_r (0.07/0.31 E/Fy) — forms curated AND confirmed by
  the §F8 applicability/equation text; case = 20 confirmed.
- Angle-leg / tee-stem limits — the *governing equations* (F9-17..19,
  F10-6..8) are authoritative from the spec; the *B4.1b case labels*
  are EC-4/EC-5; the angle compact/NC b/t numeric limits are EC-10.

**Known extract gaps (must re-pull from PDF in the owning phase, not
F-0):**
- §F7 F7-8, F7-9 bodies; F7-2/F7-6 coefficients; F7-11 denominator
  (EC-6/7/8) — owned by F-3.
- §F10 printed 16.1-69: F10-1..F10-5a + angle b/t limits (EC-9/10) —
  owned by F-6.
- §F1 / F1-1 page (EC-11) — owned by F-1.
- Shipped F2/F3/F5 page-label discrepancy vs extract (EC-12) —
  **RESOLVED at the F-1 gate by the orchestrator**: the shipped
  `flexure/F*.py` page labels are authoritative (corroborated by the
  `aisc-steel-design` skill reference + prior-phase verification); the
  extract's offset labels are a mid-chapter-truncation artefact. **No
  shipped citation is modified** (F-0 *or* F-1). See EC-12 above.

**Impact on F-0 correctness:** none. F-0 ships the generalized model +
classifier + oracle skeleton. The classifier's λ_p/λ_r are unit-anchored
to hand-derived values per `section_kind`; the independent oracle
re-derives every λ numerically. The unconfirmed items are *string
labels* (`aisc_b4_1b_case`, citation `page`) and *future-phase*
equation bodies, none of which affect any F-0 numeric result or any
shipped behaviour.

---

## ENGINEER-CONFIRM ledger (consolidated — Phase F-8 reconciliation)

Single place of record for every Chapter-F ENGINEER-CONFIRM raised
across F-0…F-8 and its resolution. Entries above (EC-1…EC-12) are the
F-0-scoped B4.1b-label / page-label items; this ledger consolidates the
*equation/value* ENGINEER-CONFIRMs the phase work raised and adjudicated,
and restates the still-open label-only items as non-blocking.

| ID | What | Status | Resolution / authority |
|---|---|---|---|
| **F6-EC-1** | §F6 Eq. F6-4 `Fcr` / §F6.2 plateau coefficient (`0.70` vs the 360-16 `0.69`) | **RESOLVED** | AISC 360-22 §F6 Eq. F6-4 `Fcr = 0.70·E/λ²` and §F6.2 plateau `0.70·Fy·Sy`, verbatim `a360-22w.pdf` (orchestrator-verified, `spec_chapterF.txt` L1293/L1312). The staged "0 70" is PyMuPDF stripping the decimal of "0.70" (text extraction never transposes digits). 360-16 used 0.69 — a **documented edition delta** (design note 10 §1/§9). `0.70` is used in both the library (`F6_minor_axis.py`) and the independent oracle, so the tier-1 bit-exact anchor does not mask the choice. |
| **F10-EC-1** | §F10.2(b) geometric-axis `Me` (Eq. F10-5a / F10-5b) form | **RESOLVED** | `Me = 0.58·E·b⁴·t·Cb/Lb²·[√(1+0.88·(Lb·t/b²)²) ∓ 1]` (`−1` Eq. F10-5a compression-at-toe / `+1` Eq. F10-5b tension-at-toe), CONFIRMED verbatim from `_aisc_src_extract/spec_F10_geometric.txt` (printed 16.1-69/70, orchestrator-staged; AISC spec 16.1-69/70). Dimensionally a moment (`[F/L²]·[L⁴]·[L]/[L²]=F·L`) and reproduces AISC Manual v15.1 Ex. F.11A `Mcr=107 kip-in` / Ex. F.11B `Mcr=1.25·F10-5a=176 kip-in` to 3 sig figs. The earlier curated `b·t²/Lb` powers were correctly REJECTED (wrong dimensions). |
| **F11-1** | §F11.1 rectangular-bar cap `1.5·Fy·Sx` (vs round-bar `1.6·Fy·Sx`) | **RESOLVED** | AISC **360-22** §F11.1 (the authority, `spec_chapterF.txt` printed 16.1-71) tightened the rectangular-bar Eq. F11-1 cap to `1.5·Fy·Sx`; the round-bar Eq. F11-2 cap is `1.6·Fy·Sx`. The AISC Manual v15.1 Ex. F.12 prints the looser 360-16 `1.6` rect cap — a **documented edition delta** (design note 10 §1/§9); the 360-22 capped result is pinned bit-exactly in `test_chapterF_F11_F12_golden.py` so the delta is explicit, never hidden. |
| **F7tail-EC-1** | AISC Manual v15.1 Ex. F.13 (round bar) printed `Mn`/`φMn` truncated from the staged source | **RESOLVED (Phase F-8 — orchestrator)** | The orchestrator extracted the full Ex. F.13 body to `_aisc_src_extract/manual_F13_roundbar.txt` (verbatim, PDF p.212-213). Manual prints `Mn=5.66 kip-in.=0.472 kip-ft`, `φMn=0.425 kip-ft`, `Mn/Ω=0.283 kip-ft`. `test_chapterF_F11_F12_golden.py::test_F11_manual_v15_1_example_F13_round_bar_handcalc` already asserts these (3 sig figs) + the Eq. F11-2 closed form bit-exactly. The F-8 reconciliation fixed only the now-stale Ex. F.13 **module-docstring** bullet (the test/asserts were already updated). |
| **F9-EC-1** | §F9.2(b)(2) double-angle web-legs-in-compression LTB (F-5 conservatively bounded it by the §F9.2(b)(1)-form `Mn=min(Mcr,My)` because §F10 did not exist yet) | **RESOLVED (this phase, F-8)** | AISC 360-22 §F9.2(b)(2) (`spec_chapterF.txt` printed 16.1-67, verbatim): "For double-angle web legs, `Mn` shall be determined using **Equations F10-2 and F10-3** with `Mcr` determined using Equation **F9-10** and `My` determined using Equation **F9-3**." §F10 shipped in F-6 (before this F-8 phase), so §F9 now applies the **exact** §F10.2 inelastic/elastic-LTB reduction by reusing §F10's `_mn_ltb_from_me` via the permitted intra-`flexure`-layer import (single source of truth — no re-derivation, so §F9/§F10 cannot disagree). The §F9 oracle (`_chapterF_F9_oracle.py`, re-derives Eq. F10-2/F10-3 from spec literals, **not** imported from apeSteel) and that one golden sub-case (`test_F9_double_angle_EC1_web_compression_ltb_uses_exact_F10_2_3`) were updated to the exact §F10 value; **every other §F9 number is bit-identical** (the branch fires only for `section_kind=="double_angle"` *and* web legs in compression — tee stems still use Eq. F9-13 `Mn=Mcr≤My`). §F10.3 leg-LB duplication between §F9 and §F10 was **deliberately kept** (Phase-F-8 contract: bit-exactness > DRY; an extraction whose bit-exactness could not be gate-proven is not taken) with matching cross-citing comments on `F9_tee_double_angle._f10_3_leg_local_buckling` and `F10_single_angle._leg_local_buckling`. |
| **F8-EC-1** | SS-slender §F5 (plate-girder) AISC Manual tier-2 anchor — Ex. **F.15** | **RESOLVED (orchestrator investigation, F-8 close-out)** | The orchestrator extracted the full Ex. F.15 body to `_aisc_src_extract/manual_F14_F15plus.txt` (verbatim, PDF p.216-229). **Finding:** Ex. F.15 "Plate Girder Flexural Member" is a **doubly-symmetric** built-up I (ASTM A572 Gr.50, equal flanges) — it is **not** singly-symmetric, so it does not anchor the SS-specific `Sxc≠Sxt` path. The Companion has **no** singly-symmetric slender-web §F5 worked example (SS plate girders are not a Companion example). The §F5 *machinery* the SS variant shares (`Rpg` Eq. F5-6, F5-1..F5-10) is **already** externally anchored by the original pre-Phase-F engineer-validated **"Plate Girders" spreadsheet golden** (the §6 external authority — same Excel-anchor precedent as F-1 §F2 / F-6 §H1.1). Therefore §6 ("no §F section lacks a published external anchor") **is satisfied for §F5** independently of Ex. F.15, and the SS-specific `Sxc/Sxt` path is correctly tier-1 bit-exact stdlib-oracle + hand-calc anchored (`test_chapterF_F1_additions.py`, `rel_tol=1e-9`) — the documented §6 fallback, Phase-E/H precedent. No mismatched/invented anchor was manufactured. **No code change**; the §F5-SS test is unchanged. |
| EC-3 | B4.1b **round-HSS** flexure row *page label* (the case number **is** confirmed `Case 20` from Manual Ex. F.9B) | **OPEN — label-only, non-blocking** | `page=None` on the B4.1b round-HSS row citation. The independent §F8 oracle re-derives the `0.07`/`0.31·E/Fy` λ limits numerically, so no numeric result depends on the page label. |
| EC-4 / EC-5 | B4.1b **single/double-angle-leg** (EC-4) and **tee-stem** (EC-5) flexure *case-number labels* | **OPEN — label-only, non-blocking** | Emitted `aisc_b4_1b_case="B4.1b Case ?"`. §F10.3 (angle leg) and §F9.4 (tee stem) supply the governing breakpoints/equations directly (authoritative from `spec_chapterF.txt`); the oracle re-derives every λ numerically. Correctness does not depend on the case label. |
| EC-9 / EC-10 | §F10 printed **16.1-69** absent from the staged spec → Eq. F10-1..F10-5a *page labels* (EC-9) and the §F10.3 compact/NC `b/t` numeric limits `0.54`/`0.91·√(E/Fy)` (EC-10) | **OPEN — label/curated, non-blocking** | F10-1/F10-2/F10-4 are numerically Manual-CONFIRMED (Ex. F.11A/C); F10-5a/5b are **F10-EC-1 RESOLVED** (re-pulled `spec_F10_geometric.txt`); F10-6/7/8 are CONFIRMED from 16.1-70. The `0.54`/`0.91` leg limits are curated and the independent §F10 oracle re-derives them numerically, so no numeric result depends on EC-9/EC-10. `page=None` retained on the affected citations until 16.1-69 is re-pulled. |

**Net for the gate:** F6-EC-1, F10-EC-1, F11-1, F7tail-EC-1,
**F9-EC-1** and **F8-EC-1** are all RESOLVED (with the authority
quoted above; the edition deltas are documented and pinned, never
hidden; F8-EC-1 resolved by investigation — §F5 is already §6-anchored
by the original Plate-Girders spreadsheet golden, and no SS-slender
§F5 Companion example exists). The only OPEN items are
the **label-only** B4.1b items EC-3/4/5/9/10 (`aisc_b4_1b_case` /
citation `page` strings; the independent oracle re-derives every λ
numerically, so **no numeric result and no shipped behaviour depends
on them**). None is blocking.
