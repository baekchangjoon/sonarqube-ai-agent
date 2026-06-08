한국어 | **[English](README.en.md)**

# SonarQube AI Agent

SonarQube 결함 자동 수정을 위한 LLM-agnostic AI Agent Orchestrator.

## 문서

| 문서 | 설명 |
|----------|-------------|
| [거버넌스 청사진](docs/sonarqube_ai_agent_governance_blueprint.md) | RACI 매트릭스, 소유권 모델, 운영 프로세스 |
| [구현 아키텍처](docs/ai_agent_implementation_architecture.md) | MCP Server, 임시(ephemeral) 프로젝트 워크플로, LLM 추상화 |

## 설치

세 가지 방법 중 하나를 선택한다:

```bash
# A. pipx (권장 — 한 줄 설치, 격리된 venv)
pipx install "git+https://github.com/baekchangjoon/sonarqube-ai-agent#subdirectory=orchestrator"
sonar-ai-agent --help

# B. Docker 이미지 (Python/Node 불필요 — orchestrator + Claude Code + docker/gh CLI 동봉)
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  -v "$PWD":/work -w /work -e SONAR_TOKEN \
  ghcr.io/baekchangjoon/sonarqube-ai-agent --help

# C. 소스 (개발·데모용 — 아래 빠른 시작)
git clone https://github.com/baekchangjoon/sonarqube-ai-agent
cd sonarqube-ai-agent && pip install ./orchestrator
```

A/C 설치 후에는 `sonar-ai-agent` 명령을, 저장소 안에서는
`python -m src.main`(동일 CLI)을 사용할 수 있다.

## 사전 요구사항

- Docker Engine 20.10+ ([설치](https://docs.docker.com/engine/install/)) —
  SonarQube·스캐너·빌드 컨테이너 실행
- `pip`가 포함된 Python 3.9+ (Docker 이미지 사용 시 불필요)
- Node.js 18+ — LLM Agent CLI 설치용 (Docker 이미지 사용 시 불필요)
- `gh` CLI ([설치](https://cli.github.com/)) — PR 코멘트/Fix PR 전달 기능
  사용 시에만
- 여유 RAM 약 4 GB (SonarQube + PostgreSQL + 스캐너 컨테이너)
- 인터넷 접속 (최초 실행 시 Docker 이미지 pull)
- Linux/macOS (Windows는 WSL2 권장 — 셸 스크립트 기반)

### LLM Agent CLI 도구 (최소 하나 필요)

| Agent | 설치 | 인증 | 검증된 버전 |
|-------|---------|------|-----------------|
| [Claude Code](https://docs.anthropic.com/en/docs/claude-code) | `npm i -g @anthropic-ai/claude-code` | `claude` (최초 1회 대화형 실행) | >= 2.1.x |
| [Gemini CLI](https://github.com/google-gemini/gemini-cli) | `npm i -g @google/gemini-cli` | `gemini` (최초 1회 대화형 실행) | >= 0.30.x |
| [Cursor Agent](https://docs.cursor.com/agent) | Cursor IDE에 번들 | Cursor 로그인 | >= 2026.03.x |

## 아키텍처

```
sonarqube-ai-agent/
├── docs/
│   ├── ai_agent_implementation_architecture.md
│   └── sonarqube_ai_agent_governance_blueprint.md
│
├── action.yml ──────────── 재사용 가능한 GitHub Action (CI 통합)
├── Dockerfile ──────────── 올인원 이미지 (orchestrator + LLM/docker/gh CLI)
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
│   ├── pyproject.toml             pip/pipx 패키징 (`sonar-ai-agent` CLI)
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

## 빠른 시작

### Step 1 — 인프라

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

### Step 2 — Orchestrator 설정

```bash
pip install ./orchestrator

# Verify SonarQube connectivity (run inside orchestrator/ where config.yml lives)
cd orchestrator
sonar-ai-agent summary
```

### Step 3 — 실행 모드

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

각 모드는 JSON 결과를 출력한다:

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

### 정리

```bash
./scripts/99-teardown.sh          # stop containers (keep data)
./scripts/99-teardown.sh --clean  # stop + delete all data
```

## 내 프로젝트에 적용하기

위 빠른 시작은 동봉된 샘플 프로젝트 시연이다. 실제 프로젝트에 붙이려면:

### 1. config 작성

기존 SonarQube 서버를 쓴다면 docker-compose/scripts는 필요 없다.
[`orchestrator/config-remote.yml`](orchestrator/config-remote.yml)
(원격 서버 + fixer/judge 분리 + triage 예시)을 복사해 수정한다:

```yaml
sonarqube:
  url: "https://sonar.mycompany.com"
  token: "${SONAR_TOKEN}"          # .env 또는 환경변수
  main_project_key: "my-project"
scanner:
  pr_mode: "ephemeral"             # 플러그인 없으면 ephemeral
  rebuild_command: "mvn -q clean compile"
  # Maven 표준 레이아웃이 아니면 분석 경로를 바꾼다 (빈 값 = 플래그 생략)
  sources: "src/main/java"
  tests: "src/test/java"           # 테스트 루트가 없으면 ""
  java_binaries: "target/classes"
assessment:
  strategy: "triage_review"        # 운영 기본값 — 판정→수정→리뷰 3패스
```

```bash
sonar-ai-agent --config my-config.yml pr-premerge \
  --repo owner/repo --pr-number 42 --project-dir . --cleanup
```

> 제약: 스캐너 기본값은 Maven 표준 레이아웃 Java 프로젝트다. 다른
> 레이아웃은 위 `scanner.*` 경로를 조정한다. 스캔 전 컴파일된 클래스가
> 있어야 하므로(`sonar.java.binaries`) `rebuild_command`를 꼭 맞춘다.

### 2. CI에서 사용 (GitHub Action)

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
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}  # 또는 Bedrock OIDC
```

LLM 인증은 `ANTHROPIC_API_KEY` 또는 AWS Bedrock
(`CLAUDE_CODE_USE_BEDROCK=1` + OIDC AssumeRole)을 사용한다.
실사용 예시는 [`fp-triage-benchmark.yml`](.github/workflows/fp-triage-benchmark.yml) 참조.

### 3. Docker로 사용

```bash
docker run --rm \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v "$PWD":/work -w /work \
  -e SONAR_TOKEN -e CLAUDE_CODE_USE_BEDROCK=1 -e AWS_REGION \
  ghcr.io/baekchangjoon/sonarqube-ai-agent \
  --config config.yml post-merge --project-dir /work
```

스캐너·리빌드가 호스트 docker로 실행되므로 docker 소켓 마운트가 필요하다.

## 수정 파이프라인

세 모드 모두 동일한 핵심 파이프라인을 공유한다:

```
scan → issues → FP assessment → LLM fix (in place) → rebuild + re-scan → verified fixes → deliver
```

1. **스캔(Scan)** — Docker를 통한 sonar-scanner. Mode 1은 두 가지 PR 분석
   전략을 지원한다 (`scanner.pr_mode`):
   - `ephemeral` — PR마다 임시 프로젝트 (CE 우회책, 플러그인 불필요)
   - `native` — `sonar.pullrequest.*` 파라미터 (community
     branch/PR 플러그인 필요); PR 슬롯에는 base 대비 신규 이슈만 표시
2. **FP 평가(FP assessment)** (`assessment.strategy`) — 코드를 건드리기
   전에 정적 분석 오탐을 완화한다:
   - `none` — 모든 이슈를 수정
   - `triage` — read-only LLM 호출이 각 이슈를 먼저 판정;
     FALSE_POSITIVE → skip + confidence와 함께 리포트
   - `review` — 수정 프롬프트에 FP escape hatch가 있고, 이후
     **독립적인** LLM 호출이 적용된 diff(또는 FP 주장)를 리뷰하여
     confidence를 제공한다 — 자기 평가 편향을 회피. 수정 리뷰어는
     수정 전 코드(스캔 스냅샷), diff, 수정 에이전트의 근거, 그리고
     룰의 how-to-fix 문서(`include_rule_docs`)를 함께 받는다.
     파싱 불가/실패한 판정은 "수정한다"(안전 기본값)로 fallback한다.
   - `triage_review` (운영 기본값) — 3패스: judge가 먼저 FP를
     판정(FP→skip), fixer가 **true positive만** 수정, 이후 judge가
     각 결과(적용된 수정 또는 FP skip)를 리뷰한다. FP 판정 주체를
     fixer에서 분리해 `review`보다 재현율을 보존하면서 검토 안전망을
     더한다 — 벤치마크에서 재현율·정밀도 모두 최고(이슈당 비용도 최고).
     비교는 [`benchmark/results`](benchmark/results) 참고.

   판정(judgment) 호출은 파일 편집 harness가 필요 없으므로, 수정
   에이전트(fixer)와 다른 백엔드/모델에서 실행할 수 있다
   (`agent.judge_type` / `agent.judge_model`) — 예: fixer = Claude Code의
   Sonnet, judge = Bedrock Converse의 Opus 4.6. SonarQube가 이슈의
   소스를 제공하지 못할 때(PR에서 새로 추가된 파일), 판정 프롬프트는
   로컬 checkout으로 fallback한다.
3. **수정(Fix)** — 에이전트 CLI가 작업 디렉터리의 파일을 직접 편집한다
   (`claude -p --permission-mode acceptEdits`, `gemini --yolo`, ...).
   이슈는 순차적으로 처리되어 이후 수정이 이전 수정을 본다.
4. **검증(Verify)** — rebuild(`scanner.rebuild_command`) 후 re-scan하고,
   해당 이슈 키가 서버에서 **더 이상 open이 아닐 때에만** 수정을 검증된
   것으로 집계한다. 검증에 LLM의 자기 보고는 절대 신뢰하지 않는다.
5. **전달(Deliver)** — 검증된 수정만:
   - Mode 1: PR comment(`delivery: comment`) 및/또는 PR 브랜치에 push되는
     새 커밋(`push_fix_commit: true`)
   - Mode 2/3: Fix PR(`create_fix_pr: true` + `fix_pr.repo`)

리포트, 커밋 메시지, Fix PR 본문에는 수정별·skip별 confidence가 포함되며
`LLM-assessed`로 라벨링된다(보정되지 않음 — 확률이 아니라 트리아지(판정)
우선순위 신호로 다룰 것). 리포트와 결과 JSON에는 **LLM Usage** 분석도
담긴다 — 역할별(fixer / judge) 토큰과 비용, 그리고 실행 총계. Claude Code는
자신의 비용을 보고하고(`--output-format json`), Bedrock 비용은
`agents/pricing.py`를 통해 Converse usage로부터 추정된다(미지의 모델은
토큰만 보고).

## 설정 레퍼런스 (config.yml)

| 키 | 값 | 설명 |
|-----|--------|-------------|
| `agent.type` | `claude-code` `gemini-cli` `kiro-cli` `bedrock-api` | 수정 에이전트 백엔드 (`bedrock-api`는 harness가 없음 — 판정/제안 전용) |
| `agent.judge_type` / `judge_model` | agent type / model id | 판정 호출(FP 트리아지, 수정 리뷰)용 별도 백엔드/모델; 미설정 시 수정 에이전트 |
| `sonarqube.url` / `token` | `${ENV}` 지원 | SonarQube 서버 + 인증 |
| `sonarqube.main_project_key` | string | 메인 브랜치 프로젝트 |
| `scanner.pr_mode` | `ephemeral` / `native` | PR 분석 전략 (Mode 1) |
| `scanner.rebuild_command` | shell string | 각 스캔 전 프로젝트 디렉터리에서 실행 (빈 값 = skip) |
| `scanner.sources` / `tests` / `java_binaries` / `java_test_binaries` | path string | 분석 경로 (기본 = Maven 표준 레이아웃; 빈 값 = 해당 플래그 생략) |
| `assessment.strategy` | `none` / `triage` / `review` / `triage_review` | 오탐 스크리닝 (수정 파이프라인 참고; 운영 기본값 `triage_review`) |
| `assessment.context_lines` | int (기본 5) | 판정/수정 프롬프트에 넣는 이슈 라인 주변 소스 줄 수 |
| `assessment.full_file_max_lines` | int (기본 150) | 이 줄 수 이하 파일은 윈도우 대신 전체 주입 (`0` = 항상 윈도우) |
| `assessment.include_rule_docs` | bool (기본 false) | SonarQube 룰 문서 주입 — fixer엔 how-to-fix, judge엔 Exceptions |
| `modes.pr_premerge.delivery` | `comment` / `log` | 분석 리포트를 PR에 게시하거나 log만 |
| `modes.pr_premerge.push_fix_commit` | bool | 검증된 수정을 커밋으로 PR 브랜치에 push |
| `modes.*.max_issues_per_run` | int | 실행당 상한, `0` = 무제한 |
| `modes.post_merge.create_fix_pr` | bool + `fix_pr.repo`/`base` | 검증된 수정으로 Fix PR 생성 |
| `modes.nightly_batch.create_fix_pr` | bool + `fix_pr.repo`/`base` | nightly batch에 대해 동일 |
| `modes.nightly_batch.severity_filter` | list | 선택할 이슈 심각도 |

Git 사전 요구사항: `push_fix_commit`은 `--project-dir`가 PR 브랜치의 git
checkout이어야 하고, `create_fix_pr`은 인증된 `origin`을 가진 git clone과
`gh` CLI가 필요하다.

## 환경 변수

`.env` 파일은 `02-setup-project.sh`가 자동 생성한다.
`.env.example`로부터 수동으로 만들 수도 있다:

| 변수 | 기본값 | 설명 |
|----------|---------|-------------|
| `SONAR_URL` | `http://localhost:9000` | SonarQube 서버 URL |
| `SONAR_TOKEN` | *(생성됨)* | SonarQube 사용자 토큰 |
| `SONAR_PROJECT_KEY` | `sonarqube-agent-test` | 메인 프로젝트 키 |

## 샘플 프로젝트: 의도된 결함

샘플 Java 프로젝트에는 SonarQube 스캔으로 검증된 **26개의 의도된 결함**이 들어 있다:

| 파일 | 룰 | 심각도 | 설명 | 개수 |
|------|------|----------|-------------|-------|
| `UserService.java` | S6437 | BLOCKER | `DB_PASSWORD`에 하드코딩된 비밀번호 | 1 |
| `UserService.java` | S2095 | BLOCKER | 리소스 누수 — Connection/Statement 미종료 | 2 |
| `UserService.java` | S2259 | MAJOR | `result`에 대한 NullPointerException 위험 | 1 |
| `UserService.java` | S1192 | CRITICAL | 상수 대신 중복된 문자열 리터럴 | 1 |
| `UserService.java` | S2447 | CRITICAL | `Boolean` 타입에 `null` 반환 | 1 |
| `UserService.java` | S1186 | CRITICAL | 설명 없는 빈 메서드 본문 | 1 |
| `UserService.java` | S106 | MAJOR | logger 대신 `System.out` | 1 |
| `UserService.java` | S1068 | MAJOR | 미사용 private 필드 | 2 |
| `UserService.java` | S1854 | MAJOR | 지역 변수에 대한 무의미한 대입 | 2 |
| `UserService.java` | S1643 | MINOR | 루프 내 문자열 연결 | 2 |
| `UserService.java` | S1481 | MINOR | 미사용 지역 변수 | 1 |
| `OrderProcessor.java` | S2095 | BLOCKER | 리소스 누수 — FileReader 미종료 | 1 |
| `OrderProcessor.java` | S3776 | CRITICAL | 인지 복잡도 과다 | 1 |
| `OrderProcessor.java` | S106 | MAJOR | logger 대신 `System.out` | 2 |
| `OrderProcessor.java` | S1104 | MINOR | public mutable 필드 | 2 |
| `OrderProcessor.java` | S2184 | MINOR | 정수 나눗셈 cast 절삭 | 1 |
| `SecurityUtils.java` | S2119 | CRITICAL | 호출마다 생성되는 `new Random()` | 1 |
| `SecurityUtils.java` | S1118 | MAJOR | private 생성자가 없는 유틸리티 클래스 | 1 |
| `SecurityUtils.java` | S107 | MAJOR | 파라미터가 너무 많은 메서드 (8 > 7) | 1 |
| `SecurityUtils.java` | S1172 | MAJOR | 미사용 메서드 파라미터 | 1 |

테스트 커버리지는 테스트 파일 하나만으로 의도적으로 낮다(~5%).

## LLM Agent CLI 레퍼런스

각 에이전트는 Orchestrator 통합을 위해 **비대화형(headless) 모드**가 필요하다.
아래는 검증된 CLI 호출이다:

### Claude Code

```bash
claude -p \
  --output-format json \
  --permission-mode acceptEdits \
  --allowedTools "Read,Write,Edit" \
  "Fix SonarQube issue S2095 in UserService.java ..." \
  < /dev/null
```

| 플래그 | 용도 |
|------|---------|
| `-p` / `--print` | Headless 모드 — 응답 출력 후 종료 |
| `--output-format json` | `result`, `usage`, `total_cost_usd`를 담은 JSON envelope |
| `--permission-mode acceptEdits` | 프롬프트 없이 파일 편집 자동 승인 |
| `--allowedTools "Read,Write,Edit"` | 파일 작업 도구로만 제한 |
| `< /dev/null` | **필수** — 3초 stdin 대기 방지 |

### Gemini CLI

```bash
gemini --yolo -p "Fix SonarQube issue S3776 in OrderProcessor.java ..."
```

| 플래그 | 용도 |
|------|---------|
| `-p` / `--prompt` | Headless 모드 — 프롬프트 실행 후 종료 |
| `--yolo` | 모든 도구 호출 자동 승인 (파일 편집, 셸 명령) |

### Cursor Agent

```bash
agent -p --yolo --trust "Fix SonarQube issue S1104 in OrderProcessor.java ..."
```

| 플래그 | 용도 |
|------|---------|
| `-p` / `--print` | Headless 모드 — 응답 출력 후 종료 |
| `--yolo` | 모든 도구 호출 자동 승인 |
| `--trust` | 프롬프트 없이 workspace 신뢰 |

## E2E 수정 검증 워크플로

전체 사이클을 검증한다: SonarQube scan → LLM fix → re-scan → 이슈 0개.

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
#    (admin/admin = 초기 기본값 — 첫 웹 로그인에서 변경했다면 그 값을 사용)
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

### 검증된 E2E 결과 (2026-03-21)

| Agent | 대상 파일 | 이슈 | 수정 | 잔여 |
|-------|-------------|--------|-------|----------|
| Gemini CLI `--yolo` | SecurityUtils.java | 4 | 3 | 1 |
| Cursor Agent `--yolo --trust` | UserService.java | 15 | 14 | 1 |
| Claude Code `acceptEdits` | 잔여 2개 이슈 | 2 | 2 | 0 |
| Gemini CLI `--yolo` | OrderProcessor.java | 7 | 7 | 0 |
| **합계** | **3개 파일** | **26** | **26** | **0** |

## 임시(ephemeral) 프로젝트 워크플로

`06-scan-ephemeral.sh` 스크립트는 PR pre-merge 분석 패턴을 시연한다:

```
1. Create ephemeral project: myproject-pr-{number}
2. Run sonar-scanner against ephemeral key
3. Query issues from ephemeral project
4. Verify main project is unaffected
5. Delete ephemeral project
```

이는 Community Edition이 메인 브랜치 분석을 오염시키지 않고 PR 코드를
독립적으로 분석할 수 있음을 검증한다.

## MCP Server 통합

`05-test-mcp-server.sh` 실행 후, 출력된 설정을 사용해 LLM 도구(Claude Code,
Cursor, Gemini CLI, Kiro CLI)를 MCP Server를 통해 SonarQube에 연결한다.

## 테스트 실행

```bash
cd orchestrator
pip install -r requirements.txt

# Unit tests only (no SonarQube needed)
pytest tests/ -m "not integration"

# All tests including integration (requires running SonarQube with scanned project)
SONAR_URL=http://localhost:9000 SONAR_TOKEN=<token> pytest tests/ -v
```

## 포트

| 서비스 | 포트 | URL |
|---------|------|-----|
| SonarQube | 9000 | http://localhost:9000 |
| PostgreSQL | 5433 | localhost:5433 |
