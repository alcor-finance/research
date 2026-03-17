#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/common.sh"

activate_venv
load_env
ensure_tools

require_var ZODIAC_MANAGER
require_var AAVE_POOL_ADDRESS
require_var AAVE_BORROW_ASSET_USDC
AMOUNT_USDC="${1:-1000}"
MANAGER="${ZODIAC_MANAGER}"
POOL="${AAVE_POOL_ADDRESS}"
USDC="${AAVE_BORROW_ASSET_USDC}"
ON_BEHALF="${TEST_ON_BEHALF_ADDRESS:-${ZODIAC_MANAGER}}"

impersonate "${MANAGER}"
set_balance_eth "${MANAGER}" "10"

decimals="$(token_decimals "${USDC}")"
amount_raw="$(to_units "${AMOUNT_USDC}" "${decimals}")"

borrow_tx="$(cast send "${POOL}" "borrow(address,uint256,uint256,uint16,address)" "${USDC}" "${amount_raw}" 2 0 "${ON_BEHALF}" --from "${MANAGER}" --unlocked --rpc-url "${ANVIL_RPC_URL}" --json | jq -r '.transactionHash')"

stop_impersonate "${MANAGER}"

echo "T4 borrow tx: ${borrow_tx}"
echo "expected: PASS (if collateral is sufficient)"
echo "onBehalfOf used: ${ON_BEHALF}"
