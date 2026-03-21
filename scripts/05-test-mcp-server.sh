#!/usr/bin/env bash
set -euo pipefail

# Step 5: Test SonarQube MCP Server connectivity
# Reference: https://docs.sonarsource.com/sonarqube-mcp-server/quickstart-guide
# Reference: https://hub.docker.com/mcp/server/sonarqube/overview

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$(dirname "$SCRIPT_DIR")/.env"

if [[ ! -f "$ENV_FILE" ]]; then
    echo "[ERROR] .env file not found. Run 02-setup-project.sh first."
    exit 1
fi

source "$ENV_FILE"

echo "=== Step 5: Testing SonarQube MCP Server ==="
echo ""

# Determine Docker host address
if [[ "$(uname)" == "Darwin" ]]; then
    SONAR_HOST_FOR_MCP="http://host.docker.internal:9000"
else
    SONAR_HOST_FOR_MCP="http://172.17.0.1:9000"
fi

echo "[1/3] Pulling MCP Server image..."
docker pull mcp/sonarqube --quiet 2>/dev/null || docker pull mcp/sonarqube

echo ""
echo "[2/3] Testing MCP Server stdio connectivity..."
echo "  Sending ping request via MCP protocol..."

# MCP uses JSON-RPC over stdio. Send an initialize + ping request.
MCP_INIT='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}'
MCP_LIST='{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'

RESULT=$(echo -e "$MCP_INIT\n$MCP_LIST" | timeout 30 docker run --rm -i \
    -e SONARQUBE_URL="$SONAR_HOST_FOR_MCP" \
    -e SONARQUBE_TOKEN="$SONAR_TOKEN" \
    mcp/sonarqube 2>/dev/null || echo "MCP_TIMEOUT")

if echo "$RESULT" | grep -q "analyze_code_snippet"; then
    echo "  [PASS] MCP Server responded with tool list"
    echo ""
    echo "  Available MCP tools:"
    echo "$RESULT" | grep -o '"name":"[^"]*"' | while read -r line; do
        TOOL_NAME=$(echo "$line" | cut -d'"' -f4)
        echo "    - $TOOL_NAME"
    done
elif echo "$RESULT" | grep -q "MCP_TIMEOUT"; then
    echo "  [FAIL] MCP Server did not respond within 30s"
    echo "  Check: Is SonarQube running? Is the Docker network accessible?"
else
    echo "  [WARN] Unexpected response. MCP Server may need different config."
    echo "  Response (first 500 chars): ${RESULT:0:500}"
fi

echo ""
echo "[3/3] MCP Server configuration for LLM tools"
echo ""
echo "  Claude Code setup:"
echo "    claude mcp add sonarqube \\"
echo "      --env SONARQUBE_TOKEN=$SONAR_TOKEN \\"
echo "      --env SONARQUBE_URL=$SONAR_HOST_FOR_MCP \\"
echo "      -- docker run -i --rm --init -e SONARQUBE_TOKEN -e SONARQUBE_URL mcp/sonarqube"
echo ""
echo "  Cursor mcp.json:"
cat << MCPJSON
  {
    "mcpServers": {
      "sonarqube": {
        "command": "docker",
        "args": ["run","-i","--rm","--init","-e","SONARQUBE_TOKEN","-e","SONARQUBE_URL","mcp/sonarqube"],
        "env": {
          "SONARQUBE_TOKEN": "$SONAR_TOKEN",
          "SONARQUBE_URL": "$SONAR_HOST_FOR_MCP"
        }
      }
    }
  }
MCPJSON
echo ""
echo "=== MCP Server test complete ==="
