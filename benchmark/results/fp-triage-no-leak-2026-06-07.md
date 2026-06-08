한국어 | **[English](fp-triage-no-leak-2026-06-07.en.md)**

# FP 트리아지 벤치마크 — 답안지 격리 후 (2026-06-07, 3차)

> **실행 전략**: 이 벤치마크는 `assessment.strategy: "triage"`(전략 C — 수정 **전** 사전 스크리닝 판정)로 실행되었다. 운영 기본값은 이후 전략 D(`review`, 수정 시도 → FP escape → 독립 리뷰)로 변경되었으며, D의 성능은 본 문서의 수치에 포함되지 않는다.

[2차](fp-triage-precision-2026-06-07.md)까지의 fp-corpus는 파일 Javadoc에
`expected: java:SXXXX`, "Why it is a false positive: ..." 식으로 **정답이
파일 안에** 적혀 있었다. 3차는 코퍼스를 중립화한 뒤
([상세](../docs/fp-corpus-manifest.md)) 동일 매트릭스를 재실행했다:

- 주석을 실코드 스타일의 **의도 서술**로 재작성 (판정 단서는 유지, 정답 제거)
- `com.example.fp.Fp08KeepAliveRef` → `com.example.core.WeakRegistryScanner`
  중립 명명 (judge 프롬프트에 파일 경로가 포함되므로 이름도 힌트였음)
- 답안지(manifest)를 코퍼스 디렉터리 밖 `benchmark/docs/`로 격리

## 용어 — 재현율과 정밀도

judge의 "양성 판정" = **"오탐이다(스킵)"** 로 놓은 혼동 행렬:

| | 실제 오탐 (fp-corpus 32) | 실제 결함 (tp-corpus 24) |
|---|---|---|
| **judge: 오탐(스킵)** | 옳은 스킵 = 24 | **잘못된 스킵 = 0** ← 결함이 코드에 남음 |
| **judge: 결함(수정)** | **놓친 오탐 = 8** ← 멀쩡한 코드 수정 | 옳은 수정 = 24 |

- **재현율(recall)** = 옳은 스킵 / 실제 오탐 전체 = 24/32 = 75% —
  있는 오탐을 얼마나 빠짐없이 잡아내는가. 낮으면 오탐이 수정 단계로
  새어 들어가 멀쩡한 코드가 변경되고 수정 비용이 발생한다.
- **정밀도(precision)** = 옳은 스킵 / 스킵 전체 = 24/24 = 100% —
  스킵 판정을 얼마나 믿을 수 있는가. 낮으면 실결함이 안 고쳐지고
  남는다 (이 시스템의 최악 실패).
- 둘은 트레이드오프 관계다. 실패 비용이 비대칭(결함 잔존 ≫ 불필요
  수정)이므로 이 시스템은 "확신 없으면 결함으로 간주"로 정밀도를
  우선하고 재현율을 양보한다.

## judge는 무엇을 받는가 — 입력 동일성과 결정성

판정 파이프라인의 기계적 사실 (왜 세 세트가 같은 결과인지의 배경):

- judge 입력은 `build_triage_prompt` 템플릿 하나 — 룰 ID, 메시지,
  파일 경로, 라인, 그리고 **이슈 라인 ±5줄(11줄) 소스 컨텍스트**가
  전부다. 같은 코퍼스를 스캔하므로 이슈별 프롬프트는 세 세트에서
  **바이트 단위로 동일**하다. 세트 간 차이는 judge 모델뿐이며,
  opus-opus와 sonnet-opus는 judge가 같은 Opus 4.6이다.
- judge(`bedrock-api`)는 Converse **단발 호출** — 도구 없음, 멀티턴
  없음. 모델이 추가 정보를 요청해도 무시되고 응답 끝의 JSON만
  파싱된다. 프롬프트의 "You may read files for more context" 문구는
  Read 도구가 있는 claude-code judge용으로, bedrock judge에게는
  실행 불가능한 안내다 — 사실상 닫힌 책 시험.
- 샘플링 온도는 기본값 그대로지만, 답안지가 사라지자 각 판정이 결정
  경계에서 멀어져(확실한 TP/FP) 노이즈로 뒤집히지 않게 됐다 —
  1·2차의 run 간 ±2건 변동은 답안지 텍스트가 만든 경계선
  케이스들이었다.

## 결과 (run [27081624183](https://github.com/baekchangjoon/sonarqube-ai-agent/actions/runs/27081624183))

| 세트 (수정/판정) | 재현율 (3차, 격리) | 재현율 (2차, 답안지) | 실결함 오스킵 | 정밀도 | 비용 |
|---|---|---|---|---|---|
| sonnet-opus | 24/32 (**75%**) | 31/32 (97%) | 0/24 | 100% | $2.5210 |
| opus-opus | 24/32 (**75%**) | 30/32 (94%) | 0/24 | 100% | $3.9933 |
| haiku-sonnet | 24/32 (**75%**) | 26/32 (81%) | 0/24 | 100% | $1.2052 |

### 공통 미스 — 세 세트가 **완전히 동일한 8건**을 놓쳤다

| 케이스 | 파일 | 룰 | 주석에 남긴 단서 (그럼에도 TP 판정) |
|---|---|---|---|
| Fp01 | SettingsIntrospector | S3011 | "admin console looks fields up dynamically by name" |
| Fp02 | OrderPayload | S3011 | "serialized field-by-field via reflection (data-binding style)" |
| Fp13 | CommandDispatcher | S3011 | "handlers resolved by naming convention handle&lt;Command&gt;" |
| Fp03 | LatencyTracker | S6213 | "Public API since 1.0" |
| Fp08 | WeakRegistryScanner | S1854 | "strong reference: keeps the key alive..." (같은 줄 S1481은 스킵됨) |
| Fp15 | PollingWorker | S2142 | "interruption = stop request; loop exits on next check" |
| Fp16 | SourceFileTypes | S2386 | "Read-only by convention — do not modify" |
| Fp22 | ProgressListeners | S1186 | "receiving and ignoring events is its job" |

## 해석

1. **답안지 효과 = Opus judge 기준 19~22%p** (94~97% → 75%). 1·2차의
   높은 재현율은 상당 부분 "추론"이 아니라 답안지 "독해"였다.
2. **judge 모델 격차가 사라졌다** — 2차의 Opus(94~97%) vs Sonnet(81%)
   격차는 답안지를 읽고 활용하는 능력 차이였을 가능성이 크다. 정답이
   없어지자 세 judge가 똑같이 75%로 수렴했고, **미스 8건도 완전히
   동일**하다 (run 간 비결정성도 사실상 소멸 — 애매한 단서가 사라지니
   판정이 결정적으로 변했다).
3. **정밀도는 여전히 100%** (실결함 24건 오스킵 0, 수정 24/24 검증).
   의도 주석만으로는 확신이 안 설 때 TP로 기우는 보수적 기본값이
   유지된다 — 놓친 오탐은 수정 비용으로, 놓친 실결함은 0으로.
4. **미스 8건의 실체는 둘로 갈린다** (judge가 실제 받은 ±5줄 윈도우를
   재구성한 결과):
   - **단서 미전달 (3건)** — S3011 세 케이스는 클래스 Javadoc(리플렉션
     설계 근거)이 윈도우 **밖**이라 judge에게 전달조차 안 됐다.
     "주석을 무시했다"가 아니라 "주석을 못 봤다" — 컨텍스트 윈도우의
     구조적 한계. (다만 룰이 setAccessible 행위 자체를 경고하므로
     ground truth 라벨도 논쟁적인 회색지대다.)
   - **단서 전달됐으나 기각 (5건)** — "Public API since 1.0"(S6213),
     GC pin 인라인 주석(S1854), 협조적 종료 주석(S2142), read-only
     주석(S2386), no-op listener Javadoc(S1186)은 윈도우 안에
     있었는데도 TP 판정 — 룰 단위 사전 확신이 의도 주석을 이겼다.
     의도 주석을 "변명"이 아니라 "증거"로 채택하는 기준이 judge에
     없다는 신호.
5. **운영 함의**: 답안지 없는 현실 조건에서 자동 FP 스킵의 상한은
   이 코퍼스 기준 ~75%다. 나머지는 사람 리뷰로 남는다 — 그래도
   방향이 보수적(오스킵 0)이므로 "자동 스킵 + 잔여 사람 확인" 운영이
   안전하게 성립한다.

한계: 3차 변화에는 주석 재작성과 명명 중립화가 함께 들어가 두 효과를
분리할 수 없다. 또한 동일 코퍼스 1회 실행이므로 ±1~2건 노이즈 가능성은
남는다(단, 세 세트 완전 일치가 노이즈 가설을 약화시킨다).

### 재현 방법

GitHub Actions → **FP Triage Benchmark** workflow_dispatch 수동 실행.
