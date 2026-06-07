한국어 | **[English](fp-triage-no-leak-2026-06-07.en.md)**

# FP 트리아지 벤치마크 — 답안지 격리 후 (2026-06-07, 3차)

[2차](fp-triage-precision-2026-06-07.md)까지의 fp-corpus는 파일 Javadoc에
`expected: java:SXXXX`, "Why it is a false positive: ..." 식으로 **정답이
파일 안에** 적혀 있었다. 3차는 코퍼스를 중립화한 뒤
([상세](../docs/fp-corpus-manifest.md)) 동일 매트릭스를 재실행했다:

- 주석을 실코드 스타일의 **의도 서술**로 재작성 (판정 단서는 유지, 정답 제거)
- `com.example.fp.Fp08KeepAliveRef` → `com.example.core.WeakRegistryScanner`
  중립 명명 (judge 프롬프트에 파일 경로가 포함되므로 이름도 힌트였음)
- 답안지(manifest)를 코퍼스 디렉터리 밖 `benchmark/docs/`로 격리

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
4. **미스 8건의 성격**: S3011×3(setAccessible)은 룰이 "행위 자체"를
   경고하므로 리플렉션이 설계여도 TP로 보는 판정이 방어 가능하다 —
   ground truth 라벨 자체가 논쟁적인 회색지대. 반면 Fp08(S1854)·
   Fp15·Fp22는 주석에 근거가 명시돼 있는데도 놓쳤다 — 의도 주석을
   "변명"이 아니라 "증거"로 채택하는 기준이 judge에 없다는 신호.
5. **운영 함의**: 답안지 없는 현실 조건에서 자동 FP 스킵의 상한은
   이 코퍼스 기준 ~75%다. 나머지는 사람 리뷰로 남는다 — 그래도
   방향이 보수적(오스킵 0)이므로 "자동 스킵 + 잔여 사람 확인" 운영이
   안전하게 성립한다.

한계: 3차 변화에는 주석 재작성과 명명 중립화가 함께 들어가 두 효과를
분리할 수 없다. 또한 동일 코퍼스 1회 실행이므로 ±1~2건 노이즈 가능성은
남는다(단, 세 세트 완전 일치가 노이즈 가설을 약화시킨다).

### 재현 방법

GitHub Actions → **FP Triage Benchmark** workflow_dispatch 수동 실행.
