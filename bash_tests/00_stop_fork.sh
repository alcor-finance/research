#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/common.sh"

PID_FILE="${SCRIPT_DIR}/.runtime/anvil.pid"
if [[ -f "${PID_FILE}" ]]; then
  kill "$(cat "${PID_FILE}")" >/dev/null 2>&1 || true
  rm -f "${PID_FILE}"
  echo "stopped anvil from pid file"
  exit 0
fi

pkill -f "anvil --fork-url" >/dev/null 2>&1 || true
echo "stop attempted"
