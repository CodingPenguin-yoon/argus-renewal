#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
failed=0

check_forbidden_reference() {
  local pattern="$1"
  local label="$2"
  shift 2

  if rg --line-number --glob '*.{py,ts,tsx}' "$pattern" "$@"; then
    echo "Boundary violation: ${label}" >&2
    failed=1
  fi
}

check_forbidden_reference \
  '(^|[./])argus_v2([./]|$)' \
  'backend/src/market_data must not depend on the legacy argus_v2 package.' \
  "$repo_root/backend/src/market_data"

check_forbidden_reference \
  '(^|[./])argus_v2([./]|$)' \
  'the /market frontend must not depend on the legacy argus_v2 frontend.' \
  "$repo_root/frontend/src/market_terminal" \
  "$repo_root/frontend/src/app/market"

check_forbidden_reference \
  '(^|[[:space:]])(from|import)[[:space:]].*(adapters|FixtureMarketFlowAdapter)' \
  'the market-flow API route may read storage but must not call collection adapters.' \
  "$repo_root/backend/src/market_data/market_flow/api.py"

if (( failed != 0 )); then
  exit 1
fi

echo "Market-data boundary check passed."
