# Aave + Hyper Carry Backtest

## Summary

- Start equity: 9575599.00
- End equity: 6448380.71
- Total PnL: -3127218.29
- Funding PnL: 13556.12
- Borrow interest: 10077.72
- Gross carry PnL: 3478.40
- Setup cost: 3548.70
- Close cost: 4547.28
- Operation cost (open+close): 8095.98
- Net carry PnL: -4617.58
- Directional PnL: -3130696.69
- Total return: -32.66%
- Annualized return: -32.66%
- Max drawdown: -50.08%
- Annualized vol: 44.68%
- Sharpe: -0.6612
- Min health factor: 1.7830
- Carry entries/exits: 1/1
- Carry time share: 3.01%
- Spot time share: 96.99%
- Long-perp time share: 0.00%
- Short-perp time share: 3.01%
- Edge APR mean: -1.29%
- Edge APR positive share: 18.09%

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
  enter_edge_apr: 0.015
  exit_edge_apr: 0.0
  carry_max_payback_hours: 2000.0
  min_hold_funding_events: 1
  default_funding_interval_hours: 8.0
  non_carry_mode: spot
  long_perp_exposure_ratio: 1.0
  long_perp_enter_funding_apr: 0.0
  long_perp_exit_funding_apr: 0.0
data:
  spot_path: /Users/igoreshka/Desktop/research/btc_perp_backtest/data/raw/binance_1y_strict/spot.csv
  funding_path: /Users/igoreshka/Desktop/research/btc_perp_backtest/data/raw/binance_1y_strict/funding.csv
  borrow_apr_path: /Users/igoreshka/Desktop/research/aave_hyper_carry_backtest/data/raw/aave_v3_eth_usdt_borrow_apr_1y.csv
  spot_ts_col: ts
  spot_price_col: spot_mid
  funding_ts_col: funding_ts
  funding_rate_col: funding_rate
  funding_mark_price_col: mark_price
  borrow_apr_ts_col: ts
  borrow_apr_col: borrow_apr
results:
  results_dir: /Users/igoreshka/Desktop/research/aave_hyper_carry_backtest/results
  run_name: one_year_ratio_40_20x2_selective_usdt_borrow_strict_e0015
  save_equity: true
  save_funding: true
  save_borrow: true

```
