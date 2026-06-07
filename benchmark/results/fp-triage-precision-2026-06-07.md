한국어 | **[English](fp-triage-precision-2026-06-07.en.md)**

# FP 트리아지 벤치마크 — 재현율 + 정밀도 (2026-06-07, 2차)

[1차(재현율만)](fp-triage-comparison-2026-06-07.md)에 이어, 새로 추가된
[tp-corpus](../docs/tp-corpus-manifest.md)(실결함 24개, fp-corpus 룰 미러링)로
**정밀도(실결함을 오탐으로 오판해 스킵하는 비율)** 를 함께 측정했다.

- fp-corpus: 이슈 32개, 전부 ground truth = FALSE_POSITIVE — 스킵이 정답 (재현율)
- tp-corpus: 이슈 24개, 전부 ground truth = TRUE_POSITIVE — 스킵이 오판 (놓친 실결함)
- 파이프라인: 코퍼스별 스캔 → LLM 판정(오탐이면 스킵) → 미스킵분 수정 → 재스캔 검증 (`assessment.strategy: triage`)
- 이상적 결과: fp에서 32 스킵·수정 0, tp에서 0 스킵·수정 24

| 세트 (수정/판정) | 오탐 검출 (재현율) | 실결함 오스킵 | 정밀도 | 수정 시도 (fp/tp) | 토큰 (in/out) | 비용 |
|---|---|---|---|---|---|---|
| sonnet-opus | 31/32 (97%) | 0/24 | 100% | 1 / 24 | 1,748,136 / 31,348 | $1.9659 |
| opus-opus | 30/32 (94%) | 0/24 | 100% | 2 / 24 | 1,952,565 / 32,746 | $3.1621 |
| haiku-sonnet | 26/32 (81%) | 0/24 | 100% | 6 / 24 | 3,303,868 / 47,344 | $1.1294 |

| 세트 | 수정 모델 | 판정 모델 |
|---|---|---|
| sonnet-opus | `global.anthropic.claude-sonnet-4-6` | `global.anthropic.claude-opus-4-6-v1` |
| opus-opus | `global.anthropic.claude-opus-4-6-v1` | `global.anthropic.claude-opus-4-6-v1` |
| haiku-sonnet | `global.anthropic.claude-haiku-4-5-20251001-v1:0` | `global.anthropic.claude-sonnet-4-6` |

---

## 관찰 (run [27080844380](https://github.com/baekchangjoon/sonarqube-ai-agent/actions/runs/27080844380), 2026-06-07)

### 세트별 재현율 미스 (수정 단계로 넘어간 오탐)

| 세트 | 미스 | 내역 |
|---|---|---|
| sonnet-opus | 1 | Fp16 S2386(관례상 불변 배열) |
| opus-opus | 2 | Fp13 S3011, Fp16 S2386 |
| haiku-sonnet | 6 | Fp01·Fp02 S3011, Fp08 S1481+S1854(GC 핀 참조), Fp15 S2142, Fp16 S2386 |

### 해석

1. **정밀도 100% — 세 세트 모두 실결함 24개를 한 건도 스킵하지 않았다.**
   "실결함을 오탐으로 오판해 놓치는" 위험(이 시스템의 최악 실패 모드)은
   이번 측정에서 관찰되지 않았다. 단, 코퍼스 설계의 비대칭에 유의:
   fp-corpus는 Javadoc에 오탐 근거가 명시돼 있고 tp-corpus는 중립
   주석만 있다 — "근거가 안 보이면 TRUE_POSITIVE" 방향의 보수적
   판정이 작동한다는 신호로, 안전한 쪽으로 기울어진 바이어스다.
2. **수정 성공률도 24/24** — 세 세트 모두 tp-corpus의 실결함 전부를
   수정하고 재스캔 검증까지 통과했다. 트리아지가 올바르게 통과시킨
   이슈는 fixer가 처리한다는 파이프라인 전체 그림이 닫혔다.
3. **Fp16 S2386(관례상 읽기 전용 배열)은 이번에도 전 세트 공통 미스** —
   1차 run과 합치면 6/6 세트가 놓친 유일한 사례로, 판정 모델이 아니라
   사례 자체가 회색지대라는 해석이 굳어진다. 반면 1차에서 공통 미스였던
   Fp15(협조적 종료 플래그)는 이번에 Opus judge 두 세트가 모두 맞혔다.
4. **run 간 비결정성 재확인** — 같은 Opus judge가 1차 30·28/32 →
   2차 31·30/32. ±2/32 수준의 노이즈라는 1차 관찰과 일치하며,
   Opus(94~97%) vs Sonnet(75~81%) judge 격차는 노이즈보다 크다.
5. **FP 스크리닝 비용은 싸고, 수정 비용이 지배한다** — sonnet-opus
   기준 fp-corpus 런 $0.40 vs tp-corpus 런(수정 24건) $1.56.
   트리아지가 오탐을 잘 거를수록 전체 비용이 내려간다는 1차 함의가
   정밀도 데이터로도 유지된다.

### 재현 방법

GitHub Actions → **FP Triage Benchmark** workflow_dispatch 수동 실행.
세트 구성은 [`fp-triage-benchmark.yml`](../../.github/workflows/fp-triage-benchmark.yml)의 매트릭스 참조.
