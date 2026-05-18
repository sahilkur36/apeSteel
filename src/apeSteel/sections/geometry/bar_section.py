"""Rectangular-bar and round-bar geometry for AISC 360-22 §F11.

A solid rectangular bar (depth ``d`` x width ``b``) and a solid round
bar (diameter ``D``) are the simplest flexural cross-sections in
Chapter F: no walls, no flanges, no web, hence no Table B4.1b
local-buckling limit state (compact by inspection - see
:func:`apeSteel.classification.classify_flexural_compactness`, which
emits an empty plate-element tuple for ``rectangular_bar`` /
``round_bar``).  §F11 governs them with yielding (Eq. F11-1 / F11-2)
and, for a rectangular bar bent about its major axis, lateral-torsional
buckling (Eq. F11-3 / F11-4 / F11-5).

The section moduli are exact elementary closed forms (no fillet, no
k-radius, no catalog lookup), reproduced directly from the AISC Manual
v15.1 Table 17-27 expressions quoted in Examples F.12 / F.13:

* rectangular bar (about an axis of depth ``d``, width ``b``):
  ``Z = b d^2 / 4``,  ``S = b d^2 / 6``,  ``I = b d^3 / 12``,
  ``A = b d``;
* round bar (diameter ``D``):
  ``Z = D^3 / 6``,  ``S = pi D^3 / 32``,  ``I = pi D^4 / 64``,
  ``A = pi D^2 / 4``.

For a rectangular bar both geometric axes are carried (flexure is
axis-specific - §F11 applies to "rectangular bars bent about either
geometric axis"): the strong (major) axis bends about the centroidal
axis perpendicular to ``d`` (extreme fibre at ``d/2``), the weak (minor)
axis about the axis perpendicular to ``b`` (extreme fibre at ``b/2``).
A round bar is axisymmetric, so the two axes coincide.

The §F12 ``extreme_fibre_moduli`` tuple is populated with both
geometric-axis elastic moduli so the elastic ``Fn*Smin`` catch-all
(Eq. F12-1) can take ``Smin = min(...)`` consistently with the rest of
Chapter F, even though a doubly-symmetric bar is normally handled by
§F11, not §F12.

All dimensions are in apeSteel's canonical ``N-mm-tonne-s`` base units
(length in mm, area in mm^2, second moment in mm^4, modulus in mm^3).
See ``docs/UNITS_AND_CONVENTIONS.md`` and
``docs/design_notes/10_flexure_full_F.md`` §3.

References
----------
.. [1] AISC 360-22 §F11 "Rectangular Bars and Rounds", Eq. F11-1 -
       F11-5, p. 16.1-71.  American Institute of Steel Construction,
       2022.
.. [2] AISC Manual v15.1 Vol.1, Design Examples F.12 (rectangular bar)
       and F.13 (round bar); Manual Table 17-27 closed-form section
       properties (``Sx = b d^2/6``, ``Zx = b d^2/4``,
       ``S = pi d^3/32``, ``Z = d^3/6``).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from apeSteel.sections.flexural_properties import FlexuralSectionProperties

# ---------------------------------------------------------------------------
# Elementary closed-form section-property coefficients.  Each magic
# number is named + cited so the provenance is traceable at the call
# site (mirrors the F2 / F4 / F8 constant style).  These are textbook
# rationals, not AISC equations, but they ARE the expressions the AISC
# Manual v15.1 Table 17-27 prints and Examples F.12 / F.13 quote.
# ---------------------------------------------------------------------------

#: Rectangular bar plastic modulus ``Z = b d^2 / 4`` (denominator).
_RECT_BAR_Z_DIVISOR: float = 4.0
#: Rectangular bar elastic modulus ``S = b d^2 / 6`` (denominator).
_RECT_BAR_S_DIVISOR: float = 6.0
#: Rectangular bar second moment ``I = b d^3 / 12`` (denominator).
_RECT_BAR_I_DIVISOR: float = 12.0

#: Round bar plastic modulus ``Z = D^3 / 6`` (denominator).
_ROUND_BAR_Z_DIVISOR: float = 6.0
#: Round bar elastic modulus ``S = pi D^3 / 32`` (denominator).
_ROUND_BAR_S_DIVISOR: float = 32.0
#: Round bar second moment ``I = pi D^4 / 64`` (denominator).
_ROUND_BAR_I_DIVISOR: float = 64.0
#: Round bar gross area ``A = pi D^2 / 4`` (denominator).
_ROUND_BAR_A_DIVISOR: float = 4.0


@dataclass(frozen=True, slots=True)
class RectangularBar:
    """Solid rectangular bar, all dims in mm (AISC 360-22 §F11).

    The bar bends about either geometric axis (§F11 lead paragraph).
    The *major* (strong) geometric axis is the centroidal axis about
    which the section is deepest: bending it stresses the extreme fibre
    at :math:`\\pm d/2`.  The *minor* (weak) axis stresses the extreme
    fibre at :math:`\\pm b/2`.

    Parameters
    ----------
    depth_d : float
        Overall depth ``d`` (the dimension parallel to the major-axis
        bending plane), mm.
    width_b : float
        Width ``b`` (the dimension perpendicular to the major-axis
        bending plane), mm.

    Notes
    -----
    No fillet / corner radius - a bar is a clean rectangle, so the
    closed forms ``Zx = b d^2/4``, ``Sx = b d^2/6``,
    ``Ix = b d^3/12`` (and the ``b<->d`` swap for the minor axis) are
    exact, matching AISC Manual v15.1 Table 17-27 and Example F.12.
    """

    depth_d: float
    width_b: float

    def compute_section_properties(self) -> FlexuralSectionProperties:
        """Return the AISC 360-22 §F11 flexural snapshot for the bar.

        Strong (major) axis - bending about the centroidal axis
        perpendicular to ``d``::

            Ix = b d^3 / 12   Sx = b d^2 / 6   Zx = b d^2 / 4

        Weak (minor) axis - bending about the centroidal axis
        perpendicular to ``b`` (the ``b<->d`` swap)::

            Iy = d b^3 / 12   Sy = d b^2 / 6   Zy = d b^2 / 4

        ``extreme_fibre_moduli = (Sx, Sy)`` so the §F12 elastic
        ``Fn*Smin`` catch-all (Eq. F12-1) sees a consistent
        ``Smin = min(...)`` (a bar is doubly-symmetric, so the two
        geometric-axis moduli are the only extreme-fibre moduli).

        Returns
        -------
        FlexuralSectionProperties
            ``section_kind="rectangular_bar"``, doubly-symmetric, base
            units.  ``overall_depth_d`` is ``d`` (the major-axis
            depth), which §F11 uses for the LTB slenderness
            ``Lb d / t^2``.
        """
        d: float = self.depth_d
        b: float = self.width_b
        if d <= 0.0:
            raise ValueError(f"rectangular-bar depth_d must be positive, got {d!r}")
        if b <= 0.0:
            raise ValueError(f"rectangular-bar width_b must be positive, got {b!r}")

        area_ag: float = b * d

        # Strong (major) geometric axis: deepest dimension is d.
        ix_: float = b * d**3 / _RECT_BAR_I_DIVISOR
        sx_: float = b * d**2 / _RECT_BAR_S_DIVISOR
        zx_: float = b * d**2 / _RECT_BAR_Z_DIVISOR
        rx_: float = math.sqrt(ix_ / area_ag)

        # Weak (minor) geometric axis: the b <-> d swap.
        iy_: float = d * b**3 / _RECT_BAR_I_DIVISOR
        sy_: float = d * b**2 / _RECT_BAR_S_DIVISOR
        zy_: float = d * b**2 / _RECT_BAR_Z_DIVISOR
        ry_: float = math.sqrt(iy_ / area_ag)

        return FlexuralSectionProperties(
            section_kind="rectangular_bar",
            symmetry="doubly_symmetric",
            overall_depth_d=d,
            gross_area_Ag=area_ag,
            moment_of_inertia_Ix=ix_,
            elastic_modulus_Sx=sx_,
            plastic_modulus_Zx=zx_,
            radius_of_gyration_rx=rx_,
            moment_of_inertia_Iy=iy_,
            elastic_modulus_Sy=sy_,
            plastic_modulus_Zy=zy_,
            radius_of_gyration_ry=ry_,
            # §F11 has no local-buckling limit state (compact by
            # inspection); the classifier emits no plate elements.
            plate_elements=(),
            # §F12 elastic Fn*Smin catch-all: both geometric-axis
            # elastic moduli are the extreme-fibre moduli of a
            # doubly-symmetric bar.
            extreme_fibre_moduli=(sx_, sy_),
        )


@dataclass(frozen=True, slots=True)
class RoundBar:
    """Solid round bar of diameter ``D``, in mm (AISC 360-22 §F11).

    A round bar is axisymmetric: §F11 yielding uses Eq. F11-2 and the
    lateral-torsional-buckling limit state does not apply (§F11.2(a)).

    Parameters
    ----------
    diameter_D : float
        Bar diameter ``D``, mm.
    """

    diameter_D: float

    def compute_section_properties(self) -> FlexuralSectionProperties:
        """Return the AISC 360-22 §F11 flexural snapshot for the round bar.

        Solid-circle closed forms (AISC Manual v15.1 Table 17-27,
        Example F.13)::

            A = pi D^2 / 4    I = pi D^4 / 64
            S = pi D^3 / 32   Z = D^3 / 6

        Axisymmetric: ``Ix == Iy``, ``Sx == Sy``, ``Zx == Zy``,
        ``rx == ry``; §F11 has no LTB limit state for a round, so the
        I/channel LTB constants keep their neutral defaults.

        Returns
        -------
        FlexuralSectionProperties
            ``section_kind="round_bar"``, doubly-symmetric, base units.
        """
        big_d: float = self.diameter_D
        if big_d <= 0.0:
            raise ValueError(f"round-bar diameter_D must be positive, got {big_d!r}")

        area_ag: float = math.pi * big_d**2 / _ROUND_BAR_A_DIVISOR
        i_: float = math.pi * big_d**4 / _ROUND_BAR_I_DIVISOR
        # S = pi D^3 / 32 = I / (D/2); written via the direct closed
        # form (the I/(D/2) identity is exercised in the golden test,
        # not asserted here - IEEE evaluation order makes the two
        # forms only algebraically, not bit-, identical).
        s_: float = math.pi * big_d**3 / _ROUND_BAR_S_DIVISOR
        z_: float = big_d**3 / _ROUND_BAR_Z_DIVISOR
        r_: float = math.sqrt(i_ / area_ag)

        return FlexuralSectionProperties(
            section_kind="round_bar",
            symmetry="doubly_symmetric",
            overall_depth_d=big_d,
            gross_area_Ag=area_ag,
            moment_of_inertia_Ix=i_,
            elastic_modulus_Sx=s_,
            plastic_modulus_Zx=z_,
            radius_of_gyration_rx=r_,
            # Axisymmetric: weak-axis == strong-axis.
            moment_of_inertia_Iy=i_,
            elastic_modulus_Sy=s_,
            plastic_modulus_Zy=z_,
            radius_of_gyration_ry=r_,
            plate_elements=(),
            # Axisymmetric -> the single elastic modulus is the only
            # extreme-fibre modulus (carried for §F12 parity).
            extreme_fibre_moduli=(s_,),
        )


__all__ = ["RectangularBar", "RoundBar"]
