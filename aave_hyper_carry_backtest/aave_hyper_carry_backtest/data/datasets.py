from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from aave_hyper_carry_backtest.config.schema import BacktestConfig


@dataclass(slots=True)
class Dataset:
    timeline: pd.DatetimeIndex
    spot: pd.DataFrame
    funding: pd.DataFrame
    borrow_apr: pd.DataFrame


def _read_table(path) -> pd.DataFrame:
    if str(path).lower().endswith(".parquet"):
        return pd.read_parquet(path)
    return pd.read_csv(path)


def _require_columns(df: pd.DataFrame, required: set[str], label: str) -> None:
    missing = sorted(required.difference(df.columns))
    if missing:
        raise ValueError(f"{label} missing columns: {missing}")


def _align_spot_to_timeline(spot: pd.DataFrame, timeline: pd.DatetimeIndex) -> pd.DataFrame:
    aligned = pd.DataFrame({"ts": timeline})
    out = pd.merge_asof(aligned, spot.sort_values("ts"), on="ts", direction="backward")
    out["spot_mid"] = out["spot_mid"].ffill().bfill()
    if out["spot_mid"].isna().any():
        raise ValueError("Spot alignment produced NaN prices")
    return out


def build_dataset(cfg: BacktestConfig) -> Dataset:
    spot_raw = _read_table(cfg.data.spot_path)
    _require_columns(spot_raw, {cfg.data.spot_ts_col, cfg.data.spot_price_col}, "spot")

    spot = spot_raw[[cfg.data.spot_ts_col, cfg.data.spot_price_col]].copy()
    spot.columns = ["ts", "spot_mid"]
    spot["ts"] = pd.to_datetime(spot["ts"], utc=True, format="mixed")
    spot = spot.sort_values("ts").drop_duplicates("ts", keep="last")

    funding_raw = _read_table(cfg.data.funding_path)
    _require_columns(funding_raw, {cfg.data.funding_ts_col, cfg.data.funding_rate_col}, "funding")

    funding_cols = [cfg.data.funding_ts_col, cfg.data.funding_rate_col]
    if cfg.data.funding_mark_price_col in funding_raw.columns:
        funding_cols.append(cfg.data.funding_mark_price_col)

    funding = funding_raw[funding_cols].copy()
    rename_map = {
        cfg.data.funding_ts_col: "funding_ts",
        cfg.data.funding_rate_col: "funding_rate",
    }
    if cfg.data.funding_mark_price_col in funding.columns:
        rename_map[cfg.data.funding_mark_price_col] = "mark_price"
    funding = funding.rename(columns=rename_map)

    funding["funding_ts"] = pd.to_datetime(funding["funding_ts"], utc=True, format="mixed")
    # Exchange exports can have tiny sub-second drift (e.g. HH:00:00.001),
    # so align funding timestamps to bar grid before engine matching.
    funding["funding_ts"] = funding["funding_ts"].dt.round(cfg.bar_step)
    funding = funding.sort_values("funding_ts").drop_duplicates("funding_ts", keep="last")

    borrow_apr = pd.DataFrame(columns=["ts", "borrow_apr"])
    if cfg.data.borrow_apr_path:
        borrow_raw = _read_table(cfg.data.borrow_apr_path)
        _require_columns(borrow_raw, {cfg.data.borrow_apr_ts_col, cfg.data.borrow_apr_col}, "borrow APR")
        borrow_apr = borrow_raw[[cfg.data.borrow_apr_ts_col, cfg.data.borrow_apr_col]].copy()
        borrow_apr.columns = ["ts", "borrow_apr"]
        borrow_apr["ts"] = pd.to_datetime(borrow_apr["ts"], utc=True, format="mixed")
        borrow_apr = borrow_apr.sort_values("ts").drop_duplicates("ts", keep="last")

    timeline = pd.date_range(cfg.start_ts, cfg.end_ts, freq=cfg.bar_step, tz="UTC")

    spot = spot[(spot["ts"] >= cfg.start_ts) & (spot["ts"] <= cfg.end_ts)].copy()
    if spot.empty:
        raise ValueError("No spot data in selected backtest range")
    spot_aligned = _align_spot_to_timeline(spot, timeline)

    funding = funding[(funding["funding_ts"] >= cfg.start_ts) & (funding["funding_ts"] <= cfg.end_ts)].copy()

    if not borrow_apr.empty:
        borrow_apr = borrow_apr[(borrow_apr["ts"] >= cfg.start_ts) & (borrow_apr["ts"] <= cfg.end_ts)].copy()

    return Dataset(
        timeline=timeline,
        spot=spot_aligned.reset_index(drop=True),
        funding=funding.reset_index(drop=True),
        borrow_apr=borrow_apr.reset_index(drop=True),
    )
