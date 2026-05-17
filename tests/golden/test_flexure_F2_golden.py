"""Golden-file regression tests for compute_flexural_strength_F2_*."""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from apeSteel import (
    A36,
    A992,
    S355,
    DoublySymmetricISection,
    compute_flexural_strength_F2_compact_doubly_symmetric,
)
from apeSteel.core import units as u

if TYPE_CHECKING:
    from apeSteel.core.materials import SteelMaterial

GOLDEN_CSV_PATH: Path = Path(__file__).parent / "flexure_F2.csv"
TOL: float = 1e-9

_MATERIAL_BY_NAME: dict[str, SteelMaterial] = {"A992": A992, "A36": A36, "S355": S355}


def _load_rows() -> list[dict[str, str]]:
    with GOLDEN_CSV_PATH.open() as fp:
        return list(csv.DictReader(fp))


def _isclose(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=TOL, abs_tol=TOL)


@pytest.mark.regression
@pytest.mark.parametrize(
    "row",
    _load_rows(),
    ids=[r["case_label"] for r in _load_rows()],
)
def test_F2_golden(row: dict[str, str]) -> None:
    sec = DoublySymmetricISection(
        flange_width_bf=float(row["bf_mm"]) * u.mm,
        flange_thickness_tf=float(row["tf_mm"]) * u.mm,
        web_clear_height_hw=float(row["hw_mm"]) * u.mm,
        web_thickness_tw=float(row["tw_mm"]) * u.mm,
    )
    props = sec.compute_section_properties()
    material = _MATERIAL_BY_NAME[row["material"]]
    Lb = float(row["Lb_m"]) * u.m
    Cb = float(row["Cb"])

    r = compute_flexural_strength_F2_compact_doubly_symmetric(props, material, Lb, Cb)

    assert _isclose(r.limiting_length_plastic_Lp, float(row["Lp_mm"]))
    assert _isclose(r.limiting_length_inelastic_LTB_Lr, float(row["Lr_mm"]))
    assert _isclose(r.plastic_moment_Mp, float(row["Mp_Nmm"]))
    assert _isclose(r.elastic_LTB_moment_Mcr, float(row["Mcr_Nmm"]))
    assert r.governing_limit_state == row["regime"]
    assert _isclose(r.nominal_flexural_strength_Mn, float(row["Mn_Nmm"]))
    assert _isclose(r.phi_strength_LRFD, float(row["phi_Mn_Nmm"]))
