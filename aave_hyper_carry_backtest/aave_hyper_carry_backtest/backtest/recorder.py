from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from aave_hyper_carry_backtest.backtest.reporting import build_report
from aave_hyper_carry_backtest.utils.io import atomic_write_json, atomic_write_parquet, atomic_write_text, atomic_write_yaml, ensure_dir


@dataclass(slots=True)
class Recorder:
    save_equity: bool = True
    save_funding: bool = True
    save_borrow: bool = True
    equity_rows: list[dict[str, Any]] = field(default_factory=list)
    funding_rows: list[dict[str, Any]] = field(default_factory=list)
    borrow_rows: list[dict[str, Any]] = field(default_factory=list)

    def record_equity(self, row: dict[str, Any]) -> None:
        self.equity_rows.append(row)

    def record_funding(self, row: dict[str, Any]) -> None:
        self.funding_rows.append(row)

    def record_borrow(self, row: dict[str, Any]) -> None:
        self.borrow_rows.append(row)

    def equity_df(self) -> pd.DataFrame:
        df = pd.DataFrame(self.equity_rows)
        if not df.empty:
            df["ts"] = pd.to_datetime(df["ts"], utc=True)
            df = df.sort_values("ts").reset_index(drop=True)
        return df

    def funding_df(self) -> pd.DataFrame:
        df = pd.DataFrame(self.funding_rows)
        if not df.empty:
            df["ts"] = pd.to_datetime(df["ts"], utc=True)
            df = df.sort_values("ts").reset_index(drop=True)
        return df

    def borrow_df(self) -> pd.DataFrame:
        df = pd.DataFrame(self.borrow_rows)
        if not df.empty:
            df["ts"] = pd.to_datetime(df["ts"], utc=True)
            df = df.sort_values("ts").reset_index(drop=True)
        return df

    def save_to_dir(self, run_dir: Path, config_payload: dict[str, Any], summary: dict[str, Any]) -> None:
        ensure_dir(run_dir)

        equity = self.equity_df()
        funding = self.funding_df()
        borrow = self.borrow_df()

        atomic_write_yaml(run_dir / "config.yaml", config_payload)
        atomic_write_json(run_dir / "summary.json", summary)

        if self.save_equity and not equity.empty:
            atomic_write_parquet(run_dir / "equity_curve.parquet", equity)
        if self.save_funding and not funding.empty:
            atomic_write_parquet(run_dir / "funding.parquet", funding)
        if self.save_borrow and not borrow.empty:
            atomic_write_parquet(run_dir / "borrow.parquet", borrow)

        report = build_report(summary, config_payload)
        atomic_write_text(run_dir / "report.md", report)
