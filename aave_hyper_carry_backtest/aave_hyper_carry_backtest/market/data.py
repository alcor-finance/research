from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from aave_hyper_carry_backtest.data.datasets import Dataset


@dataclass
class HistoricalMarketData:
    dataset: Dataset

    def __post_init__(self) -> None:
        self.timeline = self.dataset.timeline

        self._spot = self.dataset.spot.set_index("ts").sort_index()

        funding = self.dataset.funding.copy()
        if "mark_price" not in funding.columns:
            funding["mark_price"] = pd.NA
        self._funding = funding.set_index("funding_ts").sort_index()

        self._funding_index = self._funding.index
        self._funding_set = set(self._funding_index)

        self._borrow = self.dataset.borrow_apr.copy()
        if not self._borrow.empty:
            self._borrow = self._borrow.set_index("ts").sort_index()

    def get_spot_mid(self, ts: pd.Timestamp) -> float:
        return float(self._spot.loc[ts, "spot_mid"])

    def is_funding_timestamp(self, ts: pd.Timestamp) -> bool:
        return ts in self._funding_set

    def get_funding_rate(self, ts: pd.Timestamp) -> float:
        return float(self._funding.loc[ts, "funding_rate"])

    def get_funding_mark_price(self, ts: pd.Timestamp) -> float:
        mark = self._funding.loc[ts, "mark_price"]
        if pd.isna(mark):
            return self.get_spot_mid(ts)
        return float(mark)

    def get_borrow_apr(self, ts: pd.Timestamp, fallback_apr: float) -> float:
        if self._borrow.empty:
            return float(fallback_apr)
        idx = self._borrow.index.searchsorted(ts, side="right") - 1
        if idx < 0:
            return float(fallback_apr)
        return float(self._borrow.iloc[idx]["borrow_apr"])
