#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/common.sh"

activate_venv
load_env
ensure_tools
require_var MAINNET_RPC_URL
require_var FORK_BLOCK

log_step "Подготавливаю запуск форка Ethereum mainnet на Anvil"
mkdir -p "${RUNTIME_DIR}"
LOG_FILE="${RUNTIME_DIR}/anvil.log"
PID_FILE="${RUNTIME_DIR}/anvil.pid"

if lsof -iTCP:8545 -sTCP:LISTEN >/dev/null 2>&1; then
  log_info "Anvil уже запущен на порту 8545"
  exit 0
fi

log_step "Запускаю Anvil (fork block: ${FORK_BLOCK})"
nohup anvil --fork-url "${MAINNET_RPC_URL}" --fork-block-number "${FORK_BLOCK}" --chain-id 1 --port 8545 >"${LOG_FILE}" 2>&1 &
echo $! >"${PID_FILE}"

sleep 2
if lsof -iTCP:8545 -sTCP:LISTEN >/dev/null 2>&1; then
  log_ok "Anvil запущен (pid $(cat "${PID_FILE}"))"
else
  echo "anvil failed to start, see ${LOG_FILE}" >&2
  exit 1
fi
