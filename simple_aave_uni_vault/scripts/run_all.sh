#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
source "${DIR}/common.sh"

cleanup() {
  "${DIR}/06_stop_fork.sh" || true
}
trap cleanup EXIT

log_step "Запускаю полный сценарий: fork -> deploy -> fund -> strategy -> access checks"
log_step "Сбрасываю состояние: останавливаю прошлый Anvil (если запущен)"
"${DIR}/06_stop_fork.sh" || true
"${DIR}/01_start_fork.sh"
"${DIR}/02_deploy_contract.sh"
"${DIR}/03_fund_from_whale.sh"
"${DIR}/04_run_strategy_flow.sh"
"${DIR}/05_access_control_checks.sh"

log_ok "Все скрипты выполнены успешно"
