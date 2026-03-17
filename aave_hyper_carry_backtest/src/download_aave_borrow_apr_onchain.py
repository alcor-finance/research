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
# keccak("ReserveDataUpdated(address,uint256,uint256,uint256,uint256,uint256)")
RESERVE_DATA_UPDATED_TOPIC0 = "0x804c9b842b2748a22bb64b345453a3de7ca54a6ca45ce00d415894979e22897a"


def _rpc_call(
    session: requests.Session,
    rpc_urls: list[str],
    method: str,
    params: list,
    retries: int = 8,
    timeout: int = 18,
    sleep_sec: float = 0.0,
):
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    last_err = None
    urls_cycle = itertools.cycle(rpc_urls)
    for i in range(retries):
        rpc_url = next(urls_cycle)
        try:
            res = session.post(rpc_url, json=payload, timeout=timeout)
            res.raise_for_status()
            body = res.json()
            if "error" in body:
                raise RuntimeError(f"rpc error for {method}: {body['error']}")
            if sleep_sec > 0:
                time.sleep(sleep_sec)
            return body["result"]
        except Exception as err:  # noqa: BLE001
            last_err = err
            # Exponential-ish backoff for rate limits / transient resets.
            time.sleep(min(1.5 * (i + 1), 10))
    raise RuntimeError(f"RPC call failed after retries: {method}; last_err={last_err}")


def _hex_to_int(value: str) -> int:
    return int(value, 16)


def _to_hex_block(n: int) -> str:
    return hex(int(n))


def _block_ts(
    session: requests.Session,
    rpc_urls: list[str],
    block_number: int,
    retries: int = 8,
    timeout: int = 18,
    sleep_sec: float = 0.0,
) -> int:
    block = _rpc_call(
        session,
        rpc_urls,
        "eth_getBlockByNumber",
        [_to_hex_block(block_number), False],
        retries=retries,
        timeout=timeout,
        sleep_sec=sleep_sec,
    )
    return _hex_to_int(block["timestamp"])


def _latest_block(
    session: requests.Session,
    rpc_urls: list[str],
    retries: int = 8,
    timeout: int = 18,
    sleep_sec: float = 0.0,
) -> int:
    return _hex_to_int(_rpc_call(session, rpc_urls, "eth_blockNumber", [], retries=retries, timeout=timeout, sleep_sec=sleep_sec))


def _find_block_by_ts(
    session: requests.Session,
    rpc_urls: list[str],
    target_ts: int,
    lo: int,
    hi: int,
    retries: int = 8,
    timeout: int = 18,
    sleep_sec: float = 0.0,
) -> int:
    # Returns first block with timestamp >= target_ts.
    ans = hi
    step = 0
    while lo <= hi:
        mid = (lo + hi) // 2
        ts = _block_ts(session, rpc_urls, mid, retries=retries, timeout=timeout, sleep_sec=sleep_sec)
        if ts >= target_ts:
            ans = mid
            hi = mid - 1
        else:
            lo = mid + 1
        step += 1
        if step % 8 == 0:
            print(f"  binary-search step={step} lo={lo} hi={hi}", flush=True)
    return ans


def _block_ts_batch(
    session: requests.Session,
    rpc_urls: list[str],
    block_numbers: list[int],
    batch_size: int = 20,
    retries: int = 8,
    timeout: int = 25,
    sleep_sec: float = 0.0,
) -> dict[int, int]:
    out: dict[int, int] = {}
    if not block_numbers:
        return out
    urls_cycle = itertools.cycle(rpc_urls)
    for i in range(0, len(block_numbers), batch_size):
        chunk = block_numbers[i : i + batch_size]
        payload = [
            {"jsonrpc": "2.0", "id": j, "method": "eth_getBlockByNumber", "params": [_to_hex_block(b), False]}
            for j, b in enumerate(chunk, start=1)
        ]
        last_err = None
        for attempt in range(retries):
            rpc_url = next(urls_cycle)
            try:
                res = session.post(rpc_url, json=payload, timeout=timeout)
                res.raise_for_status()
                arr = res.json()
                if not isinstance(arr, list):
                    raise RuntimeError("batch response is not list")
                by_id = {item["id"]: item for item in arr if "id" in item}
                for j, b in enumerate(chunk, start=1):
                    item = by_id.get(j)
                    if not item or "error" in item:
                        raise RuntimeError(f"bad batch item id={j} err={item.get('error') if item else 'missing'}")
                    out[b] = _hex_to_int(item["result"]["timestamp"])
                if sleep_sec > 0:
                    time.sleep(sleep_sec)
                break
            except Exception as err:  # noqa: BLE001
                last_err = err
                time.sleep(min(1.5 * (attempt + 1), 10))
        else:
            # Fallback: fetch block timestamps one-by-one for this chunk.
            for b in chunk:
                out[b] = _block_ts(
                    session,
                    rpc_urls,
                    b,
                    retries=retries,
                    timeout=timeout,
                    sleep_sec=sleep_sec,
                )
            print(
                f"  fallback serial block-ts for chunk {chunk[0]}-{chunk[-1]} after batch failures ({last_err})",
                flush=True,
            )
    return out


def _topic_for_address(addr: str) -> str:
    return "0x" + addr.lower().replace("0x", "").rjust(64, "0")


def _decode_variable_borrow_rate(data_hex: str) -> float:
    # ReserveDataUpdated(address indexed reserve, uint256 liquidityRate, uint256 stableBorrowRate,
    #                    uint256 variableBorrowRate, uint256 liquidityIndex, uint256 variableBorrowIndex)
    raw = data_hex[2:]
    words = [raw[i : i + 64] for i in range(0, len(raw), 64)]
    if len(words) < 3:
        raise ValueError("Unexpected ReserveDataUpdated payload")
    variable_borrow_rate_ray = int(words[2], 16)
    return float(variable_borrow_rate_ray) / float(RAY)


def main() -> None:
    parser = argparse.ArgumentParser(description="Download Aave borrow APR from on-chain ReserveDataUpdated events")
    parser.add_argument(
        "--rpc-url",
        default=",".join(DEFAULT_RPCS),
        help="Comma-separated RPC URLs; first responsive is used each request in round-robin",
    )
    parser.add_argument("--pool", default=DEFAULT_POOL, help="Aave V3 Pool contract")
    parser.add_argument("--asset", default=USDT, help="Reserve underlying asset address (USDT/USDC...)")
    parser.add_argument("--start", default="2025-02-23T19:00:00Z")
    parser.add_argument("--end", default="2026-02-23T19:00:00Z")
    parser.add_argument("--from-block", type=int, default=0, help="Optional explicit from block; skip block-by-time search")
    parser.add_argument("--to-block", type=int, default=0, help="Optional explicit to block; 0 means latest")
    parser.add_argument("--chunk-blocks", type=int, default=5000)
    parser.add_argument("--block-ts-batch-size", type=int, default=20)
    parser.add_argument("--max-retries", type=int, default=10)
    parser.add_argument("--rpc-timeout", type=int, default=18)
    parser.add_argument("--request-sleep-ms", type=float, default=40.0)
    parser.add_argument("--out", default="data/raw/aave_v3_eth_usdt_borrow_apr_1y_onchain.csv")
    args = parser.parse_args()

    session = requests.Session()
    rpc_urls = [u.strip() for u in str(args.rpc_url).split(",") if u.strip()]
    if not rpc_urls:
        raise ValueError("No rpc urls configured")
    start_ts = int(pd.Timestamp(args.start, tz="UTC").timestamp())
    end_ts = int(pd.Timestamp(args.end, tz="UTC").timestamp())
    request_sleep_sec = max(float(args.request_sleep_ms), 0.0) / 1000.0

    print(f"RPC endpoints: {rpc_urls}", flush=True)
    latest = _latest_block(
        session,
        rpc_urls,
        retries=int(args.max_retries),
        timeout=int(args.rpc_timeout),
        sleep_sec=request_sleep_sec,
    )
    latest_ts = _block_ts(
        session,
        rpc_urls,
        latest,
        retries=int(args.max_retries),
        timeout=int(args.rpc_timeout),
        sleep_sec=request_sleep_sec,
    )
    if start_ts > latest_ts:
        raise RuntimeError("start timestamp is after chain latest timestamp")
    end_ts_eff = min(end_ts, latest_ts)

    if args.from_block > 0:
        start_block = int(args.from_block)
        end_block = int(args.to_block) if args.to_block > 0 else latest
        print(
            "Using explicit block range "
            f"{start_block} -> {end_block} "
            f"for ts target {pd.Timestamp(start_ts, unit='s', tz='UTC')} -> {pd.Timestamp(end_ts_eff, unit='s', tz='UTC')}"
            ,
            flush=True,
        )
    else:
        # lower bound: estimate older block then binary search
        lo_guess = max(1, latest - 3_500_000)
        print(
            f"Finding start/end blocks for ts range {pd.Timestamp(start_ts, unit='s', tz='UTC')} -> {pd.Timestamp(end_ts_eff, unit='s', tz='UTC')}",
            flush=True,
        )
        start_block = _find_block_by_ts(
            session,
            rpc_urls,
            start_ts,
            lo_guess,
            latest,
            retries=int(args.max_retries),
            timeout=int(args.rpc_timeout),
            sleep_sec=request_sleep_sec,
        )
        end_block = _find_block_by_ts(
            session,
            rpc_urls,
            end_ts_eff,
            start_block,
            latest,
            retries=int(args.max_retries),
            timeout=int(args.rpc_timeout),
            sleep_sec=request_sleep_sec,
        )
        print(f"Block range: {start_block} -> {end_block}", flush=True)

    topic0 = RESERVE_DATA_UPDATED_TOPIC0
    topic1 = _topic_for_address(args.asset)
    total_blocks = end_block - start_block + 1
    print(
        f"Fetching ReserveDataUpdated logs for asset={args.asset} in {total_blocks} blocks with chunk={args.chunk_blocks}",
        flush=True,
    )

    rows: list[dict] = []
    block = start_block
    while block <= end_block:
        to_block = min(block + args.chunk_blocks - 1, end_block)
        params = [
            {
                "address": args.pool,
                "fromBlock": _to_hex_block(block),
                "toBlock": _to_hex_block(to_block),
                "topics": [topic0, topic1],
            }
        ]
        logs = _rpc_call(
            session,
            rpc_urls,
            "eth_getLogs",
            params,
            retries=int(args.max_retries),
            timeout=max(int(args.rpc_timeout), 25),
            sleep_sec=request_sleep_sec,
        )
        if logs:
            uniq_blocks = sorted({_hex_to_int(log["blockNumber"]) for log in logs})
            ts_map = _block_ts_batch(
                session,
                rpc_urls,
                uniq_blocks,
                batch_size=max(1, int(args.block_ts_batch_size)),
                retries=int(args.max_retries),
                timeout=max(int(args.rpc_timeout), 25),
                sleep_sec=request_sleep_sec,
            )
            for log in logs:
                bnum = _hex_to_int(log["blockNumber"])
                ts = pd.Timestamp(ts_map[bnum], unit="s", tz="UTC")
                borrow_apr = _decode_variable_borrow_rate(log["data"])
                rows.append(
                    {
                        "ts": ts,
                        "borrow_apr": borrow_apr,
                        "block_number": bnum,
                        "tx_hash": log["transactionHash"],
                        "log_index": _hex_to_int(log["logIndex"]),
                    }
                )
        print(f"blocks {block}-{to_block}: logs={len(logs)}", flush=True)
        block = to_block + 1

    if not rows:
        raise RuntimeError("No ReserveDataUpdated rows for selected asset/range")

    out = pd.DataFrame(rows).sort_values(["ts", "block_number", "log_index"]).drop_duplicates("ts", keep="last").reset_index(drop=True)
    out = out[(out["ts"] >= pd.Timestamp(start_ts, unit="s", tz="UTC")) & (out["ts"] <= pd.Timestamp(end_ts_eff, unit="s", tz="UTC"))]

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
