"""Golden-file regression tests for the three classifiers.

The companion CSV `classification.csv` pins the exact float values of
lambda, lambda_p, lambda_r, and the classification labels for every
(section, material, construction, edition, ductility) combination we
care about. 180 rows total at the time of writing - spans 5 sections,
3 materials, 2 constructions, 3 code editions, 2 ductility levels.

SCOPE: regression only, NOT correctness.  ``classification.csv`` is a
snapshot of apeSteel's own classifier output; it detects *unintended
drift* but cannot prove the limits are correct, since the expected
values came from the code under test.  Correctness of every B4.1b /
B4.1a / 341-D1 lambda_p / lambda_r coefficient is anchored independently
by the hand-derived assertions in ``tests/unit/test_flexural_compactness_B4_1b.py``,
``tests/unit/test_axial_compression_B4_1a.py`` and
``tests/unit/test_seismic_compactness_341_D1.py``.

The CSV is committed so changes are diffable.  To refresh after an
intentional formula change, regenerate the CSV from the current output
and review the diff (the independent unit tests must still pass).
"""

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
    classify_axial_compression_B4_1a,
    classify_flexural_compactness_B4_1b,
    classify_seismic_compactness_341_D1,
)
from apeSteel.core import units as u

if TYPE_CHECKING:
    from apeSteel import SteelMaterial
    from apeSteel.classification import (
        DuctilityLevel,
        SectionConstruction,
        SeismicCodeEdition,
    )


GOLDEN_CSV_PATH: Path = Path(__file__).parent / "classification.csv"
TOL_REL: float = 1e-9
TOL_ABS: float = 1e-9

_MATERIAL_BY_NAME: dict[str, SteelMaterial] = {
    "A992": A992,
    "A36": A36,
    "S355": S355,
}


def _load_rows() -> list[dict[str, str]]:
    with GOLDEN_CSV_PATH.open() as fp:
        return list(csv.DictReader(fp))


def _isclose(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=TOL_REL, abs_tol=TOL_ABS)


def _parse_optional_float(value: str) -> float | None:
    if value in {"None", ""}:
        return None
    return float(value)


@pytest.mark.regression
@pytest.mark.parametrize(
    "row",
    _load_rows(),
    ids=[r["case_label"] for r in _load_rows()],
)
def test_classification_golden(row: dict[str, str]) -> None:
    section = DoublySymmetricISection(
        flange_width_bf=float(row["bf_mm"]) * u.mm,
        flange_thickness_tf=float(row["tf_mm"]) * u.mm,
        web_clear_height_hw=float(row["hw_mm"]) * u.mm,
        web_thickness_tw=float(row["tw_mm"]) * u.mm,
    )
    props = section.compute_section_properties()
    material = _MATERIAL_BY_NAME[row["material"]]
    construction = cast("SectionConstruction", row["construction"])
    edition = cast("SeismicCodeEdition", row["edition"])
    ductility = cast("DuctilityLevel", row["ductility"])
    Ca = float(row["Ca"])

    # --- Flexural B4.1b ---
    flex = classify_flexural_compactness_B4_1b(props, material, construction)
    assert _isclose(flex.flange.slenderness_ratio_lambda, float(row["flex_flange_lambda"]))
    p_expected = _parse_optional_float(row["flex_flange_lambda_p"])
    assert p_expected is not None
    assert flex.flange.compact_limit_lambda_p is not None
    assert _isclose(flex.flange.compact_limit_lambda_p, p_expected)
    assert _isclose(flex.flange.noncompact_limit_lambda_r, float(row["flex_flange_lambda_r"]))
    assert flex.flange.classification == row["flex_flange_class"]
    assert _isclose(flex.web.slenderness_ratio_lambda, float(row["flex_web_lambda"]))
    p_expected = _parse_optional_float(row["flex_web_lambda_p"])
    assert p_expected is not None
    assert flex.web.compact_limit_lambda_p is not None
    assert _isclose(flex.web.compact_limit_lambda_p, p_expected)
    assert _isclose(flex.web.noncompact_limit_lambda_r, float(row["flex_web_lambda_r"]))
    assert flex.web.classification == row["flex_web_class"]
    assert flex.section_classification == row["flex_section_class"]

    # --- Axial B4.1a ---
    axial = classify_axial_compression_B4_1a(props, material, construction)
    assert _isclose(axial.flange.slenderness_ratio_lambda, float(row["axial_flange_lambda"]))
    assert _isclose(axial.flange.noncompact_limit_lambda_r, float(row["axial_flange_lambda_r"]))
    assert axial.flange.classification == row["axial_flange_class"]
    assert _isclose(axial.web.slenderness_ratio_lambda, float(row["axial_web_lambda"]))
    assert _isclose(axial.web.noncompact_limit_lambda_r, float(row["axial_web_lambda_r"]))
    assert axial.web.classification == row["axial_web_class"]
    assert str(axial.section_has_slender_element) == row["axial_section_has_slender_element"]

    # --- Seismic 341 D1 ---
    seismic = classify_seismic_compactness_341_D1(
        props,
        material,
        ductility,
        axial_demand_ratio_Ca=Ca,
        code_edition=edition,
    )
    assert _isclose(seismic.flange.slenderness_ratio_lambda, float(row["seismic_flange_lambda"]))
    assert _isclose(
        seismic.flange.noncompact_limit_lambda_r, float(row["seismic_flange_lambda_seismic"])
    )
    assert seismic.flange.classification == row["seismic_flange_class"]
    assert _isclose(seismic.web.slenderness_ratio_lambda, float(row["seismic_web_lambda"]))
    assert _isclose(seismic.web.noncompact_limit_lambda_r, float(row["seismic_web_lambda_seismic"]))
    assert seismic.web.classification == row["seismic_web_class"]
    assert str(seismic.is_seismically_compact_section) == row["is_seismically_compact"]
