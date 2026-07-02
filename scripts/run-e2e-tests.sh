#!/usr/bin/env bash
set -euo pipefail

# Resolve project root (parent of this script's directory)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

COMPOSE_FILE="${PROJECT_ROOT}/docker-compose.test.yml"

echo "=============================================="
echo " UW Hub E2E Test Runner"
echo " Project root: ${PROJECT_ROOT}"
echo "=============================================="

# ----------------------------------------------------------------------------
# 1. Java unit tests (exclude integration tests)
# ----------------------------------------------------------------------------
echo ""
echo ">>> [1/5] Running Java unit tests..."
( cd "${PROJECT_ROOT}/backend" && mvn test -Dtest='!*IT' )

# ----------------------------------------------------------------------------
# 2. Java integration tests
# ----------------------------------------------------------------------------
echo ""
echo ">>> [2/5] Running Java integration tests (ITs)..."
( cd "${PROJECT_ROOT}/backend" && mvn test -Dtest='*IT' -Dspring.profiles.active=integration )

# ----------------------------------------------------------------------------
# 3. Python AI worker tests
# ----------------------------------------------------------------------------
echo ""
echo ">>> [3/5] Running Python tests..."
( cd "${PROJECT_ROOT}" && pytest ai-worker/tests/ )

# ----------------------------------------------------------------------------
# 4. Bring up the full stack via docker compose
# ----------------------------------------------------------------------------
echo ""
echo ">>> [4/5] Starting docker-compose test stack..."

teardown() {
  echo ""
  echo ">>> Tearing down docker-compose test stack..."
  docker compose -f "${COMPOSE_FILE}" down -v --remove-orphans || true
}
trap teardown EXIT

docker compose -f "${COMPOSE_FILE}" up -d --build

echo ""
echo ">>> Waiting for services to become healthy..."
wait_for() {
  local name="$1"
  local url="$2"
  local tries=60
  local i=1
  while [ "${i}" -le "${tries}" ]; do
    if curl -fsS "${url}" >/dev/null 2>&1; then
      echo "    [OK] ${name} healthy (${url})"
      return 0
    fi
    echo "    [..] waiting for ${name} (${i}/${tries})..."
    sleep 3
    i=$((i + 1))
  done
  echo "    [FAIL] ${name} did not become healthy at ${url}"
  echo ""
  echo ">>> docker compose ps:"
  docker compose -f "${COMPOSE_FILE}" ps || true
  echo ">>> Recent logs:"
  docker compose -f "${COMPOSE_FILE}" logs --tail=100 || true
  return 1
}

wait_for "backend"        "http://localhost:8080/api/v1/health"
wait_for "mock-ai-worker" "http://localhost:8001/health"
wait_for "frontend"       "http://localhost:5173"

# ----------------------------------------------------------------------------
# 5. Playwright E2E tests
# ----------------------------------------------------------------------------
echo ""
echo ">>> [5/5] Running Playwright E2E tests..."
PLAYWRIGHT_EXIT=0
(
  cd "${PROJECT_ROOT}/e2e"
  npm ci
  npx playwright install chromium
  npx playwright test
) || PLAYWRIGHT_EXIT=$?

echo ""
echo "=============================================="
echo " Test reports"
echo "=============================================="
echo " Java surefire:    ${PROJECT_ROOT}/backend/target/surefire-reports/"
echo " Playwright HTML:  ${PROJECT_ROOT}/e2e/playwright-report/index.html"
echo " Playwright JSON:  ${PROJECT_ROOT}/e2e/test-results/"
echo "=============================================="

if [ "${PLAYWRIGHT_EXIT}" -eq 0 ]; then
  echo ">>> Playwright suite PASSED"
else
  echo ">>> Playwright suite FAILED (exit ${PLAYWRIGHT_EXIT})"
fi

# Teardown runs via trap; propagate Playwright's exit code.
exit "${PLAYWRIGHT_EXIT}"
