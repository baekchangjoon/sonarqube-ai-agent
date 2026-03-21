# AI Agent Implementation Architecture
## SonarQube Community Edition + MCP Server + LLM-Agnostic Agent 설계

---

## 1. 제약 조건 정리

| 항목 | 현황 | 영향 |
|------|------|------|
| SonarQube Edition | **Community Build** | PR 분석, 브랜치 분석, AI CodeFix 불가 ([CE 기능 범위](https://www.sonarsource.com/open-source-editions/sonarqube-community-edition/)) |
| 코드베이스 | Java 1.x → **Java 17** AI 모더나이제이션 완료 | AI 전환 코드 위에 외주사가 추가 개발 중 |
| 개발 주체 | **외주 계약 업체** | 코드 오너십, 품질 계약 조건 필요 |
| 조직 권장 AI 도구 | **AWS Kiro** | 기본 도구이나, 다른 LLM으로 교체 가능해야 함 |
| CI 환경 Kiro CLI | **인증 불확실** | CI 자동화 시 대안 경로 필요 |

### 설계 결정 사항

| 결정 | 선택 | 근거 |
|------|------|------|
| MCP Server 사용 여부 | **사용** | LLM 도구 교체 용이성, AI Agent의 SonarQube 네이티브 연동 |
| LLM 도구 교체 가능성 | **필수** | Orchestrator에서 LLM 인터페이스 추상화 |
| PR 수준 분석 | **임시 프로젝트 키 방식** | Community Edition에서 PR 분석 가능하게 하는 워크어라운드 |

---

## 2. 핵심 기술 발견

### 2.1 Community Edition에서 PR 브랜치 분석이 가능한가?

**가능하다. 단, 주의가 필요하다.**

`sonar-scanner`는 현재 디렉토리의 코드를 분석한다. PR 브랜치를 checkout하고 실행하면 해당 코드를 분석하는 것은 맞다. **하지만** Community Edition에서 결과 저장에 제약이 있다:

```
┌─────────────────────────────────────────────────────────────┐
│  Community Edition의 sonar-scanner 동작 원리                 │
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

### 2.2 해결책: 임시 프로젝트 키 (Ephemeral Project Key)

Community Edition 공식 워크어라운드 ([StackOverflow 참조](https://stackoverflow.com/questions/72536550/master-and-develop-branch-analysis-in-sonarqube-community-edition)):

**PR마다 고유한 임시 프로젝트 키를 사용하면, main 브랜치 분석을 오염시키지 않고 PR 코드를 독립적으로 분석할 수 있다.**

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

이 방식의 장단점:

| 장점 | 단점 |
|------|------|
| Community Edition 순정 상태 사용 | PR마다 임시 프로젝트 생성/삭제 오버헤드 |
| main 분석 오염 없음 | Quality Profile을 임시 프로젝트에도 적용 필요 |
| 여러 PR 동시 분석 가능 | 임시 프로젝트 정리 로직 구현 필요 |
| 플러그인 설치 불필요 | 대시보드에 임시 프로젝트가 보임 (정리 전) |

### 2.3 SonarQube MCP Server

SonarQube MCP Server는 AI Agent와 SonarQube 사이의 **표준 브릿지**다.

[Community Build 공식 호환 문서](https://docs.sonarsource.com/sonarqube-community-build/extension-guide/sonarqube-mcp-server) |
[MCP Server 제품 페이지](https://www.sonarsource.com/products/sonarqube/mcp-server/) |
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

### 2.4 LLM 도구 교체 가능성

MCP(Model Context Protocol)는 **LLM-Agnostic 표준 프로토콜**이다. SonarQube MCP Server를 사용하면, LLM 도구 교체가 설정 변경만으로 가능하다.

[SonarSource 공식 지원 MCP 클라이언트 목록](https://www.sonarsource.com/products/sonarqube/mcp-server/):

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

## 3. 확정 아키텍처

### 3.1 전체 구조도

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

### 3.2 세 가지 실행 모드 상세

#### Mode 1: PR Pre-merge (핵심 모드)

**외주 개발자가 PR을 올린 시점에 — 머지 전에 — 결함을 탐지하고 수정을 제안한다.**

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
 │     C) 별도 Fix PR 생성 (Phase 3)                      │
 │                                                        │
 │  6. 임시 프로젝트 정리 (PR Close 시)                   │
 │     DELETE /api/projects/delete?project=myproject-pr-142│
 │                                                        │
 └────────────────────────────────────────────────────────┘
         │
         ▼
 외주 개발자: AI 수정 제안 리뷰 → 반영 → 머지
```

#### Mode 2: Post-merge (보완 모드)

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

Mode 1에서 놓친 이슈를 잡는 **안전망** 역할이다. Mode 1이 잘 동작하면 여기서 잡히는 이슈는 점점 줄어든다.

#### Mode 3: Nightly Batch (기술 부채 감소)

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

AI 모더나이제이션으로 전환된 코드의 **레거시 기술 부채를 점진적으로 해소**한다.

---

## 4. Orchestrator 설계: LLM 추상화 인터페이스

### 4.1 전체 클래스 구조

```python
"""
SonarQube AI Agent Orchestrator

핵심 설계 원칙:
1. LLM Agent는 추상 인터페이스로 교체 가능
2. SonarQube 연동은 MCP Server 경유
3. Architecture of Trust: AI 제안 → Sandbox 검증 → Human 리뷰
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


# ─────────────────────────────────────────────
# Layer 1: LLM Agent Abstract Interface
# ─────────────────────────────────────────────

class LLMAgent(ABC):
    """
    LLM 도구 교체를 위한 추상 인터페이스.
    모든 구현체는 MCP Server와 연동하여
    SonarQube 이슈를 조회하고 수정 코드를 생성한다.
    """

    @abstractmethod
    def generate_fix(self, prompt: str, working_dir: str) -> str:
        """Send a prompt and return the raw LLM response."""

    @abstractmethod
    def supports_mcp(self) -> bool:
        """Whether this agent natively connects to MCP servers."""

    @abstractmethod
    def name(self) -> str:
        """Human-readable agent name for logging."""

    def build_fix_prompt(self, issue_rule, issue_message,
                         file_path, line, source_context) -> str:
        """Construct a standardized fix prompt from issue details."""
        pass


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
    Fallback: AWS Bedrock API 직접 호출.
    MCP 미지원 — Orchestrator가 이슈 정보를 프롬프트에 직접 삽입.
    """

    def generate_fix(self, prompt: str, working_dir: str) -> str:
        # boto3.client('bedrock-runtime').invoke_model(...)
        pass

    def supports_mcp(self) -> bool:
        return False

    def name(self) -> str:
        return "Bedrock API"


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

### 4.2 설정 파일

```yaml
# config.yml

agent:
  # LLM 도구 선택: kiro-cli | claude-code | gemini-cli | bedrock-api
  type: "kiro-cli"

  # Kiro CLI 전용 설정
  kiro:
    agent_name: "sonarqube-fixer"
    trust_all_tools: true

  # Claude Code 전용 설정
  claude:
    allowed_tools: "Read,Write,Edit"
    model: "sonnet"

  # Gemini CLI — 파라미터 없음 (--yolo -p 모드 사용)
  gemini: {}

  # Bedrock API Fallback 설정
  bedrock:
    model_id: "anthropic.claude-sonnet-4-20250514"
    region: "us-east-1"

sonarqube:
  url: "http://sonarqube.internal:9000"
  token: "${SONAR_TOKEN}"
  main_project_key: "myproject"

scanner:
  # PR 분석 시 임시 프로젝트 키 패턴
  ephemeral_key_pattern: "{project}-pr-{pr_number}"

modes:
  pr_premerge:
    enabled: true
    delivery: "comment"  # comment | commit | fix-pr

  post_merge:
    enabled: true

  nightly_batch:
    enabled: true
    # cron 스케줄은 외부(crontab/GitHub Actions)에서 관리
    max_issues_per_run: 10
    severity_filter:
      - BLOCKER
      - CRITICAL
      - MAJOR
```

### 4.3 LLM별 MCP Server 설정

각 LLM 도구에서 SonarQube MCP Server를 연동하는 구체적 설정:

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

[Kiro CLI Agent 설정 문서](https://kiro.dev/docs/cli/reference/cli-commands/#kiro-cli-agent)

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

[Claude Code + SonarQube MCP 연동 문서](https://www.sonarsource.com/blog/claude-code-sonarqube-mcp-building-an-autonomous-code-review-workflow/)

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

[Gemini CLI + SonarQube 연동 페이지](https://www.sonarsource.com/integrations/google/gemini-cli/)

**MCP Server Docker 이미지가 동일하다는 것에 주목 — 설정 파일의 위치와 형식만 다르다.**

---

## 5. CI 파이프라인 설계

### 5.1 PR Pre-merge 파이프라인 (GitHub Actions)

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

### 5.2 Post-merge 파이프라인

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

### 5.3 PR Close 시 임시 프로젝트 정리

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

## 6. SonarQube New Code Period 설정

AI 모더나이제이션 코드를 **베이스라인**으로 설정하고, 외주사의 신규 코드만 Quality Gate 대상으로 삼는다.

[New Code 설정 문서](https://docs.sonarsource.com/sonarqube-server/project-administration/configuring-new-code-calculation)

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

## 7. 외주 계약 품질 조항

[SonarSource 외주 리스크 관리](https://sonarsource.com/solutions/reduce-outsourcing-software-development-risk) |
[Pangea.ai 2026 외주 계약 가이드](https://pangea.ai/resources/software-outsourcing-contracts-what-to-include-and-how-to-negotiate) |
[GenieAI 계약 조항 가이드](https://www.genieai.co/blog/essential-contract-clauses-for-custom-software-development-outsourcing-agreements)

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

## 8. 코드 레이어별 결함 오너십

[Enterprise AI Coding Policy 2026](https://aidevdayindia.org/blogs/best-ai-mode-checker/enterprise-ai-coding-policy-template-2026.html) |
[SonarQube Clean as You Code](https://docs.sonarsource.com/sonarqube-server/latest/core-concepts/clean-as-you-code/introduction/) |
[IBM ScarfBench](https://www.ibm.com/new/announcements/scarfbench-a-public-benchmark-for-java-framework-migration)

| 코드 레이어 | 생성 주체 | 결함 오너 | 근거 |
|-------------|----------|-----------|------|
| 원본 레거시 (Java 1.x) | 과거 개발팀 | 해당 없음 (폐기) | - |
| AI 모더나이제이션 코드 (Java 17) | AI Agent | 발주사 (내부) | 수용 테스트 통과 후 귀속 |
| 외주사 신규 개발 코드 | 외주사 | **외주사** (하자보증 기간 내) | 계약 조건 |
| AI Agent 자동 수정 코드 | AI Agent | **머지한 사람** (Golden Rule) | [Enterprise AI Policy 2026](https://aidevdayindia.org/blogs/best-ai-mode-checker/enterprise-ai-coding-policy-template-2026.html) |

---

## 9. 단계별 구현 로드맵

### Phase 0: 인프라 검증 (1-2주)

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

### Phase 1: MVP — PR 코멘트 모드 (2-4주)

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

### Phase 2: Fix PR 자동화 (2-4주)

```
추가:
1. Sandbox 검증 파이프라인
2. Fix PR 자동 생성
3. Nightly Batch (Mode 3)
4. 2번째 LLM 구현체 추가

산출물: 자동 Fix PR + 야간 기술 부채 감소
```

### Phase 3: 확대 및 최적화 (4-8주)

```
추가:
1. 전체 프로젝트 확대
2. 메트릭 대시보드
3. 외주 계약 SLA 연동
4. 3~4번째 LLM 구현체 추가
```

---

## 10. 낙관/비관 시나리오

### 낙관

- PR 머지 전 결함의 **80%+** 를 Mode 1에서 사전 탐지
- 외주사 Quality Gate 통과율 **70% → 95%**
- LLM 도구 자유 교체 → 비용/성능 최적화 가능
- 임시 프로젝트 방식으로 Community Edition 제약 완전 우회

### 비관

- 임시 프로젝트 대량 생성 시 SonarQube 서버 부하 ([CE 리소스 제한](https://docs.sonarsource.com/sonarqube-community-build/))
- 임시 프로젝트 정리 실패 시 대시보드 오염
- MCP Server가 Community Edition에서 일부 도구 제한 가능성 (search_dependency_risks는 Enterprise만 지원 — [Tools 문서](https://docs.sonarsource.com/sonarqube-mcp-server/tools))
- Presidio 보고: 66% 조직이 AI Agent 실험 중이나 **11%만 프로덕션 배포 성공** ([참조](https://www.presidio.com/blogs/agentic-application-modernization-reality/))

---

## 11. References

| # | 출처 | URL |
|---|------|-----|
| 1 | SonarQube CE — MCP Server 호환 | https://docs.sonarsource.com/sonarqube-community-build/extension-guide/sonarqube-mcp-server |
| 2 | SonarQube MCP Server — Tools | https://docs.sonarsource.com/sonarqube-mcp-server/tools |
| 3 | SonarQube MCP Server — Quickstart | https://docs.sonarsource.com/sonarqube-mcp-server/quickstart-guide |
| 4 | SonarQube MCP Server — Docker | https://hub.docker.com/mcp/server/sonarqube/overview |
| 5 | SonarSource — MCP Server 제품 | https://www.sonarsource.com/products/sonarqube/mcp-server/ |
| 6 | SonarSource — Claude Code + MCP | https://www.sonarsource.com/blog/claude-code-sonarqube-mcp-building-an-autonomous-code-review-workflow/ |
| 7 | SonarSource — PR-to-green | https://www.sonarsource.com/blog/automating-quality-gate-success-with-claude-opus-4-6-and-sonarqube-mcp/ |
| 8 | SonarSource — Architecture of Trust | https://www.sonarsource.com/blog/join-the-sonarqube-remediation-agent-beta/ |
| 9 | SonarSource — 외주 리스크 관리 | https://sonarsource.com/solutions/reduce-outsourcing-software-development-risk |
| 10 | SonarQube — Webhook 설정 | https://docs.sonarsource.com/sonarqube-community-build/project-administration/webhooks |
| 11 | SonarQube — New Code Period | https://docs.sonarsource.com/sonarqube-server/project-administration/configuring-new-code-calculation |
| 12 | SonarQube — API Issues Search | https://next.sonarqube.com/sonarqube/web_api/api/issues/search |
| 13 | CE 브랜치 제약 (StackOverflow) | https://stackoverflow.com/questions/69803754 |
| 14 | CE 브랜치 워크어라운드 (StackOverflow) | https://stackoverflow.com/questions/72536550 |
| 15 | Community Branch Plugin | https://github.com/mc1arke/sonarqube-community-branch-plugin |
| 16 | Kiro CLI — Commands | https://kiro.dev/docs/cli/reference/cli-commands |
| 17 | Kiro CLI — Authentication | https://kiro.dev/docs/cli/authentication/ |
| 18 | setup-kiro-action | https://github.com/clouatre-labs/setup-kiro-action |
| 19 | Kiro CLI — Headless 이슈 | https://github.com/kirodotdev/Kiro/issues/4398 |
| 20 | SonarSource — Gemini CLI 연동 | https://www.sonarsource.com/integrations/google/gemini-cli/ |
| 21 | Enterprise AI Policy 2026 | https://aidevdayindia.org/blogs/best-ai-mode-checker/enterprise-ai-coding-policy-template-2026.html |
| 22 | IBM ScarfBench | https://www.ibm.com/new/announcements/scarfbench-a-public-benchmark-for-java-framework-migration |
| 23 | Presidio — Agentic Modernization | https://www.presidio.com/blogs/agentic-application-modernization-reality/ |
| 24 | Pangea.ai — Outsourcing Contracts | https://pangea.ai/resources/software-outsourcing-contracts-what-to-include-and-how-to-negotiate |
| 25 | GenieAI — Contract Clauses | https://www.genieai.co/blog/essential-contract-clauses-for-custom-software-development-outsourcing-agreements |
| 26 | DORA 2025 | https://dora.dev/research/2025/dora-report/ |
| 27 | SonarQube — Clean as You Code | https://docs.sonarsource.com/sonarqube-server/latest/core-concepts/clean-as-you-code/introduction/ |
| 28 | Pixeebot + SonarQube | https://github.com/pixee/upload-tool-results-action |
| 29 | SonarQube — Branch Analysis | https://docs.sonarsource.com/sonarqube-server/2025.4/analyzing-source-code/branch-analysis/setting-up-the-branch-analysis |
| 30 | SonarSource — 외주 코드 품질 전략 | https://www.sonarsource.com/resources/library/strategies-for-managing-code-quality-in-outsourced-software-development/ |

---

*Document Version: 2.0 | Created: 2026-03-21 | Classification: Internal*
