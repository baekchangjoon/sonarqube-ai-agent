#!/usr/bin/env bash
set -euo pipefail

# Step 1: Start SonarQube + PostgreSQL
# Reference: https://docs.sonarsource.com/sonarqube-community-build/setup-and-upgrade/installing-sonarqube-from-docker/

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=== Step 1: Starting SonarQube Community Edition ==="

# Required for Elasticsearch inside SonarQube container
# https://docs.sonarsource.com/sonarqube-community-build/setup-and-upgrade/installing-sonarqube-from-docker/#prerequisites
if [[ "$(uname)" == "Linux" ]]; then
    CURRENT_MAX_MAP=$(sysctl -n vm.max_map_count 2>/dev/null || echo "0")
    if [[ "$CURRENT_MAX_MAP" -lt 262144 ]]; then
        echo "[INFO] Setting vm.max_map_count=262144 (requires sudo)"
        sudo sysctl -w vm.max_map_count=262144
    fi
fi

cd "$PROJECT_ROOT"
docker compose up -d

echo ""
echo "[INFO] Waiting for SonarQube to become healthy..."
echo "[INFO] This may take 1-2 minutes on first start."
echo ""

TIMEOUT=180
ELAPSED=0
while [[ $ELAPSED -lt $TIMEOUT ]]; do
    STATUS=$(curl -sf http://localhost:9000/api/system/status 2>/dev/null | grep -o '"status":"[^"]*"' | cut -d'"' -f4 || echo "STARTING")
    if [[ "$STATUS" == "UP" ]]; then
        echo "[OK] SonarQube is UP and running at http://localhost:9000"
        echo "[OK] Default credentials: admin / admin"
        exit 0
    fi
    echo "  ... SonarQube status: $STATUS (${ELAPSED}s / ${TIMEOUT}s)"
    sleep 10
    ELAPSED=$((ELAPSED + 10))
done

echo "[ERROR] SonarQube did not start within ${TIMEOUT}s"
echo "[ERROR] Check logs: docker compose logs sonarqube"
exit 1
