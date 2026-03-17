from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

from aave_hyper_carry_backtest.config.schema import load_config


def _run_id() -> str:
    return datetime.now(UTC).strftime("%Y%m%d_%H%M%S_market_overlay")


def _load_table(path: Path) -> pd.DataFrame:
    if str(path).lower().endswith(".parquet"):
        return pd.read_parquet(path)
    return pd.read_csv(path)


def _carry_weights(cfg) -> tuple[float, float, float, float]:
    if cfg.strategy.use_ratio_structure:
        overlay_weight = float(cfg.strategy.overlay_borrow_ratio)
        funding_weight = abs(
            float(cfg.strategy.hyper_borrow_ratio)
            * float(cfg.strategy.hyper_short_leverage)
            * float(cfg.strategy.hedge_ratio)
        )
        borrow_weight = float(cfg.strategy.overlay_borrow_ratio) + float(cfg.strategy.hyper_borrow_ratio)
        setup_cost_weight = borrow_weight
        close_cost_weight = overlay_weight + funding_weight
        return funding_weight, borrow_weight, setup_cost_weight, close_cost_weight

    overlay_long_btc = max(float(cfg.strategy.target_leverage) - 1.0, 0.0)
    funding_weight = overlay_long_btc * float(cfg.strategy.hedge_ratio)
    borrow_weight = overlay_long_btc
    setup_cost_weight = borrow_weight
    close_cost_weight = overlay_long_btc + abs(funding_weight)
    return funding_weight, borrow_weight, setup_cost_weight, close_cost_weight


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot BTC price + funding APR + borrow APR overlay")
    parser.add_argument("--config", required=True)
    parser.add_argument("--out-dir", default="")
    parser.add_argument("--funding-window-events", type=int, default=9)
    args = parser.parse_args()

    cfg = load_config(args.config)
    if args.out_dir:
        out_dir = Path(args.out_dir)
    else:
        out_dir = Path(cfg.results.results_dir) / _run_id()
    out_dir.mkdir(parents=True, exist_ok=True)

    spot = _load_table(cfg.data.spot_path)[[cfg.data.spot_ts_col, cfg.data.spot_price_col]].copy()
    spot.columns = ["ts", "spot_mid"]
    spot["ts"] = pd.to_datetime(spot["ts"], utc=True, format="mixed")
    spot = spot.sort_values("ts").drop_duplicates("ts", keep="last")
    spot = spot[(spot["ts"] >= cfg.start_ts) & (spot["ts"] <= cfg.end_ts)].copy()

    funding = _load_table(cfg.data.funding_path)[[cfg.data.funding_ts_col, cfg.data.funding_rate_col]].copy()
    funding.columns = ["funding_ts", "funding_rate"]
    funding["funding_ts"] = pd.to_datetime(funding["funding_ts"], utc=True, format="mixed").dt.round(cfg.bar_step)
    funding = funding.sort_values("funding_ts").drop_duplicates("funding_ts", keep="last")
    funding = funding[(funding["funding_ts"] >= cfg.start_ts) & (funding["funding_ts"] <= cfg.end_ts)].copy()
    if funding.empty:
        raise ValueError("No funding rows in selected range")

    dt_hours = 8.0
    if len(funding) > 1:
        diffs = funding["funding_ts"].diff().dt.total_seconds().dropna() / 3600.0
        if not diffs.empty:
            dt_hours = float(diffs.median())
    funding["funding_apr"] = funding["funding_rate"].astype(float) * (8760.0 / dt_hours)
    funding["rolling_funding_apr"] = funding["funding_apr"].rolling(args.funding_window_events, min_periods=1).mean()

    if cfg.data.borrow_apr_path:
        borrow = _load_table(cfg.data.borrow_apr_path)[[cfg.data.borrow_apr_ts_col, cfg.data.borrow_apr_col]].copy()
        borrow.columns = ["ts", "borrow_apr"]
        borrow["ts"] = pd.to_datetime(borrow["ts"], utc=True, format="mixed")
        borrow = borrow.sort_values("ts").drop_duplicates("ts", keep="last")
        borrow = borrow[(borrow["ts"] >= cfg.start_ts) & (borrow["ts"] <= cfg.end_ts)].copy()
    else:
        borrow = pd.DataFrame(columns=["ts", "borrow_apr"])

    # Align price and borrow to funding timestamps for readable overlay.
    f = funding[["funding_ts", "funding_apr", "rolling_funding_apr"]].rename(columns={"funding_ts": "ts"}).sort_values("ts")
    merged = pd.merge_asof(f, spot[["ts", "spot_mid"]].sort_values("ts"), on="ts", direction="backward")
    if borrow.empty:
        merged["borrow_apr"] = float(cfg.strategy.aave_borrow_apr)
    else:
        # Match backtest timing: funding at ts uses borrow APR known at previous bar (prev_ts), not current ts.
        bar_delta = pd.to_timedelta(cfg.bar_step)
        merged["borrow_lookup_ts"] = merged["ts"] - bar_delta
        borrow_lookup = borrow[["ts", "borrow_apr"]].rename(columns={"ts": "borrow_ts"}).sort_values("borrow_ts")
        merged = pd.merge_asof(
            merged.sort_values("borrow_lookup_ts"),
            borrow_lookup,
            left_on="borrow_lookup_ts",
            right_on="borrow_ts",
            direction="backward",
        ).sort_values("ts")
        merged = merged.drop(columns=["borrow_lookup_ts", "borrow_ts"])
        merged["borrow_apr"] = merged["borrow_apr"].fillna(float(cfg.strategy.aave_borrow_apr))

    funding_weight, borrow_weight, setup_cost_weight, close_cost_weight = _carry_weights(cfg)
    dt_year = dt_hours / 8760.0
    merged["edge_apr"] = funding_weight * merged["funding_apr"] - borrow_weight * merged["borrow_apr"]
    merged["rolling_edge_apr"] = funding_weight * merged["rolling_funding_apr"] - borrow_weight * merged["borrow_apr"]
    merged["edge_ret_event"] = merged["edge_apr"] * dt_year

    roundtrip_cost_rate = max(float(cfg.strategy.setup_cost_rate), 0.0) + max(float(cfg.strategy.close_cost_rate), 0.0)
    max_payback_hours = max(float(cfg.strategy.carry_max_payback_hours), 0.0)

    active_pre: list[bool] = []
    signal_active: list[bool] = []
    entry_event: list[bool] = []
    exit_event: list[bool] = []

    active = not bool(cfg.strategy.timing_enabled)
    hold_events = 0

    for _, row in merged.iterrows():
        pre = bool(active)
        active_pre.append(pre)
        entry = False
        exit_ = False

        edge = float(row["rolling_edge_apr"])
        if pre:
            hold_events += 1

        if cfg.strategy.timing_enabled:
            if pre and hold_events >= int(cfg.strategy.min_hold_funding_events) and edge <= float(cfg.strategy.exit_edge_apr):
                exit_ = True
                active = False
                hold_events = 0

            if edge > 0.0:
                payback_hours = roundtrip_cost_rate * (8760.0 / edge) if roundtrip_cost_rate > 0.0 else 0.0
            else:
                payback_hours = float("inf")

            can_enter = (
                (not active)
                and (edge >= float(cfg.strategy.enter_edge_apr))
                and (payback_hours <= max_payback_hours)
            )
            if can_enter:
                entry = True
                active = True
                hold_events = 0

        signal_active.append(bool(active))
        entry_event.append(entry)
        exit_event.append(exit_)

    merged["active_pre_event"] = pd.Series(active_pre, index=merged.index, dtype=bool)
    merged["signal_active"] = pd.Series(signal_active, index=merged.index, dtype=bool)
    merged["entry_event"] = pd.Series(entry_event, index=merged.index, dtype=bool)
    merged["exit_event"] = pd.Series(exit_event, index=merged.index, dtype=bool)

    setup_cost_ret = setup_cost_weight * max(float(cfg.strategy.setup_cost_rate), 0.0)
    close_cost_ret = close_cost_weight * max(float(cfg.strategy.close_cost_rate), 0.0)
    merged["operation_cost_ret"] = (
        merged["entry_event"].astype(float) * setup_cost_ret + merged["exit_event"].astype(float) * close_cost_ret
    )
    if not cfg.strategy.timing_enabled and len(merged) > 0:
        merged.loc[merged.index[0], "operation_cost_ret"] += setup_cost_ret

    merged["strategy_ret_event_gross"] = merged["edge_ret_event"].where(merged["active_pre_event"], 0.0)
    merged["strategy_ret_event_net"] = merged["strategy_ret_event_gross"] - merged["operation_cost_ret"]
    merged["cum_strategy_return_gross"] = merged["strategy_ret_event_gross"].cumsum()
    merged["cum_strategy_return_net"] = merged["strategy_ret_event_net"].cumsum()
    merged["cum_always_return"] = merged["edge_ret_event"].cumsum() - setup_cost_ret

    merged.to_parquet(out_dir / "market_overlay_series.parquet", index=False)

    fig, (ax_top, ax_bot) = plt.subplots(2, 1, figsize=(14, 9), sharex=True, gridspec_kw={"height_ratios": [2.0, 1.2]})

    ax_price = ax_top
    ax_apr = ax_top.twinx()
    ax_price.plot(merged["ts"], merged["spot_mid"], color="#111111", linewidth=1.2, label="BTC spot price (USD)")
    ax_apr.plot(
        merged["ts"], merged["rolling_funding_apr"] * 100.0, color="#1f77b4", linewidth=1.2, label=f"Funding APR (rolling {args.funding_window_events})"
    )
    ax_apr.plot(merged["ts"], merged["borrow_apr"] * 100.0, color="#d62728", linewidth=1.2, linestyle="--", label="Borrow APR")
    ax_apr.fill_between(
        merged["ts"],
        merged["rolling_funding_apr"] * 100.0,
        merged["borrow_apr"] * 100.0,
        where=(merged["rolling_edge_apr"] > 0.0),
        color="#2ca02c",
        alpha=0.18,
        label="Rolling edge > 0",
    )
    ax_price.set_ylabel("BTC price, USD")
    ax_apr.set_ylabel("APR, %")
    ax_price.set_title("BTC Price vs Funding APR and Borrow APR")
    ax_price.grid(True, linestyle=":", linewidth=0.6, alpha=0.7)
    lines_l, labels_l = ax_price.get_legend_handles_labels()
    lines_r, labels_r = ax_apr.get_legend_handles_labels()
    ax_apr.legend(lines_l + lines_r, labels_l + labels_r, loc="upper left", fontsize=9)

    ax_bot.plot(
        merged["ts"],
        merged["cum_strategy_return_net"] * 100.0,
        color="#2ca02c",
        linewidth=1.4,
        label="Cumulative return (net): active when rolling funding > borrow",
    )
    ax_bot.plot(
        merged["ts"],
        merged["cum_strategy_return_gross"] * 100.0,
        color="#17becf",
        linewidth=1.0,
        linestyle=":",
        label="Cumulative return (gross): signal strategy",
    )
    ax_bot.plot(
        merged["ts"],
        merged["cum_always_return"] * 100.0,
        color="#d62728",
        linewidth=1.0,
        linestyle="--",
        label="Cumulative return: always active",
    )
    ax_bot.axhline(0.0, color="#333333", linestyle="--", linewidth=0.8)
    ax_bot.set_ylabel("Return, %")
    ax_bot.set_title("Cumulative Carry Return by Rolling Signal")
    ax_bot.grid(True, linestyle=":", linewidth=0.6, alpha=0.7)
    ax_bot.legend(loc="upper left", fontsize=9)
    ax_bot.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    ax_bot.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))

    fig.tight_layout()
    fig.savefig(out_dir / "market_overlay.png", dpi=180)
    plt.close(fig)

    print(f"Saved overlay to: {out_dir.resolve()}")
    print(f"rows={len(merged)}; min_ts={merged['ts'].min()} max_ts={merged['ts'].max()}")
    print(f"mean_funding_apr={merged['funding_apr'].mean():.6f} mean_borrow_apr={merged['borrow_apr'].mean():.6f}")
    print(
        f"strategy_final_return_net={merged['cum_strategy_return_net'].iloc[-1]:.6f} "
        f"strategy_final_return_gross={merged['cum_strategy_return_gross'].iloc[-1]:.6f} "
        f"always_final_return={merged['cum_always_return'].iloc[-1]:.6f}"
    )
    print(
        f"entries={int(merged['entry_event'].sum())} exits={int(merged['exit_event'].sum())} "
        f"operation_cost_total={merged['operation_cost_ret'].sum():.6f}"
    )


if __name__ == "__main__":
    main()
