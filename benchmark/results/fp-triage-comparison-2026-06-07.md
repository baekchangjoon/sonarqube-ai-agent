한국어 | **[English](fp-triage-comparison-2026-06-07.en.md)**

# FP 트리아지 벤치마크 — 모델 세트 비교 (2026-06-07)

> **실행 전략**: 이 벤치마크는 `assessment.strategy: "triage"`(전략 C — 수정 **전** 사전 스크리닝 판정)로 실행되었다. 운영 기본값은 이후 전략 D(`review`, 수정 시도 → FP escape → 독립 리뷰)로 변경되었으며, D의 성능은 본 문서의 수치에 포함되지 않는다.

- 대상: `benchmark/fp-corpus` — 이슈 32개, 전부 ground truth = FALSE_POSITIVE
- 파이프라인: 스캔 → LLM 판정(오탐이면 스킵) → 미스킵분 수정 → 재스캔 검증 (`assessment.strategy: triage`)
- 이상적 결과: 오탐 검출 32/32, 수정 0건 — 판정 비용만 발생

| 세트 (수정/판정) | 오탐 검출 | 재현율 | 수정 시도 | 토큰 (in/out) | 비용 |
|---|---|---|---|---|---|
| opus-opus | 30/32 | 94% | 2 | 146,722 / 10,840 | $0.5722 |
| sonnet-opus | 28/32 | 88% | 4 | 302,185 / 12,529 | $0.6016 |
| haiku-sonnet | 24/32 | 75% | 8 | 791,667 / 17,175 | $0.4022 |

| 세트 | 수정 모델 | 판정 모델 |
|---|---|---|
| haiku-sonnet | `global.anthropic.claude-haiku-4-5-20251001-v1:0` | `global.anthropic.claude-sonnet-4-6` |
| opus-opus | `global.anthropic.claude-opus-4-6-v1` | `global.anthropic.claude-opus-4-6-v1` |
| sonnet-opus | `global.anthropic.claude-sonnet-4-6` | `global.anthropic.claude-opus-4-6-v1` |

\* = CLI가 비용을 보고하지 않아 토큰×단가표로 추정한 값 (캐시 읽기를 일반 입력 단가로 계산한 상한치).

주: 오탐을 놓치면(미스킵) 그 이슈는 수정 단계로 넘어가 수정 비용이 추가되고, 멀쩡한 코드가 변경된다 — 재현율과 비용은 독립 지표가 아니라 연결되어 있다.

---

## 관찰 (run [27078654913](https://github.com/baekchangjoon/sonarqube-ai-agent/actions/runs/27078654913), 2026-06-07)

### 세트별 판정 미스 (수정 단계로 넘어간 오탐)

| 세트 | 미스 | 내역 |
|---|---|---|
| opus-opus | 2 | Fp15 S2142(인터럽트 플래그 프로토콜), Fp16 S2386(읽기 전용 관례 배열) |
| sonnet-opus | 4 | Fp13 S3011, Fp15 S2142, Fp16 S2386, Fp17 S2068(공개 dev 기본 자격증명) |
| haiku-sonnet | 8 | Fp01·Fp02·Fp13 S3011, Fp08 S1481+S1854(GC 핀 참조), Fp11 S2447(3-상태 Boolean), Fp15 S2142, Fp22 S1186(Null Object) |

### 해석

1. **공통 미스는 코퍼스에서 가장 회색지대인 사례** — Fp15(플래그 기반 협조적 종료)와
   Fp16(관례상 불변 배열)은 사람 리뷰어 사이에서도 갈릴 수 있는 케이스로, 세 세트
   모두/대부분 놓쳤다. 판정 모델의 한계라기보다 사례 난이도의 신호로 해석해야 한다.
2. **판정 모델 간 격차는 명확** — 동일 코퍼스에서 Opus judge 94·88% vs Sonnet judge 75%.
   특히 Sonnet judge는 GC 핀 참조(Fp08), 3-상태 Boolean 계약(Fp11), Null Object(Fp22)
   같은 "주석에 근거가 명시된" 사례까지 놓쳤다.
3. **동일 judge라도 run 간 변동이 있다** — opus-opus와 sonnet-opus는 판정 모델이
   같은데(Opus 4.6) 미스가 2건 vs 4건으로 달랐다 (Fp13·Fp17이 run에 따라 뒤집힘).
   단일 run 수치에는 ±2/32(≈6%p) 수준의 비결정성 노이즈가 있다 — 모델 간 우열
   판단은 이 노이즈보다 큰 차이(예: Opus vs Sonnet judge 13~19%p)에서만 유효하다.
4. **비용 최저 ≠ 최선** — haiku-sonnet이 $0.40으로 가장 쌌지만, 그 비용에는 오탐
   8건을 "수정"하느라 멀쩡한 코드를 바꾼 대가가 숨어 있다 (리플렉션 필드 접근 제거,
   GC 핀 제거 등 — 런타임 동작이 깨질 수 있는 변경). 미스 1건의 진짜 비용은 토큰이
   아니라 잘못된 코드 변경 + 그것을 리뷰로 걸러야 하는 사람의 시간이다.
5. **판정 비용은 전체의 일부에 불과** — 이상적 흐름(전부 스킵)이라면 판정 32회 비용만
   남는다. Opus judge 기준 run당 판정 비용은 ~$0.1 수준이며, 미스가 늘수록 수정
   비용이 지배한다. "더 똑똑한 judge가 오히려 전체 비용을 낮춘다"가 이 데이터의
   핵심 함의다.

### 재현 방법

GitHub Actions → **FP Triage Benchmark** workflow_dispatch 수동 실행.
세트 구성은 [`fp-triage-benchmark.yml`](../../.github/workflows/fp-triage-benchmark.yml)의 매트릭스 참조.
