"""Unit tests for Bracing - a primary domain object (node in the model graph)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from apeSteel import Bracing
from apeSteel.core import units as u


def test_bracing_stores_top_bot_lengths_and_Cb() -> None:
    br = Bracing(
        unbraced_length_top_flange_Lb_top=0.5 * u.m,
        unbraced_length_bot_flange_Lb_bot=4.0 * u.m,
        lateral_torsional_buckling_modification_factor_Cb=1.5,
    )
    assert br.unbraced_length_top_flange_Lb_top == 500.0
    assert br.unbraced_length_bot_flange_Lb_bot == 4000.0
    assert br.lateral_torsional_buckling_modification_factor_Cb == 1.5


def test_bracing_default_Cb_is_1p0() -> None:
    br = Bracing(
        unbraced_length_top_flange_Lb_top=0.001 * u.m,
        unbraced_length_bot_flange_Lb_bot=2.0 * u.m,
    )
    assert br.lateral_torsional_buckling_modification_factor_Cb == 1.0


def test_bracing_is_frozen() -> None:
    br = Bracing(0.001 * u.m, 2.0 * u.m, 1.0)
    with pytest.raises(FrozenInstanceError):
        br.unbraced_length_top_flange_Lb_top = 99.0  # type: ignore[misc]


def test_bracing_equal_by_value() -> None:
    a = Bracing(0.001 * u.m, 2.0 * u.m, 1.2)
    b = Bracing(0.001 * u.m, 2.0 * u.m, 1.2)
    c = Bracing(0.001 * u.m, 2.0 * u.m, 1.0)
    assert a == b
    assert a != c
