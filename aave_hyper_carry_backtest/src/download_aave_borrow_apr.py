from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import requests


AAVE_API_URL = "https://aave-api-v2.aave.com/data/rates-history"
# Aave V3 Ethereum: USDC reserve id = assetAddress + poolAddressesProvider + chainId.
USDC_ASSET = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
USDT_ASSET = "0xdac17f958d2ee523a2206206994597c13d831ec7"
V3_ETH_PROVIDER = "0x2f39d218133afab8f2b819b1066c7e434ad94e9e"
CHAIN_ID = "1"


def _fetch_chunk(reserve_id: str, start_ts: pd.Timestamp, end_ts: pd.Timestamp, resolution_days: int) -> list[dict]:
    params = {
        "reserveId": reserve_id,
        "from": int(start_ts.timestamp()),
        "to": int(end_ts.timestamp()),
        "resolutionInDays": int(resolution_days),
    }
    data = requests.get(AAVE_API_URL, params=params, timeout=60).json()
    if not isinstance(data, list):
        raise RuntimeError(f"Unexpected response from Aave API: {data}")
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="Download Aave V3 Ethereum variable borrow APR history")
    parser.add_argument("--start", default="2025-02-23T19:00:00Z")
    parser.add_argument("--end", default="2026-02-23T19:00:00Z")
    parser.add_argument("--chunk-days", type=int, default=120)
    parser.add_argument("--resolution-days", type=int, default=1)
    parser.add_argument("--asset", default=USDC_ASSET, help="Underlying asset address (e.g. USDC/USDT)")
    parser.add_argument("--provider", default=V3_ETH_PROVIDER, help="Aave V3 poolAddressesProvider")
    parser.add_argument("--chain-id", default=CHAIN_ID, help="Chain id as string (default: 1)")
    parser.add_argument("--out", default="data/raw/aave_v3_eth_usdc_borrow_apr_1y.csv")
    args = parser.parse_args()

    start_ts = pd.Timestamp(args.start, tz="UTC")
    end_ts = pd.Timestamp(args.end, tz="UTC")
    reserve_id = args.asset.lower() + args.provider.lower() + str(args.chain_id)

    rows: list[dict] = []
    cur = start_ts
    step = pd.Timedelta(days=args.chunk_days)
    while cur < end_ts:
        nxt = min(cur + step, end_ts)
        chunk = _fetch_chunk(reserve_id, cur, nxt, args.resolution_days)
        rows.extend(chunk)
        print(f"chunk {cur} -> {nxt}: {len(chunk)} rows")
        cur = nxt

    if not rows:
        raise RuntimeError("No rows returned from Aave API")

    df = pd.DataFrame(rows)
    x = pd.json_normalize(df["x"])
    # API month is zero-based.
    ts = pd.to_datetime(
        dict(
            year=x["year"].astype(int),
            month=(x["month"].astype(int) + 1),
            day=x["date"].astype(int),
            hour=x.get("hours", pd.Series([0] * len(x))).astype(int),
        ),
        utc=True,
    )

    out = pd.DataFrame(
        {
            "ts": ts,
            "borrow_apr": df["variableBorrowRate_avg"].astype(float),
            "stable_borrow_apr": df["stableBorrowRate_avg"].astype(float),
            "utilization_rate": df["utilizationRate_avg"].astype(float),
            "liquidity_rate": df["liquidityRate_avg"].astype(float),
        }
    )
    out = out[(out["ts"] >= start_ts) & (out["ts"] <= end_ts)]
    out = out.sort_values("ts").drop_duplicates("ts", keep="last").reset_index(drop=True)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_path, index=False)

    print(f"saved: {out_path.resolve()}")
    print(f"rows: {len(out)}")
    print(f"min ts: {out['ts'].min()} max ts: {out['ts'].max()}")
    print(
        "borrow apr stats: "
        f"mean={out['borrow_apr'].mean():.6f} "
        f"median={out['borrow_apr'].median():.6f} "
        f"min={out['borrow_apr'].min():.6f} "
        f"max={out['borrow_apr'].max():.6f}"
    )
    print(f"asset={args.asset.lower()} provider={args.provider.lower()} chain_id={args.chain_id}")


if __name__ == "__main__":
    main()
