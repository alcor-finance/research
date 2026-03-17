from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

from aave_hyper_carry_backtest.utils.io import atomic_write_parquet


def _regime_spans(equity: pd.DataFrame) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    if "carry_active" not in equity.columns or equity.empty:
        return []
    mode = equity["carry_active"].astype(int)
    starts = equity.loc[(mode == 1) & (mode.shift(fill_value=0) == 0), "ts"]
    ends = equity.loc[(mode == 1) & (mode.shift(-1, fill_value=0) == 0), "ts"]
    return list(zip(starts, ends))


def _operation_ledger(funding: pd.DataFrame, borrow: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, Any]] = []

    if not funding.empty:
        for row in funding.itertuples(index=False):
            cashflow = float(row.cashflow)
            if cashflow == 0.0:
                continue
            records.append(
                {
                    "ts": row.ts,
                    "operation": "funding",
                    "cashflow_usd": cashflow,
                    "rate": float(row.rate),
                    "apr": pd.NA,
                }
            )

    if not borrow.empty:
        for row in borrow.itertuples(index=False):
            records.append(
                {
                    "ts": row.ts,
                    "operation": "borrow_interest",
                    "cashflow_usd": -float(row.interest_usd),
                    "rate": pd.NA,
                    "apr": float(row.apr),
                }
            )

    ledger = pd.DataFrame(records)
    if ledger.empty:
        return ledger
    ledger["ts"] = pd.to_datetime(ledger["ts"], utc=True)
    return ledger.sort_values("ts").reset_index(drop=True)


def _build_mode_segments(equity: pd.DataFrame) -> list[dict[str, Any]]:
    if equity.empty:
        return []
    if "mode" in equity.columns:
        mode = equity["mode"].astype(str)
    elif "carry_active" in equity.columns:
        mode = equity["carry_active"].map({1: "carry", 0: "spot"}).fillna("spot")
    else:
        mode = pd.Series(["spot"] * len(equity), index=equity.index)
    op_cost = equity["operation_cost_usd"] if "operation_cost_usd" in equity.columns else pd.Series([0.0] * len(equity), index=equity.index)

    boundaries = mode.ne(mode.shift()).to_numpy().nonzero()[0].tolist()
    if not boundaries or boundaries[0] != 0:
        boundaries = [0] + boundaries
    boundaries.append(len(equity))

    segments: list[dict[str, Any]] = []
    for i in range(len(boundaries) - 1):
        start_idx = int(boundaries[i])
        end_excl = int(boundaries[i + 1])
        end_idx = max(start_idx, end_excl - 1)
        segments.append(
            {
                "mode": str(mode.iloc[start_idx]),
                "start_ts": equity["ts"].iloc[start_idx],
                "end_ts": equity["ts"].iloc[end_idx],
                "start_equity": float(equity["equity"].iloc[start_idx]),
                "end_equity": float(equity["equity"].iloc[end_idx]),
                "start_op_cost": float(op_cost.iloc[start_idx]),
                "end_op_cost": float(op_cost.iloc[end_idx]),
            }
        )
    return segments


def _segment_cashflows(
    segment: dict[str, Any],
    funding: pd.DataFrame,
    borrow: pd.DataFrame,
) -> dict[str, float]:
    start_ts = segment["start_ts"]
    end_ts = segment["end_ts"]
    fund_cf = 0.0
    borrow_cost = 0.0
    if not funding.empty:
        mask = (funding["ts"] >= start_ts) & (funding["ts"] <= end_ts)
        if mask.any():
            fund_cf = float(funding.loc[mask, "cashflow"].sum())
    if not borrow.empty:
        mask = (borrow["ts"] >= start_ts) & (borrow["ts"] <= end_ts)
        if mask.any():
            borrow_cost = float(borrow.loc[mask, "interest_usd"].sum())

    return {
        "equity_pnl": float(segment["end_equity"] - segment["start_equity"]),
        "funding_cf": fund_cf,
        "borrow_cost": borrow_cost,
        "operation_cost": float(max(segment["end_op_cost"] - segment["start_op_cost"], 0.0)),
    }


def _save_equity_and_ops_plot(
    path: Path,
    equity: pd.DataFrame,
    funding: pd.DataFrame,
    borrow: pd.DataFrame,
) -> None:
    fig, (ax_eq, ax_ops, ax_risk) = plt.subplots(
        3,
        1,
        figsize=(14, 10),
        sharex=True,
        gridspec_kw={"height_ratios": [2.0, 1.2, 1.2]},
    )

    ax_eq.plot(equity["ts"], equity["equity"], color="#124076", linewidth=1.2, label="Equity (USD)")
    for s, e in _regime_spans(equity):
        ax_eq.axvspan(s, e, color="#2ca02c", alpha=0.10)
    ax_eq.set_ylabel("Equity, USD")
    ax_eq.set_title("Aave+Hyper Carry: Equity and Full Operation Timeline")
    ax_eq.legend(loc="upper left")
    ax_eq.grid(True, linestyle=":", linewidth=0.6, alpha=0.7)

    if not funding.empty:
        pos = funding[funding["cashflow"] > 0]
        neg = funding[funding["cashflow"] < 0]
        ax_ops.scatter(pos["ts"], pos["cashflow"], s=10, c="#0d7c3f", label="Funding +")
        ax_ops.scatter(neg["ts"], neg["cashflow"], s=10, c="#b22222", label="Funding -")

    if not borrow.empty:
        ax_ops.scatter(
            borrow["ts"],
            -borrow["interest_usd"],
            s=5,
            c="#c0841a",
            alpha=0.65,
            label="Borrow interest",
        )

    ax_ops.axhline(0.0, color="#222222", linewidth=0.8, linestyle="--")
    ax_ops.set_ylabel("Operation CF, USD")
    ax_ops.legend(loc="upper left")
    ax_ops.grid(True, linestyle=":", linewidth=0.6, alpha=0.7)

    ax_risk.plot(equity["ts"], equity["ltv"], color="#8a2be2", linewidth=1.0, label="LTV")
    ax_risk.plot(equity["ts"], equity["health_factor"], color="#e46f00", linewidth=1.0, label="Health factor")
    ax_risk.axhline(1.0, color="#666666", linewidth=0.8, linestyle="--")
    ax_risk.set_ylabel("Risk metrics")
    ax_risk.legend(loc="upper right")
    ax_risk.grid(True, linestyle=":", linewidth=0.6, alpha=0.7)

    ax_risk.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    ax_risk.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    plt.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _save_regime_timing_plot(path: Path, equity: pd.DataFrame, funding: pd.DataFrame, borrow: pd.DataFrame) -> None:
    fig, (ax_apr, ax_mode) = plt.subplots(
        2,
        1,
        figsize=(14, 8),
        sharex=True,
        gridspec_kw={"height_ratios": [2.0, 1.0]},
    )

    if not funding.empty and {"funding_apr", "borrow_apr"}.issubset(funding.columns):
        f = funding.sort_values("ts")
        ax_apr.plot(
            f["ts"],
            f["funding_apr"] * 100.0,
            color="#1f77b4",
            linewidth=1.1,
            label="Funding APR (event annualized)",
        )
        ax_apr.plot(
            f["ts"],
            f["rolling_funding_apr"] * 100.0,
            color="#17becf",
            linewidth=1.4,
            label="Rolling funding APR",
        )
        ax_apr.plot(
            f["ts"],
            f["borrow_apr"] * 100.0,
            color="#d62728",
            linewidth=1.2,
            linestyle="--",
            label="Borrow APR",
        )
        mask = f["rolling_funding_apr"] > f["borrow_apr"]
        ax_apr.fill_between(
            f["ts"],
            f["rolling_funding_apr"] * 100.0,
            f["borrow_apr"] * 100.0,
            where=mask,
            color="#2ca02c",
            alpha=0.20,
            label="Rolling funding APR > Borrow APR",
        )
    ax_apr.set_ylabel("APR, %")
    ax_apr.set_title("Funding APR vs Borrow APR and Active Regime")
    ax_apr.grid(True, linestyle=":", linewidth=0.6, alpha=0.7)
    ax_apr.legend(loc="best", fontsize=9)

    mode_colors = {"carry": "#2ca02c", "long_perp": "#9467bd", "spot": "#9aa0a6"}
    segments = _build_mode_segments(equity)
    for segment in segments:
        color = mode_colors.get(segment["mode"], "#9aa0a6")
        ax_apr.axvspan(segment["start_ts"], segment["end_ts"], color=color, alpha=0.06)

    if segments:
        y_min, y_max = ax_apr.get_ylim()
        y_span = max(y_max - y_min, 1e-9)
        label_base = y_max - 0.06 * y_span
        row_step = 0.11 * y_span
        row_id = 0
        for segment in segments:
            if segment["mode"] == "spot":
                continue
            stats = _segment_cashflows(segment=segment, funding=funding, borrow=borrow)
            mid_ts = segment["start_ts"] + (segment["end_ts"] - segment["start_ts"]) / 2
            y = label_base - (row_id % 2) * row_step
            row_id += 1
            label = (
                f"{segment['mode']} ΔEq {stats['equity_pnl'] / 1000.0:+.1f}k | "
                f"F {stats['funding_cf'] / 1000.0:+.1f}k | "
                f"B {-stats['borrow_cost'] / 1000.0:+.1f}k | "
                f"Ops {-stats['operation_cost'] / 1000.0:+.1f}k"
            )
            ax_apr.text(
                mid_ts,
                y,
                label,
                ha="center",
                va="top",
                fontsize=8,
                color="#202124",
                bbox={"boxstyle": "round,pad=0.25", "fc": "white", "ec": "#c0c0c0", "alpha": 0.85},
            )

    if "mode" in equity.columns:
        mode_series = equity["mode"].astype(str)
        mode_code = mode_series.map({"carry": -1, "spot": 0, "long_perp": 1}).fillna(0.0)
    elif "carry_active" in equity.columns:
        mode_code = equity["carry_active"].astype(int)
    else:
        mode_code = pd.Series([0] * len(equity), index=equity.index)

    ax_mode.step(equity["ts"], mode_code, where="post", color="#2ca02c", linewidth=1.4, label="Mode code")
    if "perp_qty_active" in equity.columns:
        ax_mode2 = ax_mode.twinx()
        ax_mode2.step(
            equity["ts"],
            equity["perp_qty_active"],
            where="post",
            color="#9467bd",
            linewidth=1.1,
            label="Perp BTC qty (signed)",
        )
        ax_mode2.set_ylabel("Perp qty, BTC")
        lines_l, labels_l = ax_mode.get_legend_handles_labels()
        lines_r, labels_r = ax_mode2.get_legend_handles_labels()
        ax_mode.legend(lines_l + lines_r, labels_l + labels_r, loc="upper left", fontsize=9)
    else:
        ax_mode.legend(loc="upper left", fontsize=9)
    ax_mode.set_yticks([-1, 0, 1])
    ax_mode.set_yticklabels(["carry(short)", "spot", "long_perp"])
    ax_mode.set_ylabel("Mode")
    ax_mode.grid(True, linestyle=":", linewidth=0.6, alpha=0.7)
    ax_mode.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    ax_mode.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))

    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _save_regime_distribution_plot(path: Path, equity: pd.DataFrame, funding: pd.DataFrame) -> None:
    mode_col = equity["mode"].astype(str) if "mode" in equity.columns else pd.Series(["spot"] * len(equity))
    spot_hours = int((mode_col == "spot").sum())
    carry_hours = int((mode_col == "carry").sum())
    long_hours = int((mode_col == "long_perp").sum())

    spot_events = 0
    carry_events = 0
    long_events = 0
    if not funding.empty and "mode" in funding.columns:
        spot_events = int((funding["mode"] == "spot").sum())
        carry_events = int((funding["mode"] == "carry").sum())
        long_events = int((funding["mode"] == "long_perp").sum())

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    axes[0].bar(["spot", "carry", "long_perp"], [spot_hours, carry_hours, long_hours], color=["#4c78a8", "#2ca02c", "#9467bd"])
    axes[0].set_title("Hours in Mode")
    axes[0].set_ylabel("Hours")
    axes[0].grid(axis="y", linestyle=":", linewidth=0.6, alpha=0.7)

    axes[1].bar(["spot", "carry", "long_perp"], [spot_events, carry_events, long_events], color=["#4c78a8", "#2ca02c", "#9467bd"])
    axes[1].set_title("Funding Events by Mode")
    axes[1].set_ylabel("Count")
    axes[1].grid(axis="y", linestyle=":", linewidth=0.6, alpha=0.7)

    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _save_carry_components_plot(path: Path, equity: pd.DataFrame, funding: pd.DataFrame, borrow: pd.DataFrame, operation_cost: float) -> None:
    timeline = equity[["ts"]].copy()
    timeline["cum_funding"] = 0.0
    timeline["cum_borrow"] = 0.0

    if not funding.empty:
        f = funding[["ts", "cashflow"]].copy()
        f["cum_funding_event"] = f["cashflow"].cumsum()
        timeline = pd.merge_asof(
            timeline.sort_values("ts"),
            f[["ts", "cum_funding_event"]].sort_values("ts"),
            on="ts",
            direction="backward",
        )
        timeline["cum_funding"] = timeline["cum_funding_event"].fillna(0.0)
        timeline = timeline.drop(columns=["cum_funding_event"])

    if not borrow.empty:
        b = borrow[["ts", "interest_usd"]].copy()
        b["cum_borrow_event"] = b["interest_usd"].cumsum()
        timeline = pd.merge_asof(
            timeline.sort_values("ts"),
            b[["ts", "cum_borrow_event"]].sort_values("ts"),
            on="ts",
            direction="backward",
        )
        timeline["cum_borrow"] = timeline["cum_borrow_event"].fillna(0.0)
        timeline = timeline.drop(columns=["cum_borrow_event"])

    # Prefer true cumulative operation cost from equity curve (entry/exit costs over time).
    if "operation_cost_usd" in equity.columns:
        timeline["cum_setup"] = equity["operation_cost_usd"].astype(float).reset_index(drop=True)
    else:
        timeline["cum_setup"] = float(operation_cost)

    timeline["cum_gross_carry"] = timeline["cum_funding"] - timeline["cum_borrow"]
    timeline["cum_net_carry"] = timeline["cum_gross_carry"] - timeline["cum_setup"]
    timeline["cum_total_pnl"] = equity["equity"] - float(equity["equity"].iloc[0])
    # Additive decomposition in net terms: total PnL = directional + net carry.
    timeline["cum_directional"] = timeline["cum_total_pnl"] - timeline["cum_net_carry"]

    fig, (ax_carry, ax_total) = plt.subplots(
        2,
        1,
        figsize=(14, 8),
        sharex=True,
        gridspec_kw={"height_ratios": [1.2, 1.0]},
    )

    ax_carry.step(
        timeline["ts"],
        timeline["cum_funding"],
        where="post",
        label="Cum funding (step, event-driven)",
        linewidth=1.1,
        color="#007f5f",
    )
    ax_carry.plot(timeline["ts"], -timeline["cum_borrow"], label="Cum borrow cost", linewidth=1.1, color="#ff7f11")
    ax_carry.plot(timeline["ts"], -timeline["cum_setup"], label="Cum operation cost", linewidth=1.1, color="#a44a3f")
    ax_carry.plot(timeline["ts"], timeline["cum_net_carry"], label="Cum net carry", linewidth=1.5, color="#1d3557")
    ax_carry.axhline(0.0, color="#222222", linewidth=0.8, linestyle="--")
    ax_carry.set_title("Carry Components (USD, own scale)")
    ax_carry.set_ylabel("USD")
    ax_carry.grid(True, linestyle=":", linewidth=0.6, alpha=0.7)
    carry_lines, carry_labels = ax_carry.get_legend_handles_labels()
    if not funding.empty:
        ax_funding_evt = ax_carry.twinx()
        pos = funding[funding["cashflow"] > 0.0]
        neg = funding[funding["cashflow"] < 0.0]
        width_days = 0.06  # ~1.44h on a datetime axis (funding events are every 8h)
        bar_pos = ax_funding_evt.bar(
            pos["ts"],
            pos["cashflow"],
            width=width_days,
            color="#2a9d8f",
            alpha=0.18,
            label="Funding + per event",
            zorder=1,
        )
        bar_neg = ax_funding_evt.bar(
            neg["ts"],
            neg["cashflow"],
            width=width_days,
            color="#d62828",
            alpha=0.25,
            label="Funding - per event",
            zorder=1,
        )
        ax_funding_evt.set_ylabel("Funding cashflow / event")
        lines = carry_lines + [bar_pos, bar_neg]
        labels = carry_labels + ["Funding + per event", "Funding - per event"]
        ax_carry.legend(lines, labels, loc="best")
    else:
        ax_carry.legend(loc="best")

    line_total = ax_total.plot(
        timeline["ts"],
        timeline["cum_total_pnl"],
        label="Cum total PnL (left)",
        linewidth=1.6,
        color="#124076",
    )[0]
    line_net_carry = ax_total.plot(
        timeline["ts"],
        timeline["cum_net_carry"],
        label="Cum net carry (left)",
        linewidth=1.2,
        color="#1d3557",
        linestyle="--",
    )[0]
    ax_total.axhline(0.0, color="#222222", linewidth=0.8, linestyle="--")
    ax_total.set_title("Total and Carry (left) vs Directional Residual (right)")
    ax_total.set_ylabel("USD (left)")
    ax_total.grid(True, linestyle=":", linewidth=0.6, alpha=0.7)

    ax_total_right = ax_total.twinx()
    line_directional = ax_total_right.plot(
        timeline["ts"],
        timeline["cum_directional"],
        label="Cum directional residual (right)",
        linewidth=1.1,
        color="#6a4c93",
        alpha=0.9,
    )[0]
    ax_total_right.set_ylabel("USD (right)")

    lines = [line_total, line_net_carry, line_directional]
    labels = [line.get_label() for line in lines]
    ax_total.legend(lines, labels, loc="best")
    ax_total.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    ax_total.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))

    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def save_run_plots(
    run_dir: Path,
    equity: pd.DataFrame,
    funding: pd.DataFrame,
    borrow: pd.DataFrame,
    summary: dict[str, float],
) -> None:
    if equity.empty:
        return

    ledger = _operation_ledger(funding=funding, borrow=borrow)
    if not ledger.empty:
        atomic_write_parquet(run_dir / "operations.parquet", ledger)

    _save_equity_and_ops_plot(
        path=run_dir / "equity_and_operations.png",
        equity=equity,
        funding=funding,
        borrow=borrow,
    )
    _save_carry_components_plot(
        path=run_dir / "carry_components.png",
        equity=equity,
        funding=funding,
        borrow=borrow,
        operation_cost=float(summary.get("operation_cost", summary.get("setup_cost", 0.0))),
    )
    _save_regime_timing_plot(
        path=run_dir / "regime_timing.png",
        equity=equity,
        funding=funding,
        borrow=borrow,
    )
    _save_regime_distribution_plot(
        path=run_dir / "regime_distribution.png",
        equity=equity,
        funding=funding,
    )
