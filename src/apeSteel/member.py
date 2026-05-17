"""Deprecated stub - use :mod:`apeSteel.element` instead.

The earlier `Member` class collapsed Bracing into bare attributes; it
has been replaced by the cleaner `Element` + `Bracing` decomposition
where each object owns its own domain.  This file remains only as a
re-export shim for backwards compatibility within the same session.
"""

from apeSteel.element import Element as Member

__all__ = ["Member"]
