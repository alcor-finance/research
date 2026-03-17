#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/common.sh"

activate_venv
load_env
ensure_tools

require_var ZODIAC_MANAGER
require_var WHITELIST_6TH_WALLET_ADDRESS
require_var WBTC_TOKEN

AMOUNT_WBTC="${1:-0.01}"
MANAGER="${ZODIAC_MANAGER}"
TO="${WHITELIST_6TH_WALLET_ADDRESS}"
TOKEN="${WBTC_TOKEN}"

impersonate "${MANAGER}"
set_balance_eth "${MANAGER}" "10"

decimals="$(token_decimals "${TOKEN}")"
amount_raw="$(to_units "${AMOUNT_WBTC}" "${decimals}")"

tx="$(cast send "${TOKEN}" "transfer(address,uint256)" "${TO}" "${amount_raw}" --from "${MANAGER}" --unlocked --rpc-url "${ANVIL_RPC_URL}" --json | jq -r '.transactionHash')"

stop_impersonate "${MANAGER}"

echo "T1 tx: ${tx}"
echo "expected in Zodiac mode: PASS"
