"""Aggregate fp/tp-triage benchmark results into a markdown report.

Usage: python fp_benchmark_report.py result-*.json > report.md

Each result file is {"set", "fixer_model", "judge_model",
"fp": <ModeResult>, "tp": <ModeResult>} — fp run on benchmark/fp-corpus
(all issues false positives), tp run on benchmark/tp-corpus (all issues
real defects).
"""
import json
import sys
from datetime import date

GROUND_TRUTH_FP = 32  # benchmark/fp-corpus: every issue is a false positive
GROUND_TRUTH_TP = 24  # benchmark/tp-corpus: every issue is a real defect

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


def run_cost(run, fixer_model):
    cost = run.get("llm_cost_usd")
    if cost:
        return cost, False
    return estimate(fixer_model, run["llm_input_tokens"],
                    run["llm_output_tokens"]), True


def main(paths):
    rows = []
    for path in sorted(paths):
        r = json.load(open(path))
        fp, tp = r["fp"], r["tp"]
        correct_skips = fp["issues_skipped_as_fp"]
        wrong_skips = tp["issues_skipped_as_fp"]
        recall = correct_skips / fp["issues_found"] * 100 \
            if fp["issues_found"] else 0.0
        total_skips = correct_skips + wrong_skips
        precision = correct_skips / total_skips * 100 if total_skips else None
        fp_cost, fp_est = run_cost(fp, r["fixer_model"])
        tp_cost, tp_est = run_cost(tp, r["fixer_model"])
        cost = fp_cost + tp_cost if None not in (fp_cost, tp_cost) else None
        rows.append({**r, "recall": recall, "precision": precision,
                     "correct_skips": correct_skips,
                     "wrong_skips": wrong_skips, "cost": cost,
                     "estimated": fp_est or tp_est})

    print(f"# FP 트리아지 벤치마크 — 모델 세트 비교 ({date.today()})")
    print()
    print(f"- fp-corpus: 이슈 {GROUND_TRUTH_FP}개, 전부 ground truth = "
          f"FALSE_POSITIVE — 스킵이 정답 (재현율)")
    print(f"- tp-corpus: 이슈 {GROUND_TRUTH_TP}개, 전부 ground truth = "
          f"TRUE_POSITIVE — 스킵이 오판 (놓친 실결함)")
    print("- 파이프라인: 코퍼스별 스캔 → LLM 판정(오탐이면 스킵) → "
          "미스킵분 수정 → 재스캔 검증 (`assessment.strategy: triage`)")
    print(f"- 이상적 결과: fp에서 {GROUND_TRUTH_FP} 스킵·수정 0, "
          f"tp에서 0 스킵·수정 {GROUND_TRUTH_TP}")
    print()
    print("| 세트 (수정/판정) | 오탐 검출 (재현율) | 실결함 오스킵 | 정밀도 "
          "| 수정 시도 (fp/tp) | 토큰 (in/out) | 비용 |")
    print("|---|---|---|---|---|---|---|")
    for r in sorted(rows, key=lambda x: -x["recall"]):
        prec = f"{r['precision']:.0f}%" if r["precision"] is not None \
            else "n/a"
        tokens_in = r["fp"]["llm_input_tokens"] + r["tp"]["llm_input_tokens"]
        tokens_out = (r["fp"]["llm_output_tokens"]
                      + r["tp"]["llm_output_tokens"])
        print(f"| {r['set']} "
              f"| {r['correct_skips']}/{r['fp']['issues_found']} "
              f"({r['recall']:.0f}%) "
              f"| {r['wrong_skips']}/{r['tp']['issues_found']} "
              f"| {prec} "
              f"| {r['fp']['fixes_attempted']} / "
              f"{r['tp']['fixes_attempted']} "
              f"| {tokens_in:,} / {tokens_out:,} "
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
    print("주: 재현율 미스(오탐을 수정 단계로)는 멀쩡한 코드 변경 + 수정 "
          "비용으로, 정밀도 미스(실결함을 스킵)는 결함 잔존으로 이어진다 — "
          "후자가 더 위험하다.")


if __name__ == "__main__":
    main(sys.argv[1:])
