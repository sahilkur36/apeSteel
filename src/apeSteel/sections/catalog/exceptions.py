"""Catalog-layer exceptions.

These are raised by :mod:`apeSteel.sections.catalog` so user code can
``except`` against a stable, documented class instead of a stringly-
matched ``ValueError`` or ``KeyError``.
"""

from __future__ import annotations


class CatalogError(Exception):
    """Base for every exception raised by the catalog subpackage."""


class SectionNotFoundError(CatalogError):
    """Raised when a requested section label cannot be resolved.

    A label fails to resolve when:

    * It does not match any row exactly, *and*
    * The RapidFuzz fuzzy-match best score falls below the configured
      similarity threshold (default 80).

    Attributes
    ----------
    requested_label : str
        The label the caller asked for, exactly as supplied.
    best_fuzzy_match : str or None
        The closest catalog label found by RapidFuzz, when one exists
        (even if its similarity score was below threshold). ``None``
        when the catalog is empty or no candidates passed the minimal
        score floor RapidFuzz returns.
    best_fuzzy_score : float or None
        The similarity score (0–100) of :attr:`best_fuzzy_match`.
    similarity_threshold : float
        The score below which the fuzzy match is rejected.

    Notes
    -----
    The exception message embeds all four fields so a stack trace is
    self-explanatory without the caller needing to read these attributes
    explicitly.
    """

    def __init__(
        self,
        requested_label: str,
        *,
        best_fuzzy_match: str | None,
        best_fuzzy_score: float | None,
        similarity_threshold: float,
    ) -> None:
        self.requested_label: str = requested_label
        self.best_fuzzy_match: str | None = best_fuzzy_match
        self.best_fuzzy_score: float | None = best_fuzzy_score
        self.similarity_threshold: float = similarity_threshold

        if best_fuzzy_match is None:
            details: str = "no candidates in catalog"
        else:
            details = (
                f"best fuzzy match {best_fuzzy_match!r} scored "
                f"{best_fuzzy_score:.1f}/100, below threshold "
                f"{similarity_threshold:.1f}"
                if best_fuzzy_score is not None
                else f"best fuzzy match {best_fuzzy_match!r}"
            )

        super().__init__(f"Section {requested_label!r} not found in catalog ({details}).")


class SectionTypeNotAdaptableError(CatalogError):
    """Raised when a catalog row cannot be adapted to the requested shape.

    For example, asking for a :class:`~apeSteel.sections.geometry.DoublySymmetricISection`
    from an angle row, or for a :class:`~apeSteel.sections.properties.SectionProperties`
    from a pipe (which has no ``bf``).

    Attributes
    ----------
    section_label : str
        The catalog label of the offending row.
    section_type : str
        The AISC v16 ``Type`` code of the row (``"W"``, ``"L"``, ...).
    requested_adapter : str
        Short human label for the adapter that was called.
    reason : str
        Free-form explanation suitable for inclusion in a traceback.
    """

    def __init__(
        self,
        section_label: str,
        *,
        section_type: str,
        requested_adapter: str,
        reason: str,
    ) -> None:
        self.section_label: str = section_label
        self.section_type: str = section_type
        self.requested_adapter: str = requested_adapter
        self.reason: str = reason
        super().__init__(
            f"Cannot adapt section {section_label!r} (type {section_type!r}) "
            f"via {requested_adapter}: {reason}"
        )


__all__ = [
    "CatalogError",
    "SectionNotFoundError",
    "SectionTypeNotAdaptableError",
]
