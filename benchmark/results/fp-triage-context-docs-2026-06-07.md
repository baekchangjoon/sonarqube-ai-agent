한국어 | **[English](fp-triage-context-docs-2026-06-07.en.md)**

# FP 트리아지 벤치마크 — 컨텍스트 확장 + 룰 문서 주입 (2026-06-07, 4·5차)

> **실행 전략**: 이 벤치마크는 `assessment.strategy: "triage"`(전략 C — 수정 **전** 사전 스크리닝 판정)로 실행되었다. 운영 기본값은 이후 전략 D(`review`, 수정 시도 → FP escape → 독립 리뷰)로 변경되었으며, D의 성능은 본 문서의 수치에 포함되지 않는다.

[3차](fp-triage-no-leak-2026-06-07.md)에서 답안지 격리 후 세 judge가
재현율 75%로 수렴했다. 4·5차는 judge에게 주는 **입력을 늘리면** 그
상한이 움직이는지 측정했다. 두 세트(judge=opus / judge=sonnet, fixer는
모두 sonnet) × 두 코퍼스(fp 32이슈 / tp 24이슈), 로컬 실행.

| 차수 | 변경 | 설정 |
|---|---|---|
| 4차 | 컨텍스트 윈도우 ±5 → **±30줄** | `assessment.context_lines: 30` |
| 5차 | + **150줄 이하 파일은 전체 주입**, **SonarQube 룰 문서 주입** (fixer엔 how_to_fix, judge엔 Exceptions 소절) | `full_file_max_lines: 150`, `include_rule_docs: true` |

코퍼스 파일은 전부 150줄 이하이므로 5차의 judge는 사실상 **파일 전문 +
룰 Exceptions 문서**를 받았다 — 단발 호출 judge가 받을 수 있는 입력의
실질적 상한.

## 결과

| 세트 | 재현율 3차(±5) | 4차(±30) | 5차(전문+문서) | 실결함 오스킵 4차 | 5차 | 비용 4차(fp+tp) | 5차 |
|---|---|---|---|---|---|---|---|
| judge=opus | 75% | 24/32 (**75%**) | 25/32 (**78.1%**) | 0/24 (100%) | 1/24 (95.8%)* | $13.61 | $12.48 |
| judge=sonnet | 75% | 24/32 (**75%**) | 23/32 (**71.9%**) | 0/24 (100%) | 0/24 (**100%**) | $7.14 | $7.34 |

\* 아티팩트 — 아래 "발견한 결함 2건" 참조. judge의 추론 오류가 아니다.

### 케이스 단위 변화 (fp-corpus 32이슈)

4차 미스 8건은 두 judge가 **완전히 동일**했다 (3차와 7건 겹침):
S3011×3, S6213, S1481, S1854(WeakRegistryScanner), S2142, S2386.

| 케이스 | 룰 | 4차 | 5차 opus | 5차 sonnet | 메모 |
|---|---|---|---|---|---|
| LatencyTracker | S6213 | 미스 | **잡음** | **잡음** | 파일 전문에서 record 패턴 + "Public API" Javadoc 전체가 보임 |
| OrderPayload@20 | S3011 | 미스 | **잡음** | 미스 | 리플렉션 직렬화 의도가 전문에서 명확 |
| ChecksumJob | S1854 | 잡음 | 잡음 (0.97, **"documented S1854 exception" 인용**) | **미스(신규)** | opus는 주입된 Exceptions 문서를 판정 근거로 직접 인용 |
| ProgressListeners@19 | S1186 | 잡음 | **미스(신규)** | 잡음 | 시행간 변동 |
| EventHandler | S1172 | 잡음 | 잡음 | **미스(신규)** | 시행간 변동 |
| SettingsIntrospector·CommandDispatcher S3011, WeakRegistryScanner S1481+S1854, PollingWorker S2142, SourceFileTypes S2386 | — | 미스 | 미스 | 미스 | **불변 코어** |

## 해석

1. **컨텍스트 확장의 한계효용은 0에 가깝다.** ±5→±30(4차)은 변화 없음
   (75%→75%, 미스 8건 동일). 전문+문서(5차)도 ±1~2건 — 시행간 노이즈와
   구분이 어렵다. 3차에서 "단서 미전달(윈도우 밖)"로 분류했던 S3011
   3건 중 2건은 컨텍스트를 다 줘도 안 뒤집혔다 — 병목은 입력이 아니라
   **judge의 채택 기준**(룰 단위 사전 확신 > 코드의 의도 증거)이다.
2. **룰 문서 주입의 효과는 정밀하지만 좁다.** 놓친 8건의 룰 중
   Exceptions 소절이 있는 것은 S1854 하나뿐이고, 그 내용("초기화
   -1/0/1/null/true/false는 무시")도 해당 케이스(GC 해제용 재대입)와
   정확히는 무관하다. opus는 그래도 이를 지지 근거로 인용하며 확신을
   높였다(0.97~0.99). 효과를 보려면 Exceptions가 실제로 있는 룰
   (S1068, S1192, S1172 등)의 경계 케이스가 코퍼스에 더 필요하다.
3. **불변 코어 6건의 공통점**: setAccessible(S3011), keep-alive 변수
   (S1481/S1854), 인터럽트 프로토콜(S2142), 가변 public 배열(S2386) —
   전부 "룰이 경고하는 행위 자체는 실재하고, 무해성은 설계 의도에서만
   나오는" 케이스다. 단발 judge가 코드+문서만으로 뒤집기 가장 어려운
   부류이며, ground truth 라벨 자체가 회색지대인 것도 일부 겹친다.
4. **judge 모델 간 격차가 다시 벌어졌다** — 3·4차의 "완전 동일 수렴"이
   5차에서 깨졌다(opus 25 vs sonnet 23, 미스 집합도 상이). 입력이
   풍부해질수록 활용 능력 차이가 다시 드러난다는, 2차(답안지) 때와
   일관된 패턴.
5. **비용은 중립** (4차 합 $20.76 → 5차 $19.82). 파일 전문을 프롬프트에
   넣자 judge가 Read 툴콜로 파일을 다시 읽는 턴이 줄어 상쇄됐다.

## 벤치마크가 발견한 파이프라인 결함 2건

5차 1차 시도(폐기)에서 tp-corpus 정밀도가 6/24 급락하며 드러났다:

1. **triage 컨텍스트의 로컬 파일 오염 (수정 완료)** — 같은 파일에
   이슈가 여러 개면 앞 이슈의 fix가 로컬 파일을 바꾼 뒤 다음 이슈를
   triage한다. full-file 컨텍스트를 로컬에서 읽던 초기 구현은 judge가
   "이미 고쳐진 코드"를 보고 FP로 오판했다 (예: "password is read from
   System.getenv, not hardcoded"). 이슈의 라인 번호는 스캔 시점 기준이므로
   **스캔 스냅샷(`/api/sources/raw`)을 우선**하고 로컬은 PR 신규 파일
   폴백으로만 쓰도록 수정 (`SonarQubeClient.get_raw_source`).
2. **하네스 judge의 Read 우회 (잔존, 문서화)** — 프롬프트 컨텍스트를
   스냅샷으로 고정해도 claude-code judge는 Read 툴로 로컬(수정된)
   파일을 직접 읽을 수 있다. 5차 opus-tp의 유일한 오스킵(S2095@24)이
   이 경로다: 같은 파일 S2095@23의 fix가 try-with-resources로 감싼 뒤라
   judge가 "이미 닫힌다"고 판정했다. **운영상으로는 무해**(결함은 실제
   해결됐고 재스캔이 확인)하지만 벤치마크 지표는 감점된다. 구조적
   해결은 triage-전부-후-fix 순서 변경 또는 judge 입력의 완전한 스냅샷
   고정 — 6차 후보.

## 운영 함의

- 자동 FP 스킵의 상한은 입력 확장으로는 ~75±3%에서 못 벗어난다.
  다음 지렛대는 입력이 아니라 **판정 절차**다: 의도 주석을 증거로
  채택하는 명시 기준, 멀티턴 조사 허용, 또는 룰별 특화 프롬프트.
- 방향은 보수적으로 유지된다(실결함 오스킵 0~1, 그 1건도 이미 수정된
  결함). "자동 스킵 + 잔여 사람 확인" 운영은 여전히 성립.

### 재현 방법

```bash
# config: assessment.context_lines=30, full_file_max_lines=150,
#         include_rule_docs=true; judge_model: opus|sonnet
cd orchestrator && python3 -m src.main --config <cfg> pr-premerge \
  --repo dummy/bench --pr-number <N> --project-dir <corpus 사본> --cleanup
```
