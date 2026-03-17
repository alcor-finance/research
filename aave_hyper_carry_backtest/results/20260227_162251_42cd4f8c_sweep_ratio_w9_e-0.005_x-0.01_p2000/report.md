# Aave + Hyper Carry Backtest

## Summary

- Start equity: 9575599.00
- End equity: 6418743.66
- Total PnL: -3156855.34
- Funding PnL: 65414.94
- Borrow interest: 64771.72
- Gross carry PnL: 643.21
- Setup cost: 23675.18
- Close cost: 30145.37
- Operation cost (open+close): 53820.54
- Net carry PnL: -53177.33
- Directional PnL: -3157498.55
- Total return: -32.97%
- Annualized return: -32.97%
- Max drawdown: -50.19%
- Annualized vol: 44.68%
- Sharpe: -0.6714
- Min health factor: 1.6032
- Carry entries/exits: 7/7
- Carry time share: 18.35%
- Spot time share: 81.65%
- Long-perp time share: 0.00%
- Short-perp time share: 18.35%
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
  enter_edge_apr: -0.005
  exit_edge_apr: -0.01
  carry_max_payback_hours: 2000.0
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
  run_name: sweep_ratio_w9_e-0.005_x-0.01_p2000
  save_equity: true
  save_funding: true
  save_borrow: true

```
