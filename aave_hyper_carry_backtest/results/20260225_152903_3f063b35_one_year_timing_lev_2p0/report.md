# Aave + Hyper Carry Backtest

## Summary

- Start equity: 9575599.00
- End equity: 6225157.65
- Total PnL: -3350441.35
- Funding PnL: -122570.29
- Borrow interest: 80438.29
- Gross carry PnL: -203008.58
- Setup cost: 19948.89
- Net carry PnL: -222957.47
- Directional PnL: -3147432.76
- Total return: -34.99%
- Annualized return: -34.99%
- Max drawdown: -51.25%
- Annualized vol: 45.28%
- Sharpe: -0.7242
- Min health factor: 0.0000
- Carry entries/exits: 4/4
- Carry time share: 13.79%
- Spot time share: 0.00%
- Long-perp time share: 86.21%
- Short-perp time share: 13.79%
- Edge APR mean: -1.94%
- Edge APR positive share: 10.05%

## Config

```yaml
start_ts: '2025-02-23T19:00:00+00:00'
end_ts: '2026-02-23T19:00:00+00:00'
bar_step: 1h
initial_btc: 100.0
strategy:
  target_leverage: 2.0
  hedge_ratio: 1.0
  aave_borrow_apr: 0.0516
  setup_cost_rate: 0.0005
  liquidation_threshold: 0.8
  timing_enabled: true
  timing_window_events: 21
  enter_edge_apr: 0.0
  exit_edge_apr: -0.005
  min_hold_funding_events: 2
  default_funding_interval_hours: 8.0
  non_carry_mode: long_perp
  long_perp_exposure_ratio: 1.0
data:
  spot_path: /Users/igoreshka/Desktop/alcor-backtests/btc_perp_backtest/data/raw/binance_1y_strict/spot.csv
  funding_path: /Users/igoreshka/Desktop/alcor-backtests/btc_perp_backtest/data/raw/binance_1y_strict/funding.csv
  borrow_apr_path: null
  spot_ts_col: ts
  spot_price_col: spot_mid
  funding_ts_col: funding_ts
  funding_rate_col: funding_rate
  funding_mark_price_col: mark_price
  borrow_apr_ts_col: ts
  borrow_apr_col: borrow_apr
results:
  results_dir: /Users/igoreshka/Desktop/alcor-backtests/aave_hyper_carry_backtest/results
  run_name: one_year_timing_lev_2p0
  save_equity: true
  save_funding: true
  save_borrow: true

```
