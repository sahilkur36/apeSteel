"""Independent AISC 360-22 §F10 (single angles) oracle - Phase F-6.

A deliberately *separate*, standalone re-derivation of AISC 360-22 §F10
nominal flexural strength.  It imports **only** the standard-library
``math`` module - nothing from ``apeSteel`` and in particular nothing
from :mod:`apeSteel.flexure` (the architecture layer rule: the oracle
imports nothing from the library it pins).

Per design note 10 §6 this oracle is the **primary, bit-exact
(`rel_tol=1e-9`) regression pin** for the §F10 calculator, so its
correctness never rests on a snapshot of its own output.  Section
properties are supplied by the caller (the golden test); only the §F10
*strength composition* (Eq. F10-1 / F10-2 / F10-3 / F10-4 / F10-5a /
F10-5b / F10-6 / F10-7 / F10-8 + the §F10.3 leg ``b/t`` regime split)
is re-derived here.

Every constant is written as a literal transcribed from the printed
spec / curated reference, intentionally *not* shared with the library,
so a typo in either implementation surfaces as a disagreement.

Provenance (mirrors ``F10_single_angle.py`` [1]/[2]):

* Eq. F10-6/F10-7/F10-8 - CONFIRMED verbatim from
  ``spec_chapterF.txt`` printed 16.1-70 (reproduce AISC Manual v15.1
  Ex. F.11A = 43.3 kip-in, Ex. F.11C = 45.0 / 92.5 kip-in).
* Eq. F10-1/F10-2/F10-3/F10-4 - printed 16.1-69 absent from
  ``spec_chapterF.txt`` (ENGINEER-CONFIRM EC-9); curated forms,
  F10-1/F10-2/F10-4 numerically Manual-CONFIRMED.
* Eq. F10-5a/F10-5b - **ENGINEER-CONFIRM F10-EC-1 RESOLVED**: the
  authoritative ``Me = 0.58*E*b^4*t*Cb/Lb^2 *
  [sqrt(1+0.88*(Lb*t/b^2)^2) -/+ 1]`` form is CONFIRMED verbatim from
  ``docs/design_notes/_aisc_src_extract/spec_F10_geometric.txt``
  (printed 16.1-69/70) and reproduces AISC Manual v15.1 Ex. F.11A
  (107 kip-in) / Ex. F.11B (176 kip-in) to the printed 3 sig figs.
  Re-derived here independently (literals NOT shared with the
  library).

References
----------
AISC 360-22, Specification for Structural Steel Buildings, §F10
"Single Angles", Eq. F10-1 - F10-8, pp. 16.1-69 - 16.1-70.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# AISC 360-22 §F10 literal constants.  Duplicated here (NOT imported from
# apeSteel) on purpose.
# ---------------------------------------------------------------------------
#: Eq. F10-1 yielding plateau: Mn = 1.5*My.
_EQ_F10_1_YIELD_FACTOR: float = 1.5

#: Eq. F10-2: Mn = (1.92 - 1.17*sqrt(My/Me))*My <= 1.5*My.
_EQ_F10_2_A: float = 1.92
_EQ_F10_2_B: float = 1.17

#: Eq. F10-3: Mn = (0.92 - 0.17*Me/My)*Me.
_EQ_F10_3_A: float = 0.92
_EQ_F10_3_B: float = 0.17

#: Eq. F10-2/F10-3 regime split (F10-2 if My/Me <= 1.0 else F10-3).
_EQ_F10_2_3_REGIME_LIMIT: float = 1.0

#: Eq. F10-4 (equal-leg, major principal axis): beta_w = 0 ->
#: Me = 9*E*A*rz*t*Cb/(8*Lb).
_EQ_F10_4_NUM_COEFF: float = 9.0
_EQ_F10_4_DEN_COEFF: float = 8.0
_EQ_F10_4_BETA_W_COEFF: float = 4.4

#: Eq. F10-5a/F10-5b (geometric axis, equal-leg, no axial compression):
#: Me = 0.58*E*b^4*t*Cb/Lb^2 * [sqrt(1+0.88*(Lb*t/b^2)^2) -/+ 1]
#: (-1 = F10-5a compression-toe; +1 = F10-5b tension-toe).  F10-EC-1
#: RESOLVED - CONFIRMED verbatim from spec_F10_geometric.txt; the
#: literals are re-declared here (NOT imported from apeSteel) so a typo
#: in either implementation surfaces as a tier-1 disagreement.
_EQ_F10_5_NUM_COEFF: float = 0.58
_EQ_F10_5_BRACKET_COEFF: float = 0.88

#: §F10.2(b)(ii): with LT restraint at the max-moment point only, Mcr
#: is 1.25x the F10-5a/5b value (spec_F10_geometric.txt L285-287).
_F10_2B_II_RESTRAINT_FACTOR: float = 1.25

#: §F10.2 geometric-axis (no LT restraint) yield-moment / Sc reduction.
_F10_GEOMETRIC_YIELD_FACTOR: float = 0.80

#: §F10.3 leg b/t breakpoints (the F-0 classifier's curated coeffs;
#: re-declared here, NOT imported, so a typo disagrees).
_F10_3_LEG_COMPACT_COEFF: float = 0.54
_F10_3_LEG_NONCOMPACT_COEFF: float = 0.91

#: Eq. F10-6: Mn = Fy*Sc*(2.43 - 1.72*(b/t)*sqrt(Fy/E)).
_EQ_F10_6_A: float = 2.43
_EQ_F10_6_B: float = 1.72

#: Eq. F10-8: Fcr = 0.71*E/(b/t)^2.
_EQ_F10_8_FCR_COEFF: float = 0.71


@dataclass(frozen=True)
class F10OracleProps:
    """Plain-float single-angle §F10 inputs.

    All values in apeSteel base units (N-mm-tonne-s): ``Fy``/``E`` in
    MPa, ``b``/``t``/``rz``/``Lb`` in mm, ``Ag`` in mm^2, ``S`` in mm^3.

    ``bending_mode`` is ``"principal_major"`` / ``"principal_minor"`` /
    ``"geometric"``; ``toe_state`` is ``"compression_at_toe"`` /
    ``"tension_at_toe"``; ``S`` is the (unreduced) section modulus to
    the fibre of interest (the §F10 0.80 geometric reduction is applied
    inside :func:`mn_F10`).
    """

    Fy: float
    E: float
    b: float  # leg width (mm)
    t: float  # leg thickness (mm)
    Ag: float  # gross area (mm^2)
    rz: float  # minimum (minor principal) radius of gyration (mm)
    S: float  # elastic section modulus to the fibre of interest (mm^3)
    Lb: float  # laterally-unbraced length (mm)
    Cb: float
    bending_mode: str
    toe_state: str
    lt_restraint_at_max_moment: bool


@dataclass(frozen=True)
class F10OracleResult:
    """Oracle §F10 outcome (all moments N*mm; stresses MPa)."""

    Mn: float
    governing: str  # "yielding" | "lateral_torsional_buckling" | "leg_local_buckling"
    My_yield: float  # §F10.1 basis: Fy*S (full); F10-1 uses this
    My: float  # §F10.2 LTB basis: 0.80*Fy*Sx (geom no restraint) else Fy*S
    Mn_F10_1: float
    Me: float
    Mn_LTB: float
    b_t: float
    lambda_p: float
    lambda_r: float
    leg_classification: str  # "compact" | "non_compact" | "slender"
    Sc: float
    Fcr: float  # Eq. F10-8 (MPa); 0.0 unless slender leg + leg LB applies
    Mn_leg_LB: float


def _me_principal_major(p: F10OracleProps) -> float:
    """Eq. F10-4, equal-leg, major principal axis (beta_w = 0)."""
    beta_w = 0.0
    arg = beta_w * p.rz / (p.Lb * p.t)
    bracket = math.sqrt(1.0 + _EQ_F10_4_BETA_W_COEFF * arg**2) + _EQ_F10_4_BETA_W_COEFF * arg
    return (
        _EQ_F10_4_NUM_COEFF
        * p.E
        * p.Ag
        * p.rz
        * p.t
        * p.Cb
        / (_EQ_F10_4_DEN_COEFF * p.Lb)
        * bracket
    )


def _me_geometric(p: F10OracleProps) -> float:
    """Eq. F10-5a / F10-5b geometric-axis ``Me`` (equal-leg).

    F10-EC-1 RESOLVED.  Independent re-derivation of AISC 360-22
    §F10.2(b) (CONFIRMED verbatim from
    ``docs/design_notes/_aisc_src_extract/spec_F10_geometric.txt``)::

        Me = 0.58*E*b^4*t*Cb/Lb^2 * [sqrt(1+0.88*(Lb*t/b^2)^2) -/+ 1]

    ``- 1`` -> Eq. F10-5a (max **compression** at the toe); ``+ 1`` ->
    Eq. F10-5b (max **tension** at the toe).  Per §F10.2(b)(ii) ``Mcr``
    is ``1.25`` times this value when there is lateral-torsional
    restraint at the point of maximum moment only.  Reproduces AISC
    Manual v15.1 Ex. F.11A ``Mcr = 107 kip-in`` / Ex. F.11B
    ``Mcr = 176 kip-in``.  Written from the spec literals above,
    independent of the library (a typo disagrees at tier-1).
    """
    arg = p.Lb * p.t / p.b**2
    sign = -1.0 if p.toe_state == "compression_at_toe" else 1.0
    me = (
        _EQ_F10_5_NUM_COEFF
        * p.E
        * p.b**4
        * p.t
        * p.Cb
        / p.Lb**2
        * (math.sqrt(1.0 + _EQ_F10_5_BRACKET_COEFF * arg**2) + sign)
    )
    if p.lt_restraint_at_max_moment:
        me *= _F10_2B_II_RESTRAINT_FACTOR
    return me


def _mn_ltb(my: float, me: float) -> float:
    """Eq. F10-2 (My/Me<=1.0, capped 1.5*My) / Eq. F10-3 otherwise."""
    r_my_me = my / me
    if r_my_me <= _EQ_F10_2_3_REGIME_LIMIT:
        mn = (_EQ_F10_2_A - _EQ_F10_2_B * math.sqrt(r_my_me)) * my
        return min(mn, _EQ_F10_1_YIELD_FACTOR * my)
    r_me_my = me / my
    return (_EQ_F10_3_A - _EQ_F10_3_B * r_me_my) * me


def mn_F10(p: F10OracleProps) -> F10OracleResult:
    """Independent AISC 360-22 §F10 ``Mn`` for a single angle.

    Re-derives the three §F10 limit states (yielding Eq. F10-1; LTB
    Eq. F10-2/F10-3 via ``Me`` Eq. F10-4 / F10-5a / F10-5b; leg local
    buckling Eq. F10-6/F10-7/F10-8) and the §F10.3 ``b/t`` regime split
    from the spec literals above, with **no** apeSteel import.  The
    minor principal axis has no LTB limit state (§F10 User Note).
    """
    s_e_fy = math.sqrt(p.E / p.Fy)
    b_t = p.b / p.t
    lambda_p = _F10_3_LEG_COMPACT_COEFF * s_e_fy
    lambda_r = _F10_3_LEG_NONCOMPACT_COEFF * s_e_fy
    if b_t <= lambda_p:
        leg_classification = "compact"
    elif b_t <= lambda_r:
        leg_classification = "non_compact"
    else:
        leg_classification = "slender"

    geometric_no_restraint = p.bending_mode == "geometric" and not p.lt_restraint_at_max_moment
    # §F10.1 yielding always uses the full Fy*S; §F10.2 LTB uses the
    # 0.80-reduced value only for geometric-axis / no-LT-restraint
    # (AISC Manual v15.1 Ex. F.11A: F10-1 = "1.5 Fy Sx", LTB My =
    # "0.80 Fy Sx" - two distinct My).
    my_yield = p.Fy * p.S
    my = _F10_GEOMETRIC_YIELD_FACTOR * p.Fy * p.S if geometric_no_restraint else p.Fy * p.S

    # Eq. F10-1 yielding (full Fy*S basis).
    mn_f10_1 = _EQ_F10_1_YIELD_FACTOR * my_yield

    # Eq. F10-2/F10-3 LTB (none for the minor principal axis); LTB
    # basis ``my``.
    me = 0.0
    mn_ltb_val = 0.0
    if p.bending_mode == "principal_major":
        me = _me_principal_major(p)
        mn_ltb_val = _mn_ltb(my, me)
    elif p.bending_mode == "geometric":
        # F10-EC-1 RESOLVED: geometric-axis Me via Eq. F10-5a (toe in
        # compression) / F10-5b (toe in tension), with the §F10.2(b)(ii)
        # 1.25 factor folded in by the helper.  ``my`` already carries
        # the matching basis (0.80*Fy*S with no restraint, full Fy*S
        # with restraint at the max-moment point).
        me = _me_geometric(p)
        mn_ltb_val = _mn_ltb(my, me)

    # §F10.3 leg local buckling - only when the toe is in compression.
    sc = 0.0
    fcr = 0.0
    mn_leg_lb = 0.0
    leg_lb_applies = p.toe_state == "compression_at_toe"
    if leg_lb_applies and leg_classification != "compact":
        sc = _F10_GEOMETRIC_YIELD_FACTOR * p.S if geometric_no_restraint else p.S
        if leg_classification == "non_compact":
            mn_leg_lb = p.Fy * sc * (_EQ_F10_6_A - _EQ_F10_6_B * b_t * math.sqrt(p.Fy / p.E))
        else:
            fcr = _EQ_F10_8_FCR_COEFF * p.E / b_t**2
            mn_leg_lb = fcr * sc

    candidates: list[tuple[str, float]] = [("yielding", mn_f10_1)]
    if p.bending_mode != "principal_minor":
        candidates.append(("lateral_torsional_buckling", mn_ltb_val))
    if mn_leg_lb > 0.0:
        candidates.append(("leg_local_buckling", mn_leg_lb))
    governing, mn = min(candidates, key=lambda kv: kv[1])

    return F10OracleResult(
        Mn=mn,
        governing=governing,
        My_yield=my_yield,
        My=my,
        Mn_F10_1=mn_f10_1,
        Me=me,
        Mn_LTB=mn_ltb_val,
        b_t=b_t,
        lambda_p=lambda_p,
        lambda_r=lambda_r,
        leg_classification=leg_classification,
        Sc=sc,
        Fcr=fcr,
        Mn_leg_LB=mn_leg_lb,
    )


__all__ = ["F10OracleProps", "F10OracleResult", "mn_F10"]
