**[한국어](fp-triage-no-leak-2026-06-07.md)** | English

# FP Triage Benchmark — After Answer-Sheet Isolation (2026-06-07, round 3)

> **Strategy note**: this benchmark ran with `assessment.strategy: "triage"` (option C — **pre-fix** screening judgment). The operational default has since moved to option D (`review`: fix attempt → FP escape → independent review), whose performance is not covered by these numbers.

Through [round 2](fp-triage-precision-2026-06-07.en.md), the fp-corpus
files carried the answer key in-band: Javadoc stating
`expected: java:SXXXX` and "Why it is a false positive: ...". Round 3
re-runs the same matrix after neutralizing the corpus
([details](../docs/fp-corpus-manifest.en.md)):

- Comments rewritten as production-style **intent statements** (judgment
  cues kept, verdicts removed)
- Neutral naming — `com.example.fp.Fp08KeepAliveRef` →
  `com.example.core.WeakRegistryScanner` (the judge prompt includes the
  file path, so names were hints too)
- Answer sheets (manifests) isolated outside the corpus directories
  into `benchmark/docs/`

## Terminology — recall and precision

Confusion matrix with the judge's "positive" verdict defined as
**"this is a false positive (skip)"**:

| | Actually FP (fp-corpus, 32) | Actually a defect (tp-corpus, 24) |
|---|---|---|
| **Judge: FP (skip)** | Correct skips = 24 | **Wrong skips = 0** ← defect stays in the code |
| **Judge: defect (fix)** | **Missed FPs = 8** ← healthy code gets edited | Correct fixes = 24 |

- **Recall** = correct skips / all actual FPs = 24/32 = 75% — how
  exhaustively existing false positives are caught. When low, FPs leak
  into the fix stage: healthy code gets changed and fix cost accrues.
- **Precision** = correct skips / all skips = 24/24 = 100% — how
  trustworthy a skip verdict is. When low, real defects go unfixed
  (this system's worst failure mode).
- The two trade off. Because the failure costs are asymmetric
  (a remaining defect ≫ an unnecessary fix), this system prioritizes
  precision — "treat as a defect unless convinced" — and concedes
  recall.

## What the judge actually receives — input identity and determinism

Mechanical facts of the triage pipeline (background for why all three
sets produced the same result):

- The judge input is a single `build_triage_prompt` template — rule ID,
  message, file path, line, and an **11-line source context (issue line
  ±5)**. All sets scan the same corpus, so per-issue prompts are
  **byte-identical across sets**. The only difference is the judge
  model — and opus-opus and sonnet-opus share the same Opus 4.6 judge.
- The judge (`bedrock-api`) is a **single-shot** Converse call — no
  tools, no multi-turn. If the model asks for more information, the
  request is ignored; only the trailing JSON of the response is parsed.
  The prompt line "You may read files for more context" is written for
  the Read-capable claude-code judge and is unactionable for the
  bedrock judge — effectively a closed-book exam.
- Sampling temperature is at its default, but with the answer sheet
  gone each verdict moved far from the decision boundary (clearly TP or
  clearly FP), so sampling noise no longer flips them — the ±2-issue
  run-to-run variance of rounds 1–2 came from borderline cases the
  in-file answer text created.

## Results (run [27081624183](https://github.com/baekchangjoon/sonarqube-ai-agent/actions/runs/27081624183))

| Set (fixer/judge) | Recall (round 3, isolated) | Recall (round 2, answer sheet) | Real defects wrongly skipped | Precision | Cost |
|---|---|---|---|---|---|
| sonnet-opus | 24/32 (**75%**) | 31/32 (97%) | 0/24 | 100% | $2.5210 |
| opus-opus | 24/32 (**75%**) | 30/32 (94%) | 0/24 | 100% | $3.9933 |
| haiku-sonnet | 24/32 (**75%**) | 26/32 (81%) | 0/24 | 100% | $1.2052 |

### Common misses — all three sets missed the **same 8 issues**

| Case | File | Rule | Cue left in the comments (judged TP anyway) |
|---|---|---|---|
| Fp01 | SettingsIntrospector | S3011 | "admin console looks fields up dynamically by name" |
| Fp02 | OrderPayload | S3011 | "serialized field-by-field via reflection (data-binding style)" |
| Fp13 | CommandDispatcher | S3011 | "handlers resolved by naming convention handle&lt;Command&gt;" |
| Fp03 | LatencyTracker | S6213 | "Public API since 1.0" |
| Fp08 | WeakRegistryScanner | S1854 | "strong reference: keeps the key alive..." (S1481 on the same line WAS skipped) |
| Fp15 | PollingWorker | S2142 | "interruption = stop request; loop exits on next check" |
| Fp16 | SourceFileTypes | S2386 | "Read-only by convention — do not modify" |
| Fp22 | ProgressListeners | S1186 | "receiving and ignoring events is its job" |

## Interpretation

1. **The answer-sheet effect is 19–22pp for the Opus judge**
   (94–97% → 75%). Much of the high recall in rounds 1–2 was reading
   comprehension, not inference.
2. **The judge-model gap disappeared** — the round-2 gap between Opus
   (94–97%) and Sonnet (81%) was likely the ability to read and apply
   the in-file answer sheet. With the answers gone, all three judges
   converge to exactly 75%, and **the 8 misses are identical** —
   run-to-run nondeterminism has effectively vanished too (with the
   ambiguous cue removed, judgments became deterministic).
3. **Precision is still 100%** (0/24 real defects wrongly skipped,
   24/24 fixes verified). The conservative default — lean TRUE_POSITIVE
   when intent alone is not convincing — holds: missed false positives
   cost fix tokens, missed real defects remain zero.
4. **The 8 misses split into two kinds** (reconstructed from the exact
   ±5-line window each judge received):
   - **Cue never delivered (3)** — for all three S3011 cases, the class
     Javadoc carrying the reflection-by-design justification falls
     **outside** the window: the judge never saw the comment, it did
     not ignore it — a structural limit of the context window. (The
     ground-truth label is also contestable here, since the rule warns
     about the setAccessible act itself.)
   - **Cue delivered but overruled (5)** — "Public API since 1.0"
     (S6213), the GC-pin inline comment (S1854), the cooperative-
     shutdown comment (S2142), the read-only comment (S2386) and the
     no-op listener Javadoc (S1186) were inside the window and still
     judged TP — rule-level priors beat the intent statements. A signal
     that judges lack a standard for accepting intent comments as
     evidence rather than excuses.
5. **Operational implication**: under realistic, no-answer-sheet
   conditions the ceiling for automatic FP skipping is ~75% on this
   corpus. The rest stays with human review — but since the bias is
   conservative (zero wrong skips), an "auto-skip + human review of the
   remainder" operation remains safe.

Caveats: round 3 changed both comments and naming, so the two effects
cannot be separated. It is also a single run per set, so ±1–2 issue
noise is possible (though the exact three-way agreement weakens the
noise hypothesis).

### How to reproduce

GitHub Actions → manually dispatch the **FP Triage Benchmark** workflow.
