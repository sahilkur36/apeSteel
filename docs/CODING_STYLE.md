# Coding style

`apeSteel` is a code-of-record library: engineers will use its outputs to
sign drawings. Every line is written like that's true.

This document is the contract between contributors. It complements
`ARCHITECTURE.md` (what the modules are) and `UNITS_AND_CONVENTIONS.md` (how
numbers flow). Here we cover *how the Python looks*.

---

## 1. The toolchain

| Tool | Purpose | Strict? |
| --- | --- | --- |
| Python | runtime | ≥ 3.11 |
| `pyright` | static type checker | **strict** (CI fails on warnings) |
| `ruff` | linter + formatter | default rules + custom set below |
| `pytest` | test runner | with `--strict-markers --strict-config` |
| `pytest-cov` | coverage | `--cov-fail-under=90` for `apeSteel/` |
| `pre-commit` | local enforcement | runs `ruff`, `pyright`, `pytest -q -k fast` |

CI runs the same toolchain against every PR.

### pyright config (`pyrightconfig.json`)

```jsonc
{
  "include": ["src", "tests"],
  "pythonVersion": "3.11",
  "typeCheckingMode": "strict",
  "reportMissingTypeStubs": "warning",
  "reportImplicitOverride": "error",
  "reportImportCycles": "error",
  "reportPrivateUsage": "error",
  "reportUnnecessaryTypeIgnoreComment": "error",
  "reportUnnecessaryIsInstance": "error",
  "reportShadowedImports": "error"
}
```

### ruff config (`ruff.toml`)

```toml
target-version = "py311"
line-length = 100

[lint]
select = [
  "E", "F", "W", "I",    # pycodestyle, pyflakes, isort
  "UP",                  # pyupgrade
  "B",                   # bugbear
  "PL",                  # pylint subset
  "RUF",                 # ruff-specific
  "ANN",                 # flake8-annotations
  "SIM",                 # simplify
  "TCH",                 # type-checking imports
  "PT",                  # pytest style
  "N",                   # PEP 8 naming
]
ignore = [
  "N802",  # function lowercase  — we allow capital_AISC_symbol_suffix
  "N803",  # argument lowercase  — same reason
  "N806",  # variable in function lowercase — same reason
  "PLR0913", # too many arguments — calculators legitimately take many
]
```

The `N802/803/806` exceptions are critical: our naming convention deliberately
appends an `AISC_symbol` to verbose names (e.g. `flange_width_bf`,
`limiting_length_plastic_Lp`). Inside short calculators we also rebind to
the bare AISC symbol (`Lp = ...`). Both patterns trip stock PEP 8 naming.

---

## 2. Naming

See `UNITS_AND_CONVENTIONS.md` §4 for the full table. The short version:

- **Public**: `flange_width_bf`, `yield_stress_Fy`,
  `limiting_length_plastic_Lp`.
- **Private**: prefix with `_`, e.g. `_section_properties_cached`.
- **Constants** (module-level): `SCREAMING_SNAKE_CASE` with an AISC
  reference in the trailing comment:
  ```python
  AISC_F2_REDUCED_STRESS_FACTOR_0p7: float = 0.7  # AISC 360 §F2.2 (Eq. F2-2)
  ```
- **Local rebinds** to bare AISC symbols are allowed **only inside short
  calculators** (≤ ~40 lines, single AISC paragraph), and only after a
  comment that quotes the AISC equation number. See
  `UNITS_AND_CONVENTIONS.md` §4 rule 2 for the template.

---

## 3. The shape of a calculator

Every calculator is a **pure function** that returns a frozen `Report`. No
class state. No globals. No side effects.

```python
"""AISC 360 §F2 — flexural strength of compact doubly-symmetric I-shapes."""
from __future__ import annotations

import math
from dataclasses import dataclass

import baseUnits as u
assert u.BASE == "N-mm-tonne-s", f"apeSteel requires N-mm-tonne-s, got {u.BASE!r}"

from apeSteel.core.materials import SteelMaterial
from apeSteel.core.result_types import AISCClauseReference, Report
from apeSteel.sections.properties import SectionProperties


@dataclass(frozen=True, slots=True)
class FlexureF2Report(Report):
    unbraced_length_Lb:                  float
    limiting_length_plastic_Lp:          float
    limiting_length_inelastic_LTB_Lr:    float
    plastic_moment_Mp:                   float
    nominal_flexural_strength_Mn:        float
    phi_nominal_flexural_strength_phi_Mn_LRFD: float
    Cb_used: float


_PHI_FLEXURE_LRFD: float = 0.90   # AISC 360 §F1 (LRFD strength factor)


def compute_flexural_strength_F2_compact_doubly_symmetric(
    section_properties: SectionProperties,
    material: SteelMaterial,
    unbraced_length_Lb: float,
    lateral_torsional_buckling_modification_factor_Cb: float,
) -> FlexureF2Report:
    """Return the nominal flexural strength Mn per AISC 360 §F2.

    Assumes the section is compact (both flange and web). The caller is
    responsible for verifying this via classify_flexural_compactness_B4.

    Parameters
    ----------
    section_properties : SectionProperties
        Frozen dataclass with Zx, Sx, ry, rts, J, Cw, ho — all in
        N-mm-tonne-s base units.
    material : SteelMaterial
        Steel grade (Fy, E in base units).
    unbraced_length_Lb : float
        Distance between points braced against lateral displacement of
        the compression flange, in base units (mm).
    lateral_torsional_buckling_modification_factor_Cb : float
        Cb per AISC 360 §F1, dimensionless. Caller must compute it
        explicitly — there is no default.

    Returns
    -------
    FlexureF2Report
    """
    # … short body with local AISC-symbol rebinds …
```

Style points to copy:

1. The module docstring names the AISC section it implements.
2. The `assert u.BASE == ...` is the second statement after `from __future__`.
3. Every public function has a numpydoc docstring (parameters + returns).
4. The `Report` subclass is defined in the same file as the calculator.
5. Constants (`_PHI_FLEXURE_LRFD`) are module-level, named, cited.

---

## 4. Banned patterns

| Pattern | Why | Use instead |
| --- | --- | --- |
| `print(...)` inside `src/apeSteel/` | Reports format themselves | `report.format()` returns `str` |
| Bare `except:` | Hides bugs | Catch the specific exception |
| `Any` in type hints | pyright will warn | Concrete type or `object` + isinstance |
| `from x import *` | hides origins | Explicit imports |
| Mutating a frozen dataclass via `object.__setattr__` | defeats `frozen=True` | Make a new dataclass with `replace()` |
| Implicit `Optional` (`def f(x: int = None)`) | pyright strict will error | `x: int \| None = None` |
| Magic literals (`0.7`, `1.76`, `5.7`, `260`) | not traceable | named constant with AISC citation comment |
| Class-level mutable state in calculators | side effects | pure functions only |
| Floats compared with `==` | precision | `math.isclose` or a tested tolerance |
| `numpy` inside calculators (unless vectorising) | hides intent | plain `math` for scalars |

---

## 5. Tests

Three tiers:

1. **Unit tests** (`tests/unit/`) — one Python file per module, with the
   same name. Tests each pure function on a handful of inputs.
2. **Golden tests** (`tests/golden/`) — CSV files with hand-computed (or
   spreadsheet-extracted) expected outputs. The test loops over rows and
   compares with `math.isclose(rel_tol=1e-9, abs_tol=1e-12)`. These are
   the regression net for AISC equations.
3. **End-to-end tests** (`tests/e2e/`) — exercise `BeamCheck` against the
   exact default sections shown in the original spreadsheet, and pin the
   final phi·Mn and phi·Vn values.

Tests are marked `fast` or `slow`. `pre-commit` runs only `fast`; CI runs
both. Coverage must stay ≥ 90% for `src/apeSteel/`.

---

## 6. Docstrings

NumPy style. Sections in this order: Summary, Extended summary, Parameters,
Returns, Raises, Notes, References, Examples.

Every public calculator's `References` section cites the AISC clauses it
implements:

```rst
References
----------
.. [1] AISC 360-22, §F2.2 "Lateral-Torsional Buckling", Eq. F2-1 through
       F2-6. Steel Construction Manual, 16th ed., pp. 16.1-49 – 16.1-50.
.. [2] AISC 341-22, §D1.2b "Lateral Bracing of Beams in Special Moment
       Frames", Eq. D1-1. p. 9.1-21.
```

The same citations are also embedded in the `Report` via
`cited_clauses: tuple[AISCClauseReference, ...]` so users can inspect them
programmatically.

---

## 7. Commits and PRs

- One AISC equation per commit when porting (the commit subject contains
  the AISC reference, e.g. `flexure(F2): port Lp formula (Eq. F2-5)`).
- Every PR must update or add at least one golden CSV.
- Every PR must update `docs/ROADMAP.md` to tick off completed items.
- `pyright`, `ruff`, `pytest`, and `pytest --cov` must all pass before
  merge.

---

## 8. Reading the AISC code

When in doubt, the order of authority is:

1. **AISC 360** + **AISC 341** + **AISC 358** for connection prequalification.
2. AISC **Steel Construction Manual** (15th and 16th editions), for tables.
3. AISC **Design Guides** (DG 1, 9, 11, 24, 28, 29 are most likely to come up).
4. AISC **Seismic Design Manual** for design examples and worked details.

The `aisc-steel-design` skill (see project skills) is the in-house expert
for resolving ambiguity; consult it before guessing.
