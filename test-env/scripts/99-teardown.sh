#!/usr/bin/env bash
set -euo pipefail

# Teardown: Stop all containers and optionally remove volumes

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=== Teardown: Stopping SonarQube environment ==="

cd "$PROJECT_ROOT"

if [[ "${1:-}" == "--clean" ]]; then
    echo "[WARN] Removing all containers AND volumes (data will be lost)"
    docker compose down -v
    echo "[OK] All containers and volumes removed."
else
    docker compose down
    echo "[OK] Containers stopped. Volumes preserved."
    echo "  To also remove volumes: $0 --clean"
fi
