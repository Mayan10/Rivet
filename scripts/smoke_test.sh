#!/usr/bin/env bash
# Post-deploy smoke test (docs/saas-buildout.md section 13). Exercises
# the one generation endpoint that's always safe to hit without creating
# real data or touching billing -- POST /api/v1/generate is
# unauthenticated, synchronous, and makes no database writes (Phase 6) --
# alongside the two health endpoints. Confirms a deploy actually serves
# traffic correctly, not just that the process started. Plain curl, no
# Python dependency -- this needs to run from a bare CI/deploy runner.
#
# Usage: scripts/smoke_test.sh https://api.example.com
set -euo pipefail

BASE_URL="${1:?Usage: smoke_test.sh <base_url>}"
RESPONSE_FILE="$(mktemp)"
trap 'rm -f "$RESPONSE_FILE"' EXIT

_check() {
  local method="$1" path="$2" expected_status="$3" body="${4:-}"
  local status
  if [ -n "$body" ]; then
    status=$(curl -s -o "$RESPONSE_FILE" -w "%{http_code}" -X "$method" \
      -H "Content-Type: application/json" -d "$body" "${BASE_URL}${path}")
  else
    status=$(curl -s -o "$RESPONSE_FILE" -w "%{http_code}" -X "$method" "${BASE_URL}${path}")
  fi
  if [ "$status" != "$expected_status" ]; then
    echo "FAIL: $method $path -> $status (expected $expected_status)"
    cat "$RESPONSE_FILE"
    exit 1
  fi
  echo "OK: $method $path -> $status"
}

_check GET /healthz 200
_check GET /readyz 200

_check POST /api/v1/generate 200 '{
  "plot": {"width_m": 15, "length_m": 13, "entrance": "north", "abutting_road_width_m": 9, "proposed_height_m": 6},
  "rooms": [
    {"room_type": "living_room", "count": 1},
    {"room_type": "master_bedroom", "count": 1, "attached_bathroom": true},
    {"room_type": "bedroom", "count": 2, "attached_bathroom": true},
    {"room_type": "kitchen", "count": 1},
    {"room_type": "dining_room", "count": 1},
    {"room_type": "bathroom", "count": 1}
  ],
  "seed": 1
}'

echo "All smoke tests passed."
