"""Core primitives: units, materials, result types.

This subpackage intentionally does NOT re-export the contents of its
modules. Users should import from the top-level apeSteel namespace
(from apeSteel import A992, Report) or from the specific submodule
they need (from apeSteel.core.units import MPa).

Keeping core/__init__.py empty avoids an import cycle between
apeSteel.core.materials (which depends on apeSteel.core.units) and the
package's own __init__.

See docs/ARCHITECTURE.md for the module map.
"""
