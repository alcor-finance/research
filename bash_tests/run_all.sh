#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"

"${DIR}/00_start_fork.sh"
"${DIR}/01_fund_manager.sh"
"${DIR}/02_t1_whitelist_transfer.sh"
"${DIR}/03_t2_non_whitelist_transfer.sh"
"${DIR}/04_t3_aave_supply_wbtc.sh"
"${DIR}/05_t4_aave_borrow_usdc.sh"
"${DIR}/06_t5_aave_borrow_too_much.sh"
"${DIR}/07_t6_uniswap_v3_swap.sh"
"${DIR}/08_t7_uniswap_forbidden_route.sh"
"${DIR}/09_t8_manual_outside_policy.sh"
"${DIR}/10_t9_manual_3of5_override.sh"
"${DIR}/11_t10_manual_replay.sh"
