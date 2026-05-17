"""Golden-file regression tests for the three Phase 8c companion checks.

* Panel-zone shear (AISC 360 §J10.6 / AISC 341 §E3.6e)
* Doubler-plate sizing (AISC 341 §E3.6e(2))
* Continuity-plate need (AISC 358 §2.4.4)

The companion CSV ``panel_zone_companions.csv`` pins six joint
configurations spanning all four panel-zone equations (J10-9 -
J10-12), one-sided and two-sided beam attachments, two material
combinations (A992 and S355), and both catalog and plate-built beams
and columns.
"""

from __future__ import annotations

import ast
import csv
import math
from pathlib import Path
from typing import TYPE_CHECKING

import baseUnits as u
import pytest

from apeSteel import (
    A36,
    A992,
    S355,
    AISCv16Catalog,
    DoublySymmetricISection,
    check_continuity_plates_required_358,
    check_panel_zone_shear_341,
    recommend_doubler_plate_thickness_341,
)

if TYPE_CHECKING:
    from apeSteel.core.materials import SteelMaterial
    from apeSteel.sections.properties import SectionProperties

GOLDEN_CSV_PATH: Path = Path(__file__).parent / "panel_zone_companions.csv"
TOL: float = 1e-9

_MATERIAL_BY_NAME: dict[str, SteelMaterial] = {
    "ASTM A992": A992,
    "ASTM A36": A36,
    "EN 10025 S355": S355,
}


def _isclose(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=TOL, abs_tol=TOL)


def _load_rows() -> list[dict[str, str]]:
    with GOLDEN_CSV_PATH.open() as fp:
        return list(csv.DictReader(fp))


def _section_props(kind: str, value_repr: str) -> SectionProperties:
    if kind == "catalog":
        return AISCv16Catalog().get_section_properties(value_repr)
    if kind == "plate":
        bf, tf, hw, tw = ast.literal_eval(value_repr)
        section = DoublySymmetricISection(
            flange_width_bf=float(bf) * u.mm,
            flange_thickness_tf=float(tf) * u.mm,
            web_clear_height_hw=float(hw) * u.mm,
            web_thickness_tw=float(tw) * u.mm,
        )
        return section.compute_section_properties()
    raise AssertionError(f"Unknown section kind: {kind!r}")


@pytest.mark.regression
@pytest.mark.parametrize(
    "row",
    _load_rows(),
    ids=[r["case_label"] for r in _load_rows()],
)
def test_panel_zone_companions_golden(row: dict[str, str]) -> None:
    beam_props = _section_props(row["beam_kind"], row["beam_value"])
    col_props = _section_props(row["column_kind"], row["column_value"])
    beam_mat = _MATERIAL_BY_NAME[row["beam_material_name"]]
    col_mat = _MATERIAL_BY_NAME[row["column_material_name"]]
    Pr_over_Pc: float = float(row["Pr_over_Pc"])
    consider_deform: bool = bool(int(row["consider_deform"]))
    n_sides: int = int(row["n_sides"])
    Pc: float = col_mat.yield_stress_Fy * col_props.gross_area_Ag
    Pr: float = Pr_over_Pc * Pc

    pz = check_panel_zone_shear_341(
        beam_props,
        beam_mat,
        col_props,
        col_mat,
        column_axial_demand_Pr=Pr,
        consider_panel_zone_deformation_in_frame_stability=consider_deform,
        number_of_beam_sides=n_sides,
    )
    dp = recommend_doubler_plate_thickness_341(
        beam_props,
        beam_mat,
        col_props,
        col_mat,
        column_axial_demand_Pr=Pr,
        consider_panel_zone_deformation_in_frame_stability=consider_deform,
        number_of_beam_sides=n_sides,
    )
    cp = check_continuity_plates_required_358(
        beam_props,
        beam_mat,
        col_props,
        col_mat,
        number_of_beam_sides=n_sides,
    )

    # Panel-zone shear
    assert _isclose(pz.panel_zone_shear_demand_Vu_pz, float(row["Vu_pz_N"]))
    assert _isclose(pz.panel_zone_shear_capacity_Rn, float(row["Rn_pz_N"]))
    assert _isclose(pz.phi_panel_zone_shear_capacity_phi_Rn_LRFD, float(row["phi_Rn_pz_N"]))
    assert pz.governing_equation == row["pz_governing_equation"]
    assert _isclose(pz.demand_to_capacity_ratio, float(row["pz_DCR"]))
    assert _isclose(pz.probable_strain_hardening_factor_Cpr, float(row["Cpr"]))
    assert _isclose(pz.probable_beam_plastic_moment_Mpr, float(row["Mpr_Nmm"]))

    # Doubler-plate
    assert int(dp.is_doubler_plate_required) == int(row["doubler_required"])
    assert _isclose(dp.minimum_doubler_thickness_for_shear_t_dp_shear, float(row["t_dp_shear_mm"]))
    assert _isclose(
        dp.minimum_doubler_thickness_for_local_buckling_t_dp_local,
        float(row["t_dp_local_mm"]),
    )
    assert _isclose(dp.minimum_doubler_thickness_required_t_dp_min, float(row["t_dp_min_mm"]))
    assert _isclose(
        dp.recommended_doubler_thickness_t_dp_recommended,
        float(row["t_dp_recommended_mm"]),
    )

    # Continuity-plate
    assert int(cp.is_required) == int(row["continuity_required"])
    assert _isclose(
        cp.minimum_column_flange_thickness_for_no_continuity,
        float(row["tcf_min_for_no_cp_mm"]),
    )
    assert _isclose(cp.minimum_continuity_plate_thickness_t_cp_min, float(row["t_cp_min_mm"]))
    assert _isclose(cp.minimum_continuity_plate_width_b_cp_min, float(row["b_cp_min_mm"]))
