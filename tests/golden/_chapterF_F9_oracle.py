"""Independent AISC 360-22 §F9 (tees & double angles) oracle - Phase F-5.

This is a deliberately *separate*, standalone re-derivation of AISC
360-22 §F9 nominal flexural strength.  It imports **only** the
standard-library ``math`` module - nothing from ``apeSteel`` and in
particular nothing from :mod:`apeSteel.flexure`.

It is kept distinct from the shared
:mod:`tests.golden._chapterF_full_aisc_oracle` on purpose: that shared
scaffold has a Phase-F-5 ``mn_F9`` *stub*; per the F-5 contract that
stub is **left untouched** here to avoid a cross-phase merge seam, and
§F9 is re-derived in this self-contained module instead.  (Note for the
orchestrator: ``_chapterF_full_aisc_oracle.mn_F9`` remains the
unmodified F-0 stub; wiring it is out of F-5 scope.)

Per design note 10 §6 this oracle is the **primary, bit-exact
(`rel_tol=1e-9`) regression pin** for the §F9 calculator, so its
correctness never rests on a snapshot of its own output.  Section
properties (``Zx``, ``Sx``, ``Sxc``, ``d``, ``Iy``, ``J``, ``ry``) and
the flange / stem slenderness ratios are supplied by the caller (the
golden test); only the §F9 *strength composition* (Eq. F9-1 .. F9-19 +
the §F10.3 double-angle leg-LB delegation + the regime splits) is
re-derived here.

Every constant is written as a literal transcribed from the printed
spec, intentionally *not* shared with the library, so a typo in either
implementation surfaces as a disagreement.

References
----------
AISC 360-22, Specification for Structural Steel Buildings, §F9 "Tees
and Double Angles Loaded in the Plane of Symmetry", pp. 16.1-65 ..
16.1-68 (transcribed from
``docs/design_notes/_aisc_src_extract/spec_chapterF.txt``):

* §F9.1 Yielding ``Mn = Mp`` (Eq. F9-1):

  - (a) tee stems / web legs in tension: ``Mp = Fy Zx <= 1.6 My``
    (Eq. F9-2), ``My = Fy Sx`` (Eq. F9-3);
  - (b) tee stems in compression: ``Mp = My`` (Eq. F9-4);
  - (c) double angles, web legs in compression: ``Mp = 1.5 My``
    (Eq. F9-5).

* §F9.2 LTB:

  - (a) stems/web legs in tension: ``Lb<=Lp`` -> N/A; ``Lp<Lb<=Lr`` ->
    Eq. F9-6 ``Mn = Mp - (Mp - My)(Lb-Lp)/(Lr-Lp) <= Mp``;
    ``Lb>Lr`` -> ``Mn = Mcr`` (Eq. F9-7).
  - ``Lp = 1.76 ry sqrt(E/Fy)`` (Eq. F9-8);
  - ``Lr = 1.95 (E/Fy) sqrt(Iy J)/Sx sqrt(2.36 (Fy/E)(d Sx/J)+1)``
    (Eq. F9-9);
  - ``Mcr = (1.95 E/Lb) sqrt(Iy J)(B + sqrt(1+B^2))`` (Eq. F9-10);
  - ``B = +2.3 (d/Lb) sqrt(Iy/J)`` (Eq. F9-11, stems/web legs in
    tension) / ``B = -2.3 (d/Lb) sqrt(Iy/J)`` (Eq. F9-12, in
    compression);
  - (b) stems/web legs in compression: tee stems ``Mn = Mcr <= My``
    (Eq. F9-13); double-angle web legs §F9.2(b)(2) (F9-EC-1
    **RESOLVED**) -> ``Mn`` via Eq. F10-2/F10-3 with ``Mcr`` (F9-10)
    as the §F10 ``Me`` and ``My`` (F9-3, ``Fy Sx``).  Eq. F10-2/F10-3
    are re-derived here from the spec literals (NOT imported from
    apeSteel) so a typo disagrees at tier-1.

* §F9.3 Flange local buckling:

  - (a) tee flanges: compact -> N/A; noncompact -> Eq. F9-14
    ``Mn = Mp - (Mp - 0.7 Fy Sxc)(l-lpf)/(lrf-lpf) <= 1.6 My``;
    slender -> Eq. F9-15 ``Mn = 0.7 E Sxc / (bf/2tf)^2``;
  - (b) double-angle flange legs -> §F10.3 with ``Sc = Sxc``.

* §F9.4 Local buckling of tee stems / 2L web legs in flexural
  compression:

  - (a) tee stems ``Mn = Fcr Sx`` (Eq. F9-16); ``Fcr = Fy``
    (Eq. F9-17, ``d/tw <= 0.84 sqrt(E/Fy)``);
    ``Fcr = (1.43 - 0.515 (d/tw) sqrt(Fy/E)) Fy`` (Eq. F9-18,
    ``0.84 sqrt(E/Fy) < d/tw <= 1.52 sqrt(E/Fy)``);
    ``Fcr = 1.52 E / (d/tw)^2`` (Eq. F9-19, ``d/tw > 1.52 sqrt(E/Fy)``);
  - (b) double-angle web legs -> §F10.3 with ``Sc = Sx``.

§F10.3 leg local buckling (referenced by §F9.3(b)/§F9.4(b);
spec_chapterF.txt printed 16.1-70): compact -> N/A; noncompact
Eq. F10-6 ``Mn = Fy Sc (2.43 - 1.72 (b/t) sqrt(Fy/E))``; slender
Eq. F10-7 ``Mn = Fcr Sc``, Eq. F10-8 ``Fcr = 0.71 E / (b/t)^2``.

Table B4.1b Case 10 tee flange (rolled I-flange rule, §F9.3):
``lambda_pf = 0.38 sqrt(E/Fy)``, ``lambda_rf = 1.0 sqrt(E/Fy)``.
§F9.4 tee-stem breakpoints: ``0.84`` / ``1.52`` ``sqrt(E/Fy)``.
§F10.3 double-angle-leg breakpoints: ``0.54`` / ``0.91`` ``sqrt(E/Fy)``
(curated, oracle-re-derived; classifier ENGINEER-CONFIRM EC-4/EC-10).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# AISC 360-22 §F9 / §F10.3 / Table B4.1b literal constants (printed
# 16.1-65..70).  Duplicated here (NOT imported from apeSteel) on purpose.
# ---------------------------------------------------------------------------
#: Eq. F9-2 yielding cap multiplier (stems/web legs in tension); also the
#: Eq. F9-14 upper bound: Mp = Fy Zx <= 1.6 My.
_EQ_F9_2_MY_CAP: float = 1.6
#: Eq. F9-5 double-angle (web legs in compression): Mp = 1.5 My.
_EQ_F9_5_MY_FACTOR: float = 1.5
#: Eq. F9-8: Lp = 1.76 ry sqrt(E/Fy).
_EQ_F9_8_LP_COEFF: float = 1.76
#: Eq. F9-9 leading coefficient.
_EQ_F9_9_LR_COEFF: float = 1.95
#: Eq. F9-9 inner coefficient (2.36 under the radical).
_EQ_F9_9_INNER_COEFF: float = 2.36
#: Eq. F9-10 leading coefficient.
_EQ_F9_10_MCR_COEFF: float = 1.95
#: Eq. F9-11 / F9-12 LTB-constant magnitude: B = +/- 2.3 (d/Lb) sqrt(Iy/J).
_EQ_F9_11_B_COEFF: float = 2.3
#: Eq. F9-14 residual factor 0.7 Fy Sxc / Eq. F9-15 numerator 0.7 E Sxc.
_EQ_F9_14_15_07: float = 0.7
#: Eq. F9-18 coefficients: Fcr = (1.43 - 0.515 (d/tw) sqrt(Fy/E)) Fy.
_EQ_F9_18_A: float = 1.43
_EQ_F9_18_B: float = 0.515
#: Eq. F9-19 numerator: Fcr = 1.52 E / (d/tw)^2.
_EQ_F9_19_COEFF: float = 1.52
#: Eq. F10-6 coefficients: Mn = Fy Sc (2.43 - 1.72 (b/t) sqrt(Fy/E)).
_EQ_F10_6_A: float = 2.43
_EQ_F10_6_B: float = 1.72
#: Eq. F10-8 numerator: Fcr = 0.71 E / (b/t)^2.
_EQ_F10_8_COEFF: float = 0.71
#: Eq. F10-1 yielding plateau factor (the Eq. F10-2 cap = 1.5*My).
_EQ_F10_1_YIELD_FACTOR: float = 1.5
#: Eq. F10-2 inelastic-LTB coefficients
#: Mn = (1.92 - 1.17 sqrt(My/Me)) My <= 1.5 My.
_EQ_F10_2_A: float = 1.92
_EQ_F10_2_B: float = 1.17
#: Eq. F10-3 elastic-LTB coefficients  Mn = (0.92 - 0.17 Me/My) Me.
_EQ_F10_3_A: float = 0.92
_EQ_F10_3_B: float = 0.17
#: Eq. F10-2 / F10-3 regime split (F10-2 if My/Me <= 1.0 else F10-3).
_EQ_F10_2_3_REGIME_LIMIT: float = 1.0

#: Table B4.1b Case 10 tee flange (rolled I-flange rule, §F9.3).
_B4_1B_TEE_FLANGE_LAMBDA_P_COEFF: float = 0.38
_B4_1B_TEE_FLANGE_LAMBDA_R_COEFF: float = 1.00
#: §F9.4 tee-stem compact / noncompact breakpoints (Eq. F9-17/F9-19).
_F9_4_STEM_LAMBDA_P_COEFF: float = 0.84
_F9_4_STEM_LAMBDA_R_COEFF: float = 1.52
#: §F10.3 double-angle-leg compact / noncompact breakpoints.
_F10_3_LEG_LAMBDA_P_COEFF: float = 0.54
_F10_3_LEG_LAMBDA_R_COEFF: float = 0.91


@dataclass(frozen=True)
class F9OracleProps:
    """Plain-float tee / double-angle section properties for the oracle.

    All values in apeSteel base units (N-mm-tonne-s): ``Fy``/``E`` in
    MPa, lengths in mm, ``Zx``/``Sx``/``Sxc`` in mm^3, ``Iy``/``J`` in
    mm^4.

    ``section_kind`` is ``"tee"`` or ``"double_angle"``.  ``Sx`` is the
    elastic modulus to the extreme fibre (the stem tip for a tee);
    ``Sxc`` is the modulus to the compression-flange fibre (Eq. F9-14/
    F9-15).  ``flange_lambda`` is ``bf/2tf`` (tee) / flange-leg ``b/t``
    (2L); ``stem_lambda`` is ``d/tw`` (tee) / web-leg ``b/t`` (2L).
    ``Lb`` is the unbraced length (mm); ``Cb`` the §F1 factor.
    ``stem_in_tension`` selects §F9.1(a)/§F9.2(a) vs the compression
    branch.
    """

    Fy: float
    E: float
    section_kind: str  # "tee" | "double_angle"
    Zx: float
    Sx: float
    Sxc: float
    d: float
    Iy: float
    J: float
    ry: float
    flange_lambda: float
    stem_lambda: float
    Lb: float
    Cb: float = 1.0
    stem_in_tension: bool = True


@dataclass(frozen=True)
class F9OracleResult:
    """Oracle §F9 outcome."""

    Mn: float
    governing: str  # yielding|lateral_torsional_buckling|flange_local_buckling|stem_local_buckling
    Mp: float
    My: float
    Mn_yield: float
    Lp: float
    Lr: float
    B: float
    Mcr: float
    Mn_ltb: float  # math.inf when LTB N/A
    lambda_pf: float
    lambda_rf: float
    flange_class: str
    Mn_flb: float  # math.inf when FLB N/A
    stem_lambda_p: float
    stem_lambda_r: float
    stem_class: str
    Fcr: float  # 0.0 unless tee stem in compression & slender/NC
    Mn_slb: float  # math.inf when stem LB N/A
    stem_in_compression_low_ductility: bool


def _classify(lam: float, lam_p: float, lam_r: float) -> str:
    if lam <= lam_p:
        return "compact"
    if lam <= lam_r:
        return "non_compact"
    return "slender"


def _f10_3_leg_lb(leg_class: str, *, Fy: float, E: float, Sc: float, b_t: float) -> float:
    """§F10.3 leg local buckling Mn (Eq. F10-6/7/8); inf if compact."""
    if leg_class == "compact":
        return math.inf
    if leg_class == "non_compact":
        return Fy * Sc * (_EQ_F10_6_A - _EQ_F10_6_B * b_t * math.sqrt(Fy / E))  # F10-6
    Fcr = _EQ_F10_8_COEFF * E / b_t**2  # F10-8
    return Fcr * Sc  # F10-7


def _mn_ltb_from_me_f10_2_3(*, My: float, Me: float) -> float:
    """Eq. F10-2 / F10-3 LTB nominal moment from ``My`` and ``Me``.

    §F9.2(b)(2) (F9-EC-1 RESOLVED): for double-angle web legs in
    compression ``Mn`` is determined using Equations F10-2 and F10-3
    with ``Mcr`` (Eq. F9-10) as the §F10 ``Me`` and ``My`` (Eq. F9-3,
    ``Fy Sx``).  ``My/Me <= 1.0`` -> Eq. F10-2
    ``Mn = (1.92 - 1.17 sqrt(My/Me)) My <= 1.5 My``; otherwise Eq. F10-3
    ``Mn = (0.92 - 0.17 Me/My) Me``.  Re-derived from the spec literals
    above (NOT imported from apeSteel) so a typo disagrees at tier-1.
    """
    ratio_my_me = My / Me
    if ratio_my_me <= _EQ_F10_2_3_REGIME_LIMIT:
        mn_f10_2 = (_EQ_F10_2_A - _EQ_F10_2_B * math.sqrt(ratio_my_me)) * My
        return min(mn_f10_2, _EQ_F10_1_YIELD_FACTOR * My)  # <= 1.5*My
    ratio_me_my = Me / My
    return (_EQ_F10_3_A - _EQ_F10_3_B * ratio_me_my) * Me


def _lr_f9_9(*, Fy: float, E: float, Iy: float, J: float, Sx: float, d: float) -> float:
    """Eq. F9-9 Lr."""
    return (
        _EQ_F9_9_LR_COEFF
        * (E / Fy)
        * (math.sqrt(Iy * J) / Sx)
        * math.sqrt(_EQ_F9_9_INNER_COEFF * (Fy / E) * (d * Sx / J) + 1.0)
    )


def _yielding(p: F9OracleProps, *, My: float) -> float:
    """§F9.1 Mp (Eq. F9-2 / F9-4 / F9-5)."""
    if p.stem_in_tension:
        return min(p.Fy * p.Zx, _EQ_F9_2_MY_CAP * My)  # F9-2
    if p.section_kind == "tee":
        return My  # F9-4
    return _EQ_F9_5_MY_FACTOR * My  # F9-5


def _ltb(
    p: F9OracleProps, *, My: float, Mp: float, sqrt_E_Fy: float
) -> tuple[float, float, float, float, float]:
    """§F9.2 LTB -> (Mn, Lp, Lr, B, Mcr); Mn = inf when LTB N/A."""
    b_mag = _EQ_F9_11_B_COEFF * (p.d / p.Lb) * math.sqrt(p.Iy / p.J)
    B = b_mag if p.stem_in_tension else -b_mag  # F9-11 / F9-12
    Mcr = (
        p.Cb
        * (_EQ_F9_10_MCR_COEFF * p.E / p.Lb)
        * math.sqrt(p.Iy * p.J)
        * (B + math.sqrt(1.0 + B**2))
    )  # F9-10
    Lp = _EQ_F9_8_LP_COEFF * p.ry * sqrt_E_Fy  # F9-8
    Lr = _lr_f9_9(Fy=p.Fy, E=p.E, Iy=p.Iy, J=p.J, Sx=p.Sx, d=p.d)  # F9-9
    if not p.stem_in_tension:
        # §F9.2(b): tee stems F9-13 Mn = Mcr <= My.  2L web legs
        # §F9.2(b)(2) (F9-EC-1 RESOLVED): Mn via Eq. F10-2/F10-3 with
        # Mcr (F9-10) as Me and My (F9-3, Fy Sx).
        if p.section_kind == "double_angle":
            return _mn_ltb_from_me_f10_2_3(My=My, Me=Mcr), Lp, Lr, B, Mcr
        return min(Mcr, My), Lp, Lr, B, Mcr
    if p.Lb <= Lp:
        return math.inf, Lp, Lr, B, Mcr  # §F9.2(a)(1)
    if p.Lb <= Lr:
        return min(Mp - (Mp - My) * (p.Lb - Lp) / (Lr - Lp), Mp), Lp, Lr, B, Mcr  # F9-6
    return Mcr, Lp, Lr, B, Mcr  # F9-7


def _flange_lb(
    p: F9OracleProps, *, My: float, Mp: float, lam_pf: float, lam_rf: float, flange_class: str
) -> float:
    """§F9.3 FLB -> Mn; inf when compact."""
    if flange_class == "compact":
        return math.inf
    if p.section_kind == "double_angle":
        return _f10_3_leg_lb(flange_class, Fy=p.Fy, E=p.E, Sc=p.Sxc, b_t=p.flange_lambda)
    residual = _EQ_F9_14_15_07 * p.Fy * p.Sxc
    if flange_class == "non_compact":
        mn = Mp - (Mp - residual) * (p.flange_lambda - lam_pf) / (lam_rf - lam_pf)  # F9-14
        return min(mn, _EQ_F9_2_MY_CAP * My)
    return _EQ_F9_14_15_07 * p.E * p.Sxc / p.flange_lambda**2  # F9-15


def _stem_lb(
    p: F9OracleProps, *, sqrt_E_Fy: float, stem_lam_p: float, stem_lam_r: float, stem_class: str
) -> tuple[float, float]:
    """§F9.4 stem / web-leg LB -> (Mn, Fcr); inf when stem in tension."""
    if p.stem_in_tension:
        return math.inf, 0.0  # §F9.4 applies only in compression
    if p.section_kind == "double_angle":
        return (
            _f10_3_leg_lb(stem_class, Fy=p.Fy, E=p.E, Sc=p.Sx, b_t=p.stem_lambda),
            0.0,
        )
    if p.stem_lambda <= stem_lam_p:
        Fcr = p.Fy  # F9-17
    elif p.stem_lambda <= stem_lam_r:
        Fcr = (_EQ_F9_18_A - _EQ_F9_18_B * p.stem_lambda * math.sqrt(p.Fy / p.E)) * p.Fy  # F9-18
    else:
        Fcr = _EQ_F9_19_COEFF * p.E / p.stem_lambda**2  # F9-19
    return Fcr * p.Sx, Fcr  # F9-16


def mn_F9(p: F9OracleProps) -> F9OracleResult:
    """Independent AISC 360-22 §F9 ``Mn`` for a tee / double angle.

    Re-derives Eq. F9-1 .. F9-19 (+ the §F10.3 double-angle leg-LB
    delegation and the regime splits) from the spec literals above,
    with **no** apeSteel import.
    """
    sqrt_E_Fy = math.sqrt(p.E / p.Fy)
    lam_pf = _B4_1B_TEE_FLANGE_LAMBDA_P_COEFF * sqrt_E_Fy
    lam_rf = _B4_1B_TEE_FLANGE_LAMBDA_R_COEFF * sqrt_E_Fy
    if p.section_kind == "double_angle":
        # §F9.3(b)/§F9.4(b): the §F10.3 leg classification is used for
        # both the flange-leg and web-leg checks.
        lam_pf = _F10_3_LEG_LAMBDA_P_COEFF * sqrt_E_Fy
        lam_rf = _F10_3_LEG_LAMBDA_R_COEFF * sqrt_E_Fy
        stem_lam_p = lam_pf
        stem_lam_r = lam_rf
    else:
        stem_lam_p = _F9_4_STEM_LAMBDA_P_COEFF * sqrt_E_Fy
        stem_lam_r = _F9_4_STEM_LAMBDA_R_COEFF * sqrt_E_Fy

    flange_class = _classify(p.flange_lambda, lam_pf, lam_rf)
    stem_class = _classify(p.stem_lambda, stem_lam_p, stem_lam_r)

    My = p.Fy * p.Sx  # Eq. F9-3
    Mp = _yielding(p, My=My)
    mn_yield = Mp  # Eq. F9-1

    mn_ltb, Lp, Lr, B, Mcr = _ltb(p, My=My, Mp=Mp, sqrt_E_Fy=sqrt_E_Fy)
    mn_flb = _flange_lb(p, My=My, Mp=Mp, lam_pf=lam_pf, lam_rf=lam_rf, flange_class=flange_class)
    mn_slb, Fcr = _stem_lb(
        p, sqrt_E_Fy=sqrt_E_Fy, stem_lam_p=stem_lam_p, stem_lam_r=stem_lam_r, stem_class=stem_class
    )

    candidates = {
        "yielding": mn_yield,
        "lateral_torsional_buckling": mn_ltb,
        "flange_local_buckling": mn_flb,
        "stem_local_buckling": mn_slb,
    }
    governing = min(candidates, key=lambda k: candidates[k])
    Mn = candidates[governing]

    return F9OracleResult(
        Mn=Mn,
        governing=governing,
        Mp=Mp,
        My=My,
        Mn_yield=mn_yield,
        Lp=Lp,
        Lr=Lr,
        B=B,
        Mcr=Mcr,
        Mn_ltb=mn_ltb,
        lambda_pf=lam_pf,
        lambda_rf=lam_rf,
        flange_class=flange_class,
        Mn_flb=mn_flb,
        stem_lambda_p=stem_lam_p,
        stem_lambda_r=stem_lam_r,
        stem_class=stem_class,
        Fcr=Fcr,
        Mn_slb=mn_slb,
        stem_in_compression_low_ductility=not p.stem_in_tension,
    )


__all__ = ["F9OracleProps", "F9OracleResult", "mn_F9"]
