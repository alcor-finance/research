from __future__ import annotations

import yaml


def build_report(summary: dict[str, float], config_payload: dict) -> str:
    rows = [
        "# Aave + Hyper Carry Backtest",
        "",
        "## Summary",
        "",
        f"- Start equity: {summary['start_equity']:.2f}",
        f"- End equity: {summary['end_equity']:.2f}",
        f"- Total PnL: {summary['total_pnl']:.2f}",
        f"- Funding PnL: {summary['funding_pnl']:.2f}",
        f"- Borrow interest: {summary['borrow_interest']:.2f}",
        f"- Gross carry PnL: {summary['gross_carry_pnl']:.2f}",
        f"- Setup cost: {summary['setup_cost']:.2f}",
        f"- Close cost: {summary.get('close_cost', 0.0):.2f}",
        f"- Operation cost (open+close): {summary.get('operation_cost', summary['setup_cost']):.2f}",
        f"- Net carry PnL: {summary['net_carry_pnl']:.2f}",
        f"- Directional PnL: {summary['directional_pnl']:.2f}",
        f"- Total return: {summary['total_return']:.2%}",
        f"- Annualized return: {summary['annualized_return']:.2%}",
        f"- Max drawdown: {summary['max_drawdown']:.2%}",
        f"- Annualized vol: {summary['annualized_vol']:.2%}",
        f"- Sharpe: {summary['sharpe']:.4f}",
        f"- Min health factor: {summary['min_health_factor']:.4f}",
        f"- Carry entries/exits: {summary.get('carry_entries', 0)}/{summary.get('carry_exits', 0)}",
        f"- Carry time share: {summary.get('carry_time_share', 0.0):.2%}",
        f"- Spot time share: {summary.get('spot_time_share', 0.0):.2%}",
        f"- Long-perp time share: {summary.get('long_perp_time_share', 0.0):.2%}",
        f"- Short-perp time share: {summary.get('short_perp_time_share', 0.0):.2%}",
        f"- Edge APR mean: {summary.get('edge_apr_mean', 0.0):.2%}",
        f"- Edge APR positive share: {summary.get('edge_apr_positive_share', 0.0):.2%}",
        "",
        "## Config",
        "",
        "```yaml",
        yaml.safe_dump(config_payload, sort_keys=False),
        "```",
        "",
    ]
    return "\n".join(rows)
