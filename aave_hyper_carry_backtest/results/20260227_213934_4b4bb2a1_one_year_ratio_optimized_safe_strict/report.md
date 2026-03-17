# Aave + Hyper Carry Backtest

## Summary

- Start equity: 9575599.00
- End equity: 11119102.10
- Total PnL: 1543503.10
- Funding PnL: 675466.20
- Borrow interest: 155514.59
- Gross carry PnL: 519951.61
- Setup cost: 24780.31
- Close cost: 101585.69
- Operation cost (open+close): 126366.00
- Net carry PnL: 393585.60
- Directional PnL: 1023551.49
- Total return: 16.12%
- Annualized return: 16.12%
- Max drawdown: -13.88%
- Annualized vol: 22.93%
- Sharpe: 0.7664
- Min health factor: 1.6032
- Carry entries/exits: 15/14
- Carry time share: 84.24%
- Spot time share: 15.76%
- Long-perp time share: 0.00%
- Short-perp time share: 84.24%
- Edge APR mean: 4.67%
- Edge APR positive share: 85.47%

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
  overlay_borrow_ratio: 0.1
  hyper_borrow_ratio: 0.25
  hyper_short_leverage: 5.75
  aave_borrow_apr: 0.0515
  setup_cost_rate: 0.0005
  close_cost_rate: 0.0005
  liquidation_threshold: 0.8
  timing_enabled: true
  timing_window_events: 9
  enter_edge_apr: 0.0
  exit_edge_apr: 0.0
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
  borrow_apr_path: /Users/igoreshka/Desktop/alcor-backtests/aave_hyper_carry_backtest/data/raw/aave_v3_eth_usdt_borrow_apr_1y.csv
  spot_ts_col: ts
  spot_price_col: spot_mid
  funding_ts_col: funding_ts
  funding_rate_col: funding_rate
  funding_mark_price_col: mark_price
  borrow_apr_ts_col: ts
  borrow_apr_col: borrow_apr
results:
  results_dir: /Users/igoreshka/Desktop/alcor-backtests/aave_hyper_carry_backtest/results
  run_name: one_year_ratio_optimized_safe_strict
  save_equity: true
  save_funding: true
  save_borrow: true

```
