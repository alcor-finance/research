#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/common.sh"

activate_venv
load_env
ensure_tools

require_var ZODIAC_MANAGER
require_var AAVE_POOL_ADDRESS
require_var AAVE_COLLATERAL_ASSET_WBTC
AMOUNT_WBTC="${1:-0.05}"
MANAGER="${ZODIAC_MANAGER}"
POOL="${AAVE_POOL_ADDRESS}"
WBTC="${AAVE_COLLATERAL_ASSET_WBTC}"
ON_BEHALF="${TEST_ON_BEHALF_ADDRESS:-${ZODIAC_MANAGER}}"

impersonate "${MANAGER}"
set_balance_eth "${MANAGER}" "10"

decimals="$(token_decimals "${WBTC}")"
amount_raw="$(to_units "${AMOUNT_WBTC}" "${decimals}")"

approve_tx="$(cast send "${WBTC}" "approve(address,uint256)" "${POOL}" "${amount_raw}" --from "${MANAGER}" --unlocked --rpc-url "${ANVIL_RPC_URL}" --json | jq -r '.transactionHash')"
supply_tx="$(cast send "${POOL}" "supply(address,uint256,address,uint16)" "${WBTC}" "${amount_raw}" "${ON_BEHALF}" 0 --from "${MANAGER}" --unlocked --rpc-url "${ANVIL_RPC_URL}" --json | jq -r '.transactionHash')"

stop_impersonate "${MANAGER}"

echo "T3 approve tx: ${approve_tx}"
echo "T3 supply tx:  ${supply_tx}"
echo "expected: PASS"
echo "onBehalfOf used: ${ON_BEHALF}"
