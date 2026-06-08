**[한국어](fp-triage-comparison-2026-06-07.md)** | English

# FP Triage Benchmark — Model set comparison (2026-06-07)

> **Strategy note**: this benchmark ran with `assessment.strategy: "triage"` (option C — **pre-fix** screening judgment). The operational default has since moved to option D (`review`: fix attempt → FP escape → independent review), whose performance is not covered by these numbers.

- Target: `benchmark/fp-corpus` — 32 issues, all ground truth = FALSE_POSITIVE
- Pipeline: scan → LLM triage (skip if false positive) → fix the non-skipped → rescan verification (`assessment.strategy: triage`)
- Ideal result: false-positive detection 32/32, 0 fixes — only triage cost is incurred

| Set (fix/judge) | FP detection | Recall | Fix attempts | Tokens (in/out) | Cost |
|---|---|---|---|---|---|
| opus-opus | 30/32 | 94% | 2 | 146,722 / 10,840 | $0.5722 |
| sonnet-opus | 28/32 | 88% | 4 | 302,185 / 12,529 | $0.6016 |
| haiku-sonnet | 24/32 | 75% | 8 | 791,667 / 17,175 | $0.4022 |

| Set | Fix model | Judge model |
|---|---|---|
| haiku-sonnet | `global.anthropic.claude-haiku-4-5-20251001-v1:0` | `global.anthropic.claude-sonnet-4-6` |
| opus-opus | `global.anthropic.claude-opus-4-6-v1` | `global.anthropic.claude-opus-4-6-v1` |
| sonnet-opus | `global.anthropic.claude-sonnet-4-6` | `global.anthropic.claude-opus-4-6-v1` |

\* = Since the CLI does not report cost, this is estimated from tokens × the unit-price table (an upper bound that counts cache reads at the normal input unit price).

Note: when a false positive is missed (not skipped), that issue moves on to the fix stage, adding fix cost and changing healthy code — recall and cost are not independent metrics but linked.

---

## Observations (run [27078654913](https://github.com/baekchangjoon/sonarqube-ai-agent/actions/runs/27078654913), 2026-06-07)

### Triage misses per set (false positives that moved to the fix stage)

| Set | Misses | Details |
|---|---|---|
| opus-opus | 2 | Fp15 S2142 (interrupt-flag protocol), Fp16 S2386 (read-only convention array) |
| sonnet-opus | 4 | Fp13 S3011, Fp15 S2142, Fp16 S2386, Fp17 S2068 (public dev default credentials) |
| haiku-sonnet | 8 | Fp01·Fp02·Fp13 S3011, Fp08 S1481+S1854 (GC pin reference), Fp11 S2447 (3-state Boolean), Fp15 S2142, Fp22 S1186 (Null Object) |

### Interpretation

1. **The common misses are the grayest-area cases in the corpus** — Fp15 (flag-based cooperative
   shutdown) and Fp16 (conventionally immutable array) are cases that even human reviewers may
   disagree on, and all/most of the three sets missed them. This should be read as a signal of case
   difficulty rather than a limitation of the judge model.
2. **The gap between judge models is clear** — on the same corpus, Opus judge 94/88% vs Sonnet judge 75%.
   In particular, the Sonnet judge even missed cases "with the rationale spelled out in the comments"
   such as the GC pin reference (Fp08), the 3-state Boolean contract (Fp11), and the Null Object (Fp22).
3. **Even the same judge varies between runs** — opus-opus and sonnet-opus use the same judge model
   (Opus 4.6), yet the misses differed at 2 vs 4 (Fp13·Fp17 flipped depending on the run).
   A single-run figure carries non-determinism noise on the order of ±2/32 (≈6pp) — judgments about
   superiority between models are only valid for differences larger than this noise (e.g. Opus vs Sonnet judge 13–19pp).
4. **Cheapest ≠ best** — haiku-sonnet was cheapest at $0.40, but hidden in that cost is the price of
   "fixing" 8 false positives by changing healthy code (removing reflection field access, removing GC
   pins, etc. — changes that can break runtime behavior). The real cost of one miss is not tokens but
   the wrong code change + the human time needed to filter it out in review.
5. **Triage cost is only a fraction of the total** — in the ideal flow (skip everything), only the
   cost of 32 triages remains. On an Opus-judge basis the triage cost per run is around ~$0.1, and as
   misses grow the fix cost dominates. "A smarter judge actually lowers the total cost" is the core
   implication of this data.

### How to reproduce

GitHub Actions → **FP Triage Benchmark** workflow_dispatch manual run.
For the set composition, see the matrix in [`fp-triage-benchmark.yml`](../../.github/workflows/fp-triage-benchmark.yml).
