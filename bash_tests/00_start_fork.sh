#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/common.sh"

activate_venv
load_env
ensure_tools
require_cmd anvil
require_var MAINNET_RPC_URL
require_var FORK_BLOCK

mkdir -p "${SCRIPT_DIR}/.runtime"
LOG_FILE="${SCRIPT_DIR}/.runtime/anvil.log"
PID_FILE="${SCRIPT_DIR}/.runtime/anvil.pid"

if lsof -iTCP:8545 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "anvil already running on 8545"
  exit 0
fi

nohup anvil \
  --fork-url "${MAINNET_RPC_URL}" \
  --fork-block-number "${FORK_BLOCK}" \
  --chain-id 1 \
  --port 8545 >"${LOG_FILE}" 2>&1 &
echo $! >"${PID_FILE}"

sleep 2
if lsof -iTCP:8545 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "anvil started (pid $(cat "${PID_FILE}"))"
  echo "log: ${LOG_FILE}"
else
  echo "failed to start anvil; see ${LOG_FILE}" >&2
  exit 1
fi
