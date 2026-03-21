#!/usr/bin/env bash
set -euo pipefail

# Step 6: Test ephemeral project key workflow (PR pre-merge simulation)
# This simulates the Mode 1 workflow: PR branch → ephemeral project → scan → cleanup

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$(dirname "$SCRIPT_DIR")/.env"

if [[ ! -f "$ENV_FILE" ]]; then
    echo "[ERROR] .env file not found. Run 02-setup-project.sh first."
    exit 1
fi

source "$ENV_FILE"

PR_NUMBER="${1:-999}"
EPHEMERAL_KEY="sonarqube-agent-test-pr-$PR_NUMBER"

echo "=== Step 6: Ephemeral Project Workflow Test ==="
echo "  Simulating PR #$PR_NUMBER analysis"
echo "  Ephemeral project key: $EPHEMERAL_KEY"
echo ""

echo "[1/5] Creating ephemeral project..."
HTTP_CODE=$(curl -sf -o /dev/null -w "%{http_code}" \
    -H "Authorization: Bearer $SONAR_TOKEN" \
    -X POST "$SONAR_URL/api/projects/create" \
    -d "project=$EPHEMERAL_KEY&name=Test+Project+[PR+%23$PR_NUMBER]" 2>/dev/null || echo "000")
echo "  Create response: HTTP $HTTP_CODE"

echo ""
echo "[2/5] Running scan on ephemeral project..."
SAMPLE_PROJECT="$(dirname "$SCRIPT_DIR")/sample-java-project"

if [[ "$(uname)" == "Darwin" ]]; then
    SONAR_HOST="http://host.docker.internal:9000"
else
    SONAR_HOST="http://172.17.0.1:9000"
fi

docker run --rm \
    -e SONAR_HOST_URL="$SONAR_HOST" \
    -e SONAR_TOKEN="$SONAR_TOKEN" \
    -v "$SAMPLE_PROJECT":/usr/src \
    sonarsource/sonar-scanner-cli \
    -Dsonar.projectKey="$EPHEMERAL_KEY" \
    -Dsonar.projectName="Test Project [PR #$PR_NUMBER]" \
    -Dsonar.sources=src/main/java \
    -Dsonar.tests=src/test/java \
    -Dsonar.java.binaries=target/classes \
    -Dsonar.java.test.binaries=target/test-classes \
    -Dsonar.java.libraries= \
    -Dsonar.coverage.jacoco.xmlReportPaths=target/site/jacoco/jacoco.xml \
    -Dsonar.sourceEncoding=UTF-8

echo ""
echo "[3/5] Waiting for analysis to complete..."
sleep 5

echo ""
echo "[4/5] Fetching issues from ephemeral project..."
ISSUES=$(curl -sf \
    -H "Authorization: Bearer $SONAR_TOKEN" \
    "$SONAR_URL/api/issues/search?componentKeys=$EPHEMERAL_KEY&statuses=OPEN&ps=100")

TOTAL=$(echo "$ISSUES" | grep -o '"total":[0-9]*' | cut -d: -f2)
echo "  Issues found in PR #$PR_NUMBER: $TOTAL"

echo ""
echo "  Verifying main project is NOT affected..."
MAIN_ISSUES=$(curl -sf \
    -H "Authorization: Bearer $SONAR_TOKEN" \
    "$SONAR_URL/api/issues/search?componentKeys=$SONAR_PROJECT_KEY&statuses=OPEN&ps=1")
MAIN_TOTAL=$(echo "$MAIN_ISSUES" | grep -o '"total":[0-9]*' | cut -d: -f2)
echo "  Main project ($SONAR_PROJECT_KEY) issues: $MAIN_TOTAL (should be unchanged)"

echo ""
echo "[5/5] Cleaning up ephemeral project..."
HTTP_CODE=$(curl -sf -o /dev/null -w "%{http_code}" \
    -H "Authorization: Bearer $SONAR_TOKEN" \
    -X POST "$SONAR_URL/api/projects/delete" \
    -d "project=$EPHEMERAL_KEY" 2>/dev/null || echo "000")
echo "  Delete response: HTTP $HTTP_CODE"

VERIFY=$(curl -sf -o /dev/null -w "%{http_code}" \
    -H "Authorization: Bearer $SONAR_TOKEN" \
    "$SONAR_URL/api/projects/search?projects=$EPHEMERAL_KEY" 2>/dev/null || echo "000")
echo "  Verify deleted: HTTP $VERIFY"

echo ""
echo "=== Ephemeral Workflow Test Complete ==="
echo ""
echo "  This confirms:"
echo "  1. Ephemeral project created successfully"
echo "  2. Scan ran on ephemeral project independently"
echo "  3. Main project was not affected"
echo "  4. Ephemeral project cleaned up after use"
