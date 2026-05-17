"""Plate-built singly-symmetric I-section geometry.

A :class:`SinglySymmetricISection` is the immutable plate-dimension
description of a welded built-up I with **unequal flanges** (web
attached at the mid-width of each flange).  The web is concentric with
the flanges so the y-axis (weak axis) is still a principal axis; only
the x-axis (strong axis) loses its symmetry.

Conventions
-----------
* ``y`` is measured from the bottom fiber of the section upward.
* The top flange sits at the top of the section, the bottom flange at
  the bottom.  Which one is in compression depends on the bending
  direction:

    * Positive moment about the strong axis (sagging beam) → top flange
      is in compression.
    * Negative moment (hogging beam, at a support) → bottom flange is
      in compression.

  AISC §F4 must be evaluated for the relevant direction; for design,
  both directions are usually checked separately and the smaller
  capacity governs.  The
  :meth:`compute_section_properties` method takes a
  ``compression_flange_side`` parameter ("top" or "bot") and returns a
  :class:`SectionProperties` populated with the corresponding ``Sxc``,
  ``Sxt``, ``Iyc``, ``hc``, ``hp``, ``bfc``, ``tfc`` values.

Limitations
-----------
* Only welded plate-built sections.  Rolled SS shapes (e.g., MC channels,
  asymmetric tees) are out of scope.
* Web attached at flange mid-width (the standard AISC §F4 / Table B4.1b
  Case 16 assumption).
* Plastic neutral axis is assumed to lie inside the web (true for most
  practical proportions).  If the PNA falls in a flange,
  ``compute_section_properties`` still returns ``hp`` but the value will
  not match AISC's plastic-zone definition; a ``ValueError`` is raised
  in that pathological case.

The closed-form formulas reproduce the standard plate-girder textbook
derivation (Galambos & Surovek, "Structural Stability of Steel"; AISC
Commentary §F4).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from apeSteel.core.materials import CARBON_STEEL_DENSITY_rho
from apeSteel.core.units import g as gravitational_acceleration_g
from apeSteel.sections.properties import SectionProperties

if TYPE_CHECKING:
    from apeSteel.bracing import Bracing
    from apeSteel.classification import SectionConstruction, SeismicCodeEdition
    from apeSteel.core.materials import SteelMaterial
    from apeSteel.element import Element


CompressionFlangeSide = Literal["top", "bot"]


@dataclass(frozen=True, slots=True)
class SinglySymmetricISection:
    """Plate-built singly-symmetric I-section (unequal top and bot flanges).

    All values are in apeSteel's ``N-mm-tonne-s`` base units (mm).

    Parameters
    ----------
    top_flange_width_bf_top : float
        Width of the top flange.
    top_flange_thickness_tf_top : float
        Thickness of the top flange.
    bot_flange_width_bf_bot : float
        Width of the bottom flange.
    bot_flange_thickness_tf_bot : float
        Thickness of the bottom flange.
    web_clear_height_hw : float
        Clear height of the web between the inside faces of the flanges.
    web_thickness_tw : float
        Thickness of the web.
    """

    top_flange_width_bf_top: float
    top_flange_thickness_tf_top: float
    bot_flange_width_bf_bot: float
    bot_flange_thickness_tf_bot: float
    web_clear_height_hw: float
    web_thickness_tw: float

    # ------------------------------------------------------------------ #
    # Section-property computation
    # ------------------------------------------------------------------ #
    def compute_section_properties(  # noqa: PLR0915 - one sequential closed-form derivation; splitting risks the verified math
        self,
        compression_flange_side: CompressionFlangeSide = "top",
    ) -> SectionProperties:
        """Return integrated section properties.

        Parameters
        ----------
        compression_flange_side : {"top", "bot"}, default "top"
            Which flange is in compression for the bending direction
            being checked.  Drives ``Sxc``, ``Sxt``, ``Iyc``,
            ``compression_flange_*``, ``hc``, ``hp``.

        Returns
        -------
        SectionProperties
            Populated with both the doubly-symmetric base fields (Sx, Zx,
            Iy, ho, J, Cw, ry, rts, ...) and the singly-symmetric
            optional fields (Sxc, Sxt, Iyc, hc, hp, bfc, tfc).
        """
        bft = self.top_flange_width_bf_top
        tft = self.top_flange_thickness_tf_top
        bfb = self.bot_flange_width_bf_bot
        tfb = self.bot_flange_thickness_tf_bot
        hw = self.web_clear_height_hw
        tw = self.web_thickness_tw

        # --- Overall geometry ---
        d: float = hw + tft + tfb

        # Areas
        At = bft * tft  # top flange area
        Aw = hw * tw  # web area
        Ab = bfb * tfb  # bot flange area
        Ag = At + Aw + Ab

        # Centroid measured from bottom fiber
        yt_centroid = tfb + hw + tft / 2.0  # top flange centroid (from bottom)
        yw_centroid = tfb + hw / 2.0
        yb_centroid = tfb / 2.0
        y_c = (At * yt_centroid + Aw * yw_centroid + Ab * yb_centroid) / Ag

        # Distance between flange centroids (used by J, Cw, ho)
        ho: float = tft / 2.0 + hw + tfb / 2.0

        # --- Strong-axis inertia about centroid (parallel-axis) ---
        It_self = bft * tft**3 / 12.0
        Iw_self = tw * hw**3 / 12.0
        Ib_self = bfb * tfb**3 / 12.0
        Ix: float = (
            It_self
            + At * (yt_centroid - y_c) ** 2
            + Iw_self
            + Aw * (yw_centroid - y_c) ** 2
            + Ib_self
            + Ab * (yb_centroid - y_c) ** 2
        )

        # Elastic moduli to extreme fibers
        c_top = d - y_c  # distance from centroid to top fiber
        c_bot = y_c  # distance from centroid to bottom fiber
        Sx_top_fiber = Ix / c_top
        Sx_bot_fiber = Ix / c_bot
        # AISC's published `Sx` is conventionally the smaller of the two
        # (the section modulus to the most-stressed fiber).
        Sx: float = min(Sx_top_fiber, Sx_bot_fiber)

        # rx
        rx: float = math.sqrt(Ix / Ag)

        # --- Plastic section modulus and plastic NA ---
        # Solve for plastic NA assumed in the web: area above PNA equals
        # area below PNA, each equals Ag/2.
        # Let dPNA = distance from bottom fiber to the plastic NA.
        # If PNA is in the web (tfb <= dPNA <= tfb + hw):
        #   A_below_PNA = Ab + (dPNA - tfb)*tw  = Ag/2
        #   -> dPNA = tfb + (Ag/2 - Ab) / tw
        dPNA = tfb + (Ag / 2.0 - Ab) / tw
        if not (tfb <= dPNA <= tfb + hw):
            raise ValueError(
                "SinglySymmetricISection.compute_section_properties: plastic NA "
                "falls outside the web; this geometry is out of scope for the "
                f"Phase 9b implementation. tfb={tfb}, hw={hw}, computed dPNA={dPNA}."
            )

        # Zx = first moment of area about the plastic NA (both halves are
        # equal in area so we sum |y - dPNA|*dA over the section).
        Zx_above = At * (yt_centroid - dPNA) + tw * (tfb + hw - dPNA) ** 2 / 2.0
        Zx_below = Ab * (dPNA - yb_centroid) + tw * (dPNA - tfb) ** 2 / 2.0
        Zx: float = Zx_above + Zx_below

        # --- Weak-axis inertia (about y-axis through web centerline) ---
        Iy_top = tft * bft**3 / 12.0
        Iy_web = hw * tw**3 / 12.0
        Iy_bot = tfb * bfb**3 / 12.0
        Iy: float = Iy_top + Iy_web + Iy_bot
        # Sy referenced to the larger flange width / 2 (most-stressed fiber)
        max_half_flange_width = max(bft, bfb) / 2.0
        Sy: float = Iy / max_half_flange_width
        Zy: float = tft * bft**2 / 4.0 + tfb * bfb**2 / 4.0 + hw * tw**2 / 4.0
        ry: float = math.sqrt(Iy / Ag)

        # --- Torsional and warping constants (open section approx) ---
        # AISC Design Guide 9 closed forms generalized to unequal flanges.
        # J = (b1*t1^3 + b2*t2^3 + ho*tw^3) / 3
        J: float = (bft * tft**3 + bfb * tfb**3 + ho * tw**3) / 3.0
        # Cw for a singly-symmetric I (web attached at flange mid-width):
        # Cw = ho^2 * Iy_top * Iy_bot / (Iy_top + Iy_bot)
        # (Galambos & Surovek, Eq. 2.41; equivalent to AISC Commentary F4.)
        if (Iy_top + Iy_bot) > 0:
            Cw: float = ho**2 * Iy_top * Iy_bot / (Iy_top + Iy_bot)
        else:  # pragma: no cover - cannot happen for real geometry
            Cw = 0.0

        # rts per AISC F2 (DS-derived).  For SS the F4 module uses its
        # own rt (F4-11) so rts is mostly a courtesy here.
        rts: float = math.sqrt(math.sqrt(Iy * Cw) / Sx) if (Iy * Cw) > 0 else 0.0

        # Plate-element slenderness ratios.  For SS, the flange ratio
        # reported here is the *compression-side* ratio (since that's
        # what Table B4.1b uses).  The web ratio is hc/tw, not hw/tw,
        # because Case 16 uses hc.
        if compression_flange_side == "top":
            bfc = bft
            tfc = tft
            bft_tens = bfb
            tft_tens = tfb
            Sxc = Sx_top_fiber
            Sxt = Sx_bot_fiber
            Iyc = Iy_top
            # hc = 2 * (centroid-to-inside-face-of-compression-flange)
            # For top compression: inside top face is at d - tft = tfb + hw.
            # centroid is at y_c; distance = (tfb + hw) - y_c = hw + tfb - y_c.
            hc = 2.0 * (hw + tfb - y_c)
            # hp = 2 * (centroid-to-plastic-NA) on the compression side.
            # Plastic NA at dPNA (from bottom). For top compression, the
            # compression zone extends from PNA upward, so hp = 2*(centroid
            # distance from PNA, taken positive on the compression side).
            # When PNA is below the elastic NA (typical for top compression
            # when bot flange is larger), hp = 2*(y_c - dPNA).
            hp = 2.0 * abs(y_c - dPNA)
        else:  # bot compression
            bfc = bfb
            tfc = tfb
            bft_tens = bft
            tft_tens = tft
            Sxc = Sx_bot_fiber
            Sxt = Sx_top_fiber
            Iyc = Iy_bot
            # For bot compression: inside bot face is at tfb.
            # distance from centroid = y_c - tfb.
            hc = 2.0 * (y_c - tfb)
            hp = 2.0 * abs(y_c - dPNA)
        # Suppress unused-variable warnings for tension-side flange dims
        # (reserved for a future singly-symmetric F4 hc/hp Case 16 refinement).
        del bft_tens, tft_tens

        flange_width_to_thickness_ratio_bf_2tf: float = bfc / (2.0 * tfc)
        web_height_to_thickness_ratio_h_tw: float = hc / tw

        # Nominal weight per unit length
        nominal_weight_per_unit_length_w: float = (
            CARBON_STEEL_DENSITY_rho * gravitational_acceleration_g * Ag
        )

        return SectionProperties(
            overall_depth_d=d,
            gross_area_Ag=Ag,
            nominal_weight_per_unit_length_w=nominal_weight_per_unit_length_w,
            moment_of_inertia_strong_axis_Ix=Ix,
            elastic_section_modulus_strong_axis_Sx=Sx,
            plastic_section_modulus_strong_axis_Zx=Zx,
            radius_of_gyration_strong_axis_rx=rx,
            moment_of_inertia_weak_axis_Iy=Iy,
            elastic_section_modulus_weak_axis_Sy=Sy,
            plastic_section_modulus_weak_axis_Zy=Zy,
            radius_of_gyration_weak_axis_ry=ry,
            torsional_constant_J=J,
            warping_constant_Cw=Cw,
            distance_between_flange_centroids_ho=ho,
            effective_radius_of_gyration_for_LTB_rts=rts,
            flange_width_to_thickness_ratio_bf_2tf=flange_width_to_thickness_ratio_bf_2tf,
            web_height_to_thickness_ratio_h_tw=web_height_to_thickness_ratio_h_tw,
            web_thickness_tw=tw,
            # The flange_width_bf / flange_thickness_tf fields are nominally
            # the doubly-symmetric ``one true flange`` dimensions.  For SS
            # we route the compression-side dimensions here so callers that
            # don't know about the SS-specific fields still see a coherent
            # bf / tf (the compression-side ones).
            flange_width_bf=bfc,
            flange_thickness_tf=tfc,
            # Plate-built sections have no fillet at the flange-web
            # junction: kdes = kdet = tfc, k1 = tw/2.
            k_design_kdes=tfc,
            k_detailing_kdet=tfc,
            k_one_k1=tw / 2.0,
            # --- Singly-symmetric explicit fields (Phase 9b) ---
            compression_flange_width_bfc=bfc,
            compression_flange_thickness_tfc=tfc,
            elastic_section_modulus_compression_flange_Sxc=Sxc,
            elastic_section_modulus_tension_flange_Sxt=Sxt,
            moment_of_inertia_compression_flange_about_y_Iyc=Iyc,
            compression_zone_depth_hc=hc,
            plastic_neutral_axis_depth_hp=hp,
        )

    # ------------------------------------------------------------------ #
    # Element builder
    # ------------------------------------------------------------------ #
    def element(
        self,
        material: SteelMaterial,
        construction: SectionConstruction = "welded",
        bracing: Bracing | None = None,
        code_edition_for_seismic: SeismicCodeEdition = "AISC 341-22",
    ) -> Element:
        """Return an Element binding this section to material + bracing."""
        # Local import to break the cycle:
        # apeSteel.element imports SinglySymmetricISection via TYPE_CHECKING.
        from apeSteel.element import Element  # noqa: PLC0415

        return Element.from_section(
            section=self,
            material=material,
            construction=construction,
            bracing=bracing,
            code_edition_for_seismic=code_edition_for_seismic,
        )


__all__ = ["CompressionFlangeSide", "SinglySymmetricISection"]
