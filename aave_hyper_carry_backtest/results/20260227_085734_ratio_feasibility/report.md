# Feasibility Report: Ratio Carry (40/20/x2 style)

## Parameters
- Borrow APR (fixed): 5.15%
- Overlay borrow ratio: 0.40
- Hyper borrow ratio: 0.20
- Hyper short leverage: 2.00
- Hedge ratio: 1.00
- Funding weight: 0.40
- Borrow weight: 0.60

## Core Formula
- `edge_apr = funding_weight * funding_apr - borrow_weight * borrow_apr`
- Break-even funding APR: **7.72%**

## What Data Says
- Avg funding APR (all events): 4.49%
- Avg funding APR in short-positive zone: 5.92%
- Avg funding APR in long-negative zone: -3.14%
- Share of structurally positive events (`edge_apr > 0`): 27.95%

## Gross Return Scenarios (before execution fees/slippage)
- Always active: -1.29%
- Oracle (trade only when `edge_apr > 0`): 0.25%
- 75/70 by funding sign: -0.66%
- 75/70 by edge sign: -0.27%

## Conclusion
На этом годовом срезе конструкция неустойчива при текущем borrow: даже при выборочном входе преимущество funding слишком редкое/слабое, чтобы стабильно перекрыть borrow + операционные издержки.

## Charts
- `why_not_profitable.png`
- `zone_summary.png`
