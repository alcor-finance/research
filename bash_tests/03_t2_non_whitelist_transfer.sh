#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/common.sh"

activate_venv
load_env
ensure_tools

require_var ZODIAC_MANAGER
require_var WHITELIST_6TH_WALLET_ADDRESS
require_var WBTC_TOKEN

AMOUNT_WBTC="${1:-0.005}"
TO="${2:-0x1111111111111111111111111111111111111111}"
MANAGER="${ZODIAC_MANAGER}"
TOKEN="${WBTC_TOKEN}"

to_lc="$(echo "${TO}" | tr '[:upper:]' '[:lower:]')"
wl_lc="$(echo "${WHITELIST_6TH_WALLET_ADDRESS}" | tr '[:upper:]' '[:lower:]')"
if [[ "${to_lc}" == "${wl_lc}" ]]; then
  echo "target must be non-whitelist address" >&2
  exit 1
fi

impersonate "${MANAGER}"
set_balance_eth "${MANAGER}" "10"

decimals="$(token_decimals "${TOKEN}")"
amount_raw="$(to_units "${AMOUNT_WBTC}" "${decimals}")"

tx="$(cast send "${TOKEN}" "transfer(address,uint256)" "${TO}" "${amount_raw}" --from "${MANAGER}" --unlocked --rpc-url "${ANVIL_RPC_URL}" --json | jq -r '.transactionHash')"

stop_impersonate "${MANAGER}"

echo "T2 tx: ${tx}"
echo "note: direct EOA tx on fork can pass; Zodiac-policy test should be executed via Safe Roles UI and must REJECT"
