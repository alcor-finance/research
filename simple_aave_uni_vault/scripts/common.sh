#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
TASK_DIR="$(cd "${PROJECT_DIR}/.." && pwd)"
REPO_DIR="$(cd "${TASK_DIR}/.." && pwd)"
ENV_FILE_OVERRIDE="${ENV_FILE:-}"
RUNTIME_DIR="${PROJECT_DIR}/.runtime"
DEPLOY_FILE="${RUNTIME_DIR}/deploy.env"
ANVIL_RPC_URL="${ANVIL_RPC_URL:-http://127.0.0.1:8545}"
DEPLOYER_PK="${DEPLOYER_PK:-0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80}"

activate_venv() {
  local venv_activate=""
  if [[ -f "${TASK_DIR}/.venv/bin/activate" ]]; then
    venv_activate="${TASK_DIR}/.venv/bin/activate"
  elif [[ -f "${REPO_DIR}/.venv/bin/activate" ]]; then
    venv_activate="${REPO_DIR}/.venv/bin/activate"
  fi

  if [[ -n "${venv_activate}" ]]; then
    # shellcheck disable=SC1091
    source "${venv_activate}"
  fi
}

resolve_env_file() {
  if [[ -n "${RESOLVED_ENV_FILE:-}" ]]; then
    return 0
  fi

  local candidate
  if [[ -n "${ENV_FILE_OVERRIDE}" ]]; then
    candidate="${ENV_FILE_OVERRIDE}"
    if [[ ! -f "${candidate}" && -f "${TASK_DIR}/${candidate}" ]]; then
      candidate="${TASK_DIR}/${candidate}"
    fi

    if [[ ! -f "${candidate}" ]]; then
      echo "env file not found: ${ENV_FILE_OVERRIDE}" >&2
      exit 1
    fi

    RESOLVED_ENV_FILE="${candidate}"
    return 0
  fi

  for candidate in "${TASK_DIR}/.env" "${TASK_DIR}/.env.safe_setup"; do
    if [[ -f "${candidate}" ]]; then
      RESOLVED_ENV_FILE="${candidate}"
      return 0
    fi
  done

  echo "missing env file. expected one of: ${TASK_DIR}/.env, ${TASK_DIR}/.env.safe_setup or set ENV_FILE=/path/to/env" >&2
  exit 1
}

load_env() {
  resolve_env_file
  set -a
  # shellcheck disable=SC1090
  source "${RESOLVED_ENV_FILE}"
  set +a
  log_info "Использую env файл: ${RESOLVED_ENV_FILE}"
}

load_deploy() {
  if [[ ! -f "${DEPLOY_FILE}" ]]; then
    echo "missing deploy file: ${DEPLOY_FILE}" >&2
    exit 1
  fi
  set -a
  # shellcheck disable=SC1090
  source "${DEPLOY_FILE}"
  set +a
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || { echo "missing command: $1" >&2; exit 1; }
}

require_var() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    echo "missing env var: $name" >&2
    exit 1
  fi
}

rpc() {
  local method="$1"
  local params="$2"
  curl -sS "${ANVIL_RPC_URL}" -H 'content-type: application/json' --data "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"${method}\",\"params\":${params}}"
}

impersonate() {
  local addr="$1"
  rpc "anvil_impersonateAccount" "[\"${addr}\"]" >/dev/null
}

stop_impersonate() {
  local addr="$1"
  rpc "anvil_stopImpersonatingAccount" "[\"${addr}\"]" >/dev/null
}

set_balance_eth() {
  local addr="$1"
  local eth="$2"
  local wei
  wei="$(python - <<PY
from decimal import Decimal
print(hex(int(Decimal('${eth}') * (10**18))))
PY
)"
  rpc "anvil_setBalance" "[\"${addr}\",\"${wei}\"]" >/dev/null
  log_info "ETH баланс установлен локально через anvil_setBalance: ${addr} = ${eth} ETH (это не перевод от другого адреса)"
}

token_decimals() {
  cast call "$1" "decimals()(uint8)" --rpc-url "${ANVIL_RPC_URL}"
}

erc20_balance_raw() {
  local token="$1"
  local addr="$2"
  cast call "${token}" "balanceOf(address)(uint256)" "${addr}" --rpc-url "${ANVIL_RPC_URL}" | awk '{print $1}'
}

eth_balance_human() {
  local addr="$1"
  cast balance "${addr}" --rpc-url "${ANVIL_RPC_URL}" --ether
}

to_units() {
  local amount="$1"
  local decimals="$2"
  python - <<PY
from decimal import Decimal
print(int(Decimal('${amount}') * (10 ** int('${decimals}'))))
PY
}

now_plus() {
  local sec="$1"
  python - <<PY
import time
print(int(time.time()) + int('${sec}'))
PY
}

ensure_tools() {
  require_cmd anvil
  require_cmd cast
  require_cmd forge
  require_cmd jq
  require_cmd curl
  require_cmd python
}

log_step() {
  local msg="$1"
  echo "[ШАГ] ${msg}"
}

log_info() {
  local msg="$1"
  echo "[ИНФО] ${msg}"
}

log_ok() {
  local msg="$1"
  echo "[OK] ${msg}"
}

wait_for_tx_and_print_block() {
  local tx_hash="$1"
  local label="${2:-Транзакция}"
  local receipt_json block_hex block_dec status_hex status_dec

  receipt_json="$(cast receipt "${tx_hash}" --rpc-url "${ANVIL_RPC_URL}" --json)"
  block_hex="$(echo "${receipt_json}" | jq -r '.blockNumber')"
  status_hex="$(echo "${receipt_json}" | jq -r '.status')"

  if [[ -z "${status_hex}" || "${status_hex}" == "null" ]]; then
    echo "${label}: не удалось прочитать status из receipt для tx ${tx_hash}" >&2
    exit 1
  fi

  status_dec="$(cast to-dec "${status_hex}")"
  if [[ "${status_dec}" != "1" ]]; then
    echo "${label}: транзакция завершилась с ошибкой (status=${status_hex}, tx=${tx_hash})" >&2
    exit 1
  fi

  if [[ -z "${block_hex}" || "${block_hex}" == "null" ]]; then
    log_info "${label}: receipt получен, но blockNumber не найден"
    return 0
  fi

  block_dec="$(cast to-dec "${block_hex}")"
  log_ok "${label} подтверждена в блоке #${block_dec}"
}

format_units() {
  local raw="$1"
  local decimals="$2"
  python - <<PY
from decimal import Decimal, getcontext
getcontext().prec = 80
raw = Decimal("${raw}")
decimals = int("${decimals}")
value = raw / (Decimal(10) ** decimals)
text = format(value, "f")
if "." in text:
    text = text.rstrip("0").rstrip(".")
print(text if text else "0")
PY
}

token_balance_human() {
  local token="$1"
  local addr="$2"
  local decimals="$3"
  local raw
  raw="$(erc20_balance_raw "${token}" "${addr}")"
  format_units "${raw}" "${decimals}"
}

print_balances_snapshot() {
  local label="$1"
  shift

  local wbtc_token usdc_token wbtc_decimals usdc_decimals
  wbtc_token="${WBTC_TOKEN:-${AAVE_COLLATERAL_ASSET_WBTC:-}}"
  usdc_token="${AAVE_BORROW_ASSET_USDC:-}"

  if [[ -n "${wbtc_token}" ]]; then
    wbtc_decimals="$(token_decimals "${wbtc_token}")"
  else
    wbtc_decimals=""
  fi

  if [[ -n "${usdc_token}" ]]; then
    usdc_decimals="$(token_decimals "${usdc_token}")"
  else
    usdc_decimals=""
  fi

  log_info "Снимок балансов: ${label}"

  while [[ $# -ge 2 ]]; do
    local actor_name="$1"
    local actor_addr="$2"
    shift 2

    local eth_human
    eth_human="$(eth_balance_human "${actor_addr}")"
    local line
    line="  - ${actor_name} (${actor_addr}) | ETH=${eth_human}"

    if [[ -n "${wbtc_token}" && -n "${wbtc_decimals}" ]]; then
      local wbtc_human
      wbtc_human="$(token_balance_human "${wbtc_token}" "${actor_addr}" "${wbtc_decimals}")"
      line="${line} | WBTC=${wbtc_human}"
    fi

    if [[ -n "${usdc_token}" && -n "${usdc_decimals}" ]]; then
      local usdc_human
      usdc_human="$(token_balance_human "${usdc_token}" "${actor_addr}" "${usdc_decimals}")"
      line="${line} | USDC=${usdc_human}"
    fi

    echo "${line}"
  done
}
