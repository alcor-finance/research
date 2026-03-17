from __future__ import annotations

import argparse
import dataclasses
import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from aave_hyper_carry_backtest.backtest.context import BacktestContext
from aave_hyper_carry_backtest.backtest.engine import BacktestEngine
from aave_hyper_carry_backtest.backtest.plotting import save_run_plots
from aave_hyper_carry_backtest.backtest.recorder import Recorder
from aave_hyper_carry_backtest.config.schema import BacktestConfig, load_config
from aave_hyper_carry_backtest.data.datasets import build_dataset
from aave_hyper_carry_backtest.market.data import HistoricalMarketData
from aave_hyper_carry_backtest.strategy.carry_trade import AaveHyperCarryStrategy


def _to_serializable(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return {k: _to_serializable(v) for k, v in dataclasses.asdict(value).items()}
    if isinstance(value, dict):
        return {k: _to_serializable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_serializable(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def _run_id(cfg: BacktestConfig) -> str:
    now = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    payload = str(_to_serializable(cfg))
    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:8]
    base = f"{now}_{digest}"
    if cfg.results.run_name:
        return f"{base}_{cfg.results.run_name}"
    return base


def run_from_config(cfg: BacktestConfig, save_plots: bool = True) -> tuple[str, Path, dict[str, float]]:
    dataset = build_dataset(cfg)
    market_data = HistoricalMarketData(dataset)

    strategy = AaveHyperCarryStrategy(
        target_leverage=cfg.strategy.target_leverage,
        hedge_ratio=cfg.strategy.hedge_ratio,
        use_ratio_structure=cfg.strategy.use_ratio_structure,
        overlay_borrow_ratio=cfg.strategy.overlay_borrow_ratio,
        hyper_borrow_ratio=cfg.strategy.hyper_borrow_ratio,
        hyper_short_leverage=cfg.strategy.hyper_short_leverage,
        setup_cost_rate=cfg.strategy.setup_cost_rate,
        close_cost_rate=cfg.strategy.close_cost_rate,
        timing_enabled=cfg.strategy.timing_enabled,
        timing_window_events=cfg.strategy.timing_window_events,
        enter_edge_apr=cfg.strategy.enter_edge_apr,
        exit_edge_apr=cfg.strategy.exit_edge_apr,
        carry_max_payback_hours=cfg.strategy.carry_max_payback_hours,
        min_hold_funding_events=cfg.strategy.min_hold_funding_events,
        default_funding_interval_hours=cfg.strategy.default_funding_interval_hours,
        non_carry_mode=cfg.strategy.non_carry_mode,
        long_perp_exposure_ratio=cfg.strategy.long_perp_exposure_ratio,
        long_perp_enter_funding_apr=cfg.strategy.long_perp_enter_funding_apr,
        long_perp_exit_funding_apr=cfg.strategy.long_perp_exit_funding_apr,
    )
    recorder = Recorder(
        save_equity=cfg.results.save_equity,
        save_funding=cfg.results.save_funding,
        save_borrow=cfg.results.save_borrow,
    )

    ctx = BacktestContext(
        config=cfg,
        market_data=market_data,
        strategy=strategy,
        recorder=recorder,
    )
    engine = BacktestEngine(ctx=ctx)
    summary = engine.run()

    run_id = _run_id(cfg)
    run_dir = Path(cfg.results.results_dir) / run_id

    config_payload = _to_serializable(cfg)
    recorder.save_to_dir(run_dir=run_dir, config_payload=config_payload, summary=summary)
    if save_plots:
        save_run_plots(
            run_dir=run_dir,
            equity=recorder.equity_df(),
            funding=recorder.funding_df(),
            borrow=recorder.borrow_df(),
            summary=summary,
        )

    return run_id, run_dir, summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Aave + Hyperliquid carry backtest")
    parser.add_argument("--config", required=True, help="Path to YAML config")
    parser.add_argument("--skip-plots", action="store_true", help="Skip PNG plot generation")
    args = parser.parse_args()

    cfg = load_config(args.config)
    run_id, run_dir, summary = run_from_config(cfg, save_plots=not args.skip_plots)

    print(f"Run complete: {run_id}")
    print(f"Results dir: {run_dir}")
    print(f"End equity: {summary['end_equity']:.2f}")
    print(f"Net carry PnL: {summary['net_carry_pnl']:.2f}")


if __name__ == "__main__":
    main()
