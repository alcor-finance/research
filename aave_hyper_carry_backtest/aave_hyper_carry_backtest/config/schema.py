from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import yaml


@dataclass(slots=True)
class StrategyConfig:
    target_leverage: float = 2.0
    hedge_ratio: float = 1.0
    use_ratio_structure: bool = False
    overlay_borrow_ratio: float = 0.4
    hyper_borrow_ratio: float = 0.2
    hyper_short_leverage: float = 2.0
    aave_borrow_apr: float = 0.0516
    setup_cost_rate: float = 0.0005
    close_cost_rate: float = 0.0005
    liquidation_threshold: float = 0.8
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


@dataclass(slots=True)
class DataConfig:
    spot_path: Path
    funding_path: Path
    borrow_apr_path: Path | None
    spot_ts_col: str
    spot_price_col: str
    funding_ts_col: str
    funding_rate_col: str
    funding_mark_price_col: str
    borrow_apr_ts_col: str
    borrow_apr_col: str


@dataclass(slots=True)
class ResultsConfig:
    results_dir: Path
    run_name: str
    save_equity: bool
    save_funding: bool
    save_borrow: bool


@dataclass(slots=True)
class BacktestConfig:
    start_ts: pd.Timestamp
    end_ts: pd.Timestamp
    bar_step: str
    initial_btc: float
    strategy: StrategyConfig
    data: DataConfig
    results: ResultsConfig


def _to_timestamp(value: str | pd.Timestamp) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if ts.tz is None:
        ts = ts.tz_localize("UTC")
    return ts.tz_convert("UTC")


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        payload = yaml.safe_load(fh) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"Config at {path} must be a mapping")
    return payload


def _resolve_path(base_dir: Path, raw: str) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path
    return (base_dir / path).resolve()


def _maybe_resolve_path(base_dir: Path, raw: str | None) -> Path | None:
    if not raw:
        return None
    return _resolve_path(base_dir, raw)


def load_config(path: str | Path) -> BacktestConfig:
    cfg_path = Path(path)
    payload = _load_yaml(cfg_path)
    base_dir = cfg_path.parent

    strategy = payload.get("strategy", {})
    data = payload.get("data", {})
    results = payload.get("results", {})

    return BacktestConfig(
        start_ts=_to_timestamp(payload["start_ts"]),
        end_ts=_to_timestamp(payload["end_ts"]),
        bar_step=str(payload.get("bar_step", "1h")),
        initial_btc=float(payload.get("initial_btc", 100.0)),
        strategy=StrategyConfig(
            target_leverage=float(strategy.get("target_leverage", 2.0)),
            hedge_ratio=float(strategy.get("hedge_ratio", 1.0)),
            use_ratio_structure=bool(strategy.get("use_ratio_structure", False)),
            overlay_borrow_ratio=float(strategy.get("overlay_borrow_ratio", 0.4)),
            hyper_borrow_ratio=float(strategy.get("hyper_borrow_ratio", 0.2)),
            hyper_short_leverage=float(strategy.get("hyper_short_leverage", 2.0)),
            aave_borrow_apr=float(strategy.get("aave_borrow_apr", 0.0516)),
            setup_cost_rate=float(strategy.get("setup_cost_rate", 0.0005)),
            close_cost_rate=float(strategy.get("close_cost_rate", 0.0005)),
            liquidation_threshold=float(strategy.get("liquidation_threshold", 0.8)),
            timing_enabled=bool(strategy.get("timing_enabled", False)),
            timing_window_events=int(strategy.get("timing_window_events", 21)),
            enter_edge_apr=float(strategy.get("enter_edge_apr", 0.0)),
            exit_edge_apr=float(strategy.get("exit_edge_apr", -0.005)),
            carry_max_payback_hours=float(strategy.get("carry_max_payback_hours", 720.0)),
            min_hold_funding_events=int(strategy.get("min_hold_funding_events", 1)),
            default_funding_interval_hours=float(strategy.get("default_funding_interval_hours", 8.0)),
            non_carry_mode=str(strategy.get("non_carry_mode", "spot")),
            long_perp_exposure_ratio=float(strategy.get("long_perp_exposure_ratio", 1.0)),
            long_perp_enter_funding_apr=float(strategy.get("long_perp_enter_funding_apr", 0.0)),
            long_perp_exit_funding_apr=float(strategy.get("long_perp_exit_funding_apr", 0.002)),
        ),
        data=DataConfig(
            spot_path=_resolve_path(base_dir, str(data.get("spot_path", ""))),
            funding_path=_resolve_path(base_dir, str(data.get("funding_path", ""))),
            borrow_apr_path=_maybe_resolve_path(base_dir, data.get("borrow_apr_path")),
            spot_ts_col=str(data.get("spot_ts_col", "ts")),
            spot_price_col=str(data.get("spot_price_col", "spot_mid")),
            funding_ts_col=str(data.get("funding_ts_col", "funding_ts")),
            funding_rate_col=str(data.get("funding_rate_col", "funding_rate")),
            funding_mark_price_col=str(data.get("funding_mark_price_col", "mark_price")),
            borrow_apr_ts_col=str(data.get("borrow_apr_ts_col", "ts")),
            borrow_apr_col=str(data.get("borrow_apr_col", "borrow_apr")),
        ),
        results=ResultsConfig(
            results_dir=_resolve_path(base_dir, str(results.get("results_dir", "results"))),
            run_name=str(results.get("run_name", "")),
            save_equity=bool(results.get("save_equity", True)),
            save_funding=bool(results.get("save_funding", True)),
            save_borrow=bool(results.get("save_borrow", True)),
        ),
    )
