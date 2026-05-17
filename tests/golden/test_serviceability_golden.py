"""Golden-file regression tests for serviceability deflection calculators.

The companion CSV ``serviceability.csv`` pins one row per representative
load configuration across the four cases shipped in Phase 8b:

* ``ss_udl``      - simply-supported UDL
* ``ss_pl_mid``   - simply-supported point load at mid-span
* ``ss_pl_arb``   - simply-supported point load at distance ``a``
* ``cantilever``  - cantilever UDL + tip load

Bit-for-bit comparison against ``rel_tol = abs_tol = 1e-9``.  If any
deflection formula in the codebase ever drifts, the relevant row fails
loudly.

To regenerate after an intentional change, re-run the inline generator
(see commit history) and review the diff before committing.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import TYPE_CHECKING

import baseUnits as u
import pytest

from apeSteel import A992, S355, DoublySymmetricISection
from apeSteel.serviceability import (
    compute_deflection_cantilever_udl_and_tip_load,
    compute_deflection_simply_supported_point_load_arbitrary,
    compute_deflection_simply_supported_point_load_midspan,
    compute_deflection_simply_supported_udl,
    recommend_camber_from_dead_load_deflection,
)

if TYPE_CHECKING:
    from apeSteel.core.materials import SteelMaterial

GOLDEN_CSV_PATH: Path = Path(__file__).parent / "serviceability.csv"
TOL: float = 1e-9

_MATERIAL_BY_NAME: dict[str, SteelMaterial] = {
    "ASTM A992": A992,
    "EN 10025 S355": S355,
}


def _spreadsheet_default_section() -> DoublySymmetricISection:
    """The spreadsheet's default 100x6 / 300x4 plate-built I."""
    return DoublySymmetricISection(
        flange_width_bf=100 * u.mm,
        flange_thickness_tf=6 * u.mm,
        web_clear_height_hw=300 * u.mm,
        web_thickness_tw=4 * u.mm,
    )


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
def test_serviceability_golden(row: dict[str, str]) -> None:
    sp = _spreadsheet_default_section().compute_section_properties()
    material = _MATERIAL_BY_NAME[row["material_name"]]
    L = float(row["span_or_length_L_mm"])

    if row["case_kind"] == "ss_udl":
        r = compute_deflection_simply_supported_udl(
            section_properties=sp,
            material=material,
            span_length_L=L,
            distributed_load_dead_w_dead=float(row["w_dead_N_per_mm"]),
            distributed_load_superdead_w_sd=float(row["w_sd_N_per_mm"]),
            distributed_load_live_w_live=float(row["w_live_N_per_mm"]),
        )
        assert _isclose(r.deflection_under_live_load_delta_live, float(row["delta_live_mm"]))
        assert _isclose(r.deflection_under_total_load_delta_total, float(row["delta_total_mm"]))
        assert _isclose(r.deflection_under_dead_load_delta_dead, float(row["delta_dead_mm"]))
        assert _isclose(r.deflection_limit_live, float(row["limit_live_mm"]))
        assert _isclose(r.deflection_limit_total, float(row["limit_total_mm"]))
        assert int(r.is_live_load_deflection_acceptable) == int(row["is_live_ok"])
        assert int(r.is_total_load_deflection_acceptable) == int(row["is_total_ok"])
        assert r.governing_limit_state == row["governing_limit_state"]
        # Camber: 0.8 * delta_dead.
        camber = recommend_camber_from_dead_load_deflection(r.deflection_under_dead_load_delta_dead)
        assert _isclose(camber, float(row["camber_mm"]))

    elif row["case_kind"] == "ss_pl_mid":
        r = compute_deflection_simply_supported_point_load_midspan(
            section_properties=sp,
            material=material,
            span_length_L=L,
            point_load_dead_P_dead=float(row["P_dead_N"]),
            point_load_live_P_live=float(row["P_live_N"]),
        )
        assert _isclose(r.deflection_under_live_load_delta_live, float(row["delta_live_mm"]))
        assert _isclose(r.deflection_under_total_load_delta_total, float(row["delta_total_mm"]))
        assert _isclose(r.deflection_under_dead_load_delta_dead, float(row["delta_dead_mm"]))
        assert int(r.is_live_load_deflection_acceptable) == int(row["is_live_ok"])
        assert int(r.is_total_load_deflection_acceptable) == int(row["is_total_ok"])
        assert r.governing_limit_state == row["governing_limit_state"]

    elif row["case_kind"] == "ss_pl_arb":
        r = compute_deflection_simply_supported_point_load_arbitrary(
            section_properties=sp,
            material=material,
            span_length_L=L,
            distance_from_left_support_a=float(row["distance_a_mm"]),
            point_load_total_P_total=float(row["P_total_N"]),
        )
        assert _isclose(r.deflection_at_midspan_delta_midspan, float(row["delta_midspan_mm"]))
        assert _isclose(r.deflection_maximum_delta_max, float(row["delta_max_mm"]))
        assert _isclose(r.location_of_max_from_left_support_x_max, float(row["x_max_mm"]))
        assert _isclose(r.deflection_limit_total, float(row["limit_total_mm"]))
        assert int(r.is_max_deflection_acceptable) == int(row["is_max_ok"])
        assert r.governing_limit_state == row["governing_limit_state"]

    elif row["case_kind"] == "cantilever":
        r = compute_deflection_cantilever_udl_and_tip_load(
            section_properties=sp,
            material=material,
            cantilever_length_L=L,
            distributed_load_w=float(row["w_live_N_per_mm"]),
            tip_point_load_P=float(row["P_total_N"]),
        )
        assert _isclose(r.deflection_from_udl_delta_udl, float(row["delta_from_udl_mm"]))
        assert _isclose(
            r.deflection_from_tip_load_delta_tip_load, float(row["delta_from_tip_load_mm"])
        )
        assert _isclose(r.deflection_at_tip_delta_tip, float(row["delta_tip_mm"]))
        assert _isclose(r.deflection_limit, float(row["limit_tip_mm"]))
        assert int(r.is_tip_deflection_acceptable) == int(row["is_tip_ok"])
        assert r.governing_limit_state == row["governing_limit_state"]

    else:
        raise AssertionError(f"Unknown case_kind: {row['case_kind']!r}")
