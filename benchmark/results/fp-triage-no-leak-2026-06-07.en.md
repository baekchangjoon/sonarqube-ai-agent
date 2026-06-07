**[한국어](fp-triage-no-leak-2026-06-07.md)** | English

# FP Triage Benchmark — After Answer-Sheet Isolation (2026-06-07, round 3)

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
4. **Nature of the 8 misses**: the three S3011 cases (setAccessible)
   are defensible TP verdicts — the rule warns about the act itself, so
   even by-design reflection can reasonably be flagged; the ground
   truth label itself is a contested gray zone. By contrast Fp08
   (S1854), Fp15 and Fp22 were missed despite explicit justification in
   the comments — a signal that judges lack a standard for accepting
   intent comments as evidence rather than excuses.
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
