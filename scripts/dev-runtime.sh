#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

pids=()

cleanup() {
  if ((${#pids[@]} > 0)); then
    kill "${pids[@]}" 2>/dev/null || true
    wait "${pids[@]}" 2>/dev/null || true
  fi
}

trap cleanup EXIT INT TERM

run_service() {
  local name="$1"
  shift
  (
    cd "$ROOT_DIR"
    "$@"
  ) &
  local pid=$!
  pids+=("$pid")
  printf '[argus-dev] started %s pid=%s\n' "$name" "$pid"
}

run_service "backend" pnpm dev:backend
run_service "frontend" pnpm dev:frontend
run_service "market-collector" pnpm dev:collector:market
run_service "news-collector" pnpm dev:collector:news

wait -n "${pids[@]}"
exit_code=$?
cleanup
exit "$exit_code"

