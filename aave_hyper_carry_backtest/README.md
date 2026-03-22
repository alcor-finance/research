# Aave + Hyperliquid Carry Backtest

Бэктест стратегии для BTC, где совмещаются:

- заемная часть на Aave (стоимость: `borrow APR`),
- позиция в BTC perps на Hyperliquid (доход/расход: `funding`),
- переключение режимов по edge-сигналу.

Проект отвечает на вопрос: перекрывает ли funding-доход стоимость займа и операционные издержки.

## Что моделируется

Базовый капитал: `initial_btc` (часто `100 BTC`).

Режимы:

- `spot`: держим только базовый BTC.
- `carry`: добавляем заем в Aave + держим short perp для сбора funding.
- `long_perp` (опционально): вне carry держим long perp вместо spot.

## Стратегия и формулы

### 1) Структура позиции

Если `use_ratio_structure: false`:

- `overlay_long_btc = initial_btc * (target_leverage - 1)`
- `short_btc = overlay_long_btc * hedge_ratio`
- `borrow_total_btc = overlay_long_btc`

Если `use_ratio_structure: true`:

- `overlay_long_btc = initial_btc * overlay_borrow_ratio`
- `short_btc = initial_btc * hyper_borrow_ratio * hyper_short_leverage * hedge_ratio`
- `borrow_total_btc = initial_btc * (overlay_borrow_ratio + hyper_borrow_ratio)`

### 2) Edge (годовой)

- `funding_weight = abs(short_btc) / initial_btc`
- `borrow_weight = borrow_total_btc / initial_btc`
- `edge_apr = funding_weight * rolling_funding_apr - borrow_weight * borrow_apr`

### 3) Правила входа/выхода

Если `timing_enabled: false`:

- стартуем в `carry` и не переключаемся по сигналам.

Если `timing_enabled: true`:

- вход в carry: `edge_apr >= enter_edge_apr` и payback по издержкам не хуже `carry_max_payback_hours`;
- выход из carry: `edge_apr <= exit_edge_apr` и выдержано минимум `min_hold_funding_events`;
- вне carry можно держать `spot` или `long_perp` (по `non_carry_mode`).

Payback-оценка:

- `payback_hours = (setup_cost_rate + close_cost_rate) * 8760 / edge_apr`, если `edge_apr > 0`.

### 4) Порядок начислений внутри движка

На каждом баре:

1. Начисляется borrow interest за прошедший интервал.
2. На funding-таймстемпе фиксируется funding cashflow.
3. После этого считаются rolling funding APR / edge и принимается решение о смене режима.
4. Пишется snapshot equity.

Это важно для корректной интерпретации: решение не “подглядывает” в будущие funding-события.

## Декомпозиция PnL

- `funding_pnl`: сумма funding cashflow.
- `borrow_interest`: начисленные проценты займа.
- `operation_cost`: вход/выход (setup + close).
- `gross_carry_pnl = funding_pnl - borrow_interest`.
- `net_carry_pnl = gross_carry_pnl - operation_cost`.
- `directional_pnl = total_pnl - gross_carry_pnl`.

## Формат входных данных

### Spot CSV/Parquet

Обязательные поля:

- `ts` (UTC timestamp),
- `spot_mid`.

### Funding CSV/Parquet

Обязательные поля:

- `funding_ts`,
- `funding_rate`.

Опционально:

- `mark_price`.

### Borrow APR CSV/Parquet

Если задан `borrow_apr_path`, обязательные поля:

- `ts`,
- `borrow_apr`.

Если путь пустой, берется константа `strategy.aave_borrow_apr`.

## Быстрый старт

```bash
cd aave_hyper_carry_backtest
pip install -e .
```

Прогон:

```bash
python -m src.run_backtest --config config/one_year_ratio_40_20x2_selective_usdt_borrow_strict_entry.yaml
```

Ожидаемый консольный вывод:

- `Run complete: <run_id>`
- `Results dir: <abs_path>`
- `End equity: ...`
- `Net carry PnL: ...`

## Что должно появиться в `results/<run_id>/`

Основные файлы:

- `config.yaml` — фактический конфиг запуска.
- `summary.json` — агрегированные метрики.
- `report.md` — человекочитаемая сводка.
- `equity_curve.parquet` — почасовая кривая и состояние портфеля.
- `funding.parquet` — funding-события (rate/apr/cashflow/mode).
- `borrow.parquet` — начисления процентов по займу.
- `operations.parquet` — объединенный журнал cashflow операций.
- `equity_and_operations.png` — equity + операции + risk.
- `carry_components.png` — кумулятивный funding/borrow/ops/net carry.
- `regime_timing.png` — APR-линии и режимы по времени.
- `regime_distribution.png` — распределение времени/событий по режимам.

## Как читать `summary.json`

Минимальный набор для оценки стратегии:

- `end_equity`, `total_pnl`, `total_return`, `max_drawdown`.
- `funding_pnl`, `borrow_interest`, `operation_cost`, `net_carry_pnl`.
- `carry_entries`, `carry_exits`, `carry_time_share`.
- `edge_apr_mean`, `edge_apr_positive_share`.

Интерпретация:

- если `funding_pnl > borrow_interest`, но `net_carry_pnl < 0`, значит издержки входа/выхода “съели” carry;
- если `net_carry_pnl > 0`, но `total_pnl < 0`, то стратегия carry прибыльна сама по себе, но directional BTC-движение доминировало.

## Мини-чеклист корректного запуска

- В консоли есть `Run complete`.
- В `results/<run_id>/` присутствует `summary.json`.
- В `summary.json` не пустые `funding_events`, `carry_entries`, `carry_exits`.
- В `equity_curve.parquet` есть колонки `mode`, `edge_apr`, `borrow_apr`, `rolling_funding_apr`.
- Графики открываются без ошибок.
