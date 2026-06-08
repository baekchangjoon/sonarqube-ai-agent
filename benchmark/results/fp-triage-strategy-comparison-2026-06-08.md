한국어 | **[English](fp-triage-strategy-comparison-2026-06-08.en.md)**

# FP 트리아지 벤치마크 — 전략 C/D/E 비교 (2026-06-08, 5·6·7차)

오탐 평가(`assessment.strategy`)의 세 가지 전략을 **동일 조건**(judge=opus,
fixer=sonnet, `context_lines: 30`, `full_file_max_lines: 150`,
`include_rule_docs: true`)에서 같은 두 코퍼스(fp 32이슈 전부 오탐 /
tp 24이슈 전부 실결함)로 비교했다. 유일한 변수는 **전략**이다.

## 세 전략의 구조

| 전략 | 패스 구성 | FP 판정 주체 | 검토(리뷰) |
|---|---|---|---|
| **C** `triage` (5차) | ① judge 판정(FP→skip) → ② fixer가 비-skip 수정 | judge (opus) | 없음 |
| **D** `review` (6차) | ① fixer가 수정 또는 FP-escape → ② judge가 결과 리뷰 | **fixer (sonnet)** | judge (opus) |
| **E** `triage_review` (7차) | ① judge 판정(FP→skip) → ② fixer가 TP만 수정 → ③ judge가 각 결과 리뷰 | judge (opus) | judge (opus) |

핵심 차이는 **"누가 FP를 판정하는가"**다. C·E는 독립 judge(opus)가,
D는 코드를 고치러 들어간 fixer(sonnet)가 판정한다.

## 용어

judge의 "양성 판정" = "오탐이다(skip)"로 놓은 혼동 행렬 기준
([3차 문서](fp-triage-no-leak-2026-06-07.md) 정의 계승):

- **재현율(recall)** = 옳은 skip / 실제 오탐 32 — 있는 오탐을 얼마나
  빠짐없이 거르는가. 낮으면 멀쩡한 코드가 수정된다.
- **실결함 오escape** = 실결함을 오탐으로 잘못 판정해 skip한 수 / 24 —
  낮을수록 좋다. 이 시스템 최악의 실패(결함 잔존).

## 결과

| 전략 | 재현율 (fp skip/32) | 실결함 오escape (tp/24) | tp 수정 검증 | 비용 (fp+tp) | 리뷰어 안전 플래그 |
|---|---|---|---|---|---|
| **C** (5차) | 25 = **78.1%** | 1 | 23/24 | **$12.48** | — (검토 없음) |
| **D** (6차) | 19 = 59.4% | **2** | 18/24 | $20.21 | DISAGREE 1 / 무력* |
| **E** (7차) | 25 = **78.1%** | **0** ✅ | 20/24 | $27.59 | DISAGREE 5 + INAPPROPRIATE 2 |

\* D의 tp 오escape 2건(S6437 하드코딩 비밀번호: OrderRepository@18,
TlsClientFactory@26)을 리뷰어가 **둘 다 AGREE_FALSE_POSITIVE로 추인**
(0.82, 0.90) — 잘못된 escape를 한 건도 거르지 못했다.

## 해석

1. **D의 재현율 붕괴(78→59%)의 원인은 FP 판정 주체였다.** D에서는
   "고치라"는 임무를 받은 fixer가 1차 판정을 겸하므로 fix 쪽으로
   기운다. C에서 안정적으로 걸러지던 S107(Builder 생성자), S2189(데몬
   루프), S2447(3-상태 Boolean), S6213, S1186까지 D는 멀쩡한 코드로
   수정했다.

2. **E가 그 결함을 직접 제거했다.** FP 판정을 fixer에서 독립 judge로
   되돌리자 **재현율이 C와 동일(78.1%)하게 복원**됐다. E는 본질적으로
   "C의 판정 + 사후 리뷰"다.

3. **정밀도(실결함 보존)는 E가 최고(오escape 0).** D가 FP로 흘려보낸
   S6437 하드코딩 비밀번호 2건을 E의 패스 1(opus triage)이 전부 TP로
   잡았다. E를 설계한 직접적 목표가 달성됐다.

4. **같은 opus 리뷰어가 D에선 무력, E에선 작동 — 차이는 입력의 질.**
   D의 리뷰어는 fix로 기운 fixer의 결과를 보고 추인했고(잘못된 escape
   2/2 통과), E의 리뷰어는 독립 triage가 거른 결과를 검토해 FP skip
   25건 중 5건을 DISAGREE, 수정 26건 중 2건을 INAPPROPRIATE로 플래깅해
   사람 재검토 큐로 회부했다. 리뷰는 "무엇을 리뷰하느냐"에 좌우된다.

5. **E의 부수 효과 — 검증 전 불량 수정 예고.** tp에서 검증 실패한
   수정 4건(fixer의 컴파일/불완전 수정, 전략 무관) 중 1건을 E의 패스 3이
   재스캔 전에 INAPPROPRIATE(0.62)로 이미 플래깅했다.

6. **비용은 E가 최고($27.59, C의 2.2배).** FP는 2패스(판정+리뷰), TP는
   3패스라 fp-corpus(전부 오탐)에서 리뷰 패스가 32번 다 돈다. 정밀도·
   안전이 비용보다 중요한 운영(보안 결함 잔존이 치명적)에서 정당화된다.

## 결론 — 운영 기본값을 E로

| 우선순위 | 권장 전략 |
|---|---|
| 정밀도·안전 최우선 (보안 결함 잔존 불허) | **E** `triage_review` ← 운영 기본값 |
| 비용 최소·검토 불요 | C `triage` |
| (이 코퍼스에선 권장 안 함) | D `review` — 재현율·정밀도·검토 모두 열위 |

D는 "자기 평가 편향 회피"를 의도했으나, FP 판정까지 fixer에 맡긴
설계 때문에 그 의도가 무너졌다. E는 판정을 독립시키고 리뷰를 더해
D의 의도(독립 검토)를 실제로 달성한다.

## 한계

- judge=opus 단일 축. judge=sonnet 일반화는 CLI 안정성 확보 후 보류
  (홀딩). 모델 격차가 전략 우열을 바꾸지는 않을 것으로 보이나 미검증.
- 동일 코퍼스 1회 실행 — run 간 ±1~2건 노이즈 가능. 단 C·E의 재현율
  완전 일치(25/25)와 D의 명확한 하락(19)은 노이즈로 설명되지 않는다.
- tp 수정 미검증 4건은 fixer 품질 문제로 전략 비교와 독립적이다.

### 재현 방법

```bash
# strategy: triage|review|triage_review, judge_model: opus
cd orchestrator && python3 -m src.main --config <cfg> pr-premerge \
  --repo dummy/bench --pr-number <N> --project-dir <corpus 사본> --cleanup
```
