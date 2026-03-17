from __future__ import annotations

from math import sqrt

import pandas as pd


def _max_drawdown(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    running_max = equity.cummax()
    drawdown = equity / running_max - 1.0
    return float(drawdown.min())


def compute_summary(
    equity: pd.DataFrame,
    funding: pd.DataFrame,
    borrow: pd.DataFrame,
    setup_cost_usd: float,
    close_cost_usd: float = 0.0,
    carry_entries: int = 1,
    carry_exits: int = 0,
) -> dict[str, float]:
    if equity.empty:
        raise ValueError("equity DataFrame is empty")

    start_equity = float(equity["equity"].iloc[0])
    end_equity = float(equity["equity"].iloc[-1])
    total_pnl = end_equity - start_equity

    funding_pnl = float(funding["cashflow"].sum()) if not funding.empty else 0.0
    borrow_interest = float(borrow["interest_usd"].sum()) if not borrow.empty else 0.0
    gross_carry_pnl = funding_pnl - borrow_interest
    operation_cost = float(setup_cost_usd) + float(close_cost_usd)
    net_carry_pnl = gross_carry_pnl - operation_cost
    directional_pnl = total_pnl - gross_carry_pnl

    returns = equity["equity"].pct_change().fillna(0.0)
    annualizer = sqrt(24.0 * 365.0)
    annualized_vol = float(returns.std() * annualizer)
    sharpe = float((returns.mean() * 24.0 * 365.0) / annualized_vol) if annualized_vol > 0 else 0.0

    duration_hours = (equity["ts"].iloc[-1] - equity["ts"].iloc[0]).total_seconds() / 3600.0
    duration_years = max(duration_hours / 8760.0, 1e-12)
    total_return = total_pnl / start_equity if start_equity else 0.0
    annualized_return = (1.0 + total_return) ** (1.0 / duration_years) - 1.0 if start_equity > 0 else 0.0

    summary = {
        "start_equity": start_equity,
        "end_equity": end_equity,
        "total_pnl": total_pnl,
        "total_return": float(total_return),
        "annualized_return": float(annualized_return),
        "funding_pnl": funding_pnl,
        "borrow_interest": borrow_interest,
        "gross_carry_pnl": gross_carry_pnl,
        "setup_cost": float(setup_cost_usd),
        "close_cost": float(close_cost_usd),
        "operation_cost": float(operation_cost),
        "net_carry_pnl": net_carry_pnl,
        "directional_pnl": directional_pnl,
        "max_drawdown": _max_drawdown(equity["equity"]),
        "annualized_vol": annualized_vol,
        "sharpe": sharpe,
        "funding_events": int(len(funding)),
        "min_ltv": float(equity["ltv"].min()),
        "max_ltv": float(equity["ltv"].max()),
        "min_health_factor": float(equity["health_factor"].min()),
        "carry_entries": int(carry_entries),
        "carry_exits": int(carry_exits),
    }
    if "carry_active" in equity.columns and len(equity) > 0:
        carry_share = float(equity["carry_active"].astype(float).mean())
        summary["carry_time_share"] = carry_share
        summary["spot_time_share"] = 1.0 - carry_share
    if "mode" in equity.columns and len(equity) > 0:
        mode = equity["mode"].astype(str)
        summary["spot_time_share"] = float((mode == "spot").mean())
        summary["carry_time_share"] = float((mode == "carry").mean())
        summary["long_perp_time_share"] = float((mode == "long_perp").mean())
    if "perp_qty_active" in equity.columns and len(equity) > 0:
        perp = equity["perp_qty_active"].astype(float)
        summary["short_perp_time_share"] = float((perp < 0).mean())
        summary["long_perp_time_share"] = float((perp > 0).mean())
    if "edge_apr" in equity.columns:
        edge = equity["edge_apr"].dropna()
        if not edge.empty:
            summary["edge_apr_mean"] = float(edge.mean())
            summary["edge_apr_median"] = float(edge.median())
            summary["edge_apr_q75"] = float(edge.quantile(0.75))
            summary["edge_apr_positive_share"] = float((edge > 0).mean())
    return summary
