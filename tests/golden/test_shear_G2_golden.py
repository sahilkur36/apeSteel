"""Golden-file regression tests for compute_shear_strength_G2_doubly_symmetric."""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest

from apeSteel import (
    A36,
    A992,
    S355,
    DoublySymmetricISection,
    compute_shear_strength_G2_doubly_symmetric,
)
from apeSteel.core import units as u

if TYPE_CHECKING:
    from apeSteel.classification import SectionConstruction
    from apeSteel.core.materials import SteelMaterial


GOLDEN_CSV_PATH: Path = Path(__file__).parent / "shear_G2.csv"
TOL: float = 1e-9

_MATERIAL_BY_NAME: dict[str, SteelMaterial] = {"A992": A992, "A36": A36, "S355": S355}


def _load_rows() -> list[dict[str, str]]:
    with GOLDEN_CSV_PATH.open() as fp:
        return list(csv.DictReader(fp))


def _isclose(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=TOL, abs_tol=TOL)


@pytest.mark.golden
@pytest.mark.parametrize(
    "row",
    _load_rows(),
    ids=[r["case_label"] for r in _load_rows()],
)
def test_G2_golden(row: dict[str, str]) -> None:
    sec = DoublySymmetricISection(
        flange_width_bf=float(row["bf_mm"]) * u.mm,
        flange_thickness_tf=float(row["tf_mm"]) * u.mm,
        web_clear_height_hw=float(row["hw_mm"]) * u.mm,
        web_thickness_tw=float(row["tw_mm"]) * u.mm,
    )
    material = _MATERIAL_BY_NAME[row["material"]]
    construction = cast("SectionConstruction", row["construction"])
    a_str = row["stiffener_spacing_a_m"]
    stiffener_spacing = (float(a_str) * u.m) if a_str else None

    r = compute_shear_strength_G2_doubly_symmetric(
        sec.compute_section_properties(),
        material,
        construction,
        transverse_stiffener_spacing_a=stiffener_spacing,
    )

    assert _isclose(r.web_slenderness_ratio_lambda_w, float(row["lambda_w"]))
    assert _isclose(r.web_plate_buckling_coefficient_kv, float(row["kv"]))
    assert _isclose(r.yielding_limit_lambda_1, float(row["lambda_1"]))
    assert _isclose(r.inelastic_limit_lambda_2, float(row["lambda_2"]))
    assert _isclose(r.web_shear_strength_coefficient_Cv1, float(row["Cv1"]))
    assert _isclose(r.web_area_Aw, float(row["Aw_mm2"]))
    assert _isclose(r.nominal_shear_strength_Vn, float(row["Vn_N"]))
    assert _isclose(r.phi_strength_LRFD, float(row["phi_Vn_N"]))
    assert r.governing_shear_regime == row["regime"]
    assert _isclose(r.phi_LRFD, float(row["phi"]))
    assert str(r.is_qualified_for_phi_1p00_stocky_rolled_exception) == row["is_stocky_qualified"]
