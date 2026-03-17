from __future__ import annotations

from typing import Protocol

from aave_hyper_carry_backtest.portfolio.position import CarryPosition


class Strategy(Protocol):
    def open_position(
        self,
        entry_ts,
        entry_price: float,
        initial_btc: float,
    ) -> CarryPosition: ...
