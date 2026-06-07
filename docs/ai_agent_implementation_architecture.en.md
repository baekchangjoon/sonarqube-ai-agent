**[한국어](ai_agent_implementation_architecture.md)** | English

# AI Agent Implementation Architecture
## SonarQube Community Edition + MCP Server + LLM-Agnostic Agent Design

---

## 1. Constraints

| Item | Status | Impact |
|------|------|------|
| SonarQube Edition | **Community Build** | PR analysis, branch analysis, AI CodeFix unavailable ([CE feature scope](https://www.sonarsource.com/open-source-editions/sonarqube-community-edition/)) |
| Codebase | Java 1.x → **Java 17** AI modernization complete | A contractor is developing on top of the AI-converted code |
| Development owner | **Outsourced contractor** | Requires code ownership and quality contract terms |
| Org-recommended AI tool | **AWS Kiro** | Default tool, but must be swappable for other LLMs |
| CI environment Kiro CLI | **Authentication uncertain** | Alternative path needed for CI automation |

### Design Decisions

| Decision | Choice (at design time) | Implementation result (2026-06-07) |
|------|------|------|
| Whether to use an MCP Server | Use | **Changed: direct REST calls** — the orchestrator's triage/verification loop is simpler and easier to test with deterministic REST. MCP is retained for conversational agent integration (§4.3, `05-test-mcp-server.sh`) |
| LLM tool swappability | Required | **Implemented + extended**: 4 backends + role separation (separate routing for fixer/judge agents) |
| PR-level analysis | Ephemeral project key approach | **Implemented + extended**: `scanner.pr_mode = ephemeral \| native` — native `sonar.pullrequest.*` can be used on servers with the branch/PR plugin installed |

### Design-vs-Implementation Change Summary (v3.0, 2026-06-07)

Everything through v2.0 of this document was up-front design; the following were confirmed/added during subsequent implementation.
See [`orchestrator/`](../orchestrator) and the [README](../README.md) for detailed code.

| Area | Design (v2.0) | Implementation (v3.0) |
|------|------------|------------|
| SonarQube integration | Via MCP Server | **Direct REST** (`sonarqube_client.py`) — MCP for conversational use only |
| Fix verification | Planned for Phase 2 | **Implemented**: rebuild → rescan → confirm issue key closed (do not trust LLM self-reporting) |
| Result delivery | One of, per phase | **All implemented**: PR comment (Mode 1) + commit push to PR branch (Mode 1) + Fix PR (Mode 2/3) |
| False positive (FP) handling | Not in design | **`assessment.strategy`**: `triage` (pre-judgment) / `review` (fix + independent post-review) — reports verdict, reason, and confidence |
| Agent role separation | Single agent | **Separate fixer/judge** (`agent.judge_type/judge_model`) — judging needs no harness, so a single Bedrock Converse call is possible |
| Bedrock backend | invoke_model (Claude only) | **Converse API** (any model: Claude/Nova) + usage collection |
| Cost metering | Not in design | Per-run **LLM Usage** (tokens/cost, by role) — included in result JSON and report |
| FP benchmark | Not in design | [`benchmark/fp-corpus`](../benchmark/fp-corpus) — 22 cases/32 issues, all ground-truth FP, CE firing verified |
| Test code generation | Generated alongside fix | **Out of scope** — the fix prompt is limited to "in-place fix of only that issue" (the FixResult.test_code field remains but is unused) |

---

## 2. Key Technical Findings

### 2.1 Is PR branch analysis possible on the Community Edition?

**Yes, but it requires care.**

`sonar-scanner` analyzes the code in the current directory. If you check out a PR branch and run it, it does indeed analyze that code. **However**, the Community Edition has constraints on storing results:

```
┌─────────────────────────────────────────────────────────────┐
│  How sonar-scanner works in the Community Edition            │
│                                                             │
│  sonar-scanner는 "현재 디렉토리의 파일"을 분석한다.           │
│  Git 브랜치와 무관하게, 파일 시스템에 있는 코드를 읽는다.     │
│                                                             │
│  ✓ PR 브랜치 checkout 후 실행 → 분석 자체는 정상 동작        │
│  ✗ 하지만 결과는 프로젝트의 "main branch" 슬롯에 덮어씀      │
│  ✗ 여러 PR이 동시에 돌면 서로 결과를 덮어씀 (Race Condition) │
│  ✗ New Code Period 계산이 깨짐                               │
│                                                             │
│  근거:                                                       │
│  - "Community Edition does not support multi-branch          │
│     analysis. All analyses are merged into a single          │
│     main branch."                                            │
│    https://stackoverflow.com/questions/69803754              │
│  - "sonar.branch.name parameter is not allowed               │
│     in Community Edition."                                   │
│    https://stackoverflow.com/questions/72536550              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Solution: Ephemeral Project Key

Official Community Edition workaround ([StackOverflow reference](https://stackoverflow.com/questions/72536550/master-and-develop-branch-analysis-in-sonarqube-community-edition)):

**If you use a unique ephemeral project key per PR, you can analyze the PR code independently without polluting the main branch analysis.**

```bash
# main 브랜치 분석 (상시)
sonar-scanner \
  -Dsonar.projectKey=myproject \
  -Dsonar.projectName="My Project"

# PR 브랜치 분석 (PR마다 임시 프로젝트 생성)
sonar-scanner \
  -Dsonar.projectKey=myproject-pr-142 \
  -Dsonar.projectName="My Project [PR #142]"
```

```
┌─────────────────────────────────────────────────────────────┐
│  SonarQube Community Edition 내부 상태                        │
│                                                             │
│  프로젝트 목록:                                              │
│  ┌──────────────────────┬──────────┬─────────────────────┐  │
│  │ Project Key           │ 용도     │ 수명               │  │
│  ├──────────────────────┼──────────┼─────────────────────┤  │
│  │ myproject             │ main     │ 영구               │  │
│  │ myproject-pr-142      │ PR #142  │ PR Close 시 삭제   │  │
│  │ myproject-pr-143      │ PR #143  │ PR Close 시 삭제   │  │
│  │ myproject-pr-144      │ PR #144  │ PR Close 시 삭제   │  │
│  └──────────────────────┴──────────┴─────────────────────┘  │
│                                                             │
│  ✓ 각 PR이 독립된 프로젝트로 분석됨 → Race Condition 없음    │
│  ✓ main 프로젝트의 New Code Period 오염 없음                 │
│  ✓ PR Close 후 임시 프로젝트 자동 삭제 (API 호출)            │
│                                                             │
│  삭제 API:                                                   │
│  POST /api/projects/delete?project=myproject-pr-142          │
│  https://next.sonarqube.com/sonarqube/web_api/api/projects   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

Pros and cons of this approach:

| Pros | Cons |
|------|------|
| Uses the Community Edition stock | Per-PR overhead of creating/deleting an ephemeral project |
| No pollution of main analysis | Quality Profile must also be applied to ephemeral projects |
| Multiple PRs can be analyzed concurrently | Ephemeral project cleanup logic must be implemented |
| No plugin installation required | Ephemeral projects appear on the dashboard (until cleaned up) |

### 2.3 SonarQube MCP Server

The SonarQube MCP Server is the **standard bridge** between an AI Agent and SonarQube.

[Community Build official compatibility doc](https://docs.sonarsource.com/sonarqube-community-build/extension-guide/sonarqube-mcp-server) |
[MCP Server product page](https://www.sonarsource.com/products/sonarqube/mcp-server/) |
[Docker Hub](https://hub.docker.com/mcp/server/sonarqube/overview)

```
┌─────────────────────────────────────────────────────────────┐
│  MCP Server의 역할: 통역사 (Translator)                       │
│                                                             │
│  AI Agent ←──(MCP Protocol)──→ MCP Server ←──(REST)──→ SQ  │
│                                                             │
│  AI Agent가 자연어로:              MCP Server가 자동 변환:    │
│  "PR #142의 이슈 보여줘"     →    GET /api/issues/search    │
│                                   ?componentKeys=...pr-142  │
│                                   &statuses=OPEN            │
│                                                             │
│  "이 코드 분석해줘"          →    analyze_code_snippet       │
│                                   (fileContent, language)   │
│                                                             │
│  제공 도구 (Tools):                                          │
│  ┌────────────────────────────┬─────────────────────────┐   │
│  │ analyze_code_snippet       │ 코드 조각 즉시 분석     │   │
│  │ analyze_file_list          │ 파일 목록 분석          │   │
│  │ search_sonar_issues        │ 이슈 검색              │   │
│  │ search_duplicated_files    │ 코드 중복 검색          │   │
│  └────────────────────────────┴─────────────────────────┘   │
│  https://docs.sonarsource.com/sonarqube-mcp-server/tools    │
│                                                             │
│  핵심 가치:                                                  │
│  1. LLM 도구 교체 시 연동 코드 변경 불필요 (표준 프로토콜)    │
│  2. AI Agent가 SonarQube를 네이티브 도구로 사용              │
│  3. Community Build 공식 지원                                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

> **Implementation note (v3.0)**: The MCP Server concept above remains valid as-is
> for the scenario where "a human queries SonarQube while conversing with an LLM
> CLI." However, **the orchestrator's automated pipeline was implemented to call
> REST directly without going through MCP** — because the triage/verification loop
> consists of deterministic calls with fixed inputs and outputs, simplicity and
> testability mattered more than the flexibility the MCP layer provides. LLM
> swappability is handled by the `agents/` abstraction layer (LLMAgent ABC +
> factory) instead of MCP.

### 2.4 LLM Tool Swappability

MCP (Model Context Protocol) is an **LLM-Agnostic standard protocol**. Using the SonarQube MCP Server, swapping the LLM tool is possible with a configuration change only.

[List of MCP clients officially supported by SonarSource](https://www.sonarsource.com/products/sonarqube/mcp-server/):

```
┌─────────────────────────────────────────────────────────────┐
│  MCP Protocol = USB-C 같은 표준 인터페이스                    │
│                                                             │
│  ┌──────────────┐                                           │
│  │  Kiro CLI    │──┐                                        │
│  └──────────────┘  │                                        │
│  ┌──────────────┐  │                   ┌────────────────┐   │
│  │  Claude Code │──┼── MCP Protocol ──→│ SonarQube MCP  │   │
│  └──────────────┘  │  (동일 인터페이스) │ Server         │   │
│  ┌──────────────┐  │                   └───────┬────────┘   │
│  │  Gemini CLI  │──┤                           │            │
│  └──────────────┘  │                           ▼            │
│  ┌──────────────┐  │                   ┌────────────────┐   │
│  │  Cursor      │──┤                   │  SonarQube CE  │   │
│  └──────────────┘  │                   └────────────────┘   │
│  ┌──────────────┐  │                                        │
│  │  Codex CLI   │──┘                                        │
│  └──────────────┘                                           │
│                                                             │
│  어떤 LLM CLI든 MCP 호환이면 설정만 바꾸면 즉시 교체 가능    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Finalized Architecture

### 3.1 Overall Structure Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│                      확정 아키텍처: 전체 구조                         │
│                                                                     │
│  ┌─ 트리거 ──────────────────────────────────────────────────────┐  │
│  │                                                               │  │
│  │  Mode 1: PR 생성 시 (Pre-merge)                               │  │
│  │  외주 개발자 → PR Open → CI Webhook → Orchestrator 호출       │  │
│  │                                                               │  │
│  │  Mode 2: main 머지 후 (Post-merge)                            │  │
│  │  PR 머지 → main CI → SonarQube Webhook → Orchestrator 호출   │  │
│  │                                                               │  │
│  │  Mode 3: 야간 배치 (Tech Debt)                                │  │
│  │  Cron 02:00 → Orchestrator 실행                               │  │
│  │                                                               │  │
│  └───────────────────────────┬───────────────────────────────────┘  │
│                              │                                      │
│                              ▼                                      │
│  ┌─ Agent Server (Dedicated VM/Container) ───────────────────────┐  │
│  │                                                               │  │
│  │  ┌─────────────────────────────────────────────────────────┐  │  │
│  │  │                  Orchestrator (Python)                   │  │  │
│  │  │                                                         │  │  │
│  │  │  1. 트리거 수신 (Webhook / Cron)                        │  │  │
│  │  │  2. PR 브랜치 checkout + 임시 프로젝트 키 생성          │  │  │
│  │  │  3. sonar-scanner 실행                                  │  │  │
│  │  │  4. LLM Agent 호출 (추상화 인터페이스)                  │  │  │
│  │  │  5. Sandbox 검증 (sonar-scanner 재실행)                 │  │  │
│  │  │  6. Fix PR 생성 또는 PR 코멘트                          │  │  │
│  │  │  7. 임시 프로젝트 정리                                  │  │  │
│  │  │                                                         │  │  │
│  │  │  ┌───────────────────────────────────────────────────┐  │  │  │
│  │  │  │         LLM Agent Interface (Abstract)            │  │  │  │
│  │  │  │                                                   │  │  │  │
│  │  │  │  config.yml → agent.type 설정으로 교체:            │  │  │  │
│  │  │  │  ┌─────────────┐ ┌─────────────┐                 │  │  │  │
│  │  │  │  │ Kiro CLI    │ │ Claude Code │                 │  │  │  │
│  │  │  │  │ (조직 기본) │ │ (대안 1)    │                 │  │  │  │
│  │  │  │  └─────────────┘ └─────────────┘                 │  │  │  │
│  │  │  │  ┌─────────────┐ ┌─────────────┐                 │  │  │  │
│  │  │  │  │ Gemini CLI  │ │ Bedrock API │                 │  │  │  │
│  │  │  │  │ (대안 2)    │ │ (Fallback)  │                 │  │  │  │
│  │  │  │  └─────────────┘ └─────────────┘                 │  │  │  │
│  │  │  └───────────────────────────────────────────────────┘  │  │  │
│  │  └─────────────────────────────────────────────────────────┘  │  │
│  │                              │                                │  │
│  │                        MCP Protocol                           │  │
│  │                              │                                │  │
│  │  ┌──────────────────────────┴───────────────────────────────┐ │  │
│  │  │              SonarQube MCP Server (Docker)                │ │  │
│  │  │                                                          │ │  │
│  │  │  - analyze_code_snippet: 코드 조각 분석                  │ │  │
│  │  │  - search_sonar_issues: 이슈 검색/조회                   │ │  │
│  │  │  - search_duplicated_files: 중복 검색                    │ │  │
│  │  │                                                          │ │  │
│  │  │  https://docs.sonarsource.com/sonarqube-mcp-server/tools │ │  │
│  │  └──────────────────────────┬───────────────────────────────┘ │  │
│  │                             │ REST API                        │  │
│  └─────────────────────────────┼────────────────────────────────┘  │
│                                │                                    │
│                                ▼                                    │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                SonarQube Community Build                      │  │
│  │                                                              │  │
│  │  프로젝트:                                                    │  │
│  │  ├── myproject          (main 브랜치, 영구)                   │  │
│  │  ├── myproject-pr-142   (PR #142, 임시)                      │  │
│  │  └── myproject-pr-143   (PR #143, 임시)                      │  │
│  │                                                              │  │
│  │  https://docs.sonarsource.com/sonarqube-community-build/     │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

> **Implementation note (v3.0)**: In the diagram above, the "MCP Protocol /
> SonarQube MCP Server" segment was replaced in the final implementation by
> **Orchestrator → SonarQube REST direct calls**. In addition, a **judge role**
> was added below the LLM Agent Interface, so that FP triage and fix review can be
> routed to a different backend/model than the fixer (e.g., fix = Sonnet via Claude
> Code, judge = Opus via Bedrock Converse).

### 3.2 The Three Execution Modes in Detail

#### Mode 1: PR Pre-merge (core mode)

**At the moment the contractor opens a PR — before merge — detect defects and propose fixes.**

```
 외주 개발자: PR #142 Open
         │
         ▼
 CI (GitHub Actions):
 ┌────────────────────────────────────────────────────────┐
 │  on: pull_request                                      │
 │                                                        │
 │  1. PR 브랜치 checkout                                  │
 │     git checkout pr-branch                             │
 │                                                        │
 │  2. sonar-scanner 실행 (임시 프로젝트 키)               │
 │     sonar-scanner \                                    │
 │       -Dsonar.projectKey=myproject-pr-142 \            │
 │       -Dsonar.projectName="My Project [PR #142]"       │
 │                                                        │
 │     → PR 브랜치 코드가 분석됨                           │
 │     → main 프로젝트(myproject) 오염 없음               │
 │                                                        │
 │  3. Orchestrator Webhook 호출                           │
 │     POST /webhook/pr-analyzed                          │
 │     { project: "myproject-pr-142", pr: 142 }           │
 │                                                        │
 └────────────────────────────────────────────────────────┘
         │
         ▼
 Orchestrator:
 ┌────────────────────────────────────────────────────────┐
 │                                                        │
 │  1. 임시 프로젝트의 이슈 조회                           │
 │     (MCP Server 경유)                                  │
 │     "myproject-pr-142의 OPEN 이슈 보여줘"              │
 │                                                        │
 │  2. 이슈 발견 시 → LLM Agent 호출                      │
 │     (추상 인터페이스, config에 따라 Kiro/Claude/etc.)   │
 │                                                        │
 │  3. LLM Agent: MCP Server로 이슈 상세 조회             │
 │     → 수정 코드 생성                                    │
 │     → 테스트 코드 생성                                  │
 │                                                        │
 │  4. Sandbox 검증                                       │
 │     수정 코드 적용 → sonar-scanner 재실행              │
 │     → 새 이슈 도입 여부 확인                           │
 │     → 실패 시 수정 폐기                                │
 │                                                        │
 │  5. 결과 전달 (택 1)                                   │
 │     A) PR에 리뷰 코멘트로 수정 제안 (Phase 1)          │
 │     B) PR 브랜치에 Fix 커밋 push (Phase 2)             │
 │     C) 별도 Fix PR 생성 (Phase 3)                     │
 │                                                        │
 │  6. 임시 프로젝트 정리 (PR Close 시)                   │
 │     DELETE /api/projects/delete?project=myproject-pr-142│
 │                                                        │
 └────────────────────────────────────────────────────────┘
         │
         ▼
 외주 개발자: AI 수정 제안 리뷰 → 반영 → 머지
```

> **Implementation note (v3.0)**: Step 4 (Sandbox verification) above was
> implemented as "rebuild → rerun sonar-scanner → confirm the original issue key is
> closed," and for delivery in step 5, A (PR comment) and B (Fix commit push to PR
> branch) are implemented for Mode 1, and C (separate Fix PR) for Mode 2/3, each
> toggled by config. In addition, an **FP triage step** was added between steps 2
> and 3 — issues the judge rules as false positives skip the fix and are reported
> with reason and confidence.

#### Mode 2: Post-merge (supplementary mode)

```
 PR #142 머지 → main 브랜치
         │
         ▼
 CI: sonar-scanner 실행 (원본 프로젝트 키)
     -Dsonar.projectKey=myproject
         │
         ▼
 SonarQube: main 브랜치 분석 → Quality Gate 평가
         │
         ├── Gate Pass → 종료
         │
         ├── Gate Fail → SonarQube Webhook 발송
         │
         ▼
 Orchestrator: 신규 이슈 수집 → LLM Agent → Fix PR 생성
         │
         ▼
 개발자: Fix PR 리뷰 → 머지
```

It serves as a **safety net** that catches issues missed in Mode 1. As Mode 1 works well, the issues caught here gradually decrease.

#### Mode 3: Nightly Batch (technical debt reduction)

```
 Cron: 매일 02:00 AM
         │
         ▼
 Orchestrator:
   1. myproject(main) 이슈 중 기존 기술 부채 조회
      (sinceLeakPeriod=false, 즉 Old Code 이슈)
   2. 우선순위: BLOCKER > CRITICAL > MAJOR
   3. 상위 N건 선택 (설정 가능, 기본 10건/일)
   4. LLM Agent: 수정 + 테스트 생성
   5. Sandbox 검증
   6. Fix PR 생성 (라벨: "tech-debt-reduction")
```

It **gradually eliminates the legacy technical debt** in the code converted via AI modernization.

---

## 4. Orchestrator Design: LLM Abstraction Interface

### 4.1 Overall Class Structure

```python
"""
SonarQube AI Agent Orchestrator

핵심 설계 원칙:
1. LLM Agent는 추상 인터페이스로 교체 가능 (수정/판정 역할 분리 포함)
2. SonarQube 연동은 REST 직접 호출 (sonarqube_client.py)
3. Architecture of Trust: AI 제안 → 재스캔 검증 → Human 리뷰
   (https://www.sonarsource.com/blog/join-the-sonarqube-remediation-agent-beta/)
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum


class AgentType(Enum):
    KIRO_CLI = "kiro-cli"
    CLAUDE_CODE = "claude-code"
    GEMINI_CLI = "gemini-cli"
    BEDROCK_API = "bedrock-api"


@dataclass
class SonarIssue:
    key: str
    rule: str
    severity: str
    component: str
    line: int
    message: str
    issue_type: str
    effort: str = ""
    file_path: str = ""


@dataclass
class FixResult:
    success: bool
    issue_key: str
    file_path: str
    original_code: str
    fixed_code: str
    test_code: str
    explanation: str = ""
    errors: list = field(default_factory=list)
    fix_confidence: float = None  # LLM-assessed (review strategy: independent reviewer's value)


@dataclass
class TriageResult:
    """False positive verdict result (FP triage / fix review)."""
    verdict: str       # TRUE_POSITIVE | FALSE_POSITIVE (review: assessment string)
    confidence: float  # 0.0-1.0, LLM self-reported (uncalibrated)
    reason: str = ""


# ─────────────────────────────────────────────
# Layer 1: LLM Agent Abstract Interface
# ─────────────────────────────────────────────

class LLMAgent(ABC):
    """
    LLM 도구 교체를 위한 추상 인터페이스.
    이슈 컨텍스트는 Orchestrator가 프롬프트에 직접 주입한다
    (SonarQube 소스 조회 실패 시 로컬 체크아웃 폴백).
    """

    @abstractmethod
    def generate_fix(self, prompt: str, working_dir: str) -> str:
        """수정 프롬프트 실행 — 에이전틱 CLI는 파일을 직접 편집."""

    def generate_triage(self, prompt: str, working_dir: str) -> str:
        """읽기 전용 판정 호출 (기본: generate_fix 위임).
        Claude Code는 --allowedTools Read로, Bedrock은 단발 Converse로."""

    def get_usage(self) -> dict:
        """누적 토큰/비용 — {"input_tokens", "output_tokens", "cost_usd"}."""

    @abstractmethod
    def supports_mcp(self) -> bool: ...

    @abstractmethod
    def name(self) -> str: ...

    # 프롬프트 빌더 4종: build_fix_prompt(in-place 수정 + confidence JSON),
    # build_triage_prompt(TP/FP 판정), build_fix_or_escape_prompt(D안),
    # build_fix_review_prompt / build_fp_review_prompt(독립 리뷰)


class KiroCLIAgent(LLMAgent):
    """
    AWS Kiro CLI 구현체.
    https://kiro.dev/docs/cli/reference/cli-commands
    """

    def generate_fix(self, prompt: str, working_dir: str) -> str:
        # subprocess: kiro-cli chat --no-interactive --trust-all-tools
        #   --agent sonarqube-fixer "{prompt}"
        pass

    def supports_mcp(self) -> bool:
        return True

    def name(self) -> str:
        return "Kiro CLI"


class ClaudeCodeAgent(LLMAgent):
    """
    Anthropic Claude Code 구현체.
    Flags: -p (headless), --permission-mode acceptEdits,
           stdin=DEVNULL (3s stdin 대기 방지).
    Reference: https://docs.anthropic.com/en/docs/claude-code
    """

    def generate_fix(self, prompt: str, working_dir: str) -> str:
        # subprocess: claude -p --permission-mode acceptEdits
        #   --allowedTools "Read,Write,Edit" "{prompt}"
        #   stdin=subprocess.DEVNULL
        pass

    def supports_mcp(self) -> bool:
        return True

    def name(self) -> str:
        return "Claude Code"


class GeminiCLIAgent(LLMAgent):
    """
    Google Gemini CLI 구현체.
    Flags: --yolo (auto-approve tool calls), -p (headless prompt).
    Reference: https://github.com/google-gemini/gemini-cli
    """

    def generate_fix(self, prompt: str, working_dir: str) -> str:
        # subprocess: gemini --yolo -p "{prompt}"
        pass

    def supports_mcp(self) -> bool:
        return True

    def name(self) -> str:
        return "Gemini CLI"


class BedrockAPIAgent(LLMAgent):
    """
    AWS Bedrock Converse API 호출 (모델 불문: Claude/Nova/...).
    하네스 없음 → 파일 편집 불가, 판정(judge) 역할에 적합.
    Converse 응답의 usage로 토큰을 누적하고 단가표(pricing.py)로
    비용을 추정한다 (미등록 모델은 토큰만 보고).
    """

    def generate_fix(self, prompt: str, working_dir: str) -> str:
        # boto3.client('bedrock-runtime').converse(modelId=..., messages=...)
        pass

    def supports_mcp(self) -> bool:
        return False

    def name(self) -> str:
        return "Bedrock Converse"


# ─────────────────────────────────────────────
# Layer 2: Agent Factory
# ─────────────────────────────────────────────

class AgentFactory:
    """
    설정 파일(config.yml)의 agent.type에 따라
    적절한 LLM Agent 구현체를 반환한다.
    _AGENT_BUILDERS 딕셔너리로 AgentType → 생성 람다를 매핑.
    """

    @staticmethod
    def create(config: AgentConfig) -> LLMAgent:
        agent_type = AgentType(config.type)
        # _AGENT_BUILDERS[agent_type](config) 호출
        # config.kiro / config.claude / config.bedrock 등의
        # 에이전트별 세부 설정을 각 구현체 생성자에 전달
        pass


# ─────────────────────────────────────────────
# Layer 3: Orchestrator
# ─────────────────────────────────────────────

class SonarQubeOrchestrator:
    """
    전체 워크플로우를 조율하는 메인 오케스트레이터.

    Workflow:
    1. 트리거 수신 (PR Webhook / SonarQube Webhook / Cron)
    2. sonar-scanner 실행 (임시 프로젝트 키 또는 main)
    3. REST API / MCP 경유로 이슈 수집
    4. LLM Agent로 수정 코드 + 테스트 생성
    5. PR 코멘트 생성 또는 Fix PR 생성
    6. 임시 프로젝트 정리

    Note: Sandbox 재검증(sonar-scanner 재실행 후 이슈 감소 확인)은
    Phase 2 고도화 시 구현 예정.
    """

    def __init__(self, config: AppConfig):
        self._config = config
        self._sonar = SonarQubeClient(config.sonarqube)
        self._agent = AgentFactory.create(config.agent)

    def handle_pr_premerge(self, repo: str, pr_number: int,
                           project_dir: str) -> ModeResult:
        """Mode 1: PR Pre-merge — Ephemeral Project 스캔."""
        ephemeral_key = self._ephemeral_key(pr_number)
        # 1. Ephemeral project 생성
        # 2. sonar-scanner 실행 (project_dir)
        # 3. 이슈 수집 + Quality Gate 확인
        # 4. LLM Agent로 fix 생성
        # 5. PR 코멘트 생성
        pass

    def handle_post_merge(self, project_dir: str = None) -> ModeResult:
        """Mode 2: Post-merge — main 브랜치 New Code 분석."""
        # 1. (선택) main branch sonar-scanner 실행
        # 2. sinceLeakPeriod=true 로 new issues 수집
        # 3. LLM Agent로 fix 생성
        pass

    def handle_nightly_batch(self, project_dir: str = None) -> ModeResult:
        """Mode 3: Nightly Batch — severity 기반 기술 부채 감소."""
        # 1. severity 필터링된 open issues 수집
        # 2. max_issues_per_run 제한
        # 3. LLM Agent로 fix 생성
        pass

    def cleanup_pr_project(self, pr_number: int) -> bool:
        """PR Close 시 임시 프로젝트 삭제."""
        ephemeral_key = self._ephemeral_key(pr_number)
        return self._sonar.delete_project(ephemeral_key)

    def get_project_summary(self, project_key: str = None) -> dict:
        """프로젝트 품질 메트릭 요약을 반환한다."""
        pass

    def _run_fixes(self, issues: list,
                   working_dir: str) -> tuple[list, list]:
        # _generate_single_fix(issue, working_dir) 반복 호출
        # (all_fixes, verified_fixes) 튜플 반환
        pass

    def _generate_single_fix(self, issue, working_dir: str) -> FixResult:
        # 1. _get_source_context(issue) — 소스 라인 조회
        # 2. agent.build_fix_prompt(...) — 프롬프트 생성
        # 3. _invoke_agent(...) — LLM 호출 및 FixResult 반환
        pass

    def _log_pr_comment(self, issues, ephemeral_key, verified):
        # GitHubClient.format_issues_comment() → PR 코멘트 생성
        # Phase 1: 코멘트 생성만 (로그 출력)
        # Phase 2: gh pr comment 호출
        pass

    # Sandbox 재검증(sonar-scanner 재실행 후 이슈 감소 확인)과
    # Fix PR 자동 생성은 Phase 2 고도화 시 구현 예정.
```

### 4.2 Configuration File

```yaml
# config.yml (v3.0 — 구현 기준)

agent:
  # 수정(fixer) 백엔드: kiro-cli | claude-code | gemini-cli | bedrock-api
  type: "claude-code"
  # 판정(judge) 역할 — FP 트리아지·수정 리뷰. 하네스 불필요라
  # fixer와 다른 백엔드/모델 가능. 미설정 시 fixer와 동일.
  judge_type: "bedrock-api"
  judge_model: "global.anthropic.claude-opus-4-6-v1"

  kiro:
    agent_name: "sonarqube-fixer"
    trust_all_tools: true
  claude:
    allowed_tools: "Read,Write,Edit"
    model: "sonnet"          # CLAUDE_CODE_USE_BEDROCK=1이면 Bedrock 프로파일 ID
  gemini: {}
  bedrock:
    model_id: "global.anthropic.claude-sonnet-4-6"
    region: "ap-northeast-2"

sonarqube:
  url: "${SONAR_URL}"
  token: "${SONAR_TOKEN}"
  main_project_key: "myproject"

scanner:
  ephemeral_key_pattern: "{project}-pr-{pr_number}"
  # "ephemeral": CE 워크어라운드 / "native": branch·PR plugin의 sonar.pullrequest.*
  pr_mode: "ephemeral"
  # 검증 재스캔 전 빌드 명령 (이슈 키 폐쇄 확인의 전제)
  rebuild_command: >-
    docker run --rm -v "$(pwd)":/project -w /project
    maven:3.9-eclipse-temurin-17 mvn -q clean compile test-compile

# 오탐 대응 전략: none | triage(사전 판정) | review(수정+독립 사후 리뷰)
assessment:
  strategy: "triage"

modes:
  pr_premerge:
    enabled: true
    delivery: "comment"      # comment | log
    max_issues_per_run: 0
    push_fix_commit: true    # 검증된 수정을 PR 브랜치에 커밋 push
  post_merge:
    enabled: true
    create_fix_pr: true
    fix_pr: { repo: "", base: "main" }
  nightly_batch:
    enabled: true
    max_issues_per_run: 10
    severity_filter: [BLOCKER, CRITICAL, MAJOR]
    create_fix_pr: true
    fix_pr: { repo: "", base: "main" }
```

### 4.3 Per-LLM MCP Server Configuration

Concrete configuration for integrating the SonarQube MCP Server in each LLM tool:

#### Kiro CLI

```json
// .kiro/agents/sonarqube-fixer.json
{
  "name": "sonarqube-fixer",
  "mcpServers": {
    "sonarqube": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-e", "SONARQUBE_URL=${SONARQUBE_URL}",
        "-e", "SONARQUBE_TOKEN=${SONAR_TOKEN}",
        "mcp/sonarqube"
      ]
    }
  }
}
```

[Kiro CLI Agent configuration doc](https://kiro.dev/docs/cli/reference/cli-commands/#kiro-cli-agent)

#### Claude Code

```json
// .mcp.json (프로젝트 루트)
{
  "mcpServers": {
    "sonarqube": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-e", "SONARQUBE_URL=${SONARQUBE_URL}",
        "-e", "SONARQUBE_TOKEN=${SONAR_TOKEN}",
        "mcp/sonarqube"
      ]
    }
  }
}
```

[Claude Code + SonarQube MCP integration doc](https://www.sonarsource.com/blog/claude-code-sonarqube-mcp-building-an-autonomous-code-review-workflow/)

#### Gemini CLI

```json
// .gemini/settings.json
{
  "mcpServers": {
    "sonarqube": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-e", "SONARQUBE_URL=${SONARQUBE_URL}",
        "-e", "SONARQUBE_TOKEN=${SONAR_TOKEN}",
        "mcp/sonarqube"
      ]
    }
  }
}
```

[Gemini CLI + SonarQube integration page](https://www.sonarsource.com/integrations/google/gemini-cli/)

**Note that the MCP Server Docker image is identical — only the location and format of the configuration file differ.**

---

## 5. CI Pipeline Design

### 5.1 PR Pre-merge Pipeline (GitHub Actions)

```yaml
# .github/workflows/sonar-pr-analysis.yml
name: SonarQube PR Analysis + AI Fix

on:
  pull_request:
    types: [opened, synchronize, reopened]

jobs:
  sonar-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Run SonarQube Scanner (Ephemeral Project)
        env:
          SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}
          SONAR_HOST_URL: ${{ secrets.SONAR_HOST_URL }}
        run: |
          sonar-scanner \
            -Dsonar.projectKey=${{ github.event.repository.name }}-pr-${{ github.event.number }} \
            -Dsonar.projectName="${{ github.event.repository.name }} [PR #${{ github.event.number }}]" \
            -Dsonar.sources=src/main/java \
            -Dsonar.tests=src/test/java \
            -Dsonar.java.binaries=target/classes

      - name: Notify Orchestrator
        run: |
          curl -X POST ${{ secrets.ORCHESTRATOR_URL }}/webhook/pr-analyzed \
            -H "Content-Type: application/json" \
            -d '{
              "project_key": "${{ github.event.repository.name }}-pr-${{ github.event.number }}",
              "pr_number": ${{ github.event.number }},
              "repo": "${{ github.event.repository.full_name }}",
              "branch": "${{ github.head_ref }}"
            }'
```

### 5.2 Post-merge Pipeline

```yaml
# .github/workflows/sonar-main-analysis.yml
name: SonarQube Main Analysis

on:
  push:
    branches: [main]

jobs:
  sonar-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Run SonarQube Scanner (Main Project)
        env:
          SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}
          SONAR_HOST_URL: ${{ secrets.SONAR_HOST_URL }}
        run: |
          sonar-scanner \
            -Dsonar.projectKey=${{ github.event.repository.name }} \
            -Dsonar.projectName="${{ github.event.repository.name }}"
        # SonarQube Webhook이 자동으로 Orchestrator에 알림
```

### 5.3 Ephemeral Project Cleanup on PR Close

```yaml
# .github/workflows/sonar-pr-cleanup.yml
name: Cleanup Ephemeral SonarQube Project

on:
  pull_request:
    types: [closed]

jobs:
  cleanup:
    runs-on: ubuntu-latest
    steps:
      - name: Delete Ephemeral Project
        env:
          SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}
          SONAR_HOST_URL: ${{ secrets.SONAR_HOST_URL }}
        run: |
          curl -X POST \
            "$SONAR_HOST_URL/api/projects/delete" \
            -H "Authorization: Bearer $SONAR_TOKEN" \
            -d "project=${{ github.event.repository.name }}-pr-${{ github.event.number }}"
```

---

## 6. SonarQube New Code Period Configuration

Set the AI modernization code as the **baseline**, and make only the contractor's new code subject to the Quality Gate.

[New Code configuration doc](https://docs.sonarsource.com/sonarqube-server/project-administration/configuring-new-code-calculation)

```
 설정 경로:
 Project Settings > New Code > "Specific analysis"
 → AI 모더나이제이션 완료 시점의 분석을 선택

 효과:
 ┌─────────────────────────────────┬──────────────────────┐
 │ 코드 레이어                      │ Quality Gate 적용    │
 ├─────────────────────────────────┼──────────────────────┤
 │ AI 전환 코드 (Java 17)           │ Old Code → 적용 안됨│
 │ 외주사 신규 코드                  │ New Code → 적용됨   │
 │ AI Agent 수정 코드                │ New Code → 적용됨   │
 └─────────────────────────────────┴──────────────────────┘
```

---

## 7. Outsourcing Contract Quality Clauses

[SonarSource outsourcing risk management](https://sonarsource.com/solutions/reduce-outsourcing-software-development-risk) |
[Pangea.ai 2026 outsourcing contract guide](https://pangea.ai/resources/software-outsourcing-contracts-what-to-include-and-how-to-negotiate) |
[GenieAI contract clauses guide](https://www.genieai.co/blog/essential-contract-clauses-for-custom-software-development-outsourcing-agreements)

```
┌─────────────────────────────────────────────────────────────┐
│  외주 계약 품질 SLA                                          │
│                                                             │
│  1. Quality Gate 통과 의무                                   │
│     "납품 코드는 SonarQube Quality Gate Pass 필수"           │
│                                                             │
│  2. 구체적 기준값                                            │
│     │ New Bugs: 0 │ New Vulnerabilities: 0 │                │
│     │ Coverage ≥ 80% │ Duplicated Lines ≤ 3% │              │
│     │ Reliability: A │ Security: A │                        │
│                                                             │
│  3. AI Fix 대응 SLA                                         │
│     "AI Agent의 Fix 제안에 5영업일 이내 응답"                │
│                                                             │
│  4. 하자보증 90일                                            │
│     "Blocker/Critical 이슈 무상 수정"                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 8. Defect Ownership by Code Layer

[Enterprise AI Coding Policy 2026](https://aidevdayindia.org/blogs/best-ai-mode-checker/enterprise-ai-coding-policy-template-2026.html) |
[SonarQube Clean as You Code](https://docs.sonarsource.com/sonarqube-server/latest/core-concepts/clean-as-you-code/introduction/) |
[IBM ScarfBench](https://www.ibm.com/new/announcements/scarfbench-a-public-benchmark-for-java-framework-migration)

| Code layer | Producer | Defect owner | Basis |
|-------------|----------|-----------|------|
| Original legacy (Java 1.x) | Past dev team | N/A (deprecated) | - |
| AI modernization code (Java 17) | AI Agent | Client (internal) | Attributed after acceptance test passes |
| Contractor's new development code | Contractor | **Contractor** (within warranty period) | Contract terms |
| AI Agent auto-fix code | AI Agent | **Whoever merges** (Golden Rule) | [Enterprise AI Policy 2026](https://aidevdayindia.org/blogs/best-ai-mode-checker/enterprise-ai-coding-policy-template-2026.html) |

---

## 9. Phased Implementation Roadmap

> **Progress (2026-06-07)**: Phase 0 complete (but MCP integration verification is
> valid for conversational use only — the pipeline uses REST directly), Phase 1
> complete, Phase 2 complete (verification loop, Fix PR, Nightly, all LLM
> implementations) plus extensions not in the design (FP triage, judge separation,
> cost metering, FP corpus) added. Phase 3 (project-wide expansion, dashboard, SLA
> integration) not started.

### Phase 0: Infrastructure Verification (1-2 weeks)

```
검증 항목:
1. Kiro CLI + IAM Identity Center 인증 테스트
   → 성공: Kiro CLI 채택
   → 실패: Claude Code 또는 Gemini CLI로 전환
   (https://kiro.dev/docs/cli/authentication/)

2. SonarQube MCP Server + LLM 도구 연동 테스트
   → Docker 기동 → MCP 도구 호출 확인
   (https://docs.sonarsource.com/sonarqube-mcp-server/quickstart-guide)

3. 임시 프로젝트 키 방식 검증
   → PR 브랜치 checkout → sonar-scanner 실행
   → 별도 프로젝트로 등록 확인
   → 삭제 API 동작 확인

4. config.yml의 agent.type 교체 테스트
   → Kiro → Claude Code → Gemini CLI 순환 테스트
```

### Phase 1: MVP — PR Comment Mode (2-4 weeks)

```
구현:
1. Orchestrator 코어 (Python)
   - PR Webhook 수신
   - sonar-scanner 임시 프로젝트 실행
   - LLM Agent 추상 인터페이스 + 1개 구현체
   - GitHub PR 코멘트 생성

2. CI 파이프라인 3종
   - PR Analysis (sonar-pr-analysis.yml)
   - Main Analysis (sonar-main-analysis.yml)
   - PR Cleanup (sonar-pr-cleanup.yml)

3. SonarQube 설정
   - New Code Period: Specific Analysis
   - Webhook → Orchestrator
   - Quality Gate: Sonar Way

산출물: PR에 결함 목록 + AI 수정 제안 코멘트
```

### Phase 2: Fix PR Automation (2-4 weeks)

```
추가:
1. Sandbox 검증 파이프라인
2. Fix PR 자동 생성
3. Nightly Batch (Mode 3)
4. 2번째 LLM 구현체 추가

산출물: 자동 Fix PR + 야간 기술 부채 감소
```

### Phase 3: Scale-out and Optimization (4-8 weeks)

```
추가:
1. 전체 프로젝트 확대
2. 메트릭 대시보드
3. 외주 계약 SLA 연동
4. 3~4번째 LLM 구현체 추가
```

---

## 10. Optimistic / Pessimistic Scenarios

### Optimistic

- Detect **80%+** of defects ahead of merge in Mode 1
- Contractor Quality Gate pass rate **70% → 95%**
- Free LLM tool swapping → enables cost/performance optimization
- Fully bypass Community Edition constraints via the ephemeral project approach

### Pessimistic

- SonarQube server load when many ephemeral projects are created ([CE resource limits](https://docs.sonarsource.com/sonarqube-community-build/))
- Dashboard pollution when ephemeral project cleanup fails
- Possibility that the MCP Server restricts some tools on the Community Edition (search_dependency_risks is Enterprise-only — [Tools doc](https://docs.sonarsource.com/sonarqube-mcp-server/tools))
- Presidio report: 66% of organizations are experimenting with AI Agents but **only 11% successfully deployed to production** ([reference](https://www.presidio.com/blogs/agentic-application-modernization-reality/))

---

## 11. References

| # | Source | URL |
|---|------|-----|
| 1 | SonarQube CE — MCP Server compatibility | https://docs.sonarsource.com/sonarqube-community-build/extension-guide/sonarqube-mcp-server |
| 2 | SonarQube MCP Server — Tools | https://docs.sonarsource.com/sonarqube-mcp-server/tools |
| 3 | SonarQube MCP Server — Quickstart | https://docs.sonarsource.com/sonarqube-mcp-server/quickstart-guide |
| 4 | SonarQube MCP Server — Docker | https://hub.docker.com/mcp/server/sonarqube/overview |
| 5 | SonarSource — MCP Server product | https://www.sonarsource.com/products/sonarqube/mcp-server/ |
| 6 | SonarSource — Claude Code + MCP | https://www.sonarsource.com/blog/claude-code-sonarqube-mcp-building-an-autonomous-code-review-workflow/ |
| 7 | SonarSource — PR-to-green | https://www.sonarsource.com/blog/automating-quality-gate-success-with-claude-opus-4-6-and-sonarqube-mcp/ |
| 8 | SonarSource — Architecture of Trust | https://www.sonarsource.com/blog/join-the-sonarqube-remediation-agent-beta/ |
| 9 | SonarSource — outsourcing risk management | https://sonarsource.com/solutions/reduce-outsourcing-software-development-risk |
| 10 | SonarQube — Webhook configuration | https://docs.sonarsource.com/sonarqube-community-build/project-administration/webhooks |
| 11 | SonarQube — New Code Period | https://docs.sonarsource.com/sonarqube-server/project-administration/configuring-new-code-calculation |
| 12 | SonarQube — API Issues Search | https://next.sonarqube.com/sonarqube/web_api/api/issues/search |
| 13 | CE branch constraint (StackOverflow) | https://stackoverflow.com/questions/69803754 |
| 14 | CE branch workaround (StackOverflow) | https://stackoverflow.com/questions/72536550 |
| 15 | Community Branch Plugin | https://github.com/mc1arke/sonarqube-community-branch-plugin |
| 16 | Kiro CLI — Commands | https://kiro.dev/docs/cli/reference/cli-commands |
| 17 | Kiro CLI — Authentication | https://kiro.dev/docs/cli/authentication/ |
| 18 | setup-kiro-action | https://github.com/clouatre-labs/setup-kiro-action |
| 19 | Kiro CLI — Headless issue | https://github.com/kirodotdev/Kiro/issues/4398 |
| 20 | SonarSource — Gemini CLI integration | https://www.sonarsource.com/integrations/google/gemini-cli/ |
| 21 | Enterprise AI Policy 2026 | https://aidevdayindia.org/blogs/best-ai-mode-checker/enterprise-ai-coding-policy-template-2026.html |
| 22 | IBM ScarfBench | https://www.ibm.com/new/announcements/scarfbench-a-public-benchmark-for-java-framework-migration |
| 23 | Presidio — Agentic Modernization | https://www.presidio.com/blogs/agentic-application-modernization-reality/ |
| 24 | Pangea.ai — Outsourcing Contracts | https://pangea.ai/resources/software-outsourcing-contracts-what-to-include-and-how-to-negotiate |
| 25 | GenieAI — Contract Clauses | https://www.genieai.co/blog/essential-contract-clauses-for-custom-software-development-outsourcing-agreements |
| 26 | DORA 2025 | https://dora.dev/research/2025/dora-report/ |
| 27 | SonarQube — Clean as You Code | https://docs.sonarsource.com/sonarqube-server/latest/core-concepts/clean-as-you-code/introduction/ |
| 28 | Pixeebot + SonarQube | https://github.com/pixee/upload-tool-results-action |
| 29 | SonarQube — Branch Analysis | https://docs.sonarsource.com/sonarqube-server/2025.4/analyzing-source-code/branch-analysis/setting-up-the-branch-analysis |
| 30 | SonarSource — outsourced code quality strategy | https://www.sonarsource.com/resources/library/strategies-for-managing-code-quality-in-outsourced-software-development/ |

---

*Document Version: 3.0 | Created: 2026-03-21 | Updated: 2026-06-07 (implementation reflected) | Classification: Internal*
