"""Independent AISC 360-22 Chapter-F oracle.

This module is a deliberately *separate* implementation of the AISC
360-22 Chapter-F nominal flexural strength (sections F2/F3/F4/F5).  It
imports **only** the standard-library ``math`` module -- no apeSteel,
and in particular nothing from :mod:`apeSteel.flexure`.

Its sole purpose is to give ``test_chapterF_independent.py`` a true
oracle for the flexural facades, so their correctness no longer rests
on a snapshot of their own output.  Section properties are supplied by
the caller (taken from the apeSteel geometry layer, which has its own
independent scipy / hand-calc cross-check in the unit suite); only the
Chapter-F *strength composition* is re-derived here.

Every equation carries its AISC 360-22 citation in a comment.  The
constants are written as literals from the printed spec, intentionally
*not* shared with the library, so a typo in either implementation
surfaces as a disagreement.

References
----------
AISC 360-22, Specification for Structural Steel Buildings:
  * Table B4.1b, Cases 10/11 (flange) and 15 (web).
  * Section F2.2  Eq. F2-2, F2-4, F2-5, F2-6.
  * Section F3.2  Eq. F3-1, F3-2.
  * Section F4    Eq. F4-1, F4-2, F4-5, F4-6a/6b, F4-7, F4-8,
                  F4-9a/9b/10, F4-11, F4-12, F4-13, F4-14, F4-15,
                  F4-16a/16b/17.
  * Section F5    Eq. F5-1..F5-9, F5-11, F5-12.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class OracleProps:
    """Plain-float section properties consumed by the oracle (base units)."""

    Fy: float
    E: float
    Sx: float
    Zx: float
    ry: float
    rts: float
    ho: float
    J: float
    tw: float
    lam_w: float  # web slenderness ratio used by the library (hc/tw for SS)
    lam_f: float  # compression-flange b/2t
    bfc: float
    tfc: float
    Sxc: float
    Sxt: float
    iyc_over_iy: float
    hc: float
    Ag: float
    hp: float = 0.0  # >0 => singly-symmetric (Table B4.1b Case 16)


@dataclass(frozen=True)
class OracleResult:
    Mn: float
    governing: str


# ---------------------------------------------------------------------------
# AISC 360-22 Table B4.1b (Cases 10/11 flange, Case 15 web) + kc note [c]
# ---------------------------------------------------------------------------
def _kc(h_tw: float) -> float:
    # Table B4.1b note [c]: kc = 4/sqrt(h/tw), 0.35 <= kc <= 0.76.
    return min(0.76, max(0.35, 4.0 / math.sqrt(h_tw)))


def _classify_flange(
    lam_f: float, Fy: float, E: float, h_tw: float, construction: str
) -> tuple[float, float, str]:
    s = math.sqrt(E / Fy)
    lpf = 0.38 * s  # Case 10 & 11: lambda_pf
    # Case 10 rolled: lambda_rf = 1.00 sqrt(E/Fy).
    # Case 11 welded: lambda_rf = 0.95 sqrt(kc E / FL), FL = 0.7 Fy.
    lrf = 1.00 * s if construction == "rolled" else 0.95 * math.sqrt(_kc(h_tw) * E / (0.7 * Fy))
    if lam_f <= lpf:
        cls = "compact"
    elif lam_f <= lrf:
        cls = "non_compact"
    else:
        cls = "slender"
    return lpf, lrf, cls


def _classify_web(lam_w: float, Fy: float, E: float) -> tuple[float, float, str]:
    s = math.sqrt(E / Fy)
    lpw, lrw = 3.76 * s, 5.70 * s  # Case 15
    if lam_w <= lpw:
        cls = "compact"
    elif lam_w <= lrw:
        cls = "non_compact"
    else:
        cls = "slender"
    return lpw, lrw, cls


# ---------------------------------------------------------------------------
# Section F2.2 LTB machinery (shared by F2 and F3)
# ---------------------------------------------------------------------------
def _ltb_F2(p: OracleProps, Lb: float, Cb: float) -> tuple[float, str]:
    Fy, E, Sx, Zx = p.Fy, p.E, p.Sx, p.Zx
    Mp = Fy * Zx
    Lp = 1.76 * p.ry * math.sqrt(E / Fy)  # Eq. F2-5
    Jc = p.J * 1.0  # c = 1.0 for doubly-symmetric I
    a = Jc / (Sx * p.ho)
    b = (0.7 * Fy * Sx * p.ho) / (E * Jc)
    # Eq. F2-6
    Lr = (
        1.95
        * p.rts
        * (E / (0.7 * Fy))
        * math.sqrt(a)
        * math.sqrt(1.0 + math.sqrt(1.0 + 6.76 * b**2))
    )
    if Lb <= Lp:
        return Mp, "yielding"  # Eq. F2-1
    if Lb <= Lr:  # Eq. F2-2
        Mn = Cb * (Mp - (Mp - 0.7 * Fy * Sx) * (Lb - Lp) / (Lr - Lp))
        return min(Mn, Mp), "inelastic_LTB"
    x = (Lb / p.rts) ** 2  # Eq. F2-4
    Fcr = (Cb * math.pi**2 * E) / x * math.sqrt(1.0 + 0.078 * a * x)
    return min(Fcr * Sx, Mp), "elastic_LTB"


# ---------------------------------------------------------------------------
# Section F2 -- compact doubly-symmetric I
# ---------------------------------------------------------------------------
def mn_F2(p: OracleProps, Lb: float, Cb: float) -> OracleResult:
    Mn, reg = _ltb_F2(p, Lb, Cb)
    return OracleResult(Mn, reg)


# ---------------------------------------------------------------------------
# Section F3 -- compact web, non-compact / slender flange
# ---------------------------------------------------------------------------
def mn_F3(p: OracleProps, Lb: float, Cb: float, construction: str) -> OracleResult:
    Fy, E, Sx = p.Fy, p.E, p.Sx
    Mp = Fy * p.Zx
    Mn_ltb, reg = _ltb_F2(p, Lb, Cb)
    lpf, lrf, fcls = _classify_flange(p.lam_f, Fy, E, p.lam_w, construction)
    if fcls == "compact":
        Mn_flb = Mp
    elif fcls == "non_compact":  # Eq. F3-1
        Mn_flb = min(Mp - (Mp - 0.7 * Fy * Sx) * (p.lam_f - lpf) / (lrf - lpf), Mp)
    else:  # slender, Eq. F3-2
        Mn_flb = min(0.9 * E * _kc(p.lam_w) * Sx / p.lam_f**2, Mp)
    if Mn_flb <= Mn_ltb:
        return OracleResult(Mn_flb, "flange_local_buckling")
    return OracleResult(Mn_ltb, reg)


# ---------------------------------------------------------------------------
# Section F4 -- doubly-symmetric non-compact web, or singly-symmetric I
# ---------------------------------------------------------------------------
def mn_F4(p: OracleProps, Lb: float, Cb: float, construction: str) -> OracleResult:
    Fy, E = p.Fy, p.E
    Mp = Fy * p.Zx
    Myc, Myt = Fy * p.Sxc, Fy * p.Sxt
    aw = p.hc * p.tw / (p.bfc * p.tfc)  # Eq. F4-12
    rt = p.bfc / math.sqrt(12.0 * (1.0 + aw / 6.0))  # Eq. F4-11
    lpw, lrw, _ = _classify_web(p.lam_w, Fy, E)
    if p.hp > 0.0:
        # Table B4.1b Case 16 (singly-symmetric web): re-derived here
        # independently of the library, capped at lrw.
        _den = 0.54 * (Mp / Myc) - 0.09
        if _den > 0.0:
            lpw = min(
                (p.hc / p.hp) * math.sqrt(E / Fy) / _den**2,
                lrw,
            )
        else:
            lpw = lrw
    lpf, lrf, fcls = _classify_flange(p.lam_f, Fy, E, p.lam_w, construction)

    def _Rp(My: float) -> float:
        if p.iyc_over_iy <= 0.23:  # Eq. F4-10 / F4-17
            return 1.0
        r = Mp / My
        if p.lam_w <= lpw:  # Eq. F4-9a / F4-16a
            return r
        # Eq. F4-9b / F4-16b
        return min(r - (r - 1.0) * (p.lam_w - lpw) / (lrw - lpw), r)

    Rpc, Rpt = _Rp(Myc), _Rp(Myt)
    ratio = p.Sxt / p.Sxc  # Eq. F4-6a / F4-6b
    FL = 0.7 * Fy if ratio >= 0.7 else max(Fy * ratio, 0.5 * Fy)
    Lp = 1.1 * rt * math.sqrt(E / Fy)  # Eq. F4-7
    jt = p.J / (p.Sxc * p.ho)
    # Eq. F4-8
    Lr = 1.95 * rt * (E / FL) * math.sqrt(jt + math.sqrt(jt**2 + 6.76 * (FL / E) ** 2))

    RpcMyc = Rpc * Myc
    Mn_cfy = RpcMyc  # Eq. F4-1
    if Lb <= Lp:
        Mn_ltb = RpcMyc
    elif Lb <= Lr:  # Eq. F4-2
        Mn_ltb = min(Cb * (RpcMyc - (RpcMyc - FL * p.Sxc) * (Lb - Lp) / (Lr - Lp)), RpcMyc)
    else:  # Eq. F4-5 / F4-3 ; J = 0 when Iyc/Iy <= 0.23
        j_star = 0.0 if p.iyc_over_iy <= 0.23 else p.J
        x = (Lb / rt) ** 2
        Fcr = Cb * math.pi**2 * E / x * math.sqrt(1.0 + 0.078 * j_star / (p.Sxc * p.ho) * x)
        Mn_ltb = min(Fcr * p.Sxc, RpcMyc)

    if fcls == "compact":
        Mn_flb = RpcMyc
    elif fcls == "non_compact":  # Eq. F4-13
        Mn_flb = RpcMyc - (RpcMyc - FL * p.Sxc) * (p.lam_f - lpf) / (lrf - lpf)
    else:  # Eq. F4-14
        Mn_flb = 0.9 * E * _kc(p.lam_w) * p.Sxc / p.lam_f**2

    cands = {
        "compression_flange_yielding": Mn_cfy,
        "lateral_torsional_buckling": Mn_ltb,
        "flange_local_buckling": Mn_flb,
    }
    if p.Sxt < p.Sxc:  # Eq. F4-15 TFY only active when Sxt < Sxc
        cands["tension_flange_yielding"] = Rpt * Myt
    gov = min(cands, key=lambda k: cands[k])
    return OracleResult(cands[gov], gov)


# ---------------------------------------------------------------------------
# Section F5 -- slender-web plate girder (doubly-symmetric path)
# ---------------------------------------------------------------------------
def mn_F5(p: OracleProps, Lb: float, Cb: float, construction: str) -> OracleResult:
    Fy, E, Sx = p.Fy, p.E, p.Sx
    hw = p.lam_w * p.tw  # web clear height (= hc for the F5 aw numerator)
    bf, tf = p.bfc, p.tfc  # AISC §F5: actual compression-flange dims
    aw = min(hw * p.tw / (bf * tf), 10.0)  # Eq. F5-12 (aw capped at 10 per F4-12)
    thr = 5.7 * math.sqrt(E / Fy)
    # Eq. F5-6
    Rpg = 1.0 if p.lam_w <= thr else min(1.0, 1.0 - aw / (1200.0 + 300.0 * aw) * (p.lam_w - thr))
    rt = bf / math.sqrt(12.0 * (1.0 + aw / 6.0))  # Eq. F5-11
    Lp = 1.1 * rt * math.sqrt(E / Fy)  # Eq. F4-7 (referenced by F5.2)
    Lr = math.pi * rt * math.sqrt(E / (0.7 * Fy))  # Eq. F5-5
    if Lb <= Lp:
        Fcr = Fy
    elif Lb <= Lr:  # Eq. F5-3
        Fcr = min(Cb * (Fy - 0.3 * Fy * (Lb - Lp) / (Lr - Lp)), Fy)
    else:  # Eq. F5-4
        Fcr = min(Cb * math.pi**2 * E / (Lb / rt) ** 2, Fy)
    Mn_ltb = Rpg * Fcr * Sx  # Eq. F5-2
    Mn_cfy = Rpg * Fy * Sx  # Eq. F5-1
    lpf, lrf, fcls = _classify_flange(p.lam_f, Fy, E, p.lam_w, construction)
    if fcls == "compact":
        Mn_flb = Mn_cfy
    elif fcls == "non_compact":  # Eq. F5-8
        Mn_flb = Rpg * (Fy - 0.3 * Fy * (p.lam_f - lpf) / (lrf - lpf)) * Sx
    else:  # Eq. F5-9
        Mn_flb = Rpg * (0.9 * E * _kc(p.lam_w) / p.lam_f**2) * Sx
    Mn = min(Mn_cfy, Mn_ltb, Mn_flb)
    return OracleResult(Mn, "F5")
