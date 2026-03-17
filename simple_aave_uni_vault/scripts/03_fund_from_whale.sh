#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/common.sh"

activate_venv
load_env
load_deploy
ensure_tools

require_var WBTC_WHALE
require_var WBTC_TOKEN

FUND_ETH_TO_VAULT="${FUND_ETH_TO_VAULT:-5}"
FUND_WBTC_TO_VAULT="${FUND_WBTC_TO_VAULT:-1.5}"

WHALE="${WBTC_WHALE}"
WBTC="${WBTC_TOKEN}"

log_step "Имперсонирую кита ${WHALE}"
impersonate "${WHALE}"
log_step "Пополняю ETH кита для газа через локальный fork (anvil_setBalance)"
set_balance_eth "${WHALE}" "1000"
print_balances_snapshot "До пополнения vault" \
  "Whale" "${WHALE}" \
  "Vault" "${VAULT_ADDRESS}" \
  "Manager" "${MANAGER_ADDRESS}"

decimals=$(token_decimals "${WBTC}")
wbtc_amount=$(to_units "${FUND_WBTC_TO_VAULT}" "${decimals}")
eth_amount=$(to_units "${FUND_ETH_TO_VAULT}" 18)

log_step "Перевожу ETH в vault (${FUND_ETH_TO_VAULT} ETH)"
eth_tx=$(cast send "${VAULT_ADDRESS}" --from "${WHALE}" --unlocked --value "${eth_amount}" --rpc-url "${ANVIL_RPC_URL}" --json | jq -r '.transactionHash')
wait_for_tx_and_print_block "${eth_tx}" "Пополнение vault ETH"
print_balances_snapshot "После пополнения ETH" \
  "Whale" "${WHALE}" \
  "Vault" "${VAULT_ADDRESS}" \
  "Manager" "${MANAGER_ADDRESS}"

log_step "Перевожу WBTC в vault (${FUND_WBTC_TO_VAULT} WBTC)"
wbtc_tx=$(cast send "${WBTC}" "transfer(address,uint256)" "${VAULT_ADDRESS}" "${wbtc_amount}" --from "${WHALE}" --unlocked --rpc-url "${ANVIL_RPC_URL}" --json | jq -r '.transactionHash')
wait_for_tx_and_print_block "${wbtc_tx}" "Пополнение vault WBTC"
print_balances_snapshot "После пополнения WBTC" \
  "Whale" "${WHALE}" \
  "Vault" "${VAULT_ADDRESS}" \
  "Manager" "${MANAGER_ADDRESS}"

stop_impersonate "${WHALE}"

log_ok "Vault пополнен: ${VAULT_ADDRESS}"
log_info "ETH tx:  ${eth_tx}"
log_info "WBTC tx: ${wbtc_tx}"
