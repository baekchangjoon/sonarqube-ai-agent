**[한국어](fp-triage-strategy-comparison-2026-06-08.md)** | English

# FP Triage Benchmark — Strategies C/D/E Compared (2026-06-08, rounds 5–7)

The three false-positive assessment strategies (`assessment.strategy`)
compared under **identical conditions** (judge=opus, fixer=sonnet,
`context_lines: 30`, `full_file_max_lines: 150`,
`include_rule_docs: true`) on the same two corpora (fp: 32 issues all
false positives / tp: 24 issues all real defects). The only variable is
the **strategy**.

## The three strategies

| Strategy | Passes | Who decides FP | Review |
|---|---|---|---|
| **C** `triage` (r5) | ① judge triages (FP→skip) → ② fixer fixes the rest | judge (opus) | none |
| **D** `review` (r6) | ① fixer fixes or FP-escapes → ② judge reviews outcome | **fixer (sonnet)** | judge (opus) |
| **E** `triage_review` (r7) | ① judge triages (FP→skip) → ② fixer fixes TPs only → ③ judge reviews each outcome | judge (opus) | judge (opus) |

The pivotal difference is **who makes the FP call**. C and E use an
independent judge (opus); D uses the fixer (sonnet) that went in to fix
the code.

## Terminology

Confusion matrix where the judge's "positive" = "it's a false positive
(skip)" (inheriting the [round-3](fp-triage-no-leak-2026-06-07.en.md)
definitions):

- **Recall** = correct skips / 32 real false positives — how completely
  the FPs are filtered. Low recall means clean code gets modified.
- **Real-defect mis-escapes** = real defects wrongly judged FP and
  skipped / 24 — lower is better. The system's worst failure (defect
  left in).

## Results

| Strategy | Recall (fp skip/32) | Real-defect mis-escapes (tp/24) | tp fixes verified | Cost (fp+tp) | Reviewer safety flags |
|---|---|---|---|---|---|
| **C** (r5) | 25 = **78.1%** | 1 | 23/24 | **$12.48** | — (no review) |
| **D** (r6) | 19 = 59.4% | **2** | 18/24 | $20.21 | DISAGREE 1 / ineffective* |
| **E** (r7) | 25 = **78.1%** | **0** ✅ | 20/24 | $27.59 | DISAGREE 5 + INAPPROPRIATE 2 |

\* D's 2 tp mis-escapes (S6437 hardcoded passwords: OrderRepository@18,
TlsClientFactory@26) were **both rubber-stamped AGREE_FALSE_POSITIVE**
by the reviewer (0.82, 0.90) — it caught none of the wrong escapes.

## Interpretation

1. **D's recall collapse (78→59%) was caused by who decides FP.** In D
   the fixer, tasked to "fix it," doubles as the first judge and tilts
   toward fixing. Cases C filtered reliably — S107 (Builder ctor),
   S2189 (daemon loop), S2447 (tri-state Boolean), S6213, S1186 — D
   modified as if they were real.

2. **E removes that defect directly.** Moving the FP decision back from
   the fixer to an independent judge **restored recall to exactly C's
   78.1%**. E is essentially "C's triage + a post-hoc review."

3. **Precision (keeping real defects) is best with E (0 mis-escapes).**
   The 2 S6437 hardcoded-password defects D let through were all caught
   as TP by E's pass 1 (opus triage). E's design goal achieved.

4. **The same opus reviewer is ineffective in D, effective in E — the
   difference is input quality.** D's reviewer saw a fix-leaning
   fixer's output and rubber-stamped it (2/2 wrong escapes passed); E's
   reviewer examined the output of an independent triage and flagged 5
   of 25 FP skips as DISAGREE and 2 of 26 fixes as INAPPROPRIATE,
   routing them to human review. Review quality depends on *what* is
   being reviewed.

5. **E side effect — bad fixes flagged before verification.** Of the 4
   tp fixes that failed verification (fixer compile/incomplete errors,
   strategy-independent), E's pass 3 had already flagged one as
   INAPPROPRIATE (0.62) before the re-scan.

6. **Cost is highest with E ($27.59, 2.2× C).** FPs cost 2 passes
   (triage + review), TPs cost 3, so on the all-FP fp-corpus the review
   pass runs all 32 times. Justified when precision/safety outweighs
   cost (leaving a security defect in is catastrophic).

## Conclusion — operational default is E

| Priority | Recommended strategy |
|---|---|
| Precision/safety first (no security defect left in) | **E** `triage_review` ← operational default |
| Lowest cost, no review needed | C `triage` |
| (not recommended on this corpus) | D `review` — worse recall, precision, and review |

D intended to "avoid self-assessment bias," but by also handing the FP
decision to the fixer it undermined that intent. E independent-izes the
decision and adds review, actually delivering D's intent (independent
review).

## Limitations

- Single axis judge=opus. The judge=sonnet generalization is on hold
  pending CLI stability. A model gap is unlikely to flip the ordering
  but is unverified.
- Single run per corpus — ±1–2 cases of run noise possible. But the
  perfect C/E recall match (25/25) and D's clear drop (19) are not
  explained by noise.
- The 4 unverified tp fixes are a fixer-quality issue, independent of
  the strategy comparison.

### Reproduction

```bash
# strategy: triage|review|triage_review, judge_model: opus
cd orchestrator && python3 -m src.main --config <cfg> pr-premerge \
  --repo dummy/bench --pr-number <N> --project-dir <corpus copy> --cleanup
```
