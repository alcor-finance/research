from __future__ import annotations

from pathlib import Path

import pandas as pd

from aave_hyper_carry_backtest.config.schema import BacktestConfig, DataConfig, ResultsConfig, StrategyConfig
from aave_hyper_carry_backtest.data.datasets import build_dataset


def test_build_dataset_aligns_to_hourly_timeline(tmp_path: Path) -> None:
    spot_path = tmp_path / "spot.csv"
    funding_path = tmp_path / "funding.csv"

    pd.DataFrame(
        {
            "ts": [
                "2025-01-01T00:00:00Z",
                "2025-01-01T02:00:00Z",
            ],
            "spot_mid": [100_000.0, 102_000.0],
        }
    ).to_csv(spot_path, index=False)

    pd.DataFrame(
        {
            "funding_ts": ["2025-01-01T02:00:00Z"],
            "funding_rate": [0.0001],
            "mark_price": [102_000.0],
        }
    ).to_csv(funding_path, index=False)

    cfg = BacktestConfig(
        start_ts=pd.Timestamp("2025-01-01T00:00:00Z"),
        end_ts=pd.Timestamp("2025-01-01T03:00:00Z"),
        bar_step="1h",
        initial_btc=100.0,
        strategy=StrategyConfig(
            target_leverage=2.0,
            hedge_ratio=1.0,
            aave_borrow_apr=0.0516,
            setup_cost_rate=0.0005,
            liquidation_threshold=0.8,
        ),
        data=DataConfig(
            spot_path=spot_path,
            funding_path=funding_path,
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

    dataset = build_dataset(cfg)

    assert len(dataset.timeline) == 4
    assert len(dataset.spot) == 4
    assert dataset.spot["spot_mid"].tolist() == [100_000.0, 100_000.0, 102_000.0, 102_000.0]
    assert len(dataset.funding) == 1
    assert float(dataset.funding["funding_rate"].iloc[0]) == 0.0001
