from __future__ import annotations

from pathlib import Path

import pandas as pd

from aave_hyper_carry_backtest.backtest.context import BacktestContext
from aave_hyper_carry_backtest.backtest.engine import BacktestEngine
from aave_hyper_carry_backtest.backtest.recorder import Recorder
from aave_hyper_carry_backtest.config.schema import BacktestConfig, DataConfig, ResultsConfig, StrategyConfig
from aave_hyper_carry_backtest.data.datasets import Dataset
from aave_hyper_carry_backtest.market.data import HistoricalMarketData
from aave_hyper_carry_backtest.strategy.carry_trade import AaveHyperCarryStrategy



def _config(start_ts: pd.Timestamp, end_ts: pd.Timestamp, borrow_apr: float, setup_cost_rate: float) -> BacktestConfig:
    return BacktestConfig(
        start_ts=start_ts,
        end_ts=end_ts,
        bar_step="1h",
        initial_btc=100.0,
        strategy=StrategyConfig(
            target_leverage=2.0,
            hedge_ratio=1.0,
            aave_borrow_apr=borrow_apr,
            setup_cost_rate=setup_cost_rate,
            liquidation_threshold=0.8,
        ),
        data=DataConfig(
            spot_path=Path("spot.csv"),
            funding_path=Path("funding.csv"),
            borrow_apr_path=None,
            spot_ts_col="ts",
            spot_price_col="spot_mid",
            funding_ts_col="funding_ts",
            funding_rate_col="funding_rate",
            funding_mark_price_col="mark_price",
            borrow_apr_ts_col="ts",
            borrow_apr_col="borrow_apr",
        ),
        results=ResultsConfig(
            results_dir=Path("results"),
            run_name="",
            save_equity=True,
            save_funding=True,
            save_borrow=True,
        ),
    )



def _run(cfg: BacktestConfig, dataset: Dataset) -> dict[str, float]:
    market_data = HistoricalMarketData(dataset)
    strategy = AaveHyperCarryStrategy(
        target_leverage=cfg.strategy.target_leverage,
        hedge_ratio=cfg.strategy.hedge_ratio,
        setup_cost_rate=cfg.strategy.setup_cost_rate,
    )
    recorder = Recorder()
    ctx = BacktestContext(config=cfg, market_data=market_data, strategy=strategy, recorder=recorder)
    return BacktestEngine(ctx=ctx).run()



def test_positive_carry_for_10p9_vs_5p16_apr() -> None:
    timeline = pd.date_range("2025-01-01T00:00:00Z", periods=24 * 365 + 1, freq="1h", tz="UTC")

    funding_rate_hourly = 0.109 / 8760.0
    spot = pd.DataFrame({"ts": timeline, "spot_mid": [100_000.0] * len(timeline)})
    funding = pd.DataFrame(
        {
            "funding_ts": timeline,
            "funding_rate": [funding_rate_hourly] * len(timeline),
            "mark_price": [100_000.0] * len(timeline),
        }
    )
    dataset = Dataset(
        timeline=timeline,
        spot=spot,
        funding=funding,
        borrow_apr=pd.DataFrame(columns=["ts", "borrow_apr"]),
    )

    cfg = _config(timeline[0], timeline[-1], borrow_apr=0.0516, setup_cost_rate=0.0005)
    summary = _run(cfg, dataset)

    assert summary["net_carry_pnl"] > 500_000.0
    assert summary["funding_pnl"] > summary["borrow_interest"]
    assert abs(summary["directional_pnl"]) < 1e-6



def test_net_directional_exposure_is_plus_100_btc() -> None:
    timeline = pd.date_range("2025-01-01T00:00:00Z", periods=25, freq="1h", tz="UTC")
    start_price = 100_000.0
    end_price = 120_000.0
    spot_prices = [start_price + (end_price - start_price) * i / (len(timeline) - 1) for i in range(len(timeline))]

    spot = pd.DataFrame({"ts": timeline, "spot_mid": spot_prices})
    funding = pd.DataFrame(
        {
            "funding_ts": timeline,
            "funding_rate": [0.0] * len(timeline),
            "mark_price": spot_prices,
        }
    )
    dataset = Dataset(
        timeline=timeline,
        spot=spot,
        funding=funding,
        borrow_apr=pd.DataFrame(columns=["ts", "borrow_apr"]),
    )

    cfg = _config(timeline[0], timeline[-1], borrow_apr=0.0, setup_cost_rate=0.0)
    summary = _run(cfg, dataset)

    expected_pnl = 100.0 * (end_price - start_price)
    assert abs(summary["total_pnl"] - expected_pnl) < 1e-6
    assert abs(summary["net_carry_pnl"]) < 1e-6
