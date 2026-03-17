# Aave + Hyper Carry Backtest

## Summary

- Start equity: 9575599.00
- End equity: 6409955.67
- Total PnL: -3165643.33
- Funding PnL: 133510.21
- Borrow interest: 157402.58
- Gross carry PnL: -23892.37
- Setup cost: 16195.65
- Close cost: 19818.92
- Operation cost (open+close): 36014.56
- Net carry PnL: -59906.93
- Directional PnL: -3141750.96
- Total return: -33.06%
- Annualized return: -33.06%
- Max drawdown: -50.28%
- Annualized vol: 44.68%
- Sharpe: -0.6744
- Min health factor: 1.3887
- Carry entries/exits: 5/5
- Carry time share: 47.39%
- Spot time share: 52.61%
- Long-perp time share: 0.00%
- Short-perp time share: 47.39%
- Edge APR mean: -1.29%
- Edge APR positive share: 15.08%

## Config

```yaml
start_ts: '2025-02-23T19:00:00+00:00'
end_ts: '2026-02-23T19:00:00+00:00'
bar_step: 1h
initial_btc: 100.0
strategy:
  target_leverage: 2.0
  hedge_ratio: 1.0
  use_ratio_structure: true
  overlay_borrow_ratio: 0.4
  hyper_borrow_ratio: 0.2
  hyper_short_leverage: 2.0
  aave_borrow_apr: 0.0515
  setup_cost_rate: 0.0005
  close_cost_rate: 0.0005
  liquidation_threshold: 0.8
  timing_enabled: true
  timing_window_events: 9
  enter_edge_apr: 0.0
  exit_edge_apr: -0.02
  carry_max_payback_hours: 1000000000.0
  min_hold_funding_events: 1
  default_funding_interval_hours: 8.0
  non_carry_mode: spot
  long_perp_exposure_ratio: 1.0
  long_perp_enter_funding_apr: 0.0
  long_perp_exit_funding_apr: 0.0
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
  run_name: sweep_ratio_w9_e0.0_x-0.02_p1000000000
  save_equity: true
  save_funding: true
  save_borrow: true

```
