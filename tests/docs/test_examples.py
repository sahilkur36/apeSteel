"""Run every .py file under ``docs/examples/`` as a test.

This is the "code-grounded" guarantee for the documentation: every
example shown in the docs is also a CI-executed Python file.  If the
public API drifts, the example fails, the docs build catches it, and
the diff is obvious.

Convention for example files
----------------------------
Each ``docs/examples/<name>.py`` must:

1. Define a ``main()`` function with zero arguments (it gets called
   by this test runner).
2. Use ``matplotlib.use("Agg")`` *before* importing pyplot if it
   produces plots (so it runs headlessly in CI).
3. Write any generated images to ``docs/assets/plots/<name>.png``.
4. Not require any external state (no network, no on-disk fixtures).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


_EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "docs" / "examples"


def _discover_examples() -> list[Path]:
    if not _EXAMPLES_DIR.is_dir():
        return []
    return sorted(p for p in _EXAMPLES_DIR.glob("*.py") if not p.name.startswith("_"))


@pytest.mark.parametrize("example_path", _discover_examples(), ids=lambda p: p.stem)
def test_example_runs(example_path: Path) -> None:
    """Import the example module and invoke its ``main()``."""
    spec = importlib.util.spec_from_file_location(
        f"_docs_example_{example_path.stem}", example_path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(spec.name, None)

    main = getattr(module, "main", None)
    assert callable(main), (
        f"{example_path.name} must define a callable `main()`; "
        "see tests/docs/test_examples.py for the convention."
    )
    main()
