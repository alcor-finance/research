#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/common.sh"

activate_venv
load_env
ensure_tools

require_var ZODIAC_MANAGER
require_var SAFE_OWNER_1
require_var AAVE_POOL_ADDRESS
require_var UNISWAP_V3_SWAP_ROUTER

DEPOSITOR="${DEPOSITOR_ADDRESS:-${SAFE_OWNER_1}}"
MANAGER="${MANAGER_ADDRESS:-${ZODIAC_MANAGER}}"

mkdir -p "${RUNTIME_DIR}"

log_step "Собираю контракт ManagerAaveUniVault"
cd "${PROJECT_DIR}"
forge build >/dev/null

log_step "Деплою контракт в fork-сеть"
out=$(forge create src/ManagerAaveUniVault.sol:ManagerAaveUniVault \
  --rpc-url "${ANVIL_RPC_URL}" \
  --private-key "${DEPLOYER_PK}" \
  --broadcast \
  --constructor-args "${DEPOSITOR}" "${MANAGER}" "${AAVE_POOL_ADDRESS}" "${UNISWAP_V3_SWAP_ROUTER}")

VAULT_ADDRESS=$(echo "${out}" | awk '/Deployed to:/ {print $3}')
if [[ -z "${VAULT_ADDRESS}" ]]; then
  echo "failed to parse deployed address" >&2
  echo "${out}" >&2
  exit 1
fi

deploy_block="$(cast block-number --rpc-url "${ANVIL_RPC_URL}")"

log_step "Сохраняю адреса деплоя в ${DEPLOY_FILE}"
cat > "${DEPLOY_FILE}" <<ENV
VAULT_ADDRESS=${VAULT_ADDRESS}
DEPOSITOR_ADDRESS=${DEPOSITOR}
MANAGER_ADDRESS=${MANAGER}
ENV

log_ok "Контракт задеплоен: ${VAULT_ADDRESS}"
log_ok "Деплой подтвержден, текущий номер блока: #${deploy_block}"
log_info "Depositor: ${DEPOSITOR}"
log_info "Manager: ${MANAGER}"
