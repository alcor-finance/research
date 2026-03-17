#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/common.sh"

activate_venv
load_env
ensure_tools

require_var ZODIAC_MANAGER
require_var AAVE_BORROW_ASSET_USDC
require_var AAVE_COLLATERAL_ASSET_WBTC
require_var UNISWAP_V3_SWAP_ROUTER

AMOUNT_USDC_IN="${1:-100}"
MANAGER="${ZODIAC_MANAGER}"
USDC="${AAVE_BORROW_ASSET_USDC}"
WBTC="${AAVE_COLLATERAL_ASSET_WBTC}"
ROUTER="${UNISWAP_V3_SWAP_ROUTER}"

impersonate "${MANAGER}"
set_balance_eth "${MANAGER}" "10"

decimals="$(token_decimals "${USDC}")"
amount_raw="$(to_units "${AMOUNT_USDC_IN}" "${decimals}")"

deadline=$(( $(date +%s) + 3600 ))

approve_tx="$(cast send "${USDC}" "approve(address,uint256)" "${ROUTER}" "${amount_raw}" --from "${MANAGER}" --unlocked --rpc-url "${ANVIL_RPC_URL}" --json | jq -r '.transactionHash')"
swap_tx="$(cast send "${ROUTER}" "exactInputSingle((address,address,uint24,address,uint256,uint256,uint256,uint160))" "(${USDC},${WBTC},3000,${MANAGER},${deadline},${amount_raw},0,0)" --from "${MANAGER}" --unlocked --rpc-url "${ANVIL_RPC_URL}" --json | jq -r '.transactionHash')"

stop_impersonate "${MANAGER}"

echo "T6 approve tx: ${approve_tx}"
echo "T6 swap tx:    ${swap_tx}"
echo "expected: PASS"
