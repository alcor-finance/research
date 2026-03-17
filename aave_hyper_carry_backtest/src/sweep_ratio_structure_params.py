from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd

from aave_hyper_carry_backtest.backtest.context import BacktestContext
from aave_hyper_carry_backtest.backtest.engine import BacktestEngine
from aave_hyper_carry_backtest.backtest.recorder import Recorder
from aave_hyper_carry_backtest.config.schema import load_config
from aave_hyper_carry_backtest.data.datasets import build_dataset
from aave_hyper_carry_backtest.market.data import HistoricalMarketData
from aave_hyper_carry_backtest.strategy.carry_trade import AaveHyperCarryStrategy


def _parse_range(expr: str) -> list[float]:
    raw = expr.strip()
    if not raw:
        raise ValueError("Empty range expression")
    if ":" not in raw:
        return [float(x.strip()) for x in raw.split(",") if x.strip()]

    parts = [x.strip() for x in raw.split(":")]
    if len(parts) != 3:
        raise ValueError(f"Range must be start:end:step, got: {expr}")
    try:
        start = Decimal(parts[0])
        end = Decimal(parts[1])
        step = Decimal(parts[2])
    except InvalidOperation as exc:
        raise ValueError(f"Invalid numeric range: {expr}") from exc
    if step <= 0:
        raise ValueError(f"Range step must be > 0: {expr}")
    if end < start:
        raise ValueError(f"Range end must be >= start: {expr}")

    out: list[float] = []
    cur = start
    tol = Decimal("1e-12")
    while cur <= end + tol:
        out.append(float(cur))
        cur += step
    return out


def _run_id(prefix: str = "ratio_param_sweep") -> str:
    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    return f"{ts}_{prefix}"


def _make_strategy(cfg) -> AaveHyperCarryStrategy:
    return AaveHyperCarryStrategy(
        target_leverage=cfg.strategy.target_leverage,
        hedge_ratio=cfg.strategy.hedge_ratio,
        use_ratio_structure=cfg.strategy.use_ratio_structure,
        overlay_borrow_ratio=cfg.strategy.overlay_borrow_ratio,
        hyper_borrow_ratio=cfg.strategy.hyper_borrow_ratio,
        hyper_short_leverage=cfg.strategy.hyper_short_leverage,
        setup_cost_rate=cfg.strategy.setup_cost_rate,
        close_cost_rate=cfg.strategy.close_cost_rate,
        timing_enabled=cfg.strategy.timing_enabled,
        timing_window_events=cfg.strategy.timing_window_events,
        enter_edge_apr=cfg.strategy.enter_edge_apr,
        exit_edge_apr=cfg.strategy.exit_edge_apr,
        carry_max_payback_hours=cfg.strategy.carry_max_payback_hours,
        min_hold_funding_events=cfg.strategy.min_hold_funding_events,
        default_funding_interval_hours=cfg.strategy.default_funding_interval_hours,
        non_carry_mode=cfg.strategy.non_carry_mode,
        long_perp_exposure_ratio=cfg.strategy.long_perp_exposure_ratio,
        long_perp_enter_funding_apr=cfg.strategy.long_perp_enter_funding_apr,
        long_perp_exit_funding_apr=cfg.strategy.long_perp_exit_funding_apr,
    )


def _render_table(df: pd.DataFrame, cols: list[str], n: int = 12) -> str:
    show = df[cols].head(n).copy()
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in show.iterrows():
        vals = []
        for c in cols:
            v = row[c]
            if isinstance(v, float):
                vals.append(f"{v:.6f}")
            else:
                vals.append(str(v))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Large sweep over ratio-structure params (overlay borrow / stable borrow / short leverage)")
    parser.add_argument("--config", required=True, help="Base config YAML")
    parser.add_argument("--overlay-range", default="0.20:1.20:0.05", help="overlay_borrow_ratio range start:end:step")
    parser.add_argument("--hyper-range", default="0.05:0.45:0.05", help="hyper_borrow_ratio range start:end:step")
    parser.add_argument("--leverage-range", default="1.00:4.00:0.25", help="hyper_short_leverage range start:end:step")
    parser.add_argument("--max-total-borrow", type=float, default=1.20, help="Filter: overlay + hyper <= this value")
    parser.add_argument("--top-k", type=int, default=20, help="Top rows to include in report sections")
    parser.add_argument("--out-dir", default="", help="Output dir; default results/<timestamp>_ratio_param_sweep")
    args = parser.parse_args()

    cfg = load_config(Path(args.config))
    cfg.strategy.use_ratio_structure = True

    if args.out_dir:
        out_dir = Path(args.out_dir)
    else:
        out_dir = Path(cfg.results.results_dir) / _run_id()
    out_dir.mkdir(parents=True, exist_ok=True)

    overlay_vals = _parse_range(args.overlay_range)
    hyper_vals = _parse_range(args.hyper_range)
    lev_vals = _parse_range(args.leverage_range)

    combos: list[tuple[float, float, float]] = []
    for ov in overlay_vals:
        for hy in hyper_vals:
            if ov + hy > float(args.max_total_borrow):
                continue
            for lev in lev_vals:
                combos.append((float(ov), float(hy), float(lev)))
    if not combos:
        raise RuntimeError("No parameter combinations after filters")

    dataset = build_dataset(cfg)
    market_data = HistoricalMarketData(dataset)
    start_t = datetime.now(UTC)

    rows: list[dict] = []
    total = len(combos)
    for i, (ov, hy, lev) in enumerate(combos, start=1):
        cfg.strategy.overlay_borrow_ratio = ov
        cfg.strategy.hyper_borrow_ratio = hy
        cfg.strategy.hyper_short_leverage = lev

        strategy = _make_strategy(cfg)
        recorder = Recorder(save_equity=False, save_funding=False, save_borrow=False)
        ctx = BacktestContext(config=cfg, market_data=market_data, strategy=strategy, recorder=recorder)
        summary = BacktestEngine(ctx=ctx).run()

        funding_weight = hy * lev * cfg.strategy.hedge_ratio
        borrow_weight = ov + hy
        rows.append(
            {
                "overlay_borrow_ratio": ov,
                "hyper_borrow_ratio": hy,
                "hyper_short_leverage": lev,
                "funding_weight": funding_weight,
                "borrow_weight": borrow_weight,
                **summary,
            }
        )

        if i % 150 == 0 or i == total:
            elapsed = (datetime.now(UTC) - start_t).total_seconds()
            print(f"progress {i}/{total} ({100.0 * i / total:.1f}%) elapsed={elapsed:.1f}s", flush=True)

    df = pd.DataFrame(rows)
    df = df.sort_values(["end_equity", "net_carry_pnl"], ascending=[False, False]).reset_index(drop=True)

    csv_path = out_dir / "grid_results.csv"
    parquet_path = out_dir / "grid_results.parquet"
    summary_path = out_dir / "summary.json"
    report_path = out_dir / "report.md"

    df.to_csv(csv_path, index=False)
    df.to_parquet(parquet_path, index=False)

    top_end = df.sort_values("end_equity", ascending=False).head(args.top_k).reset_index(drop=True)
    top_carry = df.sort_values("net_carry_pnl", ascending=False).head(args.top_k).reset_index(drop=True)
    safe = df[df["min_health_factor"] >= 1.15].copy()
    top_safe = safe.sort_values("end_equity", ascending=False).head(args.top_k).reset_index(drop=True) if not safe.empty else safe

    best_row = top_end.iloc[0].to_dict()
    meta = {
        "grid_size": int(total),
        "tested": int(len(df)),
        "overlay_range": args.overlay_range,
        "hyper_range": args.hyper_range,
        "leverage_range": args.leverage_range,
        "max_total_borrow": float(args.max_total_borrow),
        "base_config": str(Path(args.config).resolve()),
        "best_by_end_equity": best_row,
        "generated_at_utc": datetime.now(UTC).isoformat(),
    }
    summary_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    table_cols = [
        "overlay_borrow_ratio",
        "hyper_borrow_ratio",
        "hyper_short_leverage",
        "funding_weight",
        "borrow_weight",
        "carry_entries",
        "net_carry_pnl",
        "end_equity",
        "max_ltv",
        "min_health_factor",
    ]
    lines = [
        "# Ratio Structure Parameter Sweep",
        "",
        "## Setup",
        f"- Base config: `{Path(args.config).resolve()}`",
        f"- Grid size tested: **{len(df)}**",
        f"- overlay range: `{args.overlay_range}`",
        f"- hyper range: `{args.hyper_range}`",
        f"- leverage range: `{args.leverage_range}`",
        f"- filter: `overlay + hyper <= {args.max_total_borrow}`",
        "",
        "## Top by End Equity",
        _render_table(top_end, table_cols, n=args.top_k),
        "",
        "## Top by Net Carry PnL",
        _render_table(top_carry, table_cols, n=args.top_k),
    ]
    if not top_safe.empty:
        lines += [
            "",
            "## Top by End Equity (Safety Filter: min_health_factor >= 1.15)",
            _render_table(top_safe, table_cols, n=args.top_k),
        ]

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"saved: {out_dir.resolve()}")
    print(f"best end_equity: {best_row['end_equity']:.2f}")
    print(
        f"best params: overlay={best_row['overlay_borrow_ratio']:.3f} "
        f"hyper={best_row['hyper_borrow_ratio']:.3f} "
        f"lev={best_row['hyper_short_leverage']:.3f}"
    )


if __name__ == "__main__":
    main()
