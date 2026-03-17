from __future__ import annotations

from dataclasses import dataclass
import math

from aave_hyper_carry_backtest.portfolio.position import CarryPosition


@dataclass(slots=True)
class AaveHyperCarryStrategy:
    target_leverage: float = 2.0
    hedge_ratio: float = 1.0
    use_ratio_structure: bool = False
    overlay_borrow_ratio: float = 0.4
    hyper_borrow_ratio: float = 0.2
    hyper_short_leverage: float = 2.0
    setup_cost_rate: float = 0.0005
    close_cost_rate: float = 0.0005
    timing_enabled: bool = False
    timing_window_events: int = 21
    enter_edge_apr: float = 0.0
    exit_edge_apr: float = -0.005
    carry_max_payback_hours: float = 720.0
    min_hold_funding_events: int = 1
    default_funding_interval_hours: float = 8.0
    non_carry_mode: str = "spot"
    long_perp_exposure_ratio: float = 1.0
    long_perp_enter_funding_apr: float = 0.0
    long_perp_exit_funding_apr: float = 0.002

    def _structure(self, initial_btc: float) -> tuple[float, float, float]:
        if self.use_ratio_structure:
            overlay_long_btc = initial_btc * self.overlay_borrow_ratio
            short_btc = initial_btc * self.hyper_borrow_ratio * self.hyper_short_leverage * self.hedge_ratio
            borrow_total_btc = initial_btc * (self.overlay_borrow_ratio + self.hyper_borrow_ratio)
            return overlay_long_btc, short_btc, borrow_total_btc
        overlay_long_btc = initial_btc * (self.target_leverage - 1.0)
        short_btc = overlay_long_btc * self.hedge_ratio
        borrow_total_btc = overlay_long_btc
        return overlay_long_btc, short_btc, borrow_total_btc

    def carry_weights(self) -> tuple[float, float]:
        base = 1.0
        overlay_long_btc, short_btc, borrow_total_btc = self._structure(base)
        funding_weight = abs(short_btc) / base
        borrow_weight = borrow_total_btc / base
        return funding_weight, borrow_weight

    def carry_edge_apr(self, rolling_funding_apr: float, borrow_apr: float) -> float:
        funding_weight, borrow_weight = self.carry_weights()
        return funding_weight * rolling_funding_apr - borrow_weight * borrow_apr

    def open_position(self, entry_ts, entry_price: float, initial_btc: float, start_in_carry: bool = True) -> CarryPosition:
        if self.target_leverage < 1.0:
            raise ValueError("target_leverage must be >= 1.0")
        if self.hedge_ratio < 0.0:
            raise ValueError("hedge_ratio must be >= 0.0")
        if self.long_perp_exposure_ratio < 0.0:
            raise ValueError("long_perp_exposure_ratio must be >= 0.0")
        if self.overlay_borrow_ratio < 0.0 or self.hyper_borrow_ratio < 0.0:
            raise ValueError("borrow ratios must be >= 0.0")
        if self.hyper_short_leverage < 0.0:
            raise ValueError("hyper_short_leverage must be >= 0.0")

        overlay_long_btc, short_btc, borrow_total_btc = self._structure(initial_btc)
        buffer_btc = max(borrow_total_btc - overlay_long_btc, 0.0)
        debt_usd = borrow_total_btc * entry_price if start_in_carry else 0.0
        setup_cost_usd = borrow_total_btc * entry_price * self.setup_cost_rate if start_in_carry else 0.0
        cash_buffer_usd = buffer_btc * entry_price if start_in_carry else 0.0

        position = CarryPosition(
            entry_ts=entry_ts,
            entry_price=float(entry_price),
            base_btc_qty=float(initial_btc),
            overlay_long_btc_qty=float(overlay_long_btc),
            short_btc_qty=float(short_btc),
            borrow_buffer_btc_qty=float(buffer_btc),
            long_perp_target_btc_qty=float(initial_btc * self.long_perp_exposure_ratio),
            debt_usd=float(debt_usd),
            cash_usd=float(cash_buffer_usd - setup_cost_usd),
            setup_cost_usd=float(setup_cost_usd),
            close_cost_usd=0.0,
            base_btc_target_qty=float(initial_btc),
            carry_active=start_in_carry,
            short_entry_price=float(entry_price) if start_in_carry else None,
            carry_entries=1 if start_in_carry else 0,
            perp_qty_btc=-float(short_btc) if start_in_carry else 0.0,
            perp_entry_price=float(entry_price) if start_in_carry and abs(short_btc) > 0 else None,
        )

        return position

    def should_enter_carry(self, rolling_edge_apr: float) -> bool:
        if not self.timing_enabled:
            return True
        if not math.isfinite(rolling_edge_apr):
            return False
        if rolling_edge_apr < self.enter_edge_apr:
            return False
        return self.payback_hours(rolling_edge_apr) <= max(self.carry_max_payback_hours, 0.0)

    def should_exit_carry(self, rolling_edge_apr: float, hold_events: int) -> bool:
        if not self.timing_enabled:
            return False
        if not math.isfinite(rolling_edge_apr):
            return False
        if hold_events < self.min_hold_funding_events:
            return False
        return rolling_edge_apr <= self.exit_edge_apr

    def payback_hours(self, rolling_edge_apr: float) -> float:
        if rolling_edge_apr <= 0.0 or not math.isfinite(rolling_edge_apr):
            return float("inf")
        roundtrip_cost_rate = max(self.setup_cost_rate, 0.0) + max(self.close_cost_rate, 0.0)
        if roundtrip_cost_rate <= 0.0:
            return 0.0
        return roundtrip_cost_rate * (8760.0 / rolling_edge_apr)

    def should_enter_long_perp(self, rolling_funding_apr: float) -> bool:
        if self.non_carry_mode != "long_perp":
            return False
        if not math.isfinite(rolling_funding_apr):
            return False
        return rolling_funding_apr <= self.long_perp_enter_funding_apr

    def should_exit_long_perp(self, rolling_funding_apr: float) -> bool:
        if not math.isfinite(rolling_funding_apr):
            return False
        return rolling_funding_apr >= self.long_perp_exit_funding_apr
