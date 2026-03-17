# Aave + Hyper Carry Backtest

## Summary

- Start equity: 9575599.00
- End equity: 6344548.80
- Total PnL: -3231050.20
- Funding PnL: 88297.79
- Borrow interest: 90267.67
- Gross carry PnL: -1969.88
- Setup cost: 71581.52
- Close cost: 94428.09
- Operation cost (open+close): 166009.61
- Net carry PnL: -167979.49
- Directional PnL: -3229080.32
- Total return: -33.74%
- Annualized return: -33.74%
- Max drawdown: -50.45%
- Annualized vol: 44.68%
- Sharpe: -0.6975
- Min health factor: 1.5618
- Carry entries/exits: 23/23
- Carry time share: 26.85%
- Spot time share: 73.15%
- Long-perp time share: 0.00%
- Short-perp time share: 26.85%
- Edge APR mean: -1.29%
- Edge APR positive share: 17.82%

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
  timing_window_events: 5
  enter_edge_apr: 0.0
  exit_edge_apr: -0.01
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
  run_name: sweep_ratio_w5_e0.0_x-0.01_p1000000000
  save_equity: true
  save_funding: true
  save_borrow: true

```
