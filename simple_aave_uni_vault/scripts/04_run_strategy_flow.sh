#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/common.sh"

activate_venv
load_env
load_deploy
ensure_tools

require_var AAVE_COLLATERAL_ASSET_WBTC
require_var AAVE_BORROW_ASSET_USDC

SUPPLY_WBTC="${SUPPLY_WBTC:-0.25}"
BORROW_USDC="${BORROW_USDC:-3000}"
SWAP_USDC_IN="${SWAP_USDC_IN:-500}"

WBTC="${AAVE_COLLATERAL_ASSET_WBTC}"
USDC="${AAVE_BORROW_ASSET_USDC}"
MANAGER="${MANAGER_ADDRESS}"
AAVE_SUPPLY_TOPIC="0x2b627736bca15cd5381dcf80b0bf11fd197d01a037c52b927a881a10fb73ba61"

aave_total_collateral_base_raw() {
  cast call "${AAVE_POOL_ADDRESS}" "getUserAccountData(address)(uint256,uint256,uint256,uint256,uint256,uint256)" "${VAULT_ADDRESS}" --rpc-url "${ANVIL_RPC_URL}" | sed -n '1p' | awk '{print $1}'
}

is_strictly_greater() {
  local left="$1"
  local right="$2"
  python - <<PY
left = int("${left}")
right = int("${right}")
print("1" if left > right else "0")
PY
}

log_step "Имперсонирую менеджера ${MANAGER}"
impersonate "${MANAGER}"
log_step "Пополняю ETH менеджера для газа через локальный fork (anvil_setBalance)"
set_balance_eth "${MANAGER}" "10"

wbtc_decimals=$(token_decimals "${WBTC}")
usdc_decimals=$(token_decimals "${USDC}")

supply_amount=$(to_units "${SUPPLY_WBTC}" "${wbtc_decimals}")
borrow_amount=$(to_units "${BORROW_USDC}" "${usdc_decimals}")
swap_amount=$(to_units "${SWAP_USDC_IN}" "${usdc_decimals}")
collateral_before_supply_raw="$(aave_total_collateral_base_raw)"

log_step "Aave Supply: ${SUPPLY_WBTC} WBTC из vault"
t1=$(cast send "${VAULT_ADDRESS}" "aaveSupply(address,uint256)" "${WBTC}" "${supply_amount}" --from "${MANAGER}" --unlocked --rpc-url "${ANVIL_RPC_URL}" --json | jq -r '.transactionHash')
wait_for_tx_and_print_block "${t1}" "Aave Supply"
print_balances_snapshot "После Aave Supply" \
  "Vault" "${VAULT_ADDRESS}" \
  "Manager" "${MANAGER}" \
  "Depositor" "${DEPOSITOR_ADDRESS}"
collateral_after_supply_raw="$(aave_total_collateral_base_raw)"
collateral_before_supply_human="$(format_units "${collateral_before_supply_raw}" 8)"
collateral_after_supply_human="$(format_units "${collateral_after_supply_raw}" 8)"

if [[ "$(is_strictly_greater "${collateral_after_supply_raw}" "${collateral_before_supply_raw}")" != "1" ]]; then
  echo "Aave Supply check failed: totalCollateralBase did not increase (${collateral_before_supply_raw} -> ${collateral_after_supply_raw})" >&2
  exit 1
fi

supply_logs_count="$(cast receipt "${t1}" --rpc-url "${ANVIL_RPC_URL}" --json | jq -r \
  --arg pool "$(echo "${AAVE_POOL_ADDRESS}" | tr '[:upper:]' '[:lower:]')" \
  --arg topic "$(echo "${AAVE_SUPPLY_TOPIC}" | tr '[:upper:]' '[:lower:]')" \
  '[.logs[] | select((.address | ascii_downcase) == $pool and (.topics[0] | ascii_downcase) == $topic)] | length')"

if [[ "${supply_logs_count}" -lt 1 ]]; then
  echo "Aave Supply check failed: Supply event not found in Aave Pool logs for tx ${t1}" >&2
  exit 1
fi

log_info "Aave Supply проверка: totalCollateralBase вырос ${collateral_before_supply_human} -> ${collateral_after_supply_human}"
log_info "Aave Supply проверка: в receipt найден event Supply из пула Aave (count=${supply_logs_count})"

log_step "Aave Borrow: ${BORROW_USDC} USDC в vault"
t2=$(cast send "${VAULT_ADDRESS}" "aaveBorrow(address,uint256,uint256)" "${USDC}" "${borrow_amount}" 2 --from "${MANAGER}" --unlocked --rpc-url "${ANVIL_RPC_URL}" --json | jq -r '.transactionHash')
wait_for_tx_and_print_block "${t2}" "Aave Borrow"
print_balances_snapshot "После Aave Borrow" \
  "Vault" "${VAULT_ADDRESS}" \
  "Manager" "${MANAGER}" \
  "Depositor" "${DEPOSITOR_ADDRESS}"

vault_usdc_raw="$(erc20_balance_raw "${USDC}" "${VAULT_ADDRESS}")"
if [[ "${vault_usdc_raw}" -lt "${borrow_amount}" ]]; then
  echo "Aave Borrow: недостаточный USDC в vault после borrow. expected>=${borrow_amount}, actual=${vault_usdc_raw}" >&2
  exit 1
fi

deadline=$(now_plus 3600)
log_step "Uniswap Swap: ${SWAP_USDC_IN} USDC -> WBTC"
t3=$(cast send "${VAULT_ADDRESS}" "uniswapV3SwapExactInputSingle(address,address,uint24,uint256,uint256,uint160,uint256)" "${USDC}" "${WBTC}" 3000 "${swap_amount}" 0 0 "${deadline}" --from "${MANAGER}" --unlocked --rpc-url "${ANVIL_RPC_URL}" --json | jq -r '.transactionHash')
wait_for_tx_and_print_block "${t3}" "Uniswap Swap"
print_balances_snapshot "После Uniswap Swap" \
  "Vault" "${VAULT_ADDRESS}" \
  "Manager" "${MANAGER}" \
  "Depositor" "${DEPOSITOR_ADDRESS}"

stop_impersonate "${MANAGER}"

log_ok "Стратегический флоу выполнен"
log_info "aaveSupply tx: ${t1}"
log_info "aaveBorrow tx: ${t2}"
log_info "uniSwap tx:    ${t3}"
