#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/common.sh"

activate_venv
load_env
load_deploy
ensure_tools

require_var WHITELIST_6TH_WALLET_ADDRESS
require_var AAVE_BORROW_ASSET_USDC

MANAGER="${MANAGER_ADDRESS}"
DEPOSITOR="${DEPOSITOR_ADDRESS}"
USDC="${AAVE_BORROW_ASSET_USDC}"
WL="${WHITELIST_6TH_WALLET_ADDRESS}"
NON_WL="${NON_WHITELIST_ADDRESS:-0x1111111111111111111111111111111111111111}"
DEPOSITOR_TARGET="${DEPOSITOR_WITHDRAW_TARGET:-${SAFE_OWNER_2:-0x61B379afb78C2FCDdC13ED98476d765b5e95df4A}}"

usdc_decimals=$(token_decimals "${USDC}")
manager_withdraw_amount=$(to_units "${MANAGER_WITHDRAW_USDC:-100}" "${usdc_decimals}")
depositor_withdraw_amount=$(to_units "${DEPOSITOR_WITHDRAW_USDC:-50}" "${usdc_decimals}")
manager_withdraw_human=$(format_units "${manager_withdraw_amount}" "${usdc_decimals}")
depositor_withdraw_human=$(format_units "${depositor_withdraw_amount}" "${usdc_decimals}")

# depositor sets whitelist
log_step "Depositor добавляет whitelist адрес ${WL}"
impersonate "${DEPOSITOR}"
log_step "Пополняю ETH depositor для газа через локальный fork (anvil_setBalance)"
set_balance_eth "${DEPOSITOR}" "10"
set_wl_tx=$(cast send "${VAULT_ADDRESS}" "setWhitelist(address,bool)" "${WL}" true --from "${DEPOSITOR}" --unlocked --rpc-url "${ANVIL_RPC_URL}" --json | jq -r '.transactionHash')
wait_for_tx_and_print_block "${set_wl_tx}" "setWhitelist"
print_balances_snapshot "После setWhitelist" \
  "Vault" "${VAULT_ADDRESS}" \
  "Depositor" "${DEPOSITOR}" \
  "Manager" "${MANAGER}" \
  "Whitelist" "${WL}"
stop_impersonate "${DEPOSITOR}"

# manager withdraw to whitelist (must pass)
log_step "Готовлю менеджера к выводу USDC ИЗ vault на whitelist адрес (ожидаем PASS)"
impersonate "${MANAGER}"
log_step "Пополняю ETH менеджера для газа через локальный fork (anvil_setBalance)"
set_balance_eth "${MANAGER}" "10"
log_step "Manager инициирует вывод USDC ИЗ vault на whitelist адрес"
log_info "Детали: caller=${MANAGER}, source(vault)=${VAULT_ADDRESS}, token=USDC, amount=${manager_withdraw_human}, destination=${WL}"
log_info "Трансфер: Vault -> Whitelist | инициатор=Manager | сумма=${manager_withdraw_human} USDC"
vault_usdc_before_manager="$(erc20_balance_raw "${USDC}" "${VAULT_ADDRESS}")"
wl_usdc_before_manager="$(erc20_balance_raw "${USDC}" "${WL}")"
manager_ok_tx=$(cast send "${VAULT_ADDRESS}" "managerWithdrawToken(address,address,uint256)" "${USDC}" "${WL}" "${manager_withdraw_amount}" --from "${MANAGER}" --unlocked --rpc-url "${ANVIL_RPC_URL}" --json | jq -r '.transactionHash')
wait_for_tx_and_print_block "${manager_ok_tx}" "Manager withdraw -> whitelist"
vault_usdc_after_manager="$(erc20_balance_raw "${USDC}" "${VAULT_ADDRESS}")"
wl_usdc_after_manager="$(erc20_balance_raw "${USDC}" "${WL}")"
vault_usdc_before_manager_human="$(format_units "${vault_usdc_before_manager}" "${usdc_decimals}")"
vault_usdc_after_manager_human="$(format_units "${vault_usdc_after_manager}" "${usdc_decimals}")"
wl_usdc_before_manager_human="$(format_units "${wl_usdc_before_manager}" "${usdc_decimals}")"
wl_usdc_after_manager_human="$(format_units "${wl_usdc_after_manager}" "${usdc_decimals}")"

manager_vault_delta_ok="$(python - <<PY
before_vault = int("${vault_usdc_before_manager}")
after_vault = int("${vault_usdc_after_manager}")
amount = int("${manager_withdraw_amount}")
print("1" if before_vault - after_vault == amount else "0")
PY
)"
manager_wl_delta_ok="$(python - <<PY
before_wl = int("${wl_usdc_before_manager}")
after_wl = int("${wl_usdc_after_manager}")
amount = int("${manager_withdraw_amount}")
print("1" if after_wl - before_wl == amount else "0")
PY
)"
if [[ "${manager_vault_delta_ok}" != "1" || "${manager_wl_delta_ok}" != "1" ]]; then
  echo "manager withdraw check failed: vault/wl USDC delta mismatch" >&2
  exit 1
fi
log_info "Проверка manager-withdraw: Vault USDC ${vault_usdc_before_manager} -> ${vault_usdc_after_manager}, Whitelist USDC ${wl_usdc_before_manager} -> ${wl_usdc_after_manager}"
log_info "Проверка manager-withdraw (human): Vault ${vault_usdc_before_manager_human} -> ${vault_usdc_after_manager_human} USDC, Whitelist ${wl_usdc_before_manager_human} -> ${wl_usdc_after_manager_human} USDC"
print_balances_snapshot "После manager withdraw -> whitelist" \
  "Vault" "${VAULT_ADDRESS}" \
  "Manager (caller)" "${MANAGER}" \
  "WhitelistRecipient" "${WL}" \
  "Depositor" "${DEPOSITOR}"

# manager withdraw to non-whitelist (must fail)
log_step "Manager выводит USDC на НЕ whitelist адрес (ожидаем REVERT)"
log_info "Трансфер (ожидаемый отказ): Vault -> NonWhitelist | инициатор=Manager | сумма=${manager_withdraw_human} USDC | destination=${NON_WL}"
set +e
manager_fail_out=$(cast send "${VAULT_ADDRESS}" "managerWithdrawToken(address,address,uint256)" "${USDC}" "${NON_WL}" "${manager_withdraw_amount}" --from "${MANAGER}" --unlocked --rpc-url "${ANVIL_RPC_URL}" 2>&1)
manager_fail_code=$?
set -e
stop_impersonate "${MANAGER}"

if [[ ${manager_fail_code} -eq 0 ]]; then
  echo "manager non-whitelist withdraw unexpectedly passed" >&2
  exit 1
fi

# depositor unrestricted withdraw (must pass)
log_step "Готовлю depositor к выводу USDC ИЗ vault на произвольный адрес (ожидаем PASS)"
impersonate "${DEPOSITOR}"
log_step "Пополняю ETH depositor для газа через локальный fork (anvil_setBalance)"
set_balance_eth "${DEPOSITOR}" "10"
log_step "Depositor инициирует вывод USDC ИЗ vault на произвольный адрес"
log_info "Детали: caller=${DEPOSITOR}, source(vault)=${VAULT_ADDRESS}, token=USDC, amount=${depositor_withdraw_human}, destination=${DEPOSITOR_TARGET}"
log_info "Трансфер: Vault -> ArbitraryRecipient | инициатор=Depositor | сумма=${depositor_withdraw_human} USDC"
vault_usdc_before_depositor="$(erc20_balance_raw "${USDC}" "${VAULT_ADDRESS}")"
target_usdc_before_depositor="$(erc20_balance_raw "${USDC}" "${DEPOSITOR_TARGET}")"
depositor_tx=$(cast send "${VAULT_ADDRESS}" "depositorWithdrawToken(address,address,uint256)" "${USDC}" "${DEPOSITOR_TARGET}" "${depositor_withdraw_amount}" --from "${DEPOSITOR}" --unlocked --rpc-url "${ANVIL_RPC_URL}" --json | jq -r '.transactionHash')
wait_for_tx_and_print_block "${depositor_tx}" "Depositor withdraw -> arbitrary"
vault_usdc_after_depositor="$(erc20_balance_raw "${USDC}" "${VAULT_ADDRESS}")"
target_usdc_after_depositor="$(erc20_balance_raw "${USDC}" "${DEPOSITOR_TARGET}")"
vault_usdc_before_depositor_human="$(format_units "${vault_usdc_before_depositor}" "${usdc_decimals}")"
vault_usdc_after_depositor_human="$(format_units "${vault_usdc_after_depositor}" "${usdc_decimals}")"
target_usdc_before_depositor_human="$(format_units "${target_usdc_before_depositor}" "${usdc_decimals}")"
target_usdc_after_depositor_human="$(format_units "${target_usdc_after_depositor}" "${usdc_decimals}")"

depositor_vault_delta_ok="$(python - <<PY
before_vault = int("${vault_usdc_before_depositor}")
after_vault = int("${vault_usdc_after_depositor}")
amount = int("${depositor_withdraw_amount}")
print("1" if before_vault - after_vault == amount else "0")
PY
)"
depositor_target_delta_ok="$(python - <<PY
before_target = int("${target_usdc_before_depositor}")
after_target = int("${target_usdc_after_depositor}")
amount = int("${depositor_withdraw_amount}")
print("1" if after_target - before_target == amount else "0")
PY
)"
if [[ "${depositor_vault_delta_ok}" != "1" || "${depositor_target_delta_ok}" != "1" ]]; then
  echo "depositor withdraw check failed: vault/target USDC delta mismatch" >&2
  exit 1
fi
log_info "Проверка depositor-withdraw: Vault USDC ${vault_usdc_before_depositor} -> ${vault_usdc_after_depositor}, Target USDC ${target_usdc_before_depositor} -> ${target_usdc_after_depositor}"
log_info "Проверка depositor-withdraw (human): Vault ${vault_usdc_before_depositor_human} -> ${vault_usdc_after_depositor_human} USDC, ArbitraryRecipient ${target_usdc_before_depositor_human} -> ${target_usdc_after_depositor_human} USDC"
print_balances_snapshot "После depositor withdraw -> arbitrary" \
  "Vault" "${VAULT_ADDRESS}" \
  "Depositor (caller)" "${DEPOSITOR}" \
  "Manager" "${MANAGER}" \
  "ArbitraryRecipient" "${DEPOSITOR_TARGET}"
stop_impersonate "${DEPOSITOR}"

log_ok "Проверки доступа завершены"
log_info "setWhitelist tx:            ${set_wl_tx}"
log_info "manager withdraw wl tx:     ${manager_ok_tx}"
log_info "manager non-wl revert msg:  ${manager_fail_out}"
log_info "depositor withdraw any tx:  ${depositor_tx}"
