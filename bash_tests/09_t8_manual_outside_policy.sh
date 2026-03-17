#!/usr/bin/env bash
set -euo pipefail

cat <<'TXT'
T8 is a Zodiac permission test and must be executed via Safe Roles UI.

Do this in app.safe.global:
1) Open Safe -> Apps -> Roles
2) Use ZODIAC_MANAGER account
3) Build a transaction that is NOT covered by TraderRole (outside whitelist/method set)
4) Submit with 1 signature via role path
Expected: REJECT

Record in test-report.md:
- tx hash (if any)
- rejection reason
TXT
