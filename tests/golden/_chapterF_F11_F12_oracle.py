"""Independent AISC 360-22 §F11 / §F12 oracle - Phase F-7.

A deliberately *separate*, standalone re-derivation of AISC 360-22 §F11
(rectangular bars & rounds) and §F12 (unsymmetrical shapes) nominal
flexural strength.  It imports **only** the standard-library ``math``
module - nothing from ``apeSteel`` and in particular nothing from
:mod:`apeSteel.flexure` (the architecture layer rule: the oracle
imports nothing from the library it pins).

Per design note 10 §6 this oracle is the **primary, bit-exact
(`rel_tol=1e-9`) regression pin** for the §F11 / §F12 calculators, so
its correctness never rests on a snapshot of its own output.  Section
properties (``Z``, ``S``, ``d``, ``t``, the extreme-fibre moduli) are
supplied by the caller (the golden test); only the §F11 / §F12
*strength composition* is re-derived here.

Every constant is written as a literal transcribed from the printed
spec, intentionally *not* shared with the library, so a typo in either
implementation surfaces as a disagreement.

Provenance - all verbatim from
``docs/design_notes/_aisc_src_extract/spec_chapterF.txt`` printed
16.1-71 / 16.1-72 (AISC 360-22 §F11 / §F12):

* Eq. F11-1  rect bar  ``Mn = Mp = Fy*Z <= 1.5*Fy*Sx``
* Eq. F11-2  round     ``Mn = Mp = Fy*Z <= 1.6*Fy*Sx``
* §F11.2(a)  LTB N/A while ``Lb*d/t^2 <= 0.08*E/Fy``
* Eq. F11-3  ``0.08*E/Fy < Lb*d/t^2 <= 1.9*E/Fy``:
  ``Mn = Cb*(1.52 - 0.274*(Lb*d/t^2)*(Fy/E))*My <= Mp``
* Eq. F11-4  ``Lb*d/t^2 > 1.9*E/Fy``: ``Mn = Fcr*Sx <= Mp``
* Eq. F11-5  ``Fcr = 1.9*E*Cb / (Lb*d/t^2)``
* Eq. F12-1  ``Mn = Fn*Smin``
* Eq. F12-2  ``Fn = Fy``
* Eq. F12-3  ``Fn = Fcr <= Fy``   (LTB, analysis-determined)
* Eq. F12-4  ``Fn = Fcr <= Fy``   (local buckling, analysis-determined)

NOTE on the §F11-1 cap: the 360-16-based AISC Manual v15.1 Ex. F.12
prints ``1.6*Fy*Sx`` for the rectangular-bar cap; AISC **360-22**
tightened it to ``1.5*Fy*Sx`` (spec_chapterF.txt printed 16.1-71).
This oracle implements the **360-22** value, matching the library
(documented edition delta - design note 10 §1/§9).
"""

from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# AISC 360-22 §F11 / §F12 literal constants (printed 16.1-71/72).
# Duplicated here (NOT imported from apeSteel) on purpose.
# ---------------------------------------------------------------------------
#: Eq. F11-1 rectangular-bar yield cap coefficient (360-22 = 1.5).
_EQ_F11_1_RECT_CAP: float = 1.5
#: Eq. F11-2 round-bar yield cap coefficient.
_EQ_F11_2_ROUND_CAP: float = 1.6
#: §F11.2(a)/(b) lower LTB slenderness gate: 0.08 * (E/Fy).
_F11_GATE_LOWER: float = 0.08
#: §F11.2(b)/(c) upper LTB slenderness gate: 1.9 * (E/Fy).
_F11_GATE_UPPER: float = 1.9
#: Eq. F11-3 inelastic-LTB lead constant.
_EQ_F11_3_A: float = 1.52
#: Eq. F11-3 inelastic-LTB slenderness coefficient.
_EQ_F11_3_B: float = 0.274
#: Eq. F11-5 elastic-LTB critical-stress coefficient.
_EQ_F11_5_FCR: float = 1.9


@dataclass(frozen=True)
class F11OracleProps:
    """Plain-float bar section properties for the §F11 oracle.

    All values in apeSteel base units (N-mm-tonne-s): ``Fy``/``E`` in
    MPa, ``d``/``t``/``Lb`` in mm, ``Z``/``S`` in mm^3.

    ``is_round`` selects the Eq. F11-2 cap (and disables LTB);
    ``bending_axis_is_major`` is ``False`` for a rectangular bar bent
    about its minor axis (LTB never applies - §F11.2(a)).  ``Lb`` is
    ``None`` when no unbraced length is supplied (LTB skipped).
    """

    Fy: float
    E: float
    Z: float
    S: float
    d: float
    t: float
    is_round: bool
    bending_axis_is_major: bool = True
    Lb: float | None = None
    Cb: float = 1.0


@dataclass(frozen=True)
class F11OracleResult:
    """Oracle §F11 outcome."""

    Mn: float
    governing: str  # "yielding" | "inelastic_LTB" | "elastic_LTB"
    Mp: float
    My: float
    uncapped_Fy_Z: float
    cap_coeff: float
    cap_value: float
    L_d_t2: float
    gate_lower: float
    gate_upper: float
    ltb_evaluated: bool
    Fcr: float  # Eq. F11-5 stress (MPa); 0.0 unless elastic LTB


def mn_F11(p: F11OracleProps) -> F11OracleResult:
    """Independent AISC 360-22 §F11 ``Mn`` for a rectangular bar / round.

    Re-derives Eq. F11-1 / F11-2 yielding and the §F11.2 LTB regime
    split (Eq. F11-3 / F11-4 / F11-5) from the spec literals above,
    with **no** apeSteel import.
    """
    # --- §F11.1 yielding (Eq. F11-1 rect / Eq. F11-2 round) ----------
    uncapped_fy_z = p.Fy * p.Z
    cap_coeff = _EQ_F11_2_ROUND_CAP if p.is_round else _EQ_F11_1_RECT_CAP
    cap_value = cap_coeff * p.Fy * p.S
    mp = min(uncapped_fy_z, cap_value)
    my = p.Fy * p.S

    gate_lower = _F11_GATE_LOWER * (p.E / p.Fy)
    gate_upper = _F11_GATE_UPPER * (p.E / p.Fy)

    governing = "yielding"
    mn = mp
    fcr = 0.0
    l_d_t2 = 0.0
    ltb_evaluated = False

    # --- §F11.2 LTB (rectangular bar, major axis, Lb supplied) -------
    if (not p.is_round) and p.bending_axis_is_major and p.Lb is not None:
        l_d_t2 = p.Lb * p.d / p.t**2
        if l_d_t2 > gate_lower:
            ltb_evaluated = True
            if l_d_t2 <= gate_upper:
                # Eq. F11-3 - inelastic LTB.
                mn_ltb = p.Cb * (_EQ_F11_3_A - _EQ_F11_3_B * l_d_t2 * (p.Fy / p.E)) * my
                mn_ltb = min(mn_ltb, mp)
                ltb_ls = "inelastic_LTB"
            else:
                # Eq. F11-5 / F11-4 - elastic LTB.
                fcr = _EQ_F11_5_FCR * p.E * p.Cb / l_d_t2
                mn_ltb = min(fcr * p.S, mp)
                ltb_ls = "elastic_LTB"
            # §F11 lead paragraph: Mn is the LOWER of yielding & LTB.
            if mn_ltb < mn:
                governing = ltb_ls
                mn = mn_ltb

    return F11OracleResult(
        Mn=mn,
        governing=governing,
        Mp=mp,
        My=my,
        uncapped_Fy_Z=uncapped_fy_z,
        cap_coeff=cap_coeff,
        cap_value=cap_value,
        L_d_t2=l_d_t2,
        gate_lower=gate_lower,
        gate_upper=gate_upper,
        ltb_evaluated=ltb_evaluated,
        Fcr=fcr,
    )


@dataclass(frozen=True)
class F12OracleProps:
    """Plain-float section properties for the §F12 oracle.

    ``extreme_fibre_moduli`` are the elastic moduli to each extreme
    fibre / corner (mm^3); ``Smin = min(...)`` (Eq. F12-1).  The two
    buckling stresses are caller-supplied (Eq. F12-3 / F12-4 are
    "by analysis"); ``None`` means that limit state does not govern.
    """

    Fy: float
    extreme_fibre_moduli: tuple[float, ...]
    Fcr_LTB: float | None = None
    Fcr_LB: float | None = None


@dataclass(frozen=True)
class F12OracleResult:
    """Oracle §F12 outcome."""

    Mn: float
    governing: str  # "yielding" | "elastic_LTB" | "flange_local_buckling"
    Smin: float
    Fn: float
    Fcr_LTB: float  # clamped to <= Fy
    Fcr_LB: float  # clamped to <= Fy


def mn_F12(p: F12OracleProps) -> F12OracleResult:
    """Independent AISC 360-22 §F12 ``Mn`` for an unsymmetrical shape.

    Eq. F12-1 ``Mn = Fn*Smin`` with
    ``Fn = min(`` Eq. F12-2 ``Fy``, Eq. F12-3 ``Fcr_LTB <= Fy``,
    Eq. F12-4 ``Fcr_LB <= Fy`` ``)``; a ``None`` stress is treated as
    non-governing (clamped to ``Fy``).  No apeSteel import.
    """
    s_min = min(p.extreme_fibre_moduli)
    fn_yield = p.Fy
    fcr_ltb = min(p.Fcr_LTB, p.Fy) if p.Fcr_LTB is not None else p.Fy
    fcr_lb = min(p.Fcr_LB, p.Fy) if p.Fcr_LB is not None else p.Fy

    fn = min(fn_yield, fcr_ltb, fcr_lb)
    mn = fn * s_min  # Eq. F12-1

    if fn >= fn_yield:
        governing = "yielding"
    elif fn == fcr_ltb:
        governing = "elastic_LTB"
    else:
        governing = "flange_local_buckling"

    return F12OracleResult(
        Mn=mn,
        governing=governing,
        Smin=s_min,
        Fn=fn,
        Fcr_LTB=fcr_ltb,
        Fcr_LB=fcr_lb,
    )


__all__ = [
    "F11OracleProps",
    "F11OracleResult",
    "F12OracleProps",
    "F12OracleResult",
    "mn_F11",
    "mn_F12",
]
