"""Independent AISC 360-22 Chapter-E oracle.

A deliberately *separate* implementation of the AISC 360-22 Chapter-E
nominal compressive strength (§E3/E4/E5/E6/E7).  Imports **only** the
standard-library ``math`` - nothing from :mod:`apeSteel.compression`.

Its purpose is to anchor the compression facade's correctness on an
independent re-derivation from the printed spec, not on a snapshot of
its own output (the provenance standard established for Chapter F).
Section properties are supplied by the caller (taken from the apeSteel
geometry layer); only the Chapter-E *strength composition* is re-derived
here.  Constants are written as literals from AISC 360-22, intentionally
not shared with the library.

References
----------
AISC 360-22 Chapter E (pp. 16.1-37 - 16.1-43) and Table E7.1.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass(frozen=True)
class OracleElement:
    kind: str  # "unstiffened" | "stiffened" | "hss_wall"
    b: float
    t: float
    lam: float
    lam_r: float


@dataclass(frozen=True)
class OracleProps:
    Fy: float
    E: float
    G: float
    Ag: float
    rx: float
    ry: float
    Ix: float
    Iy: float
    J: float
    Cw: float
    xo: float
    yo: float
    ro_bar2: float
    H: float
    symmetry: str  # "doubly_symmetric" | "singly_symmetric" | "unsymmetric"
    section_kind: str
    elements: tuple[OracleElement, ...] = field(default_factory=tuple)
    D: float = 0.0  # round HSS
    t_wall: float = 0.0


@dataclass(frozen=True)
class OracleResult:
    Fcr: float
    Ae: float
    Pn: float
    governing: str


# --- §E3 / §E4 shared Fcr kernel (Eq. E3-2 / E3-3) -------------------------
def _fcr_from_fe(Fy: float, Fe: float) -> tuple[float, str]:
    if Fy / Fe <= 2.25:
        return (0.658 ** (Fy / Fe)) * Fy, "inelastic"
    return 0.877 * Fe, "elastic"


def _fe_flexural(E: float, lc_over_r: float) -> float:
    return math.pi**2 * E / lc_over_r**2  # Eq. E3-4


# --- §E7 effective width (Table E7.1) --------------------------------------
def _c1_c2(kind: str) -> tuple[float, float]:
    if kind == "unstiffened":
        return 0.22, 1.49
    if kind == "hss_wall":
        return 0.20, 1.38
    return 0.18, 1.31  # stiffened


def _effective_area(p: OracleProps, Fy: float, E: float, Fcr: float) -> float:
    if p.section_kind == "round_HSS":
        dt = p.D / p.t_wall
        if dt <= 0.11 * E / Fy:
            return p.Ag
        if dt > 0.45 * E / Fy:
            raise ValueError("round HSS D/t over 0.45E/Fy")
        return (0.038 * E / (Fy * dt) + 2.0 / 3.0) * p.Ag  # Eq. E7-6/E7-7
    removed = 0.0
    for el in p.elements:
        if el.lam <= el.lam_r:
            continue
        if el.lam <= el.lam_r * math.sqrt(Fy / Fcr):  # Eq. E7-2
            continue
        c1, c2 = _c1_c2(el.kind)
        fel = (c2 * el.lam_r / el.lam) ** 2 * Fy  # Eq. E7-5
        ratio = math.sqrt(fel / Fcr)
        be = el.b * (1.0 - c1 * ratio) * ratio  # Eq. E7-3
        be = max(0.0, min(be, el.b))
        removed += (el.b - be) * el.t
    return p.Ag - removed


# --- §E4 elastic buckling stress -------------------------------------------
def _fe_E4(p: OracleProps, E: float, G: float, Lcx: float, Lcy: float, Lcz: float) -> float:
    fex = math.pi**2 * E / (Lcx / p.rx) ** 2  # Eq. E4-5
    fey = math.pi**2 * E / (Lcy / p.ry) ** 2  # Eq. E4-6
    if p.symmetry == "doubly_symmetric":
        # Eq. E4-2
        return (math.pi**2 * E * p.Cw / Lcz**2 + G * p.J) / (p.Ix + p.Iy)
    fez = (math.pi**2 * E * p.Cw / Lcz**2 + G * p.J) / (p.Ag * p.ro_bar2)  # Eq. E4-7
    if p.symmetry == "singly_symmetric":
        # SC lies on the axis of symmetry: xo==0 -> y is the symmetry
        # axis (tee, use Fey); yo==0 -> x is symmetry axis (channel, Fex).
        fes = fey if abs(p.xo) <= abs(p.yo) else fex
        s = fes + fez
        rad = max(0.0, 1.0 - 4.0 * fes * fez * p.H / s**2)
        return (s / (2.0 * p.H)) * (1.0 - math.sqrt(rad))  # Eq. E4-3
    # unsymmetric cubic, Eq. E4-4
    xr = p.xo**2 / p.ro_bar2
    yr = p.yo**2 / p.ro_bar2

    def cub(fe: float) -> float:
        return (
            (fe - fex) * (fe - fey) * (fe - fez) - fe**2 * (fe - fey) * xr - fe**2 * (fe - fex) * yr
        )

    hi = min(fex, fey, fez)
    lo = 1e-9 * hi
    flo = cub(lo)
    if flo == 0.0 or flo * cub(hi) > 0.0:
        return hi
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        fm = cub(mid)
        if fm == 0.0 or (hi - lo) < 1e-12 * hi:
            return mid
        if flo * fm < 0.0:
            hi = mid
        else:
            lo, flo = mid, fm
    return 0.5 * (lo + hi)


# --- §E5 modified slenderness ----------------------------------------------
def modified_slenderness_E5(L_over_rx: float, case: str) -> float:
    if case == "a":
        if L_over_rx <= 80.0:
            return 72.0 + 0.75 * L_over_rx
        return min(32.0 + 1.25 * L_over_rx, 200.0)
    if L_over_rx <= 75.0:
        return 60.0 + 0.8 * L_over_rx
    return min(45.0 + L_over_rx, 200.0)


# --- §E6 built-up modified slenderness -------------------------------------
def modified_slenderness_E6(
    base: float, a: float, ri: float, connector: str, Ki: float = 0.50
) -> float:
    ar = a / ri
    if connector == "snug_bolted":
        return math.sqrt(base**2 + ar**2)  # Eq. E6-1
    if ar <= 40.0:
        return base
    return math.sqrt(base**2 + (Ki * ar) ** 2)  # Eq. E6-2


# --- public oracle ---------------------------------------------------------
def chapter_E_strength(
    p: OracleProps,
    Lcx: float,
    Lcy: float,
    Lcz: float,
    *,
    e5_case: str | None = None,
    e5_L: float | None = None,
    evaluate_E4: bool = True,
) -> OracleResult:
    """Independent AISC 360-22 ``Pn`` (governing Fcr * Ae)."""
    Fy, E, G = p.Fy, p.E, p.G
    if e5_case is not None and p.section_kind == "single_angle":
        assert e5_L is not None
        lam = modified_slenderness_E5(e5_L / p.rx, e5_case)
        fcr, _ = _fcr_from_fe(Fy, _fe_flexural(E, lam))
        gov = "single_angle_flexural"
    else:
        fcr_x, _ = _fcr_from_fe(Fy, _fe_flexural(E, Lcx / p.rx))
        fcr_y, _ = _fcr_from_fe(Fy, _fe_flexural(E, Lcy / p.ry))
        fcr = min(fcr_x, fcr_y)
        gov = "flexural_buckling"
        if evaluate_E4:
            fcr_e4, _ = _fcr_from_fe(Fy, _fe_E4(p, E, G, Lcx, Lcy, Lcz))
            if fcr_e4 < fcr:
                fcr = fcr_e4
                gov = (
                    "torsional_buckling"
                    if p.symmetry == "doubly_symmetric"
                    else "flexural_torsional_buckling"
                )
    ae = _effective_area(p, Fy, E, fcr)
    return OracleResult(Fcr=fcr, Ae=ae, Pn=fcr * ae, governing=gov)
