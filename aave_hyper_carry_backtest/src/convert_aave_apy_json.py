from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert Aave APY history JSON into ts,borrow_apr CSV")
    parser.add_argument("--in-json", required=True, help="Path to JSON exported from Aave app/API")
    parser.add_argument("--out-csv", required=True, help="Output CSV path")
    parser.add_argument("--backup-existing", action="store_true", help="If out file exists, move it to *.bak first")
    args = parser.parse_args()

    src = Path(args.in_json)
    dst = Path(args.out_csv)
    if not src.exists():
        raise FileNotFoundError(f"Input JSON not found: {src}")

    payload = json.loads(src.read_text(encoding="utf-8"))
    values = payload.get("data", {}).get("value")
    if not isinstance(values, list):
        raise ValueError("JSON does not contain expected data.value array")

    rows: list[dict[str, object]] = []
    for item in values:
        if not isinstance(item, dict):
            continue
        ts = item.get("date")
        apr = item.get("value")
        if apr is None:
            avg_rate = item.get("avgRate", {})
            if isinstance(avg_rate, dict):
                apr = avg_rate.get("value")
        rows.append({"ts": ts, "borrow_apr": apr})

    out = pd.DataFrame(rows)
    out["ts"] = pd.to_datetime(out["ts"], utc=True, errors="coerce", format="mixed")
    out["borrow_apr"] = pd.to_numeric(out["borrow_apr"], errors="coerce")
    out = out.dropna(subset=["ts", "borrow_apr"]).sort_values("ts").drop_duplicates("ts", keep="last").reset_index(drop=True)
    if out.empty:
        raise RuntimeError("No valid rows found after parsing JSON")

    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() and args.backup_existing:
        backup = dst.with_suffix(dst.suffix + ".bak")
        dst.replace(backup)
        print(f"backup: {backup.resolve()}")

    out.to_csv(dst, index=False)
    print(f"saved: {dst.resolve()}")
    print(f"rows: {len(out)}")
    print(f"min ts: {out['ts'].min()} max ts: {out['ts'].max()}")
    print(f"borrow apr mean={out['borrow_apr'].mean():.6f}")


if __name__ == "__main__":
    main()
