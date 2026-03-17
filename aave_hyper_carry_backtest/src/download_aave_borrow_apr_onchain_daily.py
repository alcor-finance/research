from __future__ import annotations

import argparse
import itertools
import time
from pathlib import Path

import pandas as pd
import requests


RAY = 10**27
DEFAULT_RPCS = [
    "https://mainnet.gateway.tenderly.co",
    "https://1rpc.io/eth",
]
DEFAULT_POOL = "0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2"  # Aave V3 Ethereum Pool
USDT = "0xdac17f958d2ee523a2206206994597c13d831ec7"
USDC = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
GET_RESERVE_DATA_SELECTOR = "35ea6a75"  # getReserveData(address)


def _rpc_call(
    session: requests.Session,
    rpc_urls: list[str],
    method: str,
    params: list,
    retries: int = 8,
    timeout: int = 20,
    sleep_sec: float = 0.0,
):
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    urls_cycle = itertools.cycle(rpc_urls)
    last_err: Exception | None = None
    for i in range(retries):
        url = next(urls_cycle)
        try:
            res = session.post(url, json=payload, timeout=timeout)
            res.raise_for_status()
            body = res.json()
            if "error" in body:
                raise RuntimeError(f"rpc error for {method}: {body['error']}")
            if sleep_sec > 0:
                time.sleep(sleep_sec)
            return body["result"]
        except Exception as err:  # noqa: BLE001
            last_err = err
            time.sleep(min(1.25 * (i + 1), 10))
    raise RuntimeError(f"RPC call failed: method={method} last_err={last_err}")


def _hex_to_int(value: str) -> int:
    return int(value, 16)


def _to_hex_block(block_number: int) -> str:
    return hex(int(block_number))


def _latest_block(session: requests.Session, rpc_urls: list[str], retries: int, timeout: int, sleep_sec: float) -> int:
    return _hex_to_int(_rpc_call(session, rpc_urls, "eth_blockNumber", [], retries=retries, timeout=timeout, sleep_sec=sleep_sec))


def _block_ts(
    session: requests.Session,
    rpc_urls: list[str],
    block_number: int,
    cache: dict[int, int],
    retries: int,
    timeout: int,
    sleep_sec: float,
) -> int:
    cached = cache.get(block_number)
    if cached is not None:
        return cached
    block = _rpc_call(
        session,
        rpc_urls,
        "eth_getBlockByNumber",
        [_to_hex_block(block_number), False],
        retries=retries,
        timeout=timeout,
        sleep_sec=sleep_sec,
    )
    ts = _hex_to_int(block["timestamp"])
    cache[block_number] = ts
    return ts


def _find_block_by_ts(
    session: requests.Session,
    rpc_urls: list[str],
    target_ts: int,
    lo: int,
    hi: int,
    cache: dict[int, int],
    retries: int,
    timeout: int,
    sleep_sec: float,
) -> int:
    # first block with timestamp >= target_ts
    ans = hi
    while lo <= hi:
        mid = (lo + hi) // 2
        mid_ts = _block_ts(session, rpc_urls, mid, cache, retries, timeout, sleep_sec)
        if mid_ts >= target_ts:
            ans = mid
            hi = mid - 1
        else:
            lo = mid + 1
    return ans


def _borrow_apr_at_block(
    session: requests.Session,
    rpc_urls: list[str],
    pool: str,
    asset: str,
    block_number: int,
    retries: int,
    timeout: int,
    sleep_sec: float,
) -> float:
    data = "0x" + GET_RESERVE_DATA_SELECTOR + asset.lower().replace("0x", "").rjust(64, "0")
    result = _rpc_call(
        session,
        rpc_urls,
        "eth_call",
        [{"to": pool, "data": data}, _to_hex_block(block_number)],
        retries=retries,
        timeout=timeout,
        sleep_sec=sleep_sec,
    )
    raw = result[2:]
    words = [raw[i : i + 64] for i in range(0, len(raw), 64)]
    if len(words) < 5:
        raise RuntimeError(f"Unexpected getReserveData output at block={block_number}")
    variable_borrow_rate_ray = int(words[4], 16)
    return float(variable_borrow_rate_ray) / float(RAY)


def main() -> None:
    parser = argparse.ArgumentParser(description="Download Aave variable borrow APR from on-chain getReserveData snapshots")
    parser.add_argument("--rpc-url", default=",".join(DEFAULT_RPCS), help="Comma-separated RPC URLs")
    parser.add_argument("--pool", default=DEFAULT_POOL)
    parser.add_argument("--asset", default=USDT)
    parser.add_argument("--start", default="2025-02-23T19:00:00Z")
    parser.add_argument("--end", default="2026-02-23T19:00:00Z")
    parser.add_argument("--step-hours", type=int, default=24, help="Sampling step in hours")
    parser.add_argument("--max-retries", type=int, default=10)
    parser.add_argument("--rpc-timeout", type=int, default=20)
    parser.add_argument("--request-sleep-ms", type=float, default=30.0)
    parser.add_argument("--out", default="data/raw/aave_v3_eth_usdt_borrow_apr_1y_onchain_daily.csv")
    args = parser.parse_args()

    session = requests.Session()
    rpc_urls = [u.strip() for u in str(args.rpc_url).split(",") if u.strip()]
    if not rpc_urls:
        raise ValueError("No rpc urls configured")

    retries = int(args.max_retries)
    timeout = int(args.rpc_timeout)
    sleep_sec = max(float(args.request_sleep_ms), 0.0) / 1000.0
    start_ts = int(pd.Timestamp(args.start, tz="UTC").timestamp())
    end_ts = int(pd.Timestamp(args.end, tz="UTC").timestamp())
    if end_ts <= start_ts:
        raise ValueError("end must be > start")

    print(f"RPC endpoints: {rpc_urls}", flush=True)
    latest = _latest_block(session, rpc_urls, retries, timeout, sleep_sec)
    block_ts_cache: dict[int, int] = {}
    latest_ts = _block_ts(session, rpc_urls, latest, block_ts_cache, retries, timeout, sleep_sec)
    if start_ts > latest_ts:
        raise RuntimeError("start timestamp is after chain latest timestamp")
    end_ts_eff = min(end_ts, latest_ts)

    # Build sample timestamps (UTC), inclusive of end if aligned.
    timeline = pd.date_range(
        start=pd.Timestamp(start_ts, unit="s", tz="UTC"),
        end=pd.Timestamp(end_ts_eff, unit="s", tz="UTC"),
        freq=f"{int(args.step_hours)}h",
        inclusive="both",
    )
    if timeline.empty:
        raise RuntimeError("No timestamps in requested timeline")

    print(
        f"Sampling {len(timeline)} points from {timeline.min()} to {timeline.max()} (step={args.step_hours}h)",
        flush=True,
    )

    # First timestamp: coarse lower guess ~3.5m blocks ~= ~1.3 years.
    lo = max(1, latest - 3_500_000)
    hi = latest

    rows: list[dict] = []
    for i, ts in enumerate(timeline):
        target_ts = int(ts.timestamp())
        block_number = _find_block_by_ts(
            session=session,
            rpc_urls=rpc_urls,
            target_ts=target_ts,
            lo=lo,
            hi=hi,
            cache=block_ts_cache,
            retries=retries,
            timeout=timeout,
            sleep_sec=sleep_sec,
        )
        apr = _borrow_apr_at_block(
            session=session,
            rpc_urls=rpc_urls,
            pool=str(args.pool),
            asset=str(args.asset),
            block_number=block_number,
            retries=retries,
            timeout=timeout,
            sleep_sec=sleep_sec,
        )
        rows.append({"ts": ts, "borrow_apr": apr, "block_number": int(block_number)})

        # Monotonic optimization for next timestamp.
        lo = block_number
        if i + 1 < len(timeline):
            next_target_ts = int(timeline[i + 1].timestamp())
            block_step_guess = int(max(next_target_ts - target_ts, 3600) / 11.5)
            hi = min(latest, block_number + max(block_step_guess * 3, 20_000))
            hi_ts = _block_ts(session, rpc_urls, hi, block_ts_cache, retries, timeout, sleep_sec)
            while hi < latest and hi_ts < next_target_ts:
                lo_expand = hi
                hi = min(latest, hi + max((hi - lo_expand) * 2, 50_000))
                hi_ts = _block_ts(session, rpc_urls, hi, block_ts_cache, retries, timeout, sleep_sec)

        if (i + 1) % 20 == 0 or i == len(timeline) - 1:
            print(
                f"progress {i + 1}/{len(timeline)} ts={ts} block={block_number} apr={apr:.4%}",
                flush=True,
            )

    out = pd.DataFrame(rows).sort_values("ts").drop_duplicates("ts", keep="last").reset_index(drop=True)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_path, index=False)

    print(f"saved: {out_path.resolve()}", flush=True)
    print(f"rows: {len(out)}", flush=True)
    print(f"min ts: {out['ts'].min()} max ts: {out['ts'].max()}", flush=True)
    print(
        f"borrow apr mean={out['borrow_apr'].mean():.6f} "
        f"median={out['borrow_apr'].median():.6f} "
        f"min={out['borrow_apr'].min():.6f} "
        f"max={out['borrow_apr'].max():.6f}",
        flush=True,
    )


if __name__ == "__main__":
    main()
