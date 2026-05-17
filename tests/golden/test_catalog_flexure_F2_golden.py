"""Catalog-derived F2 LTB golden test (Phase 6 deliverable).

This is the integration test that proves the AISC v16 catalog path
through the apeSteel calculator chain produces the same kind of report
as the user-defined ``DoublySymmetricISection`` path: a single rolled
section (W24X94) loaded from the shipped CSV catalog is run through
:func:`compute_flexural_strength_F2_compact_doubly_symmetric` across
all three LTB regimes (yielding, inelastic, elastic), with two
materials and two ``Cb`` values, and the pinned phi*Mn values are
compared bit-for-bit against the companion CSV at
``catalog_flexure_F2.csv``.

SCOPE: regression only, NOT correctness.  ``catalog_flexure_F2.csv`` is
a snapshot of apeSteel's own output for this catalog path; it detects
*unintended drift* (in an AISC formula or in the catalog unit-conversion
table) but cannot by itself prove the numbers are correct.  The §F2 math
is anchored independently by ``tests/golden/test_chapterF_independent.py``
(AISC re-derivation with no ``apeSteel.flexure`` import); the catalog
values themselves are cross-checked against published manuals in
``tests/unit/test_aisc_v16_catalog.py``.

To refresh after an intentional change, regenerate
``catalog_flexure_F2.csv`` from the current apeSteel output and review
the diff (the independent test must still pass).
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from apeSteel import (
    A992,
    S355,
    AISCv16Catalog,
    compute_flexural_strength_F2_compact_doubly_symmetric,
)
from apeSteel.core import units as u

if TYPE_CHECKING:
    from apeSteel.core.materials import SteelMaterial

GOLDEN_CSV_PATH: Path = Path(__file__).parent / "catalog_flexure_F2.csv"

GOLDEN_RELATIVE_TOLERANCE: float = 1e-9
GOLDEN_ABSOLUTE_TOLERANCE: float = 1e-9

_MATERIAL_BY_NAME: dict[str, SteelMaterial] = {"A992": A992, "S355": S355}


def _load_rows() -> list[dict[str, str]]:
    with GOLDEN_CSV_PATH.open() as fp:
        return list(csv.DictReader(fp))


def _isclose(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=GOLDEN_RELATIVE_TOLERANCE, abs_tol=GOLDEN_ABSOLUTE_TOLERANCE)


@pytest.fixture(scope="module")
def catalog() -> AISCv16Catalog:
    return AISCv16Catalog()


@pytest.mark.regression
@pytest.mark.parametrize(
    "row",
    _load_rows(),
    ids=[r["case_label"] for r in _load_rows()],
)
def test_catalog_F2_golden(row: dict[str, str], catalog: AISCv16Catalog) -> None:
    """Catalog-derived F2 LTB outputs must match the pinned CSV exactly."""
    section_properties = catalog.get_section_properties(row["catalog_label"])
    material = _MATERIAL_BY_NAME[row["material"]]
    unbraced_length_Lb: float = float(row["Lb_m"]) * u.m
    lateral_torsional_modification_factor_Cb: float = float(row["Cb"])

    report = compute_flexural_strength_F2_compact_doubly_symmetric(
        section_properties,
        material,
        unbraced_length_Lb,
        lateral_torsional_modification_factor_Cb,
    )

    assert _isclose(report.limiting_length_plastic_Lp, float(row["Lp_mm"]))
    assert _isclose(report.limiting_length_inelastic_LTB_Lr, float(row["Lr_mm"]))
    assert _isclose(report.plastic_moment_Mp, float(row["Mp_Nmm"]))
    assert _isclose(report.elastic_LTB_moment_Mcr, float(row["Mcr_Nmm"]))
    assert report.governing_limit_state == row["regime"]
    assert _isclose(report.nominal_flexural_strength_Mn, float(row["Mn_Nmm"]))
    assert _isclose(report.phi_strength_LRFD, float(row["phi_Mn_Nmm"]))
