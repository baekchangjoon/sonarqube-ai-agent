**[한국어](README.md)** | English

# SonarQube AI Agent

LLM-agnostic AI Agent Orchestrator for automated SonarQube defect remediation.

## Documents

| Document | Description |
|----------|-------------|
| [Governance Blueprint](docs/sonarqube_ai_agent_governance_blueprint.en.md) | RACI matrix, ownership model, operational process |
| [Implementation Architecture](docs/ai_agent_implementation_architecture.en.md) | MCP Server, ephemeral project workflow, LLM abstraction |

## Installation

Choose one of three methods:

```bash
# A. pipx (recommended — one-line install, isolated venv)
pipx install "git+https://github.com/baekchangjoon/sonarqube-ai-agent#subdirectory=orchestrator"
sonar-ai-agent --help

# B. Docker image (no Python/Node needed — bundles orchestrator + Claude Code + docker/gh CLI)
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  -v "$PWD":/work -w /work -e SONAR_TOKEN \
  ghcr.io/baekchangjoon/sonarqube-ai-agent --help

# C. Source (for development/demo — see Quick Start below)
git clone https://github.com/baekchangjoon/sonarqube-ai-agent
cd sonarqube-ai-agent && pip install ./orchestrator
```

After installing via A/C you can use the `sonar-ai-agent` command, and inside
the repository you can use `python -m src.main` (the same CLI).

## Prerequisites

- Docker Engine 20.10+ ([install](https://docs.docker.com/engine/install/)) —
  runs the SonarQube, scanner, and build containers
- Python 3.9+ with `pip` (not needed with the Docker image)
- Node.js 18+ — for installing the LLM Agent CLI (not needed with the Docker image)
- `gh` CLI ([install](https://cli.github.com/)) — only when using the
  PR comment / Fix PR delivery features
- ~4 GB free RAM (SonarQube + PostgreSQL + scanner containers)
- Internet access (for pulling Docker images on first run)
- Linux/macOS (Windows: WSL2 recommended — shell-script based)

### LLM Agent CLI Tools (at least one required)

| Agent | Install | Auth | Verified Version |
|-------|---------|------|-----------------|
| [Claude Code](https://docs.anthropic.com/en/docs/claude-code) | `npm i -g @anthropic-ai/claude-code` | `claude` (interactive first run) | >= 2.1.x |
| [Gemini CLI](https://github.com/google-gemini/gemini-cli) | `npm i -g @google/gemini-cli` | `gemini` (interactive first run) | >= 0.30.x |
| [Cursor Agent](https://docs.cursor.com/agent) | Bundled with Cursor IDE | Cursor login | >= 2026.03.x |

## Architecture

```
sonarqube-ai-agent/
├── docs/
│   ├── ai_agent_implementation_architecture.md
│   └── sonarqube_ai_agent_governance_blueprint.md
│
├── action.yml ──────────── Reusable GitHub Action (CI integration)
├── Dockerfile ──────────── All-in-one image (orchestrator + LLM/docker/gh CLIs)
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
│   ├── config.yml                 Agents (fixer/judge), SonarQube, scanner
│   │                              (pr_mode), assessment strategy, modes
│   ├── pyproject.toml             pip/pipx packaging (`sonar-ai-agent` CLI)
│   ├── requirements.txt           Python dependencies
│   ├── pytest.ini                 Test runner config
│   ├── src/
│   │   ├── config.py              YAML config loader with ${ENV} resolution
│   │   ├── sonarqube_client.py    SonarQube REST API client + scanner runner
│   │   ├── github_client.py       PR comment / fix commit / Fix PR via gh CLI
│   │   ├── orchestrator.py        3-mode workflow engine
│   │   │                          (scan → assess → fix → verify → deliver)
│   │   ├── main.py                CLI entry point (4 subcommands)
│   │   └── agents/
│   │       ├── base.py            LLMAgent ABC + fix/triage/review prompts
│   │       ├── factory.py         Config-driven agent instantiation
│   │       ├── claude_code.py     Claude Code  (-p --permission-mode acceptEdits)
│   │       ├── gemini_cli.py      Gemini CLI   (--yolo -p)
│   │       ├── kiro_cli.py        AWS Kiro CLI (--no-interactive)
│   │       ├── bedrock_api.py     AWS Bedrock Converse (judge-oriented;
│   │       │                      no harness — cannot edit files)
│   │       └── pricing.py         Token price table for cost estimation
│   └── tests/
│       ├── test_config.py
│       ├── test_agents.py
│       ├── test_sonarqube_client.py   Unit + Integration
│       └── test_orchestrator.py
│
├── demo/false-positive-triage/ ── Conference demo: rules vs LLM (0/3 vs 3/3)
├── benchmark/fp-corpus/ ── Labeled false-positive corpus for judge evaluation
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
pip install ./orchestrator

# Verify SonarQube connectivity (run inside orchestrator/ where config.yml lives)
cd orchestrator
sonar-ai-agent summary
```

### Step 3 — Run Modes

```bash
# Mode 1: PR Pre-merge — PR scan + AI fix + verification + PR comment
# (--pr-branch / --pr-base are used by scanner.pr_mode: native)
python -m src.main pr-premerge \
  --repo owner/repo \
  --pr-number 42 \
  --project-dir /path/to/checkout \
  --pr-branch feature/my-change \
  --pr-base main \
  --cleanup

# Mode 2: Post-merge — scan main, fix new issues, optional Fix PR
python -m src.main post-merge \
  --project-dir /path/to/project

# Mode 3: Nightly batch — tech debt reduction, optional Fix PR
python -m src.main nightly-batch \
  --project-dir /path/to/project

# Utility: Show project quality summary
python -m src.main summary --project-key sonarqube-agent-test
```

Each mode prints a JSON result:

```json
{
  "mode": "pr_premerge",
  "project_key": "my-project",
  "issues_found": 3,
  "issues_skipped_as_fp": 1,
  "fixes_attempted": 2,
  "fixes_verified": 2,
  "quality_gate": "ERROR",
  "llm_input_tokens": 345131,
  "llm_output_tokens": 1726,
  "llm_cost_usd": 0.4118
}
```

### Cleanup

```bash
./scripts/99-teardown.sh          # stop containers (keep data)
./scripts/99-teardown.sh --clean  # stop + delete all data
```

## Applying to your own project

The Quick Start above demonstrates the bundled sample project. To wire this
into a real project:

### 1. Write a config

If you use an existing SonarQube server, you don't need docker-compose/scripts.
Copy and edit [`orchestrator/config-remote.yml`](orchestrator/config-remote.yml)
(remote server + fixer/judge split + triage example):

```yaml
sonarqube:
  url: "https://sonar.mycompany.com"
  token: "${SONAR_TOKEN}"          # .env or environment variable
  main_project_key: "my-project"
scanner:
  pr_mode: "ephemeral"             # ephemeral if you have no branch/PR plugin
  rebuild_command: "mvn -q clean compile"
  # Change the analysis paths if you don't use the Maven standard layout (empty value = omit the flag)
  sources: "src/main/java"
  tests: "src/test/java"           # "" if there is no test root
  java_binaries: "target/classes"
assessment:
  strategy: "triage_review"        # operational default — triage → fix → review (3 passes)
```

```bash
sonar-ai-agent --config my-config.yml pr-premerge \
  --repo owner/repo --pr-number 42 --project-dir . --cleanup
```

> Constraint: the scanner defaults to a Maven-standard-layout Java project.
> For a different layout, adjust the `scanner.*` paths above. Because compiled
> classes must exist before the scan (`sonar.java.binaries`), make sure
> `rebuild_command` matches.

### 2. Use in CI (GitHub Action)

```yaml
jobs:
  sonar-ai:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - uses: baekchangjoon/sonarqube-ai-agent@v1
        with:
          mode: pr-premerge
          config: .sonar-ai/config.yml
          pr-number: ${{ github.event.pull_request.number }}
        env:
          SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}  # or Bedrock OIDC
```

LLM auth uses `ANTHROPIC_API_KEY` or AWS Bedrock
(`CLAUDE_CODE_USE_BEDROCK=1` + OIDC AssumeRole).
For a real-world example see [`fp-triage-benchmark.yml`](.github/workflows/fp-triage-benchmark.yml).

### 3. Run via Docker

```bash
docker run --rm \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v "$PWD":/work -w /work \
  -e SONAR_TOKEN -e CLAUDE_CODE_USE_BEDROCK=1 -e AWS_REGION \
  ghcr.io/baekchangjoon/sonarqube-ai-agent \
  --config config.yml post-merge --project-dir /work
```

The docker socket mount is required because the scanner/rebuild run on the
host's docker.

## Fix Pipeline

All three modes share the same core pipeline:

```
scan → issues → FP assessment → LLM fix (in place) → rebuild + re-scan → verified fixes → deliver
```

1. **Scan** — sonar-scanner via Docker. Mode 1 supports two PR analysis
   strategies (`scanner.pr_mode`):
   - `ephemeral` — temp project per PR (CE workaround, no plugin needed)
   - `native` — `sonar.pullrequest.*` params (requires the community
     branch/PR plugin); the PR slot shows only issues new vs. the base
2. **FP assessment** (`assessment.strategy`) — mitigates static-analysis
   false positives before code is touched:
   - `none` — fix every issue
   - `triage` — a read-only LLM call judges each issue first;
     FALSE_POSITIVE → skip + report with confidence
   - `review` — the fix prompt has an FP escape hatch; afterwards an
     **independent** LLM call reviews the applied diff (or the FP claim)
     and provides the confidence, avoiding self-assessment bias. The fix
     reviewer receives the pre-fix code (scan snapshot), the diff, the
     fixer's stated rationale, and the rule's how-to-fix doc
     (`include_rule_docs`).
     Unparseable/failed judgments fall back to "fix it" (the safe default).
   - `triage_review` (operational default) — three passes: the judge
     triages FPs first (FP→skip), the fixer edits **true positives
     only**, then the judge reviews each outcome (the applied fix or the
     FP skip). Decoupling the FP decision from the fixer preserves recall
     better than `review` while adding the review safety net — best
     recall and precision in the benchmark (also the highest per-issue
     cost). See [`benchmark/results`](benchmark/results) for the
     comparison.

   Judgment calls need no file-editing harness, so they can run on a
   different backend/model than the fixer (`agent.judge_type` /
   `agent.judge_model`) — e.g. fixer = Sonnet via Claude Code, judge =
   Opus 4.6 via Bedrock Converse. When SonarQube cannot serve an
   issue's source (files new in a PR), the judge prompt falls back to
   the local checkout.
3. **Fix** — the agent CLI edits files in the working dir directly
   (`claude -p --permission-mode acceptEdits`, `gemini --yolo`, ...).
   Issues are processed sequentially so later fixes see earlier ones.
4. **Verify** — rebuild (`scanner.rebuild_command`), re-scan, then count
   a fix as verified **only if its issue key is no longer open** on the
   server. LLM self-reporting is never trusted for verification.
5. **Deliver** — verified fixes only:
   - Mode 1: PR comment (`delivery: comment`) and/or a new commit pushed
     to the PR branch (`push_fix_commit: true`)
   - Mode 2/3: a Fix PR (`create_fix_pr: true` + `fix_pr.repo`)

Reports, commit messages, and Fix PR bodies include per-fix and per-skip
confidences, labelled `LLM-assessed` (uncalibrated — treat as a triage
priority signal, not a probability). Reports and the result JSON also
carry an **LLM Usage** breakdown — tokens and cost per role (fixer /
judge) and a run total. Claude Code reports its own cost
(`--output-format json`); Bedrock cost is estimated from Converse usage
via `agents/pricing.py` (unknown models report tokens only).

## Configuration Reference (config.yml)

| Key | Values | Description |
|-----|--------|-------------|
| `agent.type` | `claude-code` `gemini-cli` `kiro-cli` `bedrock-api` | Fix agent backend (`bedrock-api` has no harness — judgment/suggestion only) |
| `agent.judge_type` / `judge_model` | agent type / model id | Separate backend/model for judgment calls (FP triage, fix review); unset = fix agent |
| `sonarqube.url` / `token` | `${ENV}` supported | SonarQube server + auth |
| `sonarqube.main_project_key` | string | Main branch project |
| `scanner.pr_mode` | `ephemeral` / `native` | PR analysis strategy (Mode 1) |
| `scanner.rebuild_command` | shell string | Run in project dir before each scan (empty = skip) |
| `scanner.sources` / `tests` / `java_binaries` / `java_test_binaries` | path string | Analysis paths (default = Maven standard layout; empty value omits the flag) |
| `assessment.strategy` | `none` / `triage` / `review` / `triage_review` | False-positive screening (see Fix Pipeline; operational default `triage_review`) |
| `assessment.context_lines` | int (default 5) | Source lines around the issue line in judgment/fix prompts |
| `assessment.full_file_max_lines` | int (default 150) | Files at most this many lines are injected whole instead of as a window (`0` = always window) |
| `assessment.include_rule_docs` | bool (default false) | Inject SonarQube rule docs — how-to-fix for the fixer, Exceptions for the judge |
| `modes.pr_premerge.delivery` | `comment` / `log` | Post analysis report to the PR or log only |
| `modes.pr_premerge.push_fix_commit` | bool | Push verified fixes as a commit to the PR branch |
| `modes.*.max_issues_per_run` | int | Cap per run, `0` = unlimited |
| `modes.post_merge.create_fix_pr` | bool + `fix_pr.repo`/`base` | Open a Fix PR with verified fixes |
| `modes.nightly_batch.create_fix_pr` | bool + `fix_pr.repo`/`base` | Same for nightly batch |
| `modes.nightly_batch.severity_filter` | list | Issue severities to select |

Git prerequisites: `push_fix_commit` needs `--project-dir` to be a git
checkout of the PR branch; `create_fix_pr` needs a git clone with an
authenticated `origin` and the `gh` CLI.

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
  --output-format json \
  --permission-mode acceptEdits \
  --allowedTools "Read,Write,Edit" \
  "Fix SonarQube issue S2095 in UserService.java ..." \
  < /dev/null
```

| Flag | Purpose |
|------|---------|
| `-p` / `--print` | Headless mode — print response and exit |
| `--output-format json` | JSON envelope with `result`, `usage`, `total_cost_usd` |
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
#    (admin/admin = initial default — if you changed it at first web login, use that value)
source .env
curl -sf -u admin:admin -X POST \
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
curl -sf -u admin:admin -X POST \
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
