from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class BacktestContext:
    config: object
    market_data: object
    strategy: object
    recorder: object
