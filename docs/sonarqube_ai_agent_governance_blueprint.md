한국어 | **[English](sonarqube_ai_agent_governance_blueprint.en.md)**

# SonarQube + AI Agent Governance Blueprint
## Enterprise-Grade Defect Resolution, Test Code Ownership & Operational Process

---

## 1. Executive Summary

본 문서는 소나큐브 도입 시 AI 에이전트를 활용한 결함 해결 및 테스트 코드 생성에 대한 **오너십(Ownership), R&R, 프로세스**를 업계 De Facto Standard와 Best Practice를 근거로 정의한다.

### 핵심 원칙 (Golden Rule)

> **"코드를 커밋하는 사람이 그 코드의 전적인 책임을 진다 — 작성 주체(사람/AI)와 무관하게."**
> — Enterprise AI Coding Policy Template 2026, DORA 2025

이 원칙은 **업계 표준(De Facto)**이며, SonarSource, Google DORA, GitHub, GitLab 모두 동일한 입장을 취한다.

---

## 2. Industry De Facto: SonarQube의 "Clean as You Code" 정책

### 2.1 핵심 개념

SonarQube가 공식적으로 권장하는 **Clean as You Code**는 다음을 의미한다:

| 구분 | 정책 |
|------|------|
| **신규 코드 (New Code)** | 새로 작성하거나 수정한 코드는 Quality Gate를 반드시 통과해야 함 |
| **레거시 코드 (Old Code)** | 기존 코드를 별도로 수정할 의무 없음. 업무상 터치할 때만 개선 |
| **이슈 할당** | 해당 라인의 마지막 커밋 작성자(issue author)에게 자동 할당 |
| **품질 게이트** | 신규 코드 기준으로만 Pass/Fail 판정 |

### 2.2 이것이 중요한 이유

- 개발팀이 우려하는 **"레거시 전체를 수정해야 하는 부담"은 발생하지 않음**
- Sonar 연구에 따르면 기술 부채 비용: **코드 100만 라인당 연 $306,000 (약 5,500 개발자-시간)**
- Clean as You Code는 **별도 부채 해결 스프린트 없이** 점진적으로 전체 품질을 향상시키는 전략

### 2.3 개발팀 리소스 부족 우려에 대한 답변

```
개발팀 주장: "결함 해결을 위한 리소스가 부족하여 소나큐브 도입 불가"

반론 (De Facto 기반):
1. Clean as You Code = 레거시 코드 수정 의무 없음
2. 신규 코드만 대상 = 추가 리소스 최소화
3. AI 에이전트 + Quality Gate = 자동화로 개발자 부담 경감
4. SonarLint IDE 통합 = 코딩 시점에서 실시간 피드백 (Shift-Left)
```

---

## 3. AI Agent 개입 모델: 업계 참조 아키텍처

### 3.1 SonarQube 공식 Remediation Agent 워크플로우

SonarQube 자체가 2025년에 **Remediation Agent**를 출시했다. 이것이 업계가 인정하는 표준 워크플로우다:

```
┌─────────────────────────────────────────────────────────────────┐
│                    SonarQube Remediation Agent Flow              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. Developer → PR 생성 (신규 코드 작성)                          │
│                    │                                            │
│  2. SonarQube → PR 분석 실행                                     │
│                    │                                            │
│  3. Quality Gate 위반 이슈 발견                                   │
│                    │                                            │
│  4. AI Agent → 자동 수정 코드 생성                                │
│                    │                                            │
│  5. Sandbox → 수정 코드 재검증 (새 취약점 도입 여부 확인)           │
│                    │                                            │
│  6. AI Agent → Fix PR 생성 (Developer에게 제출)                   │
│                    │                                            │
│  7. Developer → 리뷰 & 승인 & 머지                               │
│         ▲                                                       │
│         │                                                       │
│    [Human-in-the-Loop: 최종 책임은 반드시 Developer]              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 핵심 설계 원칙: "Architecture of Trust"

SonarSource가 명명한 **"Architecture of Trust"** 패턴:

1. **AI는 제안(Suggest)하고, 사람이 결정(Decide)한다**
2. **AI 수정은 머지 전 Sandbox에서 재검증된다**
3. **재검증 실패 시 자동 폐기된다**
4. **Developer-in-the-Loop가 필수다**

---

## 4. RACI 매트릭스: 역할과 책임의 명확한 정의

### 4.1 전체 RACI

| 활동 | 개발팀 (Dev) | 품질팀 (QA/QE) | AI Agent | 비고 |
|------|:---:|:---:|:---:|------|
| 신규 코드 작성 | **R/A** | I | - | 개발자 본연의 업무 |
| 소나큐브 룰/프로필 설정 | C | **R/A** | - | 품질팀이 표준 관리 |
| Quality Gate 기준 수립 | C | **R/A** | - | 품질팀이 게이트 키퍼 |
| 신규 코드 결함 수정 | **R/A** | I | **R** | Dev가 최종 책임, AI가 초안 |
| 레거시 코드 결함 수정 | C | **A** | **R** | AI가 수정, 품질팀이 관리 |
| AI 수정 코드 리뷰 | **R/A** | C | - | 커밋하는 Dev가 전적 책임 |
| 테스트 코드 생성 | **R/A** | C | **R** | AI가 초안, Dev가 최종 검증 |
| AI Agent 운영/관리 | C | **R/A** | - | 품질팀이 에이전트 운영 |
| AI Agent 성과 모니터링 | I | **R/A** | - | 품질팀이 효과성 측정 |
| False Positive 튜닝 | C | **R/A** | - | 품질팀이 노이즈 관리 |
| CI/CD 파이프라인 통합 | **R** | **A** | - | Dev가 구현, 품질팀 검증 |

> **R** = Responsible (실행), **A** = Accountable (최종 책임), **C** = Consulted (자문), **I** = Informed (통보)

### 4.2 역할별 구체적 책임

#### 개발팀 (Development Team)
```
책임:
  ✓ 자신이 작성/수정한 코드의 Quality Gate 통과
  ✓ AI Agent가 생성한 수정 코드 및 테스트 코드의 리뷰 & 승인
  ✓ 커밋한 모든 코드의 최종 오너십 (Golden Rule)
  ✓ SonarLint를 통한 IDE 단계 실시간 결함 예방

면제:
  ✗ 레거시 코드 전체 수정 의무 없음
  ✗ AI Agent 운영/관리 의무 없음
  ✗ 소나큐브 룰 설정 의무 없음
```

#### 품질팀 (Quality/QE Team)
```
책임:
  ✓ 소나큐브 Quality Profile 및 Quality Gate 설정/유지보수
  ✓ AI Agent 운영, 모니터링, 성과 측정
  ✓ False Positive 관리 및 룰 튜닝
  ✓ 레거시 코드 기술 부채 해결 로드맵 관리 (AI Agent 활용)
  ✓ 품질 메트릭 대시보드 운영 및 보고

면제:
  ✗ 개발자가 커밋한 코드의 결함에 대한 최종 책임 없음
  ✗ 프로덕션 코드 직접 수정 없음
```

#### AI Agent
```
역할:
  ✓ 소나큐브 이슈에 대한 수정 코드 초안 생성
  ✓ 테스트 코드 초안 생성
  ✓ Sandbox 내 자가 검증 (재분석)
  ✓ Fix PR 자동 생성

제한:
  ✗ 직접 머지 권한 없음 (반드시 Human Review 필요)
  ✗ Quality Gate 기준 변경 권한 없음
  ✗ 프로덕션 브랜치 직접 푸시 불가
```

---

## 5. 운영 프로세스: AI Agent 개입 시점과 워크플로우

### 5.1 이중 트랙(Dual-Track) 프로세스

업계 Best Practice는 **신규 코드**와 **레거시 코드**를 분리한 이중 트랙 운영이다:

```
═══════════════════════════════════════════════════════════════════
  Track 1: 신규 코드 (Clean as You Code)
  소유: 개발팀 | AI 개입: PR 시점 자동 | 주기: 매 PR
═══════════════════════════════════════════════════════════════════

  Developer                    AI Agent              SonarQube
     │                            │                      │
     ├── 코드 작성 ───────────────┤                      │
     │   (SonarLint 실시간 검사)   │                      │
     │                            │                      │
     ├── PR 생성 ─────────────────┼──── 분석 요청 ──────→│
     │                            │                      │
     │                            │←── 이슈 발견 ────────┤
     │                            │                      │
     │                            ├── 수정 코드 생성      │
     │                            ├── Sandbox 검증       │
     │                            ├── Fix PR 생성        │
     │                            │                      │
     │←── Fix PR 전달 ────────────┤                      │
     │                            │                      │
     ├── 리뷰 & 승인 (또는 거절)   │                      │
     ├── 머지 ────────────────────┤                      │
     │                            │                      │
  [최종 오너십: Developer]         │                      │

═══════════════════════════════════════════════════════════════════
  Track 2: 레거시 코드 (Technical Debt Reduction)
  소유: 품질팀 | AI 개입: 배치 스케줄 | 주기: 스프린트 단위
═══════════════════════════════════════════════════════════════════

  Quality Team                 AI Agent              SonarQube
     │                            │                      │
     ├── 기술부채 우선순위 선정 ───┤                      │
     │   (Severity: Critical/     │                      │
     │    Blocker 우선)           │                      │
     │                            │                      │
     ├── AI Agent에 배치 할당 ────→│                      │
     │                            │                      │
     │                            ├── 수정 코드 생성      │
     │                            ├── 테스트 코드 생성    │
     │                            ├── Sandbox 검증       │
     │                            ├── Fix PR 생성        │
     │                            │                      │
     │←── Fix PR 전달 ────────────┤                      │
     │                            │                      │
     ├── 리뷰 요청 → 개발팀 ──────┤                      │
     │                            │                      │
  [개발팀 리뷰 & 머지]            │                      │
  [최종 오너십: 머지한 Developer]  │                      │
```

### 5.2 AI Agent 개입 시점 상세

| 단계 | 시점 | 트리거 | AI 행동 | 사람의 행동 |
|------|------|--------|---------|------------|
| **Pre-commit** | 코딩 중 | SonarLint 경고 | IDE 내 실시간 수정 제안 | 개발자 즉시 반영 |
| **PR 생성** | PR 오픈 시 | 소나큐브 PR 분석 | Quality Gate 위반 이슈 자동 수정 PR 생성 | 개발자 리뷰 후 머지 |
| **Post-merge** | 머지 후 | 브랜치 분석 | 놓친 이슈 감지 및 후속 PR 생성 | 개발자 리뷰 후 머지 |
| **Scheduled Batch** | 주기적 | 스케줄 (주 1회) | 레거시 코드 기술 부채 배치 수정 | 품질팀 관리, 개발팀 리뷰 |

### 5.3 품질 게이트 설정 기준 (De Facto Standard)

```
Quality Gate: "Sonar Way" (기본값) + 강화 권장 사항

신규 코드 기준:
  ┌──────────────────────────────────┬───────────────┐
  │ 메트릭                           │ 기준값        │
  ├──────────────────────────────────┼───────────────┤
  │ New Bugs                         │ 0             │
  │ New Vulnerabilities              │ 0             │
  │ New Security Hotspots Reviewed   │ 100%          │
  │ New Code Coverage                │ ≥ 80%         │
  │ New Duplicated Lines             │ ≤ 3%          │
  │ Reliability Rating               │ A             │
  │ Security Rating                  │ A             │
  │ Maintainability Rating           │ A             │
  └──────────────────────────────────┴───────────────┘

AI 생성 코드 강화 기준 (권장):
  ┌──────────────────────────────────┬───────────────┐
  │ AI 코드 비율 > 60% PR           │ Senior 리뷰   │
  │ AI 생성 코드 커버리지            │ ≥ 90%         │
  │ AI 코드 보안 스캔               │ 필수          │
  └──────────────────────────────────┴───────────────┘
```

---

## 6. 오너십 모델: "커밋자 책임 원칙" 상세

### 6.1 업계 합의 (2025-2026 De Facto)

```
┌─────────────────────────────────────────────────────────────┐
│                   Code Ownership Model                       │
│                                                             │
│   ┌─────────┐    생성    ┌──────────┐                       │
│   │AI Agent │──────────→│ Fix Code │                        │
│   └─────────┘           └────┬─────┘                        │
│                              │                              │
│                         리뷰 & 승인                          │
│                              │                              │
│                              ▼                              │
│   ┌──────────┐   커밋    ┌──────────┐                       │
│   │Developer │←─────────│ Approved │                        │
│   └────┬─────┘          └──────────┘                        │
│        │                                                    │
│        ▼                                                    │
│   ┌──────────────────────────────────┐                      │
│   │  커밋 시점부터                     │                      │
│   │  해당 코드의 완전한 오너십은        │                      │
│   │  Developer에게 귀속               │                      │
│   │                                   │                      │
│   │  → 버그 발생 시 책임: Developer    │                      │
│   │  → 유지보수 책임: Developer        │                      │
│   │  → 보안 이슈 책임: Developer       │                      │
│   └──────────────────────────────────┘                      │
│                                                             │
│   근거: Enterprise AI Coding Policy 2026                     │
│         "The Golden Rule — the developer who commits         │
│          is fully responsible for its logic,                 │
│          regardless of authorship."                          │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 오너십 전환 흐름

| 단계 | 코드 상태 | 오너십 | 법적/조직적 책임 |
|------|-----------|--------|------------------|
| AI 생성 직후 | Draft/초안 | 없음 (도구 산출물) | 없음 |
| Sandbox 검증 통과 | 검증된 제안 | AI Agent (품질팀 관리) | 품질팀 운영 책임 |
| Fix PR 생성 | 리뷰 대기 | 미확정 | 없음 |
| Developer 리뷰 승인 | 승인됨 | **Developer** | Developer |
| 머지 & 커밋 | 프로덕션 코드 | **Developer (완전 귀속)** | Developer |

---

## 7. DORA 2025 연구 근거: AI는 증폭기(Amplifier)

### 7.1 핵심 발견

Google DORA 2025 보고서의 핵심 결론:

> **"AI는 조직의 기존 강점과 약점을 증폭시킨다."**

- 테스팅 문화가 강한 조직 → AI가 **강력한 협업자** 역할
- 테스팅 문화가 약한 조직 → AI가 **기술 부채를 더 빠르게 생성**

### 7.2 시사점

```
┌─────────────────────────────────────────────────────────┐
│  AI Agent 도입 전 반드시 선행되어야 할 조건:              │
│                                                         │
│  1. 자동화된 테스트 파이프라인 (CI/CD 내 테스트 단계)     │
│  2. 명확한 Quality Gate 기준 수립                        │
│  3. 코드 리뷰 문화 정착                                  │
│  4. RACI 기반 역할/책임 합의                             │
│                                                         │
│  이 조건 없이 AI Agent만 도입하면:                        │
│  → "기술 부채를 더 빠르게 생산하는 도구"가 됨             │
└─────────────────────────────────────────────────────────┘
```

### 7.3 낙관적/비관적 시나리오

#### 낙관적 시나리오 (Well-Governed)
- AI Agent가 결함 수정 시간 **60-70% 절감**
- 테스트 커버리지 **30% → 80%** 급속 향상
- 개발팀의 Quality Gate 통과율 **90%+** 달성
- 레거시 기술 부채 **연 20-30%** 점진적 감소

#### 비관적 시나리오 (Poorly-Governed)
- AI 생성 코드의 **45%가 보안 표준 미달** (2026 업계 통계)
- 개발자가 AI 코드를 무비판적으로 수용 → 새로운 유형의 결함 도입
- 오너십 불명확 → 결함 발생 시 책임 회피 ("AI가 만든 코드인데요")
- Alert Fatigue: False Positive 관리 부재 → 수주 내 팀의 무관심

---

## 8. 단계적 도입 로드맵

### Phase 1: Foundation (1-2개월)

```
목표: 합의 도출 및 인프라 구축

 Week 1-2: 이해관계자 워크숍
   ├── 본 RACI 매트릭스 기반 R&R 합의
   ├── Quality Gate 기준 합의
   └── Clean as You Code 정책 공유 → 개발팀 우려 해소

 Week 3-4: 기술 인프라
   ├── 소나큐브 서버 구축 (기존 CI/CD 연동)
   ├── SonarLint IDE 플러그인 전체 배포
   └── Quality Profile 초기 설정 (Sonar Way 기반)

 Week 5-8: 파일럿
   ├── 1-2개 파일럿 프로젝트 선정
   ├── Quality Gate: Warning Only 모드 (차단 없음)
   └── 메트릭 베이스라인 측정
```

### Phase 2: AI Agent Integration (2-3개월)

```
목표: AI Agent 도입 및 Track 1 (신규코드) 자동화

 Month 3: AI Agent 개발/도입
   ├── 소나큐브 API 연동
   ├── Fix PR 자동 생성 파이프라인 구축
   └── Sandbox 검증 환경 구성

 Month 4: Track 1 활성화
   ├── PR 분석 → AI 자동 수정 제안 파이프라인 가동
   ├── Quality Gate: Enforced 모드 전환 (PR 차단)
   └── 개발팀 피드백 수집 & 튜닝

 Month 5: 확대
   ├── 전체 프로젝트로 Track 1 확대
   └── False Positive 튜닝 안정화
```

### Phase 3: Full Operation (3-6개월)

```
목표: Track 2 (레거시) 포함 전체 운영

 Month 6-8: Track 2 활성화
   ├── 레거시 코드 기술 부채 우선순위 산정
   ├── AI Agent 배치 수정 시작 (Critical/Blocker 우선)
   └── 품질팀 주도 레거시 부채 감소 로드맵 운영

 Month 9-12: 최적화
   ├── 메트릭 기반 AI Agent 효과성 측정
   ├── DORA 메트릭 연동 (배포 빈도, 변경 실패율 등)
   └── 프로세스 개선 사이클 정착
```

---

## 9. 각 이해관계자의 우려에 대한 공식 답변

### 9.1 개발팀: "리소스 부족으로 소나큐브 도입 불가"

| 우려 | 답변 | 근거 |
|------|------|------|
| 레거시 전체 수정 필요? | **아니오.** Clean as You Code = 신규 코드만 | SonarSource 공식 정책 |
| 추가 업무 부담? | **최소.** AI Agent가 Fix PR 생성, 개발자는 리뷰만 | SonarQube Remediation Agent |
| 누가 테스트 코드 작성? | **AI Agent 초안 생성** → 개발자 검증 | 업계 Best Practice |
| IDE 변경 필요? | SonarLint만 설치 (2분 소요) | 기존 IDE 유지 |

### 9.2 품질팀: "R&R, 오너십, 프로세스 명확화 필요"

| 우려 | 답변 | 근거 |
|------|------|------|
| AI Agent 누가 사용? | **Track 1:** 자동 (PR 시점), **Track 2:** 품질팀 주도 | 본 문서 RACI |
| AI 코드 오너십? | **커밋한 Developer에게 완전 귀속** (Golden Rule) | Enterprise AI Policy 2026 |
| AI 개입 시점? | **4단계:** Pre-commit, PR, Post-merge, Batch | 본 문서 5.2절 |
| 품질팀 역할은? | **Gate Keeper + Agent Operator + Metrics Owner** | 본 문서 RACI |

---

## 10. 참조 (References)

1. **SonarSource** — "Clean as You Code" (https://docs.sonarsource.com/sonarqube-server/latest/core-concepts/clean-as-you-code/introduction/)
2. **SonarSource** — "SonarQube Remediation Agent" (https://docs.sonarsource.com/sonarqube-cloud/managing-your-projects/issues/with-ai-features/sonarqube-remediation-agent)
3. **SonarSource** — "AI CodeFix" (https://docs.sonarsource.com/sonarqube-server/2025.1/ai-capabilities/ai-fix-suggestions)
4. **Google DORA 2025** — "State of AI-assisted Software Development" (https://dora.dev/research/2025/dora-report/)
5. **DORA 2025** — "Balancing AI Tensions" (https://dora.dev/insights/balancing-ai-tensions/)
6. **Enterprise AI Coding Policy Template 2026** (https://aidevdayindia.org/blogs/best-ai-mode-checker/enterprise-ai-coding-policy-template-2026.html)
7. **Sonar Research** — "Cost of Technical Debt" (https://www.sonarsource.com/blog/new-research-from-sonar-on-cost-of-technical-debt)
8. **Enterprise AI Governance Framework** (https://blog.exceeds.ai/enterprise-ai-code-governance-framework)
9. **Augment Code** — "Static Code Analysis Best Practices" (https://www.augmentcode.com/guides/static-code-analysis-best-practices-enterprise)
10. **SonarSource** — "Claude Code + SonarQube MCP" (https://www.sonarsource.com/blog/claude-code-sonarqube-mcp-building-an-autonomous-code-review-workflow/)

---

*Document Version: 1.0 | Created: 2026-03-21 | Classification: Internal*
