#!/usr/bin/env bash
set -euo pipefail

cat <<'TXT'
T10 replay/duplicate behavior should be validated via Safe UI and nonce checks.

Do this:
1) Attempt duplicate submission of same intent
2) Check whether duplicate executes or is blocked/replaced as expected
3) Verify nonce progression in Safe history
Expected: controlled behavior, no unauthorized duplicate execution

Record in test-report.md:
- involved tx hashes
- nonce values
- outcome
TXT
