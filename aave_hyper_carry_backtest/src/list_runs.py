from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="List carry backtest run directories")
    parser.add_argument("--results-dir", default="results", help="Results directory")
    args = parser.parse_args()

    root = Path(args.results_dir)
    if not root.exists():
        print(f"No results directory: {root}")
        return

    runs = sorted([path for path in root.iterdir() if path.is_dir()])
    for run in runs:
        print(run.name)


if __name__ == "__main__":
    main()
