---
hide:
  - navigation
  - toc
---

<div class="ape-hero" markdown>
<img class="ape-hero__mark" src="assets/logo.svg" alt="apeSteel mark" />
<div>
  <div class="ape-hero__word">apeSteel</div>
  <div class="ape-hero__sub">LADRUÑO</div>
</div>
</div>

!!! info "Composition-based AISC steel design"
    apeSteel is a strictly-typed Python library for AISC 360-22 (member
    design), 341-22 (seismic provisions), and 358-22 (prequalified
    moment connections). Every check is a pure function with an
    AISC-cited [`Report`](api/core.md) on the way out. The
    [`Element`](api/element.md) composite ties section + material +
    construction + bracing into one object that exposes every chapter
    as a method.

## Where do you want to start?

<div class="grid cards" markdown>

-   :material-school:{ .lg .middle } &nbsp; __[First steps](getting_started.md)__

    ---

    *I'm new — orient me.*

    Install, the N-mm-tonne-s units invariant, and an end-to-end first
    check from a plate-built section to `φMn`. The right place to
    start.

-   :material-rocket-launch:{ .lg .middle } &nbsp; __[Recipes](recipes/beam_check.md)__

    ---

    *Show me a working check.*

    Full beam check, beam-column §H1.1 with envelope overlay, and a
    design-family capacity-curve comparison. Each one is an executable
    `.py` snippet run in CI.

-   :material-cube-outline:{ .lg .middle } &nbsp; __[User guide](user_guide/element.md)__

    ---

    *I want to build models.*

    Sections, the AISCv16 and EN 10365 catalogs, materials, the
    `Element` composite, and bracing — the four spine pieces of every
    apeSteel program.

-   :material-bank:{ .lg .middle } &nbsp; __[AISC chapters](aisc/E_compression.md)__

    ---

    *I'm looking up a specific check.*

    Deep dives into §B classification, §E compression, §F flexure
    (F2–F12), §G shear, §H combined forces, and AISC 341 seismic
    provisions — with the equations and apeSteel methods side by side.

-   :material-chart-line:{ .lg .middle } &nbsp; __[Plotting](plotting/capacity_curves.md)__

    ---

    *I want to visualize.*

    Capacity curves (`φPn(L)`, `φMn(Lb)`) and §H1.1 interaction
    diagrams in three views: uniaxial P-M, biaxial M-M slice, and the
    full 3D P-Mx-My envelope.

-   :material-book-open-variant:{ .lg .middle } &nbsp; __[API reference](api/element.md)__

    ---

    *Look up a signature.*

    Auto-generated from the source via `mkdocstrings`. One page per
    subpackage — element, sections, classification, compression,
    flexure, shear, tension, combined, serviceability, seismic,
    connections, checks, plotting.

</div>

## What's new

<div class="grid cards" markdown>

-   :material-chart-bell-curve: &nbsp; **Capacity-curve plotters**

    ---

    `plot_compression_curve` and `plot_flexural_curve` sweep `φPn(L)`
    and `φMn(Lb)` with optional log scale, segment-colouring by
    governing limit state, `Lp`/`Lr` landmark verticals (flexure), and
    overlay-on-shared-`ax` for design-family comparisons.

    [Reference →](plotting/capacity_curves.md) ·
    [Recipe →](recipes/design_family_overlay.md)

-   :material-grid: &nbsp; **§H1.1 interaction diagrams**

    ---

    Three views of the beam-column envelope: bilinear uniaxial P-Mx,
    biaxial M-M rhombus at fixed `Pr`, and the full 3D cone+frustum
    via `Poly3DCollection`. Demand points are colour-coded
    green/red by DCR.

    [Reference →](plotting/interaction_diagrams.md) ·
    [Recipe →](recipes/beam_column_H1.md)

-   :material-text-box-check: &nbsp; **Chapter F — F2 through F12**

    ---

    Every Chapter F clause shipped: F2 (compact DS I), F3 (NC flange),
    F4 (NC web, DS+SS), F5 (slender web plate girder), F6 (minor
    axis), F7 (rect HSS), F8 (round HSS), F9 (tees / double angle),
    F10 (single angle), F11 (bar), F12 (unsymmetric catch-all).

    [Chapter F overview →](aisc/F_flexure.md)

-   :material-code-tags-check: &nbsp; **Code-grounded documentation**

    ---

    Every snippet on this site lives as a `docs/examples/*.py` file
    and runs in CI via `tests/docs/test_examples.py`. If the public
    API drifts, the example fails the build — the docs can't lie.

    [Convention →](https://github.com/nmorabowen/apeSteel/blob/main/tests/docs/test_examples.py)

</div>

## Quick example

```python
--8<-- "examples/quickstart.py"
```

---

## Credits

**Developed by:** Nicolás Mora Bowen · Patricio Palacios · José Abell · Guppi

Part of José Abell's *El Ladruño Research Group*.
