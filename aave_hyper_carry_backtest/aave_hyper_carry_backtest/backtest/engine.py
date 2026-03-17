from __future__ import annotations

from dataclasses import dataclass
import math

from aave_hyper_carry_backtest.backtest.metrics import compute_summary


@dataclass(slots=True)
class BacktestEngine:
    ctx: object

    def run(self) -> dict[str, float]:
        timeline = self.ctx.market_data.timeline
        if len(timeline) == 0:
            raise ValueError("Timeline is empty")

        entry_ts = timeline[0]
        entry_price = self.ctx.market_data.get_spot_mid(entry_ts)
        strategy = self.ctx.strategy
        position = strategy.open_position(
            entry_ts=entry_ts,
            entry_price=entry_price,
            initial_btc=self.ctx.config.initial_btc,
            start_in_carry=not strategy.timing_enabled,
        )

        prev_ts = None
        prev_funding_ts = None
        funding_apr_history: list[float] = []
        latest_rolling_funding_apr = math.nan
        latest_borrow_apr = float(self.ctx.config.strategy.aave_borrow_apr)
        latest_edge_apr = math.nan

        for ts in timeline:
            if prev_ts is not None:
                dt_hours = (ts - prev_ts).total_seconds() / 3600.0
                borrow_apr = self.ctx.market_data.get_borrow_apr(prev_ts, self.ctx.config.strategy.aave_borrow_apr)
                latest_borrow_apr = borrow_apr
                interest = position.accrue_borrow(dt_hours, borrow_apr)
                if interest:
                    self.ctx.recorder.record_borrow(
                        {
                            "ts": ts,
                            "apr": borrow_apr,
                            "hours": dt_hours,
                            "interest_usd": interest,
                            "debt_usd": position.debt_usd,
                        }
                    )

            if prev_ts is not None and self.ctx.market_data.is_funding_timestamp(ts):
                rate = self.ctx.market_data.get_funding_rate(ts)
                mark_price = self.ctx.market_data.get_funding_mark_price(ts)
                if prev_funding_ts is None:
                    dt_funding_hours = float(max(strategy.default_funding_interval_hours, 1e-9))
                else:
                    dt_funding_hours = max((ts - prev_funding_ts).total_seconds() / 3600.0, 1e-9)
                prev_funding_ts = ts

                funding_apr = float(rate) * (8760.0 / dt_funding_hours)
                funding_apr_history.append(funding_apr)
                window = max(int(strategy.timing_window_events), 1)
                latest_rolling_funding_apr = sum(funding_apr_history[-window:]) / min(len(funding_apr_history), window)
                latest_edge_apr = strategy.carry_edge_apr(
                    rolling_funding_apr=latest_rolling_funding_apr,
                    borrow_apr=latest_borrow_apr,
                )

                current_mode = position.mode()
                cashflow = position.apply_funding(rate=rate, mark_price=mark_price)
                self.ctx.recorder.record_funding(
                    {
                        "ts": ts,
                        "rate": rate,
                        "funding_apr": funding_apr,
                        "rolling_funding_apr": latest_rolling_funding_apr,
                        "borrow_apr": latest_borrow_apr,
                        "edge_apr": latest_edge_apr,
                        "mark_price": mark_price,
                        "perp_qty": position.perp_qty_btc,
                        "short_qty": max(-position.perp_qty_btc, 0.0),
                        "long_qty": max(position.perp_qty_btc, 0.0),
                        "cashflow": cashflow,
                        "mode": current_mode,
                    }
                )

                if strategy.timing_enabled:
                    spot_mid = self.ctx.market_data.get_spot_mid(ts)

                    if current_mode == "carry" and strategy.should_exit_carry(
                        rolling_edge_apr=latest_edge_apr,
                        hold_events=position.carry_hold_funding_events,
                    ):
                        position.exit_carry(
                            ts=ts,
                            spot_price=spot_mid,
                            close_cost_rate=strategy.close_cost_rate,
                            non_carry_mode="spot",
                        )
                        current_mode = position.mode()

                    if current_mode != "carry" and strategy.should_enter_carry(rolling_edge_apr=latest_edge_apr):
                        position.enter_carry(
                            ts=ts,
                            spot_price=spot_mid,
                            setup_cost_rate=strategy.setup_cost_rate,
                        )
                        current_mode = position.mode()

                    if current_mode != "carry":
                        if strategy.should_enter_long_perp(latest_rolling_funding_apr):
                            position.enter_long_perp(ts=ts, spot_price=spot_mid)
                        elif current_mode == "long_perp" and strategy.should_exit_long_perp(latest_rolling_funding_apr):
                            position.exit_long_perp(ts=ts, spot_price=spot_mid)

            spot_price = self.ctx.market_data.get_spot_mid(ts)
            self.ctx.recorder.record_equity(
                {
                    "ts": ts,
                    "equity": position.equity_usd(spot_price),
                    "spot_mid": spot_price,
                    "collateral_usd": position.collateral_usd(spot_price),
                    "perp_unrealized_pnl_usd": position.perp_unrealized_pnl_usd(spot_price),
                    "cash_usd": position.cash_usd,
                    "debt_usd": position.debt_usd,
                    "funding_pnl_usd": position.funding_pnl_usd,
                    "borrow_interest_usd": position.borrow_interest_usd,
                    "operation_cost_usd": position.operation_cost_usd(),
                    "mode": position.mode(),
                    "carry_active": int(position.mode() == "carry"),
                    "perp_qty_active": position.perp_qty_btc,
                    "short_qty_active": max(-position.perp_qty_btc, 0.0),
                    "long_qty_active": max(position.perp_qty_btc, 0.0),
                    "rolling_funding_apr": latest_rolling_funding_apr,
                    "borrow_apr": latest_borrow_apr,
                    "edge_apr": latest_edge_apr,
                    "ltv": position.ltv(spot_price),
                    "health_factor": position.health_factor(
                        spot_price=spot_price,
                        liquidation_threshold=self.ctx.config.strategy.liquidation_threshold,
                    ),
                }
            )

            prev_ts = ts

        equity = self.ctx.recorder.equity_df()
        funding = self.ctx.recorder.funding_df()
        borrow = self.ctx.recorder.borrow_df()

        summary = compute_summary(
            equity=equity,
            funding=funding,
            borrow=borrow,
            setup_cost_usd=position.setup_cost_usd,
            close_cost_usd=position.close_cost_usd,
            carry_entries=position.carry_entries,
            carry_exits=position.carry_exits,
        )
        return summary
