#!/usr/bin/env bash
set -euo pipefail

cat <<'TXT'
T9 is a Safe multisig fallback test and must be executed via Safe Transaction flow.

Do this in app.safe.global:
1) Take same action as T8 (outside role policy)
2) Submit as normal Safe tx (not role shortcut)
3) Collect 3-of-5 owner confirmations
Expected: PASS

Record in test-report.md:
- tx hash
- list of 3 signers
TXT
