#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/common.sh"

activate_venv
load_env
ensure_tools

require_var ZODIAC_MANAGER
require_var AAVE_BORROW_ASSET_USDC
require_var UNISWAP_V3_SWAP_ROUTER

MANAGER="${ZODIAC_MANAGER}"
USDC="${AAVE_BORROW_ASSET_USDC}"
ROUTER="${UNISWAP_V3_SWAP_ROUTER}"
BAD_TOKEN="${1:-0x1111111111111111111111111111111111111111}"
AMOUNT_USDC_IN="${2:-10}"

impersonate "${MANAGER}"
set_balance_eth "${MANAGER}" "10"

decimals="$(token_decimals "${USDC}")"
amount_raw="$(to_units "${AMOUNT_USDC_IN}" "${decimals}")"

set +e
out=$(cast send "${ROUTER}" "exactInputSingle((address,address,uint24,address,uint256,uint256,uint256,uint160))" "(${USDC},${BAD_TOKEN},3000,${MANAGER},$(( $(date +%s) + 3600 )),${amount_raw},0,0)" --from "${MANAGER}" --unlocked --rpc-url "${ANVIL_RPC_URL}" 2>&1)
code=$?
set -e

stop_impersonate "${MANAGER}"

if [[ $code -ne 0 ]]; then
  echo "T7 expected REJECT, got revert/error as expected"
  echo "error: ${out}"
  exit 0
fi

echo "T7 unexpected PASS; check route/token restrictions" >&2
exit 1
