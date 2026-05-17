"""Regression snapshot tests for AISC §F4.

SCOPE: regression only, NOT correctness.  ``flexure_F4.csv`` is a
snapshot of apeSteel's own §F4 output (every intermediate quantity:
Mp, Myc, aw, rt, Rpc, FL, Lp, Lr, the three Mn_*_Nmm values, the final
Mn, phi*Mn, and the governing label) pinned at rel_tol = abs_tol = 1e-9.
It detects *unintended drift* in the §F4 result; it cannot prove the
§F4 math is correct, because the expected values were produced by the
same code under test.

Numerical correctness of §F4 is anchored independently by
``tests/golden/test_chapterF_independent.py``, which re-derives Mn from
AISC 360-22 with no ``apeSteel.flexure`` import and asserts bit-exact
agreement across every limit-state branch (CFY/LTB/CFLB/TFY, Rpc/Rpt
F4-9b/F4-16b, the Iyc/Iy<=0.23 switch, doubly- and singly-symmetric).

The CSV mixes doubly-symmetric (Phase 9a) and singly-symmetric (Phase 9b)
cases; the ``geometry`` column drives which constructor is used.  To
refresh the snapshot after an intentional change, regenerate
``flexure_F4.csv`` from the current apeSteel output and review the diff
together with the independent test above (which must still pass on its
own AISC re-derivation).
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest

from apeSteel import (
    A992,
    DoublySymmetricISection,
    SinglySymmetricISection,
    compute_flexural_strength_F4,
)
from apeSteel.core import units as u

if TYPE_CHECKING:
    from apeSteel.classification import SectionConstruction
    from apeSteel.core.materials import SteelMaterial
    from apeSteel.sections.geometry import CompressionFlangeSide


GOLDEN_CSV_PATH: Path = Path(__file__).parent / "flexure_F4.csv"
TOL: float = 1e-9

_MATERIAL_BY_NAME: dict[str, SteelMaterial] = {"A992": A992}


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
def test_F4_golden(row: dict[str, str]) -> None:
    material = _MATERIAL_BY_NAME[row["material"]]
    construction = cast("SectionConstruction", row["construction"])
    Lb = float(row["Lb_mm"]) * u.mm
    Cb = float(row["Cb"])

    if row["geometry"] == "DS":
        sec = DoublySymmetricISection(
            flange_width_bf=float(row["bf_mm"]) * u.mm,
            flange_thickness_tf=float(row["tf_mm"]) * u.mm,
            web_clear_height_hw=float(row["hw_mm"]) * u.mm,
            web_thickness_tw=float(row["tw_mm"]) * u.mm,
        )
        sp = sec.compute_section_properties()
    else:  # SS
        ss = SinglySymmetricISection(
            top_flange_width_bf_top=float(row["bft_mm"]) * u.mm,
            top_flange_thickness_tf_top=float(row["tft_mm"]) * u.mm,
            bot_flange_width_bf_bot=float(row["bfb_mm"]) * u.mm,
            bot_flange_thickness_tf_bot=float(row["tfb_mm"]) * u.mm,
            web_clear_height_hw=float(row["hw_mm"]) * u.mm,
            web_thickness_tw=float(row["tw_mm"]) * u.mm,
        )
        side = cast("CompressionFlangeSide", row["side"])
        sp = ss.compute_section_properties(side)

    r = compute_flexural_strength_F4(sp, material, Lb, Cb, construction)

    # Classification echoes
    assert r.flange_classification == row["flange_cls"]
    assert r.web_classification == row["web_cls"]

    # F4 intermediates
    assert _isclose(r.plastic_moment_Mp, float(row["Mp_Nmm"]))
    assert _isclose(r.yield_moment_compression_flange_Myc, float(row["Myc_Nmm"]))
    assert _isclose(r.web_to_flange_area_ratio_aw, float(row["aw"]))
    assert _isclose(r.F4_effective_radius_rt, float(row["rt_mm"]))
    assert _isclose(r.web_plastification_factor_Rpc, float(row["Rpc"]))
    assert _isclose(r.limit_compression_flange_stress_FL, float(row["FL_MPa"]))
    assert _isclose(r.limiting_length_plastic_Lp_F4, float(row["Lp_mm"]))
    assert _isclose(r.limiting_length_inelastic_LTB_Lr_F4, float(row["Lr_mm"]))

    # Three limit-state Mn values
    assert _isclose(r.nominal_CFY_moment_Mn_CFY, float(row["Mn_CFY_Nmm"]))
    assert _isclose(r.nominal_LTB_moment_Mn_LTB, float(row["Mn_LTB_Nmm"]))
    assert _isclose(r.nominal_FLB_moment_Mn_FLB, float(row["Mn_FLB_Nmm"]))

    # Final
    assert r.governing_F4_limit_state == row["governing_F4"]
    assert r.governing_limit_state == row["governing_limit_state"]
    assert _isclose(r.nominal_flexural_strength_Mn, float(row["Mn_Nmm"]))
    assert _isclose(r.phi_strength_LRFD, float(row["phi_Mn_Nmm"]))
