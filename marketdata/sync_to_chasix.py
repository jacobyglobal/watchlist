"""Copy the combined watchlist artifacts into TheChasIX.com/data/watchlist/.

Phase 1 replacement for the old per-output manual `cp` in the data directory's
README: emits the merged wide table (watchlist.csv) and the schema-v3 column
guide (column_guide.json) into the TheChasIX repo so a commit there deploys the
new `/api/watchlist` contract.

`data/markethighs/` syncing is intentionally untouched - the homepage,
screener, stock detail, chart, and recommendation endpoints keep their format.
"""

from __future__ import annotations

import argparse
import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

WATCHLIST_ROOT = Path(__file__).resolve().parent.parent
OUT = WATCHLIST_ROOT / "output"
CHASIX_WATCHLIST = WATCHLIST_ROOT.parent / "TheChasIX.com" / "data" / "watchlist"

# local combined artifact -> relative path inside TheChasIX.com/data/watchlist/
_ARTIFACTS = {
    "combined_watchlist.csv": "watchlist.csv",
    "combined_column_guide.json": "column_guide.json",
}


def sync(out_dir: Path = OUT, dest_dir: Path = CHASIX_WATCHLIST) -> dict[str, Path]:
    """Copy the combined outputs into `dest_dir`; raises if any source is missing."""
    if not dest_dir.exists():
        raise FileNotFoundError(f"Destination missing: {dest_dir}")
    copied: dict[str, Path] = {}
    for src_name, dest_name in _ARTIFACTS.items():
        src = out_dir / src_name
        if not src.exists():
            raise FileNotFoundError(f"Missing combined artifact: {src} (run build_combined first)")
        dest = dest_dir / dest_name
        shutil.copyfile(src, dest)
        copied[src_name] = dest
        print(f"copied {src} -> {dest}")
    return copied


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--dest", type=Path, default=CHASIX_WATCHLIST)
    args = parser.parse_args()
    sync(args.out, args.dest)


if __name__ == "__main__":
    main()