#!/usr/bin/env bash
# chaos_test.sh — Simulate container failures and verify graceful degradation.
# Usage: BACKEND_URL=http://localhost:8000 API_KEY=<key> bash chaos_test.sh

set -euo pipefail

BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
API_KEY="${API_KEY:-}"
QUERY_PATH="/api/v1/query"
PASS_COUNT=0
FAIL_COUNT=0

# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

pass() { echo -e "${GREEN}[PASS]${NC} $1"; ((PASS_COUNT++)); }
fail() { echo -e "${RED}[FAIL]${NC} $1"; ((FAIL_COUNT++)); }
info() { echo -e "${YELLOW}[INFO]${NC} $1"; }

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
check_deps() {
  for cmd in curl jq docker; do
    if ! command -v "$cmd" &>/dev/null; then
      echo "Required command not found: $cmd" >&2
      exit 1
    fi
  done
  if [[ -z "$API_KEY" ]]; then
    echo "API_KEY env var is required." >&2
    exit 1
  fi
}

post_query() {
  curl -s -o /tmp/chaos_resp.json -w "%{http_code}" \
    -X POST "${BACKEND_URL}${QUERY_PATH}" \
    -H "Authorization: Bearer ${API_KEY}" \
    -H "Content-Type: application/json" \
    -d '{"question":"What is CPS1000?","mode":"hybrid","top_k":3}' \
    --max-time 20
}

assert_http_ok() {
  local scenario="$1"
  local http_code
  http_code=$(post_query)
  if [[ "$http_code" == "200" ]]; then
    pass "$scenario — HTTP 200 (degraded gracefully)"
  else
    fail "$scenario — expected 200, got $http_code"
    cat /tmp/chaos_resp.json 2>/dev/null || true
  fi
}

container_running() {
  docker inspect -f '{{.State.Running}}' "$1" 2>/dev/null | grep -q "true"
}

stop_container() {
  local name="$1"
  if container_running "$name"; then
    info "Stopping $name ..."
    docker stop "$name" &>/dev/null
  else
    info "$name is not running — skipping stop"
  fi
}

start_container() {
  local name="$1"
  info "Restarting $name ..."
  docker start "$name" &>/dev/null || true
}

wait_healthy() {
  local name="$1"
  local secs="$2"
  info "Waiting ${secs}s for $name to recover ..."
  sleep "$secs"
}

# ---------------------------------------------------------------------------
# Scenario runner
# ---------------------------------------------------------------------------
run_scenario() {
  local container="$1"
  local label="$2"
  echo ""
  info "=== Scenario: $label ==="
  stop_container "$container"
  sleep 3
  assert_http_ok "$label"
  start_container "$container"
  wait_healthy "$container" 5
  # Verify recovery
  local http_code
  http_code=$(post_query)
  if [[ "$http_code" == "200" ]]; then
    pass "$label — recovered after restart"
  else
    fail "$label — did not recover (HTTP $http_code)"
  fi
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
check_deps

echo "========================================"
echo "  KG-RAG Chaos Test"
echo "  Backend: ${BACKEND_URL}"
echo "========================================"

# Baseline — verify backend is up before chaos
info "Baseline health check ..."
baseline=$(post_query)
if [[ "$baseline" != "200" ]]; then
  echo -e "${RED}Backend not reachable (HTTP $baseline). Aborting.${NC}" >&2
  exit 1
fi
pass "Baseline — backend is healthy"

# Scenario 1: Neo4j down → should degrade to full-text search, not 500
run_scenario "aviation-neo4j" "Neo4j down (expect full-text fallback)"

# Scenario 2: Milvus down → should degrade to keyword/graph search, not 500
run_scenario "aviation-milvus" "Milvus down (expect vector search fallback)"

# Scenario 3: Redis down → no cache, queries still served
run_scenario "aviation-redis" "Redis down (expect cache-miss, still 200)"

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "========================================"
echo -e "  Results: ${GREEN}${PASS_COUNT} passed${NC}  ${RED}${FAIL_COUNT} failed${NC}"
echo "========================================"

if [[ "$FAIL_COUNT" -gt 0 ]]; then
  exit 1
fi
exit 0
