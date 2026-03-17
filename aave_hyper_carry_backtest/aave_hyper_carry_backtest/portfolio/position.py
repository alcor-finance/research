from __future__ import annotations

from dataclasses import dataclass
from math import exp


@dataclass(slots=True)
class CarryPosition:
    entry_ts: object
    entry_price: float
    base_btc_qty: float
    overlay_long_btc_qty: float
    short_btc_qty: float
    borrow_buffer_btc_qty: float
    long_perp_target_btc_qty: float
    debt_usd: float
    cash_usd: float
    setup_cost_usd: float
    close_cost_usd: float
    base_btc_target_qty: float
    carry_active: bool = True
    short_entry_price: float | None = None
    carry_entries: int = 1
    carry_exits: int = 0
    carry_hold_funding_events: int = 0
    funding_pnl_usd: float = 0.0
    borrow_interest_usd: float = 0.0
    perp_qty_btc: float = 0.0
    perp_entry_price: float | None = None

    @property
    def total_spot_btc_qty(self) -> float:
        if self.carry_active:
            return self.base_btc_qty + self.overlay_long_btc_qty
        return self.base_btc_qty

    def mode(self) -> str:
        if self.carry_active:
            return "carry"
        if self.perp_qty_btc > 1e-12:
            return "long_perp"
        if self.perp_qty_btc < -1e-12:
            return "short_perp"
        return "spot"

    def _close_perp(self, spot_price: float) -> float:
        if abs(self.perp_qty_btc) <= 1e-12:
            return 0.0
        entry = self.perp_entry_price if self.perp_entry_price is not None else self.entry_price
        realized = (spot_price - entry) * self.perp_qty_btc
        self.cash_usd += realized
        self.perp_qty_btc = 0.0
        self.perp_entry_price = None
        return realized

    def _open_perp(self, qty_btc: float, spot_price: float) -> None:
        self.perp_qty_btc = qty_btc
        self.perp_entry_price = spot_price if abs(qty_btc) > 1e-12 else None

    def accrue_borrow(self, hours: float, apr: float) -> float:
        if not self.carry_active or hours <= 0.0 or self.debt_usd <= 0.0 or apr <= 0.0:
            return 0.0
        growth = exp(apr * (hours / 8760.0)) - 1.0
        interest = self.debt_usd * growth
        self.debt_usd += interest
        self.borrow_interest_usd += interest
        return interest

    def apply_funding(self, rate: float, mark_price: float) -> float:
        if abs(self.perp_qty_btc) <= 1e-12:
            return 0.0
        # Positive rate => longs pay shorts.
        cashflow = -self.perp_qty_btc * mark_price * rate
        self.cash_usd += cashflow
        self.funding_pnl_usd += cashflow
        if self.carry_active:
            self.carry_hold_funding_events += 1
        return cashflow

    def collateral_usd(self, spot_price: float) -> float:
        return self.total_spot_btc_qty * spot_price

    def perp_unrealized_pnl_usd(self, spot_price: float) -> float:
        if abs(self.perp_qty_btc) <= 1e-12:
            return 0.0
        entry = self.perp_entry_price if self.perp_entry_price is not None else self.entry_price
        return (spot_price - entry) * self.perp_qty_btc

    def equity_usd(self, spot_price: float) -> float:
        return self.collateral_usd(spot_price) + self.perp_unrealized_pnl_usd(spot_price) + self.cash_usd - self.debt_usd

    def operation_cost_usd(self) -> float:
        return self.setup_cost_usd + self.close_cost_usd

    def enter_long_perp(self, ts, spot_price: float) -> dict[str, float]:
        if self.mode() == "long_perp":
            return {"spot_sold_btc": 0.0, "long_qty_btc": self.perp_qty_btc}
        if self.carry_active:
            self.exit_carry(ts=ts, spot_price=spot_price, non_carry_mode="spot")
        spot_sold = self.base_btc_qty
        self.cash_usd += spot_sold * spot_price
        self.base_btc_qty = 0.0
        target = self.long_perp_target_btc_qty if self.long_perp_target_btc_qty > 0 else spot_sold
        self._open_perp(target, spot_price)
        del ts
        return {"spot_sold_btc": spot_sold, "long_qty_btc": target}

    def exit_long_perp(self, ts, spot_price: float) -> dict[str, float]:
        if self.mode() != "long_perp":
            return {"perp_closed_qty": 0.0, "spot_bought_btc": 0.0}
        qty = self.perp_qty_btc
        self._close_perp(spot_price)
        if spot_price > 0:
            max_buy = max(self.cash_usd, 0.0) / spot_price
            to_buy = min(self.base_btc_target_qty, max_buy)
        else:
            to_buy = 0.0
        self.base_btc_qty += to_buy
        self.cash_usd -= to_buy * spot_price
        del ts
        return {"perp_closed_qty": qty, "spot_bought_btc": to_buy}

    def enter_carry(self, ts, spot_price: float, setup_cost_rate: float) -> dict[str, float]:
        if self.carry_active:
            return {"setup_cost": 0.0, "borrow_notional": 0.0}

        if self.mode() == "long_perp":
            self.exit_long_perp(ts=ts, spot_price=spot_price)

        if self.base_btc_qty < self.base_btc_target_qty and spot_price > 0:
            max_buy = max(self.cash_usd, 0.0) / spot_price
            to_buy = min(self.base_btc_target_qty - self.base_btc_qty, max_buy)
            self.base_btc_qty += to_buy
            self.cash_usd -= to_buy * spot_price

        overlay_borrow_notional = self.overlay_long_btc_qty * spot_price
        buffer_borrow_notional = self.borrow_buffer_btc_qty * spot_price
        borrow_notional = overlay_borrow_notional + buffer_borrow_notional
        setup_cost = borrow_notional * setup_cost_rate
        self.debt_usd += borrow_notional
        self.cash_usd += buffer_borrow_notional
        self.cash_usd -= setup_cost
        self.setup_cost_usd += setup_cost
        self.short_entry_price = spot_price
        self._open_perp(-self.short_btc_qty, spot_price)
        self.carry_active = True
        self.carry_entries += 1
        self.carry_hold_funding_events = 0
        del ts
        return {"setup_cost": setup_cost, "borrow_notional": borrow_notional}

    def exit_carry(
        self,
        ts,
        spot_price: float,
        close_cost_rate: float = 0.0,
        non_carry_mode: str = "spot",
    ) -> dict[str, float]:
        if not self.carry_active:
            return {"short_realized": 0.0, "debt_repaid": 0.0, "base_btc_sold_for_repay": 0.0, "close_cost": 0.0}

        short_realized = self._close_perp(spot_price)
        overlay_sale_usd = self.overlay_long_btc_qty * spot_price
        self.cash_usd += overlay_sale_usd
        close_notional = overlay_sale_usd + (abs(self.short_btc_qty) * spot_price)
        close_cost = max(close_cost_rate, 0.0) * close_notional
        self.cash_usd -= close_cost
        self.close_cost_usd += close_cost

        debt_repaid = min(self.debt_usd, max(self.cash_usd, 0.0))
        self.debt_usd -= debt_repaid
        self.cash_usd -= debt_repaid

        base_btc_sold = 0.0
        if self.debt_usd > 0 and spot_price > 0 and self.base_btc_qty > 0:
            need_btc = min(self.base_btc_qty, self.debt_usd / spot_price)
            base_btc_sold = need_btc
            self.base_btc_qty -= need_btc
            repay_from_base = need_btc * spot_price
            self.debt_usd = max(self.debt_usd - repay_from_base, 0.0)

        self.carry_active = False
        self.carry_exits += 1
        self.carry_hold_funding_events = 0
        if non_carry_mode == "long_perp":
            self.enter_long_perp(ts=ts, spot_price=spot_price)
        del ts
        return {
            "short_realized": short_realized,
            "debt_repaid": debt_repaid,
            "base_btc_sold_for_repay": base_btc_sold,
            "close_cost": close_cost,
        }

    def ltv(self, spot_price: float) -> float:
        if self.debt_usd <= 0.0:
            return 0.0
        collateral = self.collateral_usd(spot_price)
        if collateral <= 0.0:
            return float("inf")
        return self.debt_usd / collateral

    def health_factor(self, spot_price: float, liquidation_threshold: float) -> float:
        if self.debt_usd <= 0.0:
            return float("inf")
        collateral = self.collateral_usd(spot_price)
        return (collateral * liquidation_threshold) / self.debt_usd
