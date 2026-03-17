#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/common.sh"

activate_venv
load_env
ensure_tools

require_var ZODIAC_MANAGER
require_var WBTC_WHALE
require_var WBTC_TOKEN
require_var FUND_WBTC_TO_MANAGER
require_var FUND_ETH_TO_MANAGER

MANAGER="${ZODIAC_MANAGER}"
WHALE="${WBTC_WHALE}"
WBTC="${WBTC_TOKEN}"

echo "funding manager ${MANAGER} from whale ${WHALE}"

impersonate "${WHALE}"
set_balance_eth "${WHALE}" "1000"

before_eth="$(eth_balance "${MANAGER}")"

decimals="$(token_decimals "${WBTC}")"
amount_wbtc="$(to_units "${FUND_WBTC_TO_MANAGER}" "${decimals}")"
amount_eth_wei="$(to_units "${FUND_ETH_TO_MANAGER}" "18")"

before_wbtc="$(erc20_balance "${WBTC}" "${MANAGER}")"

eth_tx="$(cast send "${MANAGER}" --from "${WHALE}" --unlocked --value "${amount_eth_wei}" --rpc-url "${ANVIL_RPC_URL}" --json | jq -r '.transactionHash')"

wbtc_tx="$(cast send "${WBTC}" "transfer(address,uint256)" "${MANAGER}" "${amount_wbtc}" --from "${WHALE}" --unlocked --rpc-url "${ANVIL_RPC_URL}" --json | jq -r '.transactionHash')"

after_eth="$(eth_balance "${MANAGER}")"
after_wbtc="$(erc20_balance "${WBTC}" "${MANAGER}")"

stop_impersonate "${WHALE}"

echo "ETH tx:  ${eth_tx}"
echo "WBTC tx: ${wbtc_tx}"
echo "manager ETH:  ${before_eth} -> ${after_eth}"
echo "manager WBTC raw: ${before_wbtc} -> ${after_wbtc}"
