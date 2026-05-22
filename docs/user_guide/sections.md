# Sections & Catalogs

A *section* in `apeSteel` is the immutable plate-dimension (or rolled-
shape) description of a single cross-section family. Each geometry
class lives in `apeSteel.sections.geometry` as a frozen dataclass
storing the plate dimensions in the canonical `N-mm-tonne-s` base. Its
`compute_section_properties` (or `compute_compression_properties`)
method integrates those dimensions into the universal
`SectionProperties` / `CompressionSectionProperties` /
`FlexuralSectionProperties` frozen dataclasses that every AISC
calculator downstream consumes.

The geometry classes know **nothing** about material, unbraced length,
or load — those live in the composition spine (`SteelMaterial`,
`Bracing`, and `Element`).

## Geometry families

| Class | AISC §F family | Used for |
| --- | --- | --- |
| `DoublySymmetricISection` | §F2 / §F3 / §F4 / §F5 | Welded built-up I (two identical flanges + centred web) |
| `SinglySymmetricISection` | §F4 / §F5 | I with unequal top / bottom flanges |
| `ChannelSection` | §F2 major, §F6 minor | Plate-built C / MC |
| `RectangularHSS` | §F7 | Rectangular / square HSS |
| `RoundHSS` | §F8 | Round HSS / pipe |
| `TeeSection` | §F9 | WT / MT / ST tee |
| `SingleAngleSection` | §F10 | L single angle |
| `DoubleAngleSection` | §F9 | 2L double angle |
| `RectangularBar` | §F11 | Solid rectangular bar |
| `RoundBar` | §F11 | Solid round bar |

All ten classes follow the same idiom: a small frozen dataclass with
descriptive long-form plate-dimension field names (e.g.
`flange_width_bf`, `wall_thickness_t`, `overall_depth_d`), a single
public method that returns properties, and an `element(...)` shortcut
on the I-section families that builds an `Element` directly.

## Pattern 1 — Build a plate-built section

```python
--8<-- "examples/sections_plate_built.py"
```

Every constructor takes its plate dimensions multiplied by a unit
constant from `apeSteel.core.units`; the dataclass stores the resulting
float in base units (`mm`).

## Pattern 2 — Pull a rolled shape from a catalog

```python
--8<-- "examples/sections_catalog_lookup.py"
```

`AISCv16Catalog` and `EuropeanIPECatalog` are the two shipped lookups:

- **`AISCv16Catalog`** wraps the AISC v16 SI shapes database (~2 299
  rolled shapes: W / M / S / HP I-shapes, channels, angles, HSS, pipes,
  tees). `get_row(label)` returns a validated `CatalogRowAISCv16`;
  `get_section_properties(label)` adapts a doubly-symmetric I row into
  the I-shape `SectionProperties` currency;
  `get_flexural_section_properties(label)` routes any catalogued type
  into its §F family-appropriate `FlexuralSectionProperties`;
  `get_doubly_symmetric_i_geometry(label)` returns a plate-built
  `DoublySymmetricISection` so the catalog rolled shape feeds straight
  into the `Element` composite. Lookup is case-insensitive with a
  RapidFuzz fallback when the requested label does not exact-match.

- **`EuropeanIPECatalog`** wraps an EN 10365 IPE subset (IPE 200 / 300
  / 400 / 500 / 600 ship out of the box) with the same API surface.
  Both catalogs honour user-supplied CSV paths through their
  constructors (`AISCv16Catalog(csv_path=...)`).

The catalog-adapted `SectionProperties` is byte-identical to what
`get_section_properties` produces, so a catalog-anchored golden
cross-checks bit-for-bit against the §F engine on the catalog's own
`Z` / `S` / `I` / `J` values.

## Pattern 3 — Section properties are derived, not stored

The geometry dataclass holds only plate dimensions. Everything else —
`Ag`, `Ix`, `Sx`, `Zx`, `Iy`, `J`, `Cw`, `rts`, the plate slenderness
ratios — is computed on demand by `compute_section_properties` (or
`compute_compression_properties` for the §E Chapter-E input snapshot).
The closed-form formulas reproduce the underlying spreadsheet anchor
exactly and are pinned by golden tests.

When the section is bound to an `Element`, the `Element.section_properties`
`cached_property` runs the integration once and caches the result, so
repeated checks against the same `Element` do not redo the work.
