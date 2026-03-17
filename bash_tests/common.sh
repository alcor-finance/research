#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TASK_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_DIR="$(cd "${TASK_DIR}/.." && pwd)"
ENV_FILE_OVERRIDE="${ENV_FILE:-}"
ANVIL_RPC_URL="${ANVIL_RPC_URL:-http://127.0.0.1:8545}"

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
}

require_cmd() {
  local c="$1"
  command -v "$c" >/dev/null 2>&1 || { echo "missing command: $c" >&2; exit 1; }
}

require_var() {
  local n="$1"
  local v="${!n:-}"
  if [[ -z "${v}" ]]; then
    echo "missing env var: ${n}" >&2
    exit 1
  fi
}

rpc() {
  local method="$1"
  local params="$2"
  curl -sS "${ANVIL_RPC_URL}" \
    -H 'content-type: application/json' \
    --data "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"${method}\",\"params\":${params}}"
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
}

token_decimals() {
  local token="$1"
  cast call "${token}" "decimals()(uint8)" --rpc-url "${ANVIL_RPC_URL}"
}

to_units() {
  local amount="$1"
  local decimals="$2"
  python - <<PY
from decimal import Decimal
print(int(Decimal('${amount}') * (10 ** int('${decimals}'))))
PY
}

eth_balance() {
  local addr="$1"
  cast balance "${addr}" --rpc-url "${ANVIL_RPC_URL}" --ether
}

erc20_balance() {
  local token="$1"
  local addr="$2"
  cast call "${token}" "balanceOf(address)(uint256)" "${addr}" --rpc-url "${ANVIL_RPC_URL}"
}

ensure_tools() {
  require_cmd curl
  require_cmd cast
  require_cmd python
  require_cmd jq
}
