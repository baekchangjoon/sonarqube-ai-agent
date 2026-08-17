# SonarQube 일괄 분석 · AI 오탐(FP) Triage · 크로스벤더 앙상블 실측 리포트

- 작성일: 2026-06-22
- 대상 SonarQube: `https://sonar.dev-temp-mail.com` (v26.5, CE + community branch/PR plugin)
- 도구: `sonarqube-ai-agent` (orchestrator, judge/fixer 에이전트)
- 범위: 로컬 `~/github_*` 프로젝트 43개 등록·분석 → spring-petclinic 대상 FP triage 전략 비교 → Bedrock 크로스벤더 앙상블

---

## 0. 요약 (TL;DR)

1. **로컬 43개 프로젝트를 원격 SonarQube에 등록·분석 완료** (성공률 43/43). 총 518,763 LOC, 버그 939·취약점 223·보안핫스팟 275·코드스멜 15,031.
2. **AI FP triage는 단일 모델·단일 실행으로 신뢰할 수 없다.** spring-petclinic 동일 20개 이슈에서 FP 판정이 방식마다 **0·2·4·10·11개**로 요동쳤다.
3. **크로스벤더 앙상블이 도구 수정 없이 가능하다** — Bedrock `converse` API + `model_id` 교체만으로 Claude·Amazon Nova·Mistral·DeepSeek을 judge로 사용(코드 변경 0, read-only 보장).
4. 그러나 **벤더 다양성이 오류 독립성을 보장하지 않는다.** 비-Anthropic 모델(Nova·Mistral·DeepSeek)이 같은 편향을 공유해, judge를 Mistral→DeepSeek로 바꿔도 다수결은 11→10으로 사실상 불변이었다.
5. **신뢰할 수 있는 유일한 신호는 "전 벤더 만장일치"** (20개 중 7개). 만장일치는 벤더 구성과 무관하게 안정적이었다. 운영 원칙: **만장일치만 자동 신뢰, 분열 항목은 사람 에스컬레이션.**

---

## 1. 1단계 — 로컬 43개 프로젝트 SonarQube 등록·분석

### 1.1 대상 선정
- `~/github_*` 폴더 37개에서 빌드 루트를 전수 스캔.
- **원본만 선별**: `git worktree`로 만들어진 사본은 worktree 루트의 `.git`이 **파일**(원본은 디렉터리)이라는 사실로 정밀 식별해 3개 제외 (`spring-petclinic-ponytail-eval`, `wiremock-capture-all-headers`, `wiremock-session-scenarios`).
- 제외 목록 적용: 이 repo의 테스트 픽스처(`benchmark`, `e2e-fix-test`, `sample-java-project`), 임시 폴더(`assurenet/temp`).
- 최종 **43개 빌드 루트** — Java/Maven 20, Java/Gradle 17, Python 6.

### 1.2 분석 방법
- 스캐너: **Docker 이미지**(`sonarsource/sonar-scanner-cli`, `maven`) — 로컬 설치 불필요.
- 토큰 권한이 `provisioning` + `scan` → **auto-provisioning**으로 프로젝트 사전 생성 불필요.
- 언어별 처리:
  - Maven: `sonar-maven-plugin`으로 컴파일 후 분석(binaries/libraries 자동 인식).
  - Gradle: 컴파일 후 `sonar-scanner-cli`에 binaries 경로 지정.
  - Python: `sonar-scanner-cli` + `sonar.python.version`.
- projectKey 유일화: `github_` 폴더명 prefix로 충돌 방지.

### 1.3 결과
- **1차 배치 37/43 성공**, 실패 6개를 환경별로 재시도해 **최종 43/43 성공**.
- 실패 원인과 해결:

| 프로젝트 | 원인 | 해결 |
|---|---|---|
| `advance-spring-boot-microservice` ×2 | `javax.jws.soap` 부재 (JDK 8 코드) | JDK 8 이미지로 컴파일 |
| `spring-microservice-sample` | `${tools.jar}` 의존 (JDK 8) | JDK 8 컴파일 |
| `tainted-spring__analytics` | `release version 23 not supported` | JDK 23 컴파일 |
| `open-trading-api` | 스캐너가 `.codegraph/daemon.sock` 읽기 시도 | `.codegraph` exclusion |
| `wiremock__integration-tests` | `Not inside a Git work tree` | `sonar.scm.disabled=true` |

- **전체 측정값 합계**:

| 지표 | 값 |
|---|---:|
| 분석 LOC | 518,763 |
| 버그 | 939 |
| 취약점 | 223 |
| 보안 핫스팟 | 275 |
| 코드 스멜 | 15,031 |
| 기술 부채 | 288일 |
| Quality Gate | OK 42 / ERROR 1 (`spring-petclinic`, 신규코드 기준) |

> 한계: 이번 스캔은 커버리지 리포트(JaCoCo/coverage.xml)를 생성하지 않아 **커버리지는 대부분 0%**로 표시된다. 정적 분석(버그·취약점·스멜)만 반영된 수치다.

---

## 2. 2단계 — `sonarqube-ai-agent`로 FP Triage

### 2.1 도구의 판정 전략 (직교하는 두 축)

**축 1 — strategy (판정을 몇 번·어떤 순서로):**

| strategy | 방식 | 판정 패스 |
|---|---|---|
| `none` | 판정 없이 전부 fix | 0 |
| `triage` (C) | judge가 **사전** read-only 판정 → FP skip, TP만 fix | 1 (사전) |
| `review` (D) | fixer가 fix-or-escape → judge가 **사후** 독립 리뷰 | 1 (사후) |
| `triage_review` (E) | judge 사전 triage → fixer가 TP만 fix → judge 사후 리뷰 | 2 (사전+사후) |

**축 2 — judge 분리 (`judge_type`/`judge_model`):** judge를 fixer와 **다른 backend/model**로 라우팅. 비우면 judge=fixer 동일 모델. 이 축이 "다른 모델이 리뷰"의 정체이며, 축 1(패스 수)과 **독립**이다.

### 2.2 대상: spring-petclinic
- ERROR 게이트(신규코드 위반)인 유일 프로젝트, 규모 적당(2,235 LOC), 표준 코드라 검증에 적합.
- triage 대상: 버그 2 + 취약점 18 = **20개** (보안핫스팟 1은 SonarQube issues API 밖이라 제외).
- 모든 판정은 **read-only**(원본 코드·원격 서버 측정값 보존).

### 2.3 단일 패스 (Claude sonnet, 1패스)
- 결과: **TP 16 / FP 4**.
- FP 4개: `S4684` ×3 (`@InitBinder setDisallowedFields`로 완화된 위치), `S5841` ×1 (앞선 `hasSize`가 fail-fast).
- **비결정성 실측**: 동일 이슈 `OwnerController:78`이 스모크에선 FP(0.92), 전체 실행에선 TP(0.92)로 뒤집힘.

### 2.4 Full Strategy E (git worktree 격리)
- `git worktree`로 spring-petclinic을 별도 브랜치(`triage-e-experiment`)에 복사 → fix를 거기에만 적용, **원본·원격 서버 보존**.
- 도구의 `_triage_then_review`(=strategy E)를 그대로 호출(사전 triage → TP 실제 fix → fix 사후 리뷰), 서버 재스캔은 생략.

| judge 모델 | TP fix적용 | TP fix실패(timeout) | FP skip | fix 리뷰 INAPPROPRIATE |
|---|---:|---:|---:|---:|
| Claude sonnet | 11 | 7 | 2 | 1 |
| Claude opus-4.6 (Bedrock) | 12 | 8 | 0 | **4** |

- timeout은 fix 실패가 아니라 **인프라 한계**(claude 호출 300초 상한, S4684 DTO 리팩토링이 무거움).
- **opus judge는 triage에서 보수적**(FP 0, SonarQube 탐지를 전부 인정)이면서 **fix 리뷰에선 더 엄격**(12개 중 4개를 INAPPROPRIATE로 거부: NPE 위험·미정의 DTO 참조로 컴파일 에러 가능 등). → 크로스모델 judge의 실익은 "오탐 가려내기"보다 **"약한 fix 잡아내기"**에 있었다.
- `S6437` 하드코딩 시크릿 fix는 모범적(`@Value` 환경변수 외부화 + `application.properties` placeholder).

---

## 3. 3단계 — Bedrock 크로스벤더 앙상블

### 3.1 크로스벤더가 도구 수정 없이 가능한 이유
- `bedrock_api` 에이전트가 **`converse` API**(모델 무관 통합 인터페이스)를 사용 → `model_id`만 바꾸면 코드 변경 0으로 다른 벤더 모델 호출.
- bedrock 에이전트는 파일 수정 도구 없이 텍스트 API만 호출 → **어떤 모델이든 read-only triage 보장**(`gemini-cli`의 `--yolo` write 위험과 대조).
- 실측 가용 모델(raw `converse` 검증 완료): `amazon.nova-pro-v1:0`, `mistral.mistral-large-3-675b-instruct`, `deepseek.v3.2` — 모두 verdict JSON 형식 준수.
  - 제약: **Google Gemini·OpenAI GPT는 Bedrock에 없음**(자체 플랫폼). `gemini-cli`는 이 환경에서 인증 forbidden + 도구가 read-only triage 미지원. `deepseek.r1`은 on-demand 미지원(inference profile 필요)이라 `v3.2` 사용.

### 3.2 동일 20개에 대한 벤더별 단일 triage + 다수결

| 다수결 구성 | FP 확정 | 만장일치 |
|---|---:|---:|
| Claude opus + Nova + Mistral | 11 | 7/20 |
| Claude opus + Nova + DeepSeek | 10 | 7/20 |
| DeepSeek ↔ Mistral 판정 일치 | — | 15/20 (75%) |

### 3.3 핵심 발견 — 벤더 다양성 ≠ 오류 독립성
- **Claude opus만 엄격**(거의 전부 TP, `S5841`만 FP).
- **Nova·Mistral·DeepSeek은 셋 다 `S4684`를 관대하게 FP** — 비-Anthropic 3사가 같은 방향으로 쏠림.
- 진짜 독립적 의견은 **2개 진영뿐**: Anthropic(엄격) vs 비-Anthropic(관대). 비-Anthropic 모델을 추가해도 같은 진영이라 **다수결은 그 진영을 증폭**할 뿐 — Mistral→DeepSeek 교체에도 다수결 11→10으로 불변.
- 따라서 **다수결 점수는 "정답"이 아니라 "진영 구성의 산물"**이다.

### 3.4 변하지 않은 것 = 진짜 신호: 만장일치
벤더 구성과 무관하게 동일했던 **만장일치 7개**:
- `S6437` 하드코딩 시크릿 ×2, `S5122` TLS/CORS ×2, `S4684` 일부(OwnerRest:66 등) → **만장일치 TP** (진짜 결함)
- `S5841` 테스트 fail-fast → **만장일치 FP** (진짜 오탐)
- 분열된 13개는 거의 전부 `S4684`(persistent entity를 폼 파라미터로 — `setDisallowedFields` 부분 완화된 **회색지대 룰**).

---

## 4. 결론 및 운영 원칙

### 4.1 FP 판정 요동 (동일 20개)
| 방식 | FP |
|---|---:|
| Full E (opus judge) | 0 |
| Full E (sonnet judge) | 2 |
| 단일 패스 (sonnet) | 4 |
| 다수결 (C+N+DeepSeek) | 10 |
| 다수결 (C+N+Mistral) | 11 |

→ **단일 모델도, 단순 다수결도 FP 정답을 주지 못한다.**

### 4.2 운영 원칙
1. **만장일치(전 벤더 합의)만 자동 신뢰** — TP는 수정 대상, FP는 억제 대상. 이 신호는 벤더 구성과 무관하게 안정적이다.
2. **분열 항목은 사람 에스컬레이션** — 특히 회색지대 룰(`S4684`처럼 부분 완화된 패턴). 다수결 자동화는 상관된 벤더 편향에 휘둘리므로 피한다.
3. **크로스벤더의 실익은 "다수결 점수"가 아니라 "만장일치 게이트"와 "fix 품질 리뷰"**(opus가 sonnet보다 약한 fix를 더 잡아냄)에 있다.
4. 진짜 독립성을 원하면 **서로 다른 진영**(예: Anthropic + 비-Anthropic + 가능하면 Google/OpenAI를 외부 워크플로로)을 섞되, 같은 진영 모델 추가는 가중치만 늘릴 뿐 정보량을 늘리지 않는다.

### 4.3 보존 상태
- 원본 `~/github_spring-petclinic/spring-petclinic`의 `.java`: 무변경.
- 원격 서버 spring-petclinic 측정값: 재스캔하지 않음 → 무변경.
- 모든 fix는 worktree(`triage-e-experiment`)에 격리.

---

## 부록 A — 보조 스크립트
- `orchestrator/triage_only.py` — read-only FP triage 러너(`--review`로 FP 사후 재검토, `--judge-type/--judge-model` 오버라이드).
- `orchestrator/triage_e.py` — full strategy E 러너(worktree 격리 실행용).

## 부록 B — config 정리
- `orchestrator/config-remote-review.yml` 삭제(C vs D 비교 실험의 잔재, 운영 기본값이 `triage_review`로 이동하며 잉여화).
- `orchestrator/config-remote.yml`에 judge 분리 옵션 설명·예시(gemini-cli/claude opus/bedrock) 주석 보강. **환경 의존적 judge 값은 origin 기본값으로 박지 않는다**(미설치 환경에서 실행 실패).
