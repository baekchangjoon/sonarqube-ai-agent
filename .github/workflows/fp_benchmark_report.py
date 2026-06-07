"""Aggregate fp-triage benchmark results into a markdown report.

Usage: python fp_benchmark_report.py result-*.json > report.md
"""
import json
import sys
from datetime import date

GROUND_TRUTH_FP = 32  # benchmark/fp-corpus: every issue is a false positive

# USD per 1M tokens (input, output) — fallback when the CLI reports no
# cost (e.g. Claude Code on Bedrock). Cache-read tokens are charged as
# normal input here, so the estimate is an upper bound.
PRICES = {
    "opus-4": (5.00, 25.00),
    "sonnet-4": (3.00, 15.00),
    "haiku-4": (1.00, 5.00),
}


def estimate(model, tokens_in, tokens_out):
    for key, (pi, po) in PRICES.items():
        if key in model:
            return (tokens_in * pi + tokens_out * po) / 1_000_000
    return None


def fmt_cost(value, estimated=False):
    if value is None:
        return "n/a"
    return f"${value:.4f}" + ("\\*" if estimated else "")


def main(paths):
    rows = []
    for path in sorted(paths):
        r = json.load(open(path))
        skipped = r["issues_skipped_as_fp"]
        found = r["issues_found"]
        recall = skipped / found * 100 if found else 0.0
        cost = r.get("llm_cost_usd")
        estimated = False
        if not cost:  # CLI on Bedrock may report 0 — estimate from tokens
            cost = estimate(r["fixer_model"], r["llm_input_tokens"],
                            r["llm_output_tokens"])
            estimated = True
        rows.append({**r, "recall": recall, "cost": cost,
                     "estimated": estimated})

    print(f"# FP 트리아지 벤치마크 — 모델 세트 비교 ({date.today()})")
    print()
    print(f"- 대상: `benchmark/fp-corpus` — 이슈 {GROUND_TRUTH_FP}개, "
          f"전부 ground truth = FALSE_POSITIVE")
    print("- 파이프라인: 스캔 → LLM 판정(오탐이면 스킵) → 미스킵분 수정 → "
          "재스캔 검증 (`assessment.strategy: triage`)")
    print("- 이상적 결과: 오탐 검출 32/32, 수정 0건 — 판정 비용만 발생")
    print()
    print("| 세트 (수정/판정) | 오탐 검출 | 재현율 | 수정 시도 | 토큰 (in/out) | 비용 |")
    print("|---|---|---|---|---|---|")
    for r in sorted(rows, key=lambda x: -x["recall"]):
        print(f"| {r['set']} | {r['issues_skipped_as_fp']}/{r['issues_found']} "
              f"| {r['recall']:.0f}% | {r['fixes_attempted']} "
              f"| {r['llm_input_tokens']:,} / {r['llm_output_tokens']:,} "
              f"| {fmt_cost(r['cost'], r['estimated'])} |")
    print()
    print("| 세트 | 수정 모델 | 판정 모델 |")
    print("|---|---|---|")
    for r in rows:
        print(f"| {r['set']} | `{r['fixer_model']}` | `{r['judge_model']}` |")
    print()
    print("\\* = CLI가 비용을 보고하지 않아 토큰×단가표로 추정한 값 "
          "(캐시 읽기를 일반 입력 단가로 계산한 상한치).")
    print()
    print("주: 오탐을 놓치면(미스킵) 그 이슈는 수정 단계로 넘어가 "
          "수정 비용이 추가되고, 멀쩡한 코드가 변경된다 — 재현율과 비용은 "
          "독립 지표가 아니라 연결되어 있다.")


if __name__ == "__main__":
    main(sys.argv[1:])
