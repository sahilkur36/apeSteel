"""One-shot generator: AISC_Database.pkl  ->  data/AISC_v16_shapes.csv.

The AISC v16 shapes database (2 299 rows × 82 columns) ships from AISC
as a pickled :mod:`pandas` DataFrame in
``to_review/steelProperties/AISC_Database.pkl``.  Pickles are opaque to
reviewers and brittle across pandas versions, so we materialise the data
once into a deterministic, diff-able CSV that lives in git:

    src/apeSteel/sections/catalog/data/AISC_v16_shapes.csv

This script is the *only* code that ever reads the pickle.  Everything
else in :mod:`apeSteel` reads the CSV.

Run it from the repository root:

    python tools/build_aisc_v16_csv.py

The script is deterministic — re-running it on the same pickle produces
byte-identical CSV output.  After running, commit any diff to git.

Numeric values keep the AISC v16 *SI Manual* mixed units (mm, kg/m,
:math:`10^{6}` mm⁴, :math:`10^{3}` mm³, :math:`10^{3}` mm⁴ for ``J``,
:math:`10^{9}` mm⁶ for ``Cw``) so a CSV row can be diffed line-by-line
against a printed AISC v16 SI Manual page.  Conversion to the base
``N-mm-tonne-s`` system happens at load time in
:mod:`apeSteel.sections.catalog`.

Missing values in the AISC pickle are encoded with U+2013 ``–``
(en-dash).  We rewrite them as empty cells in the CSV so the load-time
adapter can detect "this section doesn't expose this property" via the
standard pandas / csv ``NaN`` path.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT: Path = Path(__file__).resolve().parent.parent
PICKLE_PATH: Path = REPO_ROOT / "to_review" / "steelProperties" / "AISC_Database.pkl"
CSV_OUTPUT_PATH: Path = (
    REPO_ROOT / "src" / "apeSteel" / "sections" / "catalog" / "data" / "AISC_v16_shapes.csv"
)

# AISC encodes "not applicable for this section type" with U+2013 en-dash.
AISC_MISSING_MARKER: str = "–"


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
def build_csv(pickle_path: Path, csv_path: Path) -> int:
    """Convert the AISC pickle to CSV.  Return the row count written."""
    if not pickle_path.exists():
        msg = f"AISC pickle not found at {pickle_path}"
        raise FileNotFoundError(msg)

    df: pd.DataFrame = pd.read_pickle(pickle_path)

    # Replace AISC's en-dash missing-marker with NaN so to_csv writes an
    # empty cell.  Object-dtype columns are the only ones that carry the
    # marker; numeric columns stay untouched.
    df = df.replace(AISC_MISSING_MARKER, pd.NA)

    # Deterministic column order matches the original pickle exactly so
    # any future column-by-column inspection lines up with AISC's own
    # publication order.
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(
        csv_path,
        index=False,
        # `na_rep=""` would have been the default already; we set it
        # explicitly so the contract is in code, not in a global pandas
        # default that a future version might change.
        na_rep="",
        # LF line endings for cross-platform git diffs.
        lineterminator="\n",
    )

    return len(df)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pickle",
        type=Path,
        default=PICKLE_PATH,
        help=f"Path to AISC_Database.pkl (default: {PICKLE_PATH.relative_to(REPO_ROOT)})",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=CSV_OUTPUT_PATH,
        help=f"Output CSV path (default: {CSV_OUTPUT_PATH.relative_to(REPO_ROOT)})",
    )
    args = parser.parse_args()

    row_count: int = build_csv(args.pickle, args.out)
    print(f"Wrote {row_count} rows to {args.out}")


if __name__ == "__main__":
    main()
