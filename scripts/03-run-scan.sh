#!/usr/bin/env bash
set -euo pipefail

# Step 3: Build sample project and run SonarQube scanner
# Reference: https://hub.docker.com/r/sonarsource/sonar-scanner-cli
# Reference: https://docs.sonarsource.com/sonarqube-community-build/analyzing-source-code/scanners/sonarscanner/

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
SAMPLE_PROJECT="$PROJECT_ROOT/sample-java-project"
ENV_FILE="$PROJECT_ROOT/.env"

if [[ ! -f "$ENV_FILE" ]]; then
    echo "[ERROR] .env file not found. Run 02-setup-project.sh first."
    exit 1
fi

source "$ENV_FILE"

# Accept optional project key override for ephemeral PR analysis
SCAN_PROJECT_KEY="${1:-$SONAR_PROJECT_KEY}"

echo "=== Step 3: Building and scanning sample project ==="
echo "  Project Key: $SCAN_PROJECT_KEY"
echo "  SonarQube:   $SONAR_URL"

echo ""
echo "[1/3] Building Java project with Maven..."
docker run --rm \
    -v "$SAMPLE_PROJECT":/usr/src/app \
    -w /usr/src/app \
    maven:3.9-eclipse-temurin-17 \
    mvn clean verify -q -B

echo ""
echo "[2/3] Running SonarQube Scanner..."

# Determine Docker host address for SonarQube access
if [[ "$(uname)" == "Darwin" ]]; then
    SONAR_HOST_FOR_SCANNER="http://host.docker.internal:9000"
else
    SONAR_HOST_FOR_SCANNER="http://172.17.0.1:9000"
fi

docker run --rm \
    -e SONAR_HOST_URL="$SONAR_HOST_FOR_SCANNER" \
    -e SONAR_TOKEN="$SONAR_TOKEN" \
    -v "$SAMPLE_PROJECT":/usr/src \
    sonarsource/sonar-scanner-cli \
    -Dsonar.projectKey="$SCAN_PROJECT_KEY" \
    -Dsonar.projectName="SonarQube AI Agent Test Project" \
    -Dsonar.sources=src/main/java \
    -Dsonar.tests=src/test/java \
    -Dsonar.java.binaries=target/classes \
    -Dsonar.java.test.binaries=target/test-classes \
    -Dsonar.java.libraries= \
    -Dsonar.coverage.jacoco.xmlReportPaths=target/site/jacoco/jacoco.xml \
    -Dsonar.sourceEncoding=UTF-8

echo ""
echo "[3/3] Waiting for analysis to complete..."
sleep 5

echo ""
echo "[INFO] Fetching analysis results..."
ISSUES_RESPONSE=$(curl -sf \
    -H "Authorization: Bearer $SONAR_TOKEN" \
    "$SONAR_URL/api/issues/search?componentKeys=$SCAN_PROJECT_KEY&statuses=OPEN&ps=100")

TOTAL=$(echo "$ISSUES_RESPONSE" | grep -o '"total":[0-9]*' | cut -d: -f2)
echo ""
echo "=== Scan Complete ==="
echo "  Total open issues: $TOTAL"
echo ""

echo "  Issues by severity:"
for SEVERITY in BLOCKER CRITICAL MAJOR MINOR INFO; do
    COUNT=$(echo "$ISSUES_RESPONSE" | grep -o "\"severity\":\"$SEVERITY\"" | wc -l | tr -d ' ')
    echo "    $SEVERITY: $COUNT"
done

echo ""
echo "  Issues by type:"
for TYPE in BUG VULNERABILITY CODE_SMELL; do
    COUNT=$(echo "$ISSUES_RESPONSE" | grep -o "\"type\":\"$TYPE\"" | wc -l | tr -d ' ')
    echo "    $TYPE: $COUNT"
done

echo ""
echo "  Dashboard: $SONAR_URL/dashboard?id=$SCAN_PROJECT_KEY"
echo ""
echo "  Next: Run 04-verify-api.sh to test the API endpoints."
