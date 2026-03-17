#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/common.sh"

PID_FILE="${RUNTIME_DIR}/anvil.pid"
if [[ -f "${PID_FILE}" ]]; then
  log_step "Останавливаю Anvil по pid из файла"
  kill "$(cat "${PID_FILE}")" >/dev/null 2>&1 || true
  rm -f "${PID_FILE}"
  log_ok "Anvil остановлен"
  exit 0
fi

log_step "Файл pid не найден, пробую остановить Anvil по процессу"
pkill -f "anvil --fork-url" >/dev/null 2>&1 || true
log_ok "Команда остановки выполнена"
