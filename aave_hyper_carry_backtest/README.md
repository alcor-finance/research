# Aave + Hyperliquid Carry Backtest

Backtest for hypothesis:

- hold `+100 BTC` net directional exposure,
- build `2x` spot-long using Aave borrow,
- open `1x` BTC perp short on Hyperliquid,
- earn funding on short, pay borrow APR on Aave.

## Strategy model

Given `initial_btc = 100`, `target_leverage = 2.0`, `hedge_ratio = 1.0`:

- spot holdings become `200 BTC`,
- perp short is `100 BTC`,
- USD debt starts at `100 BTC * entry_price`,
- one-time setup cost is `setup_cost_rate * 100 BTC * entry_price`.

PnL decomposition:

- `funding_pnl`: short funding cashflows,
- `borrow_interest`: accrued debt interest,
- `setup_cost`: one-time opening cost,
- `net_carry_pnl = funding_pnl - borrow_interest - setup_cost`,
- `directional_pnl`: residual PnL from net +BTC exposure.

## Install

```bash
cd aave_hyper_carry_backtest
pip install -e .
```

## Run

```bash
python -m src.run_backtest --config config/defaults.yaml
```

Output in `results/<run_id>/`:

- `summary.json`
- `report.md`
- `equity_curve.parquet`
- `funding.parquet`
- `borrow.parquet`
- `operations.parquet` (full operation ledger: funding + borrow)
- `equity_and_operations.png` (equity + all operation cashflows + risk metrics)
- `carry_components.png` (cumulative PnL decomposition)

## Tests

```bash
pytest -q tests
```
