# Design note 01 — Section catalog

> **Status:** design, not yet implemented.
> **Drives:** `apeSteel.sections.catalog`, `apeSteel.sections.geometry`,
> `apeSteel.sections.properties`.

This note defines the boundary between **user-defined plate-built sections**
and **catalog (rolled) sections**, and explains how both end up speaking the
same downstream language — `SectionProperties`.

---

## 1. Two ways in, one way through

```
            ┌──────────────────────────────────┐
            │  user-defined plate-built shape  │
            │  (bf, tf, hw, tw)                │
            └──────────────┬───────────────────┘
                           │ .compute_section_properties()
                           ▼
            ┌──────────────────────────────────┐
            │       SectionProperties           │ ◄── canonical type
            │  Ag, Ix, Sx, Zx, ry, rts, J, Cw…  │
            └──────────────▲───────────────────┘
                           │ CatalogAdapter.to_section_properties()
            ┌──────────────┴───────────────────┐
            │   catalog row (AISC v16, IPE, …)  │
            │   parsed from pickle / table      │
            └──────────────────────────────────┘
```

`SectionProperties` is the **only** data structure the flexure/shear/
classification calculators see. They never need to know whether the
numbers came from `(bf, tf, hw, tw)` or from the AISC v16 pickle.

---

## 2. The catalog inventory

### AISC v16 (the existing pickle)

The file `src/apeSteel/sections/catalog/data/AISC_Database.pkl` is the AISC
v16 shapes database, 2 299 rows × 82 columns, covering:

| Type | Examples | Use |
| --- | --- | --- |
| W | W44X408, W24X94 | wide flange |
| M | M5X18.9 | miscellaneous |
| S | S24X121 | standard I |
| HP | HP14X117 | bearing piles |
| C | C15X50 | channels |
| MC | MC18X58 | misc. channels |
| L | L8X8X1 | angles (equal) |
| 2L | 2L8X6X1-LLBB | double angles |
| WT, MT, ST | WT22X167.5 | tees |
| HSS | HSS20X12X5/8 | rectangular/square HSS |
| HSS-round | HSS20.000X0.500 | round HSS |
| Pipe | Pipe10STD | standard pipe |

The pickle ships in **imperial units** (inches, ksi). The catalog loader
converts every numeric column to N-mm-tonne-s base units on load. After
that, the rest of the library is unit-agnostic.

### European catalogs (planned)

| Catalog | Range | Source |
| --- | --- | --- |
| IPE | IPE 80 – IPE 600 | EN 10365 |
| IPEA | IPEA 80 – IPEA 600 | EN 10365 |
| IPEO | IPEO 180 – IPEO 600 | EN 10365 |
| HEA | HE 100 A – HE 1000 A | EN 10365 |
| HEB | HE 100 B – HE 1000 B | EN 10365 |
| HEM | HE 100 M – HE 1000 M | EN 10365 |
| UPN, UPE | channels | EN 10365 |

The original spreadsheet embeds an IPE table at `R44:V88` (just `bf, tf, h,
tw`) and looks up section properties by depth. We will ship the full set of
EN 10365 properties (incl. `Iy`, `Sy`, `Zy`, `It`, `Iw`, `iy`) as a
versioned CSV in `sections/catalog/data/european_*.csv` so it's editable
and reviewable in git, then load+validate via pydantic v2.

---

## 3. Catalog row schema (pydantic v2)

The pydantic boundary is **read-only and load-only**. We define one model
per catalog because the columns differ:

```python
from pydantic import BaseModel, ConfigDict, Field

class CatalogRowAISCv16(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    AISC_Manual_Label:                  str                       # "W24X94"
    section_type:                       str  = Field(alias="Type")  # "W"
    weight_W:                           float                     # kg/m in base
    gross_area_Ag:                      float                     # mm^2
    overall_depth_d:                    float                     # mm
    flange_width_bf:                    float                     # mm
    flange_thickness_tf:                float
    web_thickness_tw:                   float
    moment_of_inertia_Ix:               float                     # mm^4
    elastic_section_modulus_Sx:         float
    plastic_section_modulus_Zx:         float
    radius_of_gyration_x_rx:            float                     # mm
    moment_of_inertia_Iy:               float
    elastic_section_modulus_Sy:         float
    plastic_section_modulus_Zy:         float
    radius_of_gyration_y_ry:            float
    torsional_constant_J:               float                     # mm^4
    warping_constant_Cw:                float                     # mm^6
    distance_between_flange_centroids_ho: float
    effective_radius_of_gyration_rts:   float
    # cell-formula entries that AISC v16 uses for plate-element ratios
    flange_width_to_thickness_ratio_bf_2tf: float
    web_height_to_thickness_ratio_h_tw:     float
```

European rows get their own model (`CatalogRowEuropeanIPE`, etc.) so the
column set is enforced by type. Sections that don't apply to flexure
(angles, pipes, channels weak axis) raise on `.to_doubly_symmetric_i_geometry()`.

---

## 4. Adapter — turning a catalog row into `SectionProperties`

```python
class AISCv16Catalog:
    def __init__(self, pickle_path: Path | None = None) -> None: ...

    def get_row(self, manual_label: str) -> CatalogRowAISCv16:
        """Exact match, then fuzzy fallback (RapidFuzz)."""

    def get_section_properties(self, manual_label: str) -> SectionProperties:
        row = self.get_row(manual_label)
        return SectionProperties(
            gross_area_Ag                       = row.gross_area_Ag,
            moment_of_inertia_Ix                = row.moment_of_inertia_Ix,
            elastic_section_modulus_Sx          = row.elastic_section_modulus_Sx,
            plastic_section_modulus_Zx          = row.plastic_section_modulus_Zx,
            radius_of_gyration_strong_axis_rx   = row.radius_of_gyration_x_rx,
            moment_of_inertia_Iy                = row.moment_of_inertia_Iy,
            elastic_section_modulus_Sy          = row.elastic_section_modulus_Sy,
            plastic_section_modulus_Zy          = row.plastic_section_modulus_Zy,
            radius_of_gyration_weak_axis_ry     = row.radius_of_gyration_y_ry,
            torsional_constant_J                = row.torsional_constant_J,
            warping_constant_Cw                 = row.warping_constant_Cw,
            distance_between_flange_centroids_ho= row.distance_between_flange_centroids_ho,
            effective_radius_of_gyration_for_LTB_rts = row.effective_radius_of_gyration_rts,
            flange_width_to_thickness_ratio_bf_2tf   = row.flange_width_to_thickness_ratio_bf_2tf,
            web_height_to_thickness_ratio_h_tw       = row.web_height_to_thickness_ratio_h_tw,
            source = row,                       # for trace
        )

    def get_geometry(self, manual_label: str) -> DoublySymmetricISection:
        """Reconstruct the plate-built geometry when AISC publishes (bf, tf, tw).
        Useful for verification and for cases where the calculator needs
        plate dimensions directly (e.g. compactness with the bare λ ratios)."""
```

The pickle's existing fuzzy-match behaviour (RapidFuzz) is kept. We just
move it inside a method with a real type signature and a deterministic
return type.

---

## 5. User-defined geometry

For built-up I-shapes the user constructs:

```python
@dataclass(frozen=True, slots=True)
class DoublySymmetricISection:
    flange_width_bf:        float
    flange_thickness_tf:    float
    web_clear_height_hw:    float
    web_thickness_tw:       float

    def compute_section_properties(self) -> SectionProperties:
        # ... closed-form A, Ix, Iy, Sx, Zx, J, Cw, ry, rts, ho ...
```

The math here is what the spreadsheet does in cells B39–B56. We will
implement it once, test it against the spreadsheet's defaults
(100×6 / 300×4), and also against a numerical integration for ten random
plate combinations to catch regressions.

For plate girders that may be slender-web, we use a separate type:

```python
@dataclass(frozen=True, slots=True)
class BuiltUpPlateGirder:
    flange_width_bf:        float
    flange_thickness_tf:    float
    web_clear_height_hw:    float
    web_thickness_tw:       float
    transverse_stiffener_spacing_a: float | None
    # ...
```

The `BeamCheck` facade uses the runtime type of the geometry to decide
whether to route to F2/F3 vs F5.

---

## 6. The fuzzy-match policy

The existing `AISCDatabase` falls back to `rapidfuzz.process.extractOne`
when the exact name doesn't match. We keep that behaviour but:

- Emit a warning via `logging.warning`, not `print`.
- Require the similarity score to be ≥ 80; otherwise raise
  `SectionNotFoundError` (custom exception in `apeSteel.sections.catalog`).
- The chosen alternative is included in the returned object's `source`
  field so the eventual report says which section was actually used.

---

## 7. Open questions (for the port)

1. Should we ship the AISC v16 pickle as-is, or re-ingest the public CSV
   into a CSV that lives in git (more diffable, smaller)? My recommendation
   is **re-ingest to CSV** so the data is reviewable.
2. Do we cover ASTM standard shapes vs ASTM HSS vs cold-formed HSS as
   separate catalog types? The pickle has them all in one frame today; the
   safer move is to keep them in one frame and dispatch on `section_type`.
3. The European catalog: do we also include CRS (cold-rolled steel)
   sections per EN 10219? Postpone until requested.
