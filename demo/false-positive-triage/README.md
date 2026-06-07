한국어 | **[English](README.en.md)**

# False Positive Triage Demo — 룰 vs LLM

정적분석 경고의 진위("진짜 결함이냐 오탐이냐")는 **의도와 맥락**의 문제라서
룰 기반 필터로는 양방향으로 틀리고, LLM은 사람 리뷰어처럼 맥락을 읽어
가른다 — 를 3개 사례로 보여주는 발표용 데모입니다.

## 실행

```bash
# 기본: 기록된 LLM 판정 사용 — 의존성 0, 네트워크 불필요 (Java 11+)
java FalsePositiveTriageDemo.java

# 라이브: claude CLI로 실시간 판정 (claude 로그인 필요, 사례당 ~15초)
java FalsePositiveTriageDemo.java --live
```

기대 출력: **규칙 0/3 · LLM 3/3**

## 3개 사례 (실코드: [`cases/`](cases/))

| 사례 | 규칙 | 정답 | 룰이 틀리는 이유 |
|---|---|---|---|
| A. AWS 예제 키, main 경로 | S6418 | **오탐** | 구조·엔트로피가 실키와 동일 → 키워드+엔트로피 룰이 헛경보 |
| B. `sk_live_` 운영 키, test 경로 | S6418 | **실결함** | "test 경로 제외" 룰이 진짜 유출을 통과시킴 |
| C. NPE 경고 + 커스텀 검증기 | S2259 | **오탐** | 분석기는 `Guards.ensureNotNull` 계약을 모름 |

A를 막으려 룰을 비틀면 B가 깨지고, B를 잡으려면 A가 터진다 —
**같은 규칙이 양방향으로 틀리며**, 룰을 정교화해서 풀 수 있는 문제가 아니다.

## 룰 베이스라인 (데모에 구현)

1. test 경로 제외 (`/test/` 포함 시 오탐 처리)
2. 시크릿 키워드 매칭 (`secret|key|token|credential|passw`)
3. 문자열 Shannon 엔트로피 임계값 (≥ 3.0)

## 정직성에 관해

- 기본 모드의 "LLM 판정"은 지어낸 값이 아니라, 데모와 동일한 프롬프트로
  Claude(`claude -p`, sonnet)를 실제 호출해 받은 응답을 기록한 것입니다.
  `--live`로 언제든 재현할 수 있습니다.
- 판정 불능 응답은 보수적으로 "실결함"으로 폴백합니다
  (놓치는 것보다 헛경보가 안전) — 상위 디렉터리 orchestrator의
  `assessment` 전략과 동일한 원칙입니다.
- 사례 B의 키 값은 데모용 더미이며 실키가 아닙니다.
