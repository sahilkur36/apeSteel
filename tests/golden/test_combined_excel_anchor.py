"""External anchor: apeSteel Chapter-H vs the engineer's spreadsheet.

``_combined_excel_raw.json`` is a faithful dump (formula + cached
value of every non-empty cell) of the engineer's
``Diseño Flexo-Compresion Viga I.xlsm`` - a genuinely *independent*
AISC beam-column implementation (hand-built in Excel/VBA, predating
apeSteel), produced by ``tools/dump_excel_workbook.py``.

Provenance / edition note
-------------------------
The workbook is the engineer's AISC-360 implementation (the same
``Fy = ksi*70.3`` convention and tonne-force / tonne-metre units as the
Chapter-E compression workbook).  Chapter H is an *interaction*
chapter, and the §H1.1 unity equation **Eq. H1-1a / H1-1b is
edition-independent** - identical in AISC 360-16 and 360-22.  The
workbook computes it verbatim at ``W!J29``::

    J29 = IF(J27/J3 >= 0.2,
             J27/J3      + 8/9*(J28/J4),     # Eq. H1-1a
             J27/(2*J3)  +     (J28/J4))     # Eq. H1-1b

with ``J27 = Pu``, ``J3 = governing phi*Pn`` (its own Chapter-E result,
``MIN(C68,C78,C88)``), ``J28 = Mu``, ``J4 = governing phi*Mn`` (its own
Chapter-F result, ``'Seccion Tipo I'!L11``).

This test reads the workbook's **own** ``Pc``/``Mc``/``Pr``/``Mr`` and
feeds them into :func:`apeSteel.compute_combined_strength_H1_1`.  The
interaction is therefore isolated from any 360-16-vs-360-22 difference
in ``Pc``/``Mc`` (those are taken as-is from the workbook, not
recomputed); the apeSteel DCR must reproduce ``W!J29`` to full double
precision.  Agreement is asserted at ``rel_tol = 1e-9`` (the only error
source is the JSON float round-trip, which is lossless for IEEE-754
doubles).

Scope of this anchor
--------------------
The workbook is intentionally "basic" - it ships a **single worked
§H1.1 example** (here the H1-1b branch).  §H1.2 / §H1.3 / §H2 / §H3 are
not in the workbook; those clauses are anchored bit-exact against the
independent stdlib oracle in ``test_chapterH_independent.py`` (the
primary correctness anchor) and by reviewer hand calcs.  This file is
the *secondary* external cross-check on §H1.1.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from apeSteel import compute_combined_strength_H1_1

_RAW = Path(__file__).parent / "data" / "_combined_excel_raw.json"


@pytest.fixture(scope="module")
def w_cells() -> dict[str, object]:
    if not _RAW.exists():  # pragma: no cover - fixture data must ship
        pytest.skip(f"Excel anchor dump missing: {_RAW}")
    data = json.loads(_RAW.read_text(encoding="utf-8"))
    return {c["coord"]: c["value"] for c in data["sheets"]["W"]["cells"]}


def _f(cells: dict[str, object], coord: str) -> float:
    return float(cells[coord])  # type: ignore[arg-type]


def test_workbook_J29_is_AISC_Eq_H1_1(w_cells: dict[str, object]) -> None:
    """The engineer's J29 formula *is* AISC Eq. H1-1a/H1-1b (provenance)."""
    data = json.loads(_RAW.read_text(encoding="utf-8"))
    j29 = next(c for c in data["sheets"]["W"]["cells"] if c["coord"] == "J29")
    formula = str(j29["formula"]).replace(" ", "")
    # Independent Excel/VBA implementation of the same spec equation:
    assert "J27/J3>=0.2" in formula  # the Pr/Pc >= 0.2 break
    assert "8/9*(J28/J4)" in formula  # Eq. H1-1a moment factor 8/9
    assert "J27/(2*J3)" in formula  # Eq. H1-1b axial term Pr/(2 Pc)


def test_H1_1_facade_reproduces_workbook_interaction(w_cells: dict[str, object]) -> None:
    # Workbook's own quantities (edition-independent interaction inputs).
    pu = _f(w_cells, "J27")  # required axial Pr
    phi_pn = _f(w_cells, "J3")  # governing phi*Pn  (workbook Chapter E)
    mu = _f(w_cells, "J28")  # required moment Mr
    phi_mn = _f(w_cells, "J4")  # governing phi*Mn  (workbook Chapter F)
    j29 = _f(w_cells, "J29")  # workbook H1-1a/1b ratio

    rep = compute_combined_strength_H1_1(
        required_axial_Pr=pu,
        available_axial_Pc=phi_pn,
        required_moment_x_Mrx=mu,
        available_moment_x_Mcx=phi_mn,
    )

    # The worked example is the low-axial branch (Pu/phi*Pn < 0.2).
    assert pu / phi_pn < 0.2
    assert rep.governing_equation == "H1-1b"
    # Edition-independent: identical algebra on the workbook's own
    # Pc/Mc must reproduce J29 to full double precision.
    assert math.isclose(rep.demand_capacity_ratio, j29, rel_tol=1e-9)
    # Sanity: the workbook example is (heavily) overstressed in flexure.
    assert rep.demand_capacity_ratio > 1.0
    assert rep.unity_check_passes is False
