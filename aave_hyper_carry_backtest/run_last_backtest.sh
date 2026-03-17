#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

# Default "latest" backtest config. Override by passing a config path as $1.
DEFAULT_CONFIG="config/one_year_ratio_optimized_best_end_equity_wide.yaml"
CONFIG_PATH="${1:-$DEFAULT_CONFIG}"

if [[ ! -f "$CONFIG_PATH" ]]; then
  echo "Config not found: $CONFIG_PATH" >&2
  exit 1
fi

PY_REQ_CHECK='from datetime import UTC; import pandas'

if [[ -z "${PYTHON_BIN:-}" ]]; then
  CANDIDATES=(
    "$ROOT_DIR/../.venv/bin/python3"
    "/opt/homebrew/anaconda3/bin/python3"
    "/opt/homebrew/bin/python3"
    "/usr/local/bin/python3"
    "python3.12"
    "python3.11"
    "python3"
  )
  for candidate in "${CANDIDATES[@]}"; do
    if [[ "$candidate" == /* ]]; then
      [[ -x "$candidate" ]] || continue
    else
      command -v "$candidate" >/dev/null 2>&1 || continue
    fi
    if "$candidate" -c "$PY_REQ_CHECK" >/dev/null 2>&1; then
      PYTHON_BIN="$candidate"
      break
    fi
  done
fi

if [[ -z "${PYTHON_BIN:-}" ]]; then
  echo "No suitable Python found (requires datetime.UTC + pandas)." >&2
  echo "Set PYTHON_BIN explicitly, e.g. PYTHON_BIN=python3 ./run_last_backtest.sh" >&2
  exit 1
fi

if ! "$PYTHON_BIN" -c "$PY_REQ_CHECK" >/dev/null 2>&1; then
  echo "Python does not satisfy requirements: $PYTHON_BIN" >&2
  echo "Needs: datetime.UTC (py>=3.11) and pandas installed." >&2
  exit 1
fi

SKIP_PLOTS="${SKIP_PLOTS:-0}"

CMD=("$PYTHON_BIN" -m src.run_backtest --config "$CONFIG_PATH")
if [[ "$SKIP_PLOTS" == "1" ]]; then
  CMD+=(--skip-plots)
fi

echo "Running Aave+Hyper carry backtest"
echo "  Root:   $ROOT_DIR"
echo "  Config: $CONFIG_PATH"
if [[ "$SKIP_PLOTS" == "1" ]]; then
  echo "  Plots:  skipped (SKIP_PLOTS=1)"
fi
echo

"${CMD[@]}"
