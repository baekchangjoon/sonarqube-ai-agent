# SonarQube AI Agent

LLM-agnostic AI Agent Orchestrator for automated SonarQube defect remediation.

## Documents

| Document | Description |
|----------|-------------|
| [Governance Blueprint](docs/sonarqube_ai_agent_governance_blueprint.md) | RACI matrix, ownership model, operational process |
| [Implementation Architecture](docs/ai_agent_implementation_architecture.md) | MCP Server, ephemeral project workflow, LLM abstraction |

## Prerequisites

- Docker Engine 20.10+ ([install](https://docs.docker.com/engine/install/))
- Python 3.9+ with `pip`
- ~4 GB free RAM (SonarQube + PostgreSQL + scanner containers)
- Internet access (for pulling Docker images on first run)

### LLM Agent CLI Tools (at least one required)

| Agent | Install | Auth | Verified Version |
|-------|---------|------|-----------------|
| [Claude Code](https://docs.anthropic.com/en/docs/claude-code) | `npm i -g @anthropic-ai/claude-code` | `claude` (interactive first run) | >= 2.1.x |
| [Gemini CLI](https://github.com/google-gemini/gemini-cli) | `npm i -g @anthropic-ai/gemini-cli` | `gemini` (interactive first run) | >= 0.30.x |
| [Cursor Agent](https://docs.cursor.com/agent) | Bundled with Cursor IDE | Cursor login | >= 2026.03.x |

## Architecture

```
sonarqube-ai-agent/
├── docs/
│   ├── ai_agent_implementation_architecture.md
│   └── sonarqube_ai_agent_governance_blueprint.md
│
├── docker-compose.yml ──── SonarQube CE + PostgreSQL
├── .env.example ────────── Environment variable template
├── .env ────────────────── (generated) SONAR_URL + SONAR_TOKEN
│
├── sample-java-project/ ── Java 17 project with intentional defects
│   ├── src/main/java/
│   │   ├── UserService.java      15 issues (S6437, S2095, S2259, ...)
│   │   ├── OrderProcessor.java    7 issues (S2095, S3776, S1104, ...)
│   │   └── SecurityUtils.java     4 issues (S1118, S2119, S107, ...)
│   ├── src/test/java/             Minimal tests (low coverage)
│   └── pom.xml                    Maven build with JaCoCo
│
├── scripts/
│   ├── 01-start-sonarqube.sh      Start containers
│   ├── 02-setup-project.sh        Create project + token → .env
│   ├── 03-run-scan.sh             Build + scan
│   ├── 04-verify-api.sh           Test all API endpoints
│   ├── 05-test-mcp-server.sh      Test MCP Server
│   ├── 06-scan-ephemeral.sh       Test PR workflow
│   └── 99-teardown.sh             Stop everything
│
├── orchestrator/  ──────── Python AI Agent Orchestrator
│   ├── config.yml                 Agent type, SonarQube, scanner, mode settings
│   ├── requirements.txt           Python dependencies
│   ├── pytest.ini                 Test runner config
│   ├── src/
│   │   ├── config.py              YAML config loader with ${ENV} resolution
│   │   ├── sonarqube_client.py    SonarQube REST API client
│   │   ├── github_client.py       GitHub PR comment/creation via gh CLI
│   │   ├── orchestrator.py        3-mode workflow engine
│   │   ├── main.py                CLI entry point (4 subcommands)
│   │   └── agents/
│   │       ├── base.py            LLMAgent ABC + FixResult dataclass
│   │       ├── factory.py         Config-driven agent instantiation
│   │       ├── claude_code.py     Claude Code  (-p --permission-mode acceptEdits)
│   │       ├── gemini_cli.py      Gemini CLI   (--yolo -p)
│   │       ├── kiro_cli.py        AWS Kiro CLI (--no-interactive)
│   │       └── bedrock_api.py     AWS Bedrock API fallback
│   └── tests/
│       ├── test_config.py
│       ├── test_agents.py
│       ├── test_sonarqube_client.py   Unit + Integration
│       └── test_orchestrator.py
│
└── e2e-fix-test/ ───────── (generated) E2E fix validation workspace
```

## Quick Start

### Step 1 — Infrastructure

```bash
# Copy .env.example to .env (edit if needed)
cp .env.example .env

# Start SonarQube (wait ~2 min for first boot)
./scripts/01-start-sonarqube.sh

# Create project and generate API token (writes SONAR_TOKEN to .env)
./scripts/02-setup-project.sh

# Build sample project and run initial SonarQube scan
./scripts/03-run-scan.sh

# Verify all API endpoints work (11 checks)
./scripts/04-verify-api.sh
```

### Step 2 — Orchestrator Setup

```bash
cd orchestrator
pip install -r requirements.txt

# Verify SonarQube connectivity
python -m src.main summary
```

### Step 3 — Run Modes

```bash
# Mode 1: PR Pre-merge — ephemeral project scan + AI fix
python -m src.main pr-premerge \
  --repo owner/repo \
  --pr-number 42 \
  --project-dir /path/to/checkout \
  --cleanup

# Mode 2: Post-merge — scan main branch + generate fixes
python -m src.main post-merge \
  --project-dir /path/to/project

# Mode 3: Nightly batch — tech debt reduction
python -m src.main nightly-batch \
  --project-dir /path/to/project

# Utility: Show project quality summary
python -m src.main summary --project-key sonarqube-agent-test
```

### Cleanup

```bash
./scripts/99-teardown.sh          # stop containers (keep data)
./scripts/99-teardown.sh --clean  # stop + delete all data
```

## Environment Variables

The `.env` file is auto-generated by `02-setup-project.sh`.
You can also create it manually from `.env.example`:

| Variable | Default | Description |
|----------|---------|-------------|
| `SONAR_URL` | `http://localhost:9000` | SonarQube server URL |
| `SONAR_TOKEN` | *(generated)* | SonarQube user token |
| `SONAR_PROJECT_KEY` | `sonarqube-agent-test` | Main project key |

## Sample Project: Intentional Defects

The sample Java project contains **26 intentional defects** verified by SonarQube scan:

| File | Rule | Severity | Description | Count |
|------|------|----------|-------------|-------|
| `UserService.java` | S6437 | BLOCKER | Hardcoded password in `DB_PASSWORD` | 1 |
| `UserService.java` | S2095 | BLOCKER | Resource leak — Connection/Statement not closed | 2 |
| `UserService.java` | S2259 | MAJOR | NullPointerException risk on `result` | 1 |
| `UserService.java` | S1192 | CRITICAL | Duplicated string literal instead of constant | 1 |
| `UserService.java` | S2447 | CRITICAL | Returning `null` for `Boolean` type | 1 |
| `UserService.java` | S1186 | CRITICAL | Empty method body without explanation | 1 |
| `UserService.java` | S106 | MAJOR | `System.out` instead of logger | 1 |
| `UserService.java` | S1068 | MAJOR | Unused private fields | 2 |
| `UserService.java` | S1854 | MAJOR | Useless assignment to local variable | 2 |
| `UserService.java` | S1643 | MINOR | String concatenation in loop | 2 |
| `UserService.java` | S1481 | MINOR | Unused local variable | 1 |
| `OrderProcessor.java` | S2095 | BLOCKER | Resource leak — FileReader not closed | 1 |
| `OrderProcessor.java` | S3776 | CRITICAL | Cognitive complexity too high | 1 |
| `OrderProcessor.java` | S106 | MAJOR | `System.out` instead of logger | 2 |
| `OrderProcessor.java` | S1104 | MINOR | Public mutable fields | 2 |
| `OrderProcessor.java` | S2184 | MINOR | Integer division cast truncation | 1 |
| `SecurityUtils.java` | S2119 | CRITICAL | `new Random()` created each call | 1 |
| `SecurityUtils.java` | S1118 | MAJOR | Utility class missing private constructor | 1 |
| `SecurityUtils.java` | S107 | MAJOR | Method with too many parameters (8 > 7) | 1 |
| `SecurityUtils.java` | S1172 | MAJOR | Unused method parameters | 1 |

Test coverage is intentionally low (~5%) with only one test file.

## LLM Agent CLI Reference

Each agent requires **non-interactive (headless) mode** for Orchestrator integration.
Below are the verified CLI invocations:

### Claude Code

```bash
claude -p \
  --permission-mode acceptEdits \
  --allowedTools "Read,Write,Edit" \
  "Fix SonarQube issue S2095 in UserService.java ..." \
  < /dev/null
```

| Flag | Purpose |
|------|---------|
| `-p` / `--print` | Headless mode — print response and exit |
| `--permission-mode acceptEdits` | Auto-approve file edits without prompting |
| `--allowedTools "Read,Write,Edit"` | Restrict to file operation tools only |
| `< /dev/null` | **Required** — prevents 3-second stdin wait |

### Gemini CLI

```bash
gemini --yolo -p "Fix SonarQube issue S3776 in OrderProcessor.java ..."
```

| Flag | Purpose |
|------|---------|
| `-p` / `--prompt` | Headless mode — run prompt and exit |
| `--yolo` | Auto-approve all tool calls (file edits, shell commands) |

### Cursor Agent

```bash
agent -p --yolo --trust "Fix SonarQube issue S1104 in OrderProcessor.java ..."
```

| Flag | Purpose |
|------|---------|
| `-p` / `--print` | Headless mode — print response and exit |
| `--yolo` | Auto-approve all tool calls |
| `--trust` | Trust workspace without prompting |

## E2E Fix Validation Workflow

Validates the full cycle: SonarQube scan → LLM fix → re-scan → zero issues.

```bash
# 1. Copy sample project to isolated workspace
cp -r sample-java-project e2e-fix-test
cd e2e-fix-test

# 2. Run LLM agent to fix a specific file (example: Gemini CLI)
gemini --yolo -p "Read and fix all SonarQube issues in \
  src/main/java/com/example/agent/SecurityUtils.java: \
  S1118 (add private constructor), \
  S2119 (static final Random), \
  S107+S1172 (remove unused params). \
  Edit the file in place."

# 3. Rebuild
docker run --rm -v "$(pwd)":/project -w /project \
  maven:3.9-eclipse-temurin-17 mvn -q clean compile test-compile

# 4. Create ephemeral SonarQube project and scan
source .env
curl -sf -u admin:admin1 -X POST \
  "$SONAR_URL/api/projects/create?name=e2e-fix-test&project=e2e-fix-test"

docker run --rm --network host \
  -v "$(pwd)":/usr/src -w /usr/src \
  sonarsource/sonar-scanner-cli:latest \
  -Dsonar.projectKey=e2e-fix-test \
  -Dsonar.host.url=$SONAR_URL \
  -Dsonar.token=$SONAR_TOKEN \
  -Dsonar.java.binaries=target/classes \
  -Dsonar.java.libraries= \
  -Dsonar.sources=src/main/java \
  -Dsonar.tests=src/test/java

# 5. Verify issue reduction
sleep 5
curl -sf -H "Authorization: Bearer $SONAR_TOKEN" \
  "$SONAR_URL/api/issues/search?componentKeys=e2e-fix-test&statuses=OPEN,CONFIRMED&ps=1" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Issues: {d[\"total\"]}')"

# 6. Cleanup ephemeral project
curl -sf -u admin:admin1 -X POST \
  "$SONAR_URL/api/projects/delete?project=e2e-fix-test"
```

### Verified E2E Results (2026-03-21)

| Agent | Target File | Issues | Fixed | Residual |
|-------|-------------|--------|-------|----------|
| Gemini CLI `--yolo` | SecurityUtils.java | 4 | 3 | 1 |
| Cursor Agent `--yolo --trust` | UserService.java | 15 | 14 | 1 |
| Claude Code `acceptEdits` | Residual 2 issues | 2 | 2 | 0 |
| Gemini CLI `--yolo` | OrderProcessor.java | 7 | 7 | 0 |
| **Total** | **3 files** | **26** | **26** | **0** |

## Ephemeral Project Workflow

Script `06-scan-ephemeral.sh` demonstrates the PR pre-merge analysis pattern:

```
1. Create ephemeral project: myproject-pr-{number}
2. Run sonar-scanner against ephemeral key
3. Query issues from ephemeral project
4. Verify main project is unaffected
5. Delete ephemeral project
```

This validates that Community Edition can analyze PR code independently
without corrupting the main branch analysis.

## MCP Server Integration

After running `05-test-mcp-server.sh`, use the printed configuration to connect
your LLM tool (Claude Code, Cursor, Gemini CLI, Kiro CLI) to SonarQube
via the MCP Server.

## Running Tests

```bash
cd orchestrator
pip install -r requirements.txt

# Unit tests only (no SonarQube needed)
pytest tests/ -m "not integration"

# All tests including integration (requires running SonarQube with scanned project)
SONAR_URL=http://localhost:9000 SONAR_TOKEN=<token> pytest tests/ -v
```

## Ports

| Service | Port | URL |
|---------|------|-----|
| SonarQube | 9000 | http://localhost:9000 |
| PostgreSQL | 5433 | localhost:5433 |
