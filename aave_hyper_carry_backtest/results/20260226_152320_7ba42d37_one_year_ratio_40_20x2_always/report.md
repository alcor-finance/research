# Aave + Hyper Carry Backtest

## Summary

- Start equity: 9572726.32
- End equity: 6237823.30
- Total PnL: -3334903.02
- Funding PnL: 93332.55
- Borrow interest: 303637.57
- Gross carry PnL: -210305.02
- Setup cost: 2872.68
- Close cost: 0.00
- Operation cost (open+close): 2872.68
- Net carry PnL: -213177.70
- Directional PnL: -3124598.00
- Total return: -34.84%
- Annualized return: -34.84%
- Max drawdown: -51.18%
- Annualized vol: 45.20%
- Sharpe: -0.7212
- Min health factor: 1.1677
- Carry entries/exits: 1/0
- Carry time share: 100.00%
- Spot time share: 0.00%
- Long-perp time share: 0.00%
- Short-perp time share: 100.00%
- Edge APR mean: -1.80%
- Edge APR positive share: 0.55%

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
  timing_enabled: false
  timing_window_events: 21
  enter_edge_apr: 0.0
  exit_edge_apr: 0.0
  carry_max_payback_hours: 720.0
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
  run_name: one_year_ratio_40_20x2_always
  save_equity: true
  save_funding: true
  save_borrow: true

```
