#!/usr/bin/env bash
set -euo pipefail

# Step 4: Verify SonarQube API endpoints used by the Orchestrator
# Reference: https://next.sonarqube.com/sonarqube/web_api/api/issues/search

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$(dirname "$SCRIPT_DIR")/.env"

if [[ ! -f "$ENV_FILE" ]]; then
    echo "[ERROR] .env file not found. Run 02-setup-project.sh first."
    exit 1
fi

source "$ENV_FILE"

PASS=0
FAIL=0

run_test() {
    local TEST_NAME="$1"
    local EXPECTED="$2"
    local ACTUAL="$3"

    if echo "$ACTUAL" | grep -q "$EXPECTED"; then
        echo "  [PASS] $TEST_NAME"
        PASS=$((PASS + 1))
    else
        echo "  [FAIL] $TEST_NAME"
        echo "    Expected to contain: $EXPECTED"
        echo "    Got: ${ACTUAL:0:200}"
        FAIL=$((FAIL + 1))
    fi
}

echo "=== Step 4: Verifying SonarQube API Endpoints ==="
echo ""

echo "[Test Group 1] System API"
RESULT=$(curl -sf "$SONAR_URL/api/system/status")
run_test "GET /api/system/status" '"status":"UP"' "$RESULT"

echo ""
echo "[Test Group 2] Project API"
RESULT=$(curl -sf -H "Authorization: Bearer $SONAR_TOKEN" \
    "$SONAR_URL/api/projects/search?projects=$SONAR_PROJECT_KEY")
run_test "GET /api/projects/search (project exists)" "$SONAR_PROJECT_KEY" "$RESULT"

echo ""
echo "[Test Group 3] Issues Search API"
RESULT=$(curl -sf -H "Authorization: Bearer $SONAR_TOKEN" \
    "$SONAR_URL/api/issues/search?componentKeys=$SONAR_PROJECT_KEY&statuses=OPEN&ps=5")
run_test "GET /api/issues/search (open issues)" '"total"' "$RESULT"

RESULT=$(curl -sf -H "Authorization: Bearer $SONAR_TOKEN" \
    "$SONAR_URL/api/issues/search?componentKeys=$SONAR_PROJECT_KEY&types=BUG&ps=5")
run_test "GET /api/issues/search (filter BUG)" '"type":"BUG"' "$RESULT"

RESULT=$(curl -sf -H "Authorization: Bearer $SONAR_TOKEN" \
    "$SONAR_URL/api/issues/search?componentKeys=$SONAR_PROJECT_KEY&types=VULNERABILITY&ps=5")
run_test "GET /api/issues/search (filter VULNERABILITY)" '"type":"VULNERABILITY"' "$RESULT"

RESULT=$(curl -sf -H "Authorization: Bearer $SONAR_TOKEN" \
    "$SONAR_URL/api/issues/search?componentKeys=$SONAR_PROJECT_KEY&types=CODE_SMELL&ps=5")
run_test "GET /api/issues/search (filter CODE_SMELL)" '"type":"CODE_SMELL"' "$RESULT"

RESULT=$(curl -sf -H "Authorization: Bearer $SONAR_TOKEN" \
    "$SONAR_URL/api/issues/search?componentKeys=$SONAR_PROJECT_KEY&severities=BLOCKER,CRITICAL&ps=5")
run_test "GET /api/issues/search (filter severity)" '"issues"' "$RESULT"

echo ""
echo "[Test Group 4] Measures API"
RESULT=$(curl -sf -H "Authorization: Bearer $SONAR_TOKEN" \
    "$SONAR_URL/api/measures/component?component=$SONAR_PROJECT_KEY&metricKeys=bugs,vulnerabilities,code_smells,coverage,duplicated_lines_density")
run_test "GET /api/measures/component (quality metrics)" '"metric"' "$RESULT"

echo ""
echo "[Test Group 5] Quality Gate API"
RESULT=$(curl -sf -H "Authorization: Bearer $SONAR_TOKEN" \
    "$SONAR_URL/api/qualitygates/project_status?projectKey=$SONAR_PROJECT_KEY")
run_test "GET /api/qualitygates/project_status" '"projectStatus"' "$RESULT"

echo ""
echo "[Test Group 6] Project Delete API (ephemeral project cleanup)"
TEMP_KEY="sonarqube-agent-test-temp-delete"
curl -sf -o /dev/null \
    -u "admin:admin" \
    -X POST "$SONAR_URL/api/projects/create" \
    -d "project=$TEMP_KEY&name=Temp Delete Test" 2>/dev/null || true

RESULT=$(curl -sf -o /dev/null -w "%{http_code}" \
    -H "Authorization: Bearer $SONAR_TOKEN" \
    -X POST "$SONAR_URL/api/projects/delete" \
    -d "project=$TEMP_KEY" 2>/dev/null || echo "000")
if [[ "$RESULT" == "204" || "$RESULT" == "200" ]]; then
    echo "  [PASS] POST /api/projects/delete (ephemeral cleanup)"
    PASS=$((PASS + 1))
else
    echo "  [FAIL] POST /api/projects/delete (HTTP $RESULT)"
    FAIL=$((FAIL + 1))
fi

echo ""
echo "[Test Group 7] Webhook API"
RESULT=$(curl -sf -H "Authorization: Bearer $SONAR_TOKEN" \
    "$SONAR_URL/api/webhooks/list?project=$SONAR_PROJECT_KEY")
run_test "GET /api/webhooks/list" '"webhooks"' "$RESULT"

echo ""
echo "========================================"
echo "  Results: $PASS passed, $FAIL failed"
echo "========================================"

if [[ $FAIL -gt 0 ]]; then
    echo "  [WARN] Some API tests failed. Check SonarQube configuration."
    exit 1
fi

echo ""
echo "  All API endpoints verified. Ready for Orchestrator development."
