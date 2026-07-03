#!/usr/bin/env bash
# I2 — Demo seed script
# Seeds the three synthetic submissions (Accept / Refer / Decline) and kicks
# off processing.  Requires: jq, curl, a running Java orchestrator on :8080.
set -euo pipefail

API="${API_BASE:-http://localhost:8080/api/v1}"
SUBMISSIONS_DIR="$(cd "$(dirname "$0")/submissions" && pwd)"

# ── Colours ──────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()    { echo -e "${GREEN}[seed]${NC} $*"; }
warn()    { echo -e "${YELLOW}[seed]${NC} $*"; }
err()     { echo -e "${RED}[seed]${NC} $*" >&2; }

# ── Preflight ─────────────────────────────────────────────────────────────────
for cmd in curl jq; do
  command -v "$cmd" >/dev/null 2>&1 || { err "Required command not found: $cmd"; exit 1; }
done

info "=== UW-Hub Demo Seed Script ==="
info "API base: $API"
echo ""

# Health check
HTTP_CODE=$(curl -s -o /dev/null -w '%{http_code}' "$API/health" 2>/dev/null || echo "000")
if [ "$HTTP_CODE" != "200" ]; then
  err "Orchestrator not reachable at $API/health (HTTP $HTTP_CODE)."
  err "Start it with: cd backend && mvn spring-boot:run"
  exit 1
fi
info "Orchestrator healthy."
echo ""

# ── Seed each submission ───────────────────────────────────────────────────────
declare -a SUBMISSION_IDS
declare -a SUBMISSION_NAMES

IDX=0
for f in "$SUBMISSIONS_DIR"/*.json; do
  NAME=$(basename "$f" .json)
  EXPECTED=$(jq -r '.expectedBand' "$f")
  EXPRESS=$(jq -r '.expressPath' "$f")
  RAW_TEXT=$(jq -r '.rawText' "$f")

  info "──────────────────────────────────────────"
  info "Submitting: $NAME"
  info "  Expected band : $EXPECTED"
  info "  Express path  : $EXPRESS"

  # 1. Create submission
  CREATE_BODY=$(jq -n --arg rt "$RAW_TEXT" '{"rawText": $rt}')
  RESPONSE=$(curl -s -w '\n%{http_code}' -X POST "$API/submissions" \
    -H "Content-Type: application/json" \
    -d "$CREATE_BODY")
  HTTP_CODE=$(echo "$RESPONSE" | tail -1)
  BODY=$(echo "$RESPONSE" | sed '$d')

  if [ "$HTTP_CODE" != "201" ]; then
    err "  Failed to create submission (HTTP $HTTP_CODE): $BODY"
    continue
  fi

  ID=$(echo "$BODY" | jq -r '.id')
  info "  Created ID    : $ID"

  SUBMISSION_IDS[$IDX]="$ID"
  SUBMISSION_NAMES[$IDX]="$NAME"
  IDX=$((IDX + 1))

  # 2. Trigger processing
  if [ "$EXPRESS" = "true" ]; then
    HTTP_CODE=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$API/submissions/$ID/evaluate")
    if [ "$HTTP_CODE" != "202" ]; then
      warn "  /evaluate returned HTTP $HTTP_CODE (expected 202)"
    else
      info "  Triggered      : /evaluate (express path)"
    fi
  else
    HTTP_CODE=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$API/submissions/$ID/extract")
    if [ "$HTTP_CODE" != "202" ]; then
      warn "  /extract returned HTTP $HTTP_CODE (expected 202)"
    else
      info "  Triggered      : /extract (stepwise path)"
    fi
  fi

  info "  Poll status    : curl -s $API/submissions/$ID | jq .status"
done

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
info "=== All submissions seeded ==="
echo ""
echo "  Submission IDs:"
for i in "${!SUBMISSION_IDS[@]}"; do
  printf "  %-35s %s\n" "${SUBMISSION_NAMES[$i]}" "${SUBMISSION_IDS[$i]}"
done
echo ""
info "Watch all statuses:"
echo ""
for i in "${!SUBMISSION_IDS[@]}"; do
  echo "  curl -s $API/submissions/${SUBMISSION_IDS[$i]} | jq '{status: .status, band: .currentDecision.recommendation}'"
done
echo ""
info "Frontend: http://localhost:5173"
info "RabbitMQ: http://localhost:15672  (uw/uwpass)"
