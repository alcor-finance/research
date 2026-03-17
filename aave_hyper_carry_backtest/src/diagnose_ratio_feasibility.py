from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from aave_hyper_carry_backtest.config.schema import load_config


def _run_id(prefix: str = "ratio_feasibility") -> str:
    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    return f"{ts}_{prefix}"


def _load_funding(cfg_path: Path) -> tuple[pd.DataFrame, dict]:
    cfg = load_config(cfg_path)
    funding = pd.read_csv(cfg.data.funding_path)
    funding["funding_ts"] = pd.to_datetime(funding["funding_ts"], utc=True, format="mixed")
    funding["funding_ts"] = funding["funding_ts"].dt.round(cfg.bar_step)
    funding = funding.sort_values("funding_ts").drop_duplicates("funding_ts", keep="last")
    funding = funding[(funding["funding_ts"] >= cfg.start_ts) & (funding["funding_ts"] <= cfg.end_ts)].copy()
    if funding.empty:
        raise ValueError("No funding rows in selected range")
    return funding, asdict(cfg)


def _event_hours(funding_ts: pd.Series, fallback: float = 8.0) -> float:
    if len(funding_ts) < 2:
        return fallback
    diffs = funding_ts.diff().dt.total_seconds().dropna() / 3600.0
    if diffs.empty:
        return fallback
    return float(diffs.median())


def _compute(
    funding: pd.DataFrame,
    borrow_apr: float,
    overlay_ratio: float,
    hyper_borrow_ratio: float,
    hyper_short_leverage: float,
    hedge_ratio: float,
    capture_positive: float,
    avoid_negative: float,
) -> tuple[pd.DataFrame, dict]:
    dt_hours = _event_hours(funding["funding_ts"])
    dt_year = dt_hours / 8760.0

    out = funding[["funding_ts", "funding_rate"]].copy()
    out["funding_apr"] = out["funding_rate"].astype(float) * (8760.0 / dt_hours)

    funding_weight = abs(hyper_borrow_ratio * hyper_short_leverage * hedge_ratio)
    borrow_weight = overlay_ratio + hyper_borrow_ratio
    if funding_weight <= 0:
        raise ValueError("funding_weight must be > 0")

    break_even_funding_apr = (borrow_weight * borrow_apr) / funding_weight
    out["edge_apr"] = funding_weight * out["funding_apr"] - borrow_weight * borrow_apr
    out["edge_ret_event"] = out["edge_apr"] * dt_year

    out["cum_always"] = out["edge_ret_event"].cumsum()
    out["cum_oracle"] = np.maximum(out["edge_ret_event"], 0.0).cumsum()

    p_sign = np.where(out["funding_apr"] > 0.0, capture_positive, 1.0 - avoid_negative)
    p_struct = np.where(out["edge_apr"] > 0.0, capture_positive, 1.0 - avoid_negative)
    out["cum_75_70_sign"] = (out["edge_ret_event"] * p_sign).cumsum()
    out["cum_75_70_struct"] = (out["edge_ret_event"] * p_struct).cumsum()

    pos_zone = out[out["funding_apr"] > 0.0]
    neg_zone = out[out["funding_apr"] < 0.0]
    prof_zone = out[out["edge_apr"] > 0.0]

    summary = {
        "events": int(len(out)),
        "event_hours": float(dt_hours),
        "borrow_apr": float(borrow_apr),
        "funding_weight": float(funding_weight),
        "borrow_weight": float(borrow_weight),
        "break_even_funding_apr": float(break_even_funding_apr),
        "avg_funding_apr": float(out["funding_apr"].mean()),
        "funding_apr_q50": float(out["funding_apr"].median()),
        "funding_apr_q90": float(out["funding_apr"].quantile(0.9)),
        "short_zone_share": float((out["funding_apr"] > 0.0).mean()),
        "long_zone_share": float((out["funding_apr"] < 0.0).mean()),
        "avg_funding_apr_short_zone": float(pos_zone["funding_apr"].mean()) if not pos_zone.empty else 0.0,
        "avg_funding_apr_long_zone": float(neg_zone["funding_apr"].mean()) if not neg_zone.empty else 0.0,
        "edge_positive_share": float((out["edge_apr"] > 0.0).mean()),
        "avg_edge_apr_positive_zone": float(prof_zone["edge_apr"].mean()) if not prof_zone.empty else 0.0,
        "annual_return_always_gross": float(out["cum_always"].iloc[-1]),
        "annual_return_oracle_gross": float(out["cum_oracle"].iloc[-1]),
        "annual_return_75_70_sign_gross": float(out["cum_75_70_sign"].iloc[-1]),
        "annual_return_75_70_struct_gross": float(out["cum_75_70_struct"].iloc[-1]),
    }
    return out, summary


def _plot(df: pd.DataFrame, summary: dict, out_path: Path) -> None:
    be = summary["break_even_funding_apr"] * 100.0

    fig, axes = plt.subplots(3, 1, figsize=(14, 11), sharex=False, gridspec_kw={"height_ratios": [1.4, 1.0, 1.2]})

    ax = axes[0]
    x = df["funding_ts"]
    y = df["funding_apr"] * 100.0
    ax.plot(x, y, color="#1f77b4", linewidth=1.0, label="Funding APR (event annualized)")
    ax.axhline(be, color="#d62728", linestyle="--", linewidth=1.2, label=f"Break-even funding APR ({be:.2f}%)")
    ax.fill_between(x, y, be, where=(y >= be), color="#2ca02c", alpha=0.18, interpolate=True)
    ax.fill_between(x, y, be, where=(y < be), color="#b22222", alpha=0.12, interpolate=True)
    ax.set_title("Funding APR vs Break-even Threshold")
    ax.set_ylabel("APR, %")
    ax.grid(True, linestyle=":", linewidth=0.6, alpha=0.7)
    ax.legend(loc="upper right")
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))

    ax = axes[1]
    vals = df["funding_apr"] * 100.0
    ax.hist(vals, bins=60, color="#4c78a8", alpha=0.8)
    ax.axvline(be, color="#d62728", linestyle="--", linewidth=1.2)
    ax.set_title("Funding APR Distribution")
    ax.set_xlabel("APR, %")
    ax.set_ylabel("Count")
    ax.grid(True, linestyle=":", linewidth=0.6, alpha=0.7)

    ax = axes[2]
    ax.plot(df["funding_ts"], df["cum_always"] * 100.0, color="#d62728", linewidth=1.2, label="Always active")
    ax.plot(df["funding_ts"], df["cum_oracle"] * 100.0, color="#2ca02c", linewidth=1.2, label="Oracle: only edge>0")
    ax.plot(df["funding_ts"], df["cum_75_70_sign"] * 100.0, color="#9467bd", linewidth=1.2, label="75/70 by funding sign")
    ax.plot(df["funding_ts"], df["cum_75_70_struct"] * 100.0, color="#ff7f0e", linewidth=1.2, label="75/70 by edge sign")
    ax.axhline(0.0, color="#333333", linestyle="--", linewidth=0.8)
    ax.set_title("Cumulative Gross Return (on 100 BTC base notion)")
    ax.set_ylabel("Return, %")
    ax.grid(True, linestyle=":", linewidth=0.6, alpha=0.7)
    ax.legend(loc="best")
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))

    plt.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def _plot_zone_summary(summary: dict, out_path: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    ax = axes[0]
    labels = ["Short zone\n(funding>0)", "Long zone\n(funding<0)", "Break-even"]
    values = [
        summary["avg_funding_apr_short_zone"] * 100.0,
        summary["avg_funding_apr_long_zone"] * 100.0,
        summary["break_even_funding_apr"] * 100.0,
    ]
    colors = ["#2ca02c", "#b22222", "#d62728"]
    ax.bar(labels, values, color=colors)
    ax.axhline(0.0, color="#333333", linewidth=0.8, linestyle="--")
    ax.set_title("Average Funding APR by Zone")
    ax.set_ylabel("APR, %")
    ax.grid(axis="y", linestyle=":", linewidth=0.6, alpha=0.7)

    ax = axes[1]
    scenario_labels = ["Always", "Oracle", "75/70 sign", "75/70 edge"]
    scenario_vals = [
        summary["annual_return_always_gross"] * 100.0,
        summary["annual_return_oracle_gross"] * 100.0,
        summary["annual_return_75_70_sign_gross"] * 100.0,
        summary["annual_return_75_70_struct_gross"] * 100.0,
    ]
    scenario_colors = ["#d62728", "#2ca02c", "#9467bd", "#ff7f0e"]
    ax.bar(scenario_labels, scenario_vals, color=scenario_colors)
    ax.axhline(0.0, color="#333333", linewidth=0.8, linestyle="--")
    ax.set_title("Gross Return by Scenario")
    ax.set_ylabel("Return, %")
    ax.grid(axis="y", linestyle=":", linewidth=0.6, alpha=0.7)

    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def _build_report(summary: dict, params: dict, chart_name: str) -> str:
    rows = [
        "# Feasibility Report: Ratio Carry (40/20/x2 style)",
        "",
        "## Parameters",
        f"- Borrow APR (fixed): {params['borrow_apr']:.2%}",
        f"- Overlay borrow ratio: {params['overlay_ratio']:.2f}",
        f"- Hyper borrow ratio: {params['hyper_borrow_ratio']:.2f}",
        f"- Hyper short leverage: {params['hyper_short_leverage']:.2f}",
        f"- Hedge ratio: {params['hedge_ratio']:.2f}",
        f"- Funding weight: {summary['funding_weight']:.2f}",
        f"- Borrow weight: {summary['borrow_weight']:.2f}",
        "",
        "## Core Formula",
        "- `edge_apr = funding_weight * funding_apr - borrow_weight * borrow_apr`",
        f"- Break-even funding APR: **{summary['break_even_funding_apr']:.2%}**",
        "",
        "## What Data Says",
        f"- Avg funding APR (all events): {summary['avg_funding_apr']:.2%}",
        f"- Avg funding APR in short-positive zone: {summary['avg_funding_apr_short_zone']:.2%}",
        f"- Avg funding APR in long-negative zone: {summary['avg_funding_apr_long_zone']:.2%}",
        f"- Share of structurally positive events (`edge_apr > 0`): {summary['edge_positive_share']:.2%}",
        "",
        "## Gross Return Scenarios (before execution fees/slippage)",
        f"- Always active: {summary['annual_return_always_gross']:.2%}",
        f"- Oracle (trade only when `edge_apr > 0`): {summary['annual_return_oracle_gross']:.2%}",
        f"- 75/70 by funding sign: {summary['annual_return_75_70_sign_gross']:.2%}",
        f"- 75/70 by edge sign: {summary['annual_return_75_70_struct_gross']:.2%}",
        "",
        "## Conclusion",
        "На этом годовом срезе конструкция неустойчива при текущем borrow: даже при выборочном входе преимущество funding слишком редкое/слабое, чтобы стабильно перекрыть borrow + операционные издержки.",
        "",
        "## Charts",
        f"- `{chart_name}`",
        "- `zone_summary.png`",
        "",
    ]
    return "\n".join(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose why ratio carry is/ isn't feasible on historical funding")
    parser.add_argument("--config", required=True, help="Path to config YAML (for data range and funding path)")
    parser.add_argument("--borrow-apr", type=float, default=0.0515, help="Fixed borrow APR")
    parser.add_argument("--overlay-ratio", type=float, default=0.40, help="Borrowed ratio to buy extra BTC")
    parser.add_argument("--hyper-borrow-ratio", type=float, default=0.20, help="Borrowed ratio sent to Hyper")
    parser.add_argument("--hyper-short-leverage", type=float, default=2.0, help="Short leverage on Hyper")
    parser.add_argument("--hedge-ratio", type=float, default=1.0, help="Perp hedge multiplier")
    parser.add_argument("--capture-positive", type=float, default=0.75, help="Hit-rate in positive zone (for what-if)")
    parser.add_argument("--avoid-negative", type=float, default=0.70, help="Avoid-rate in negative zone (for what-if)")
    parser.add_argument("--out-dir", default="", help="Output directory; default results/<timestamp>_ratio_feasibility")
    args = parser.parse_args()

    cfg_path = Path(args.config)
    funding, cfg_payload = _load_funding(cfg_path)
    df, summary = _compute(
        funding=funding,
        borrow_apr=float(args.borrow_apr),
        overlay_ratio=float(args.overlay_ratio),
        hyper_borrow_ratio=float(args.hyper_borrow_ratio),
        hyper_short_leverage=float(args.hyper_short_leverage),
        hedge_ratio=float(args.hedge_ratio),
        capture_positive=float(args.capture_positive),
        avoid_negative=float(args.avoid_negative),
    )

    if args.out_dir:
        out_dir = Path(args.out_dir)
    else:
        out_dir = Path(cfg_payload["results"]["results_dir"]) / _run_id("ratio_feasibility")
    out_dir.mkdir(parents=True, exist_ok=True)

    chart_path = out_dir / "why_not_profitable.png"
    _plot(df=df, summary=summary, out_path=chart_path)
    zone_chart_path = out_dir / "zone_summary.png"
    _plot_zone_summary(summary=summary, out_path=zone_chart_path)

    params = {
        "borrow_apr": float(args.borrow_apr),
        "overlay_ratio": float(args.overlay_ratio),
        "hyper_borrow_ratio": float(args.hyper_borrow_ratio),
        "hyper_short_leverage": float(args.hyper_short_leverage),
        "hedge_ratio": float(args.hedge_ratio),
        "capture_positive": float(args.capture_positive),
        "avoid_negative": float(args.avoid_negative),
    }

    report = _build_report(summary=summary, params=params, chart_name=chart_path.name)
    (out_dir / "report.md").write_text(report, encoding="utf-8")
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    df.to_parquet(out_dir / "diagnostic_series.parquet", index=False)

    print(f"Saved: {out_dir.resolve()}")
    print(f"Break-even funding APR: {summary['break_even_funding_apr']:.4%}")
    print(f"Avg funding APR: {summary['avg_funding_apr']:.4%}")
    print(f"Always gross return: {summary['annual_return_always_gross']:.4%}")
    print(f"Oracle gross return: {summary['annual_return_oracle_gross']:.4%}")


if __name__ == "__main__":
    main()
