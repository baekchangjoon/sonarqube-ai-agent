**[한국어](fp-triage-precision-2026-06-07.md)** | English

# FP Triage Benchmark — Recall + Precision (2026-06-07, round 2)

> **Strategy note**: this benchmark ran with `assessment.strategy: "triage"` (option C — **pre-fix** screening judgment). The operational default has since moved to option D (`review`: fix attempt → FP escape → independent review), whose performance is not covered by these numbers.

Following [round 1 (recall only)](fp-triage-comparison-2026-06-07.en.md),
this run adds the new [tp-corpus](../docs/tp-corpus-manifest.en.md) (24 real
defects mirroring the fp-corpus rules) to also measure **precision (how
often real defects are wrongly skipped as false positives)**.

- fp-corpus: 32 issues, all ground truth = FALSE_POSITIVE — skipping is correct (recall)
- tp-corpus: 24 issues, all ground truth = TRUE_POSITIVE — skipping is a miss (missed real defect)
- Pipeline: per-corpus scan → LLM triage (skip if FP) → fix the rest → re-scan verification (`assessment.strategy: triage`)
- Ideal outcome: 32 skips / 0 fixes on fp, 0 skips / 24 fixes on tp

| Set (fixer/judge) | FP detected (recall) | Real defects wrongly skipped | Precision | Fix attempts (fp/tp) | Tokens (in/out) | Cost |
|---|---|---|---|---|---|---|
| sonnet-opus | 31/32 (97%) | 0/24 | 100% | 1 / 24 | 1,748,136 / 31,348 | $1.9659 |
| opus-opus | 30/32 (94%) | 0/24 | 100% | 2 / 24 | 1,952,565 / 32,746 | $3.1621 |
| haiku-sonnet | 26/32 (81%) | 0/24 | 100% | 6 / 24 | 3,303,868 / 47,344 | $1.1294 |

| Set | Fixer model | Judge model |
|---|---|---|
| sonnet-opus | `global.anthropic.claude-sonnet-4-6` | `global.anthropic.claude-opus-4-6-v1` |
| opus-opus | `global.anthropic.claude-opus-4-6-v1` | `global.anthropic.claude-opus-4-6-v1` |
| haiku-sonnet | `global.anthropic.claude-haiku-4-5-20251001-v1:0` | `global.anthropic.claude-sonnet-4-6` |

---

## Observations (run [27080844380](https://github.com/baekchangjoon/sonarqube-ai-agent/actions/runs/27080844380), 2026-06-07)

### Recall misses per set (false positives that went on to the fix stage)

| Set | Misses | Detail |
|---|---|---|
| sonnet-opus | 1 | Fp16 S2386 (read-only-by-convention array) |
| opus-opus | 2 | Fp13 S3011, Fp16 S2386 |
| haiku-sonnet | 6 | Fp01·Fp02 S3011, Fp08 S1481+S1854 (GC pin reference), Fp15 S2142, Fp16 S2386 |

### Interpretation

1. **Precision 100% — none of the three sets skipped any of the 24 real
   defects.** The worst failure mode of this system (mislabeling a real
   defect as a false positive and leaving it in the code) was not
   observed in this measurement. One caveat is the corpus asymmetry by
   design: fp-corpus files state their false-positive justification in
   Javadoc while tp-corpus comments are neutral — a signal that the
   judges default to TRUE_POSITIVE when no justification is visible,
   i.e. a bias tilted toward the safe side.
2. **Fix success was also 24/24** — all three sets fixed every real
   defect in tp-corpus and passed re-scan verification. This closes the
   full pipeline picture: issues that triage correctly passes through
   are handled by the fixer.
3. **Fp16 S2386 (read-only-by-convention array) was again missed by
   every set** — combined with round 1, it is the only case missed by
   all 6 set-runs, reinforcing that the case itself is a gray zone
   rather than a judge-model weakness. Conversely Fp15 (cooperative
   shutdown flag), a common miss in round 1, was caught by both Opus
   judge sets this time.
4. **Run-to-run nondeterminism confirmed again** — the same Opus judge
   scored 30·28/32 in round 1 vs 31·30/32 in round 2, consistent with
   the ±2/32 noise estimate; the Opus (94–97%) vs Sonnet (75–81%)
   judge gap remains larger than that noise.
5. **FP screening is cheap; fixing dominates cost** — for sonnet-opus,
   the fp-corpus run cost $0.40 vs $1.56 for the tp-corpus run (24
   fixes). Round 1's implication — the better the triage filters false
   positives, the lower the total cost — holds with precision data too.

### How to reproduce

GitHub Actions → manually dispatch the **FP Triage Benchmark** workflow.
See the matrix in [`fp-triage-benchmark.yml`](../../.github/workflows/fp-triage-benchmark.yml)
for the set configuration.
