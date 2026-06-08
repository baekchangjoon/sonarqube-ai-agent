**[한국어](fp-triage-context-docs-2026-06-07.md)** | English

# FP Triage Benchmark — Context Expansion + Rule Doc Injection (2026-06-07, rounds 4–5)

> **Strategy note**: this benchmark ran with `assessment.strategy: "triage"` (option C — **pre-fix** screening judgment). The operational default has since moved to option D (`review`: fix attempt → FP escape → independent review), whose performance is not covered by these numbers.

After [round 3](fp-triage-no-leak-2026-06-07.en.md) isolated the answer
key, all three judges converged at 75% recall. Rounds 4–5 measure
whether **giving the judge more input** moves that ceiling. Two sets
(judge=opus / judge=sonnet, fixer always sonnet) × two corpora
(fp 32 issues / tp 24 issues), run locally.

| Round | Change | Config |
|---|---|---|
| 4 | Context window ±5 → **±30 lines** | `assessment.context_lines: 30` |
| 5 | + **whole file injected when ≤150 lines**, **SonarQube rule docs injected** (how_to_fix for the fixer, the Exceptions subsection for the judge) | `full_file_max_lines: 150`, `include_rule_docs: true` |

Every corpus file is under 150 lines, so the round-5 judge effectively
received the **full file plus the rule's Exceptions doc** — the
practical upper bound of what a single-shot judge can be given.

## Results

| Set | Recall r3 (±5) | r4 (±30) | r5 (full+docs) | Real-defect mis-skips r4 | r5 | Cost r4 (fp+tp) | r5 |
|---|---|---|---|---|---|---|---|
| judge=opus | 75% | 24/32 (**75%**) | 25/32 (**78.1%**) | 0/24 (100%) | 1/24 (95.8%)* | $13.61 | $12.48 |
| judge=sonnet | 75% | 24/32 (**75%**) | 23/32 (**71.9%**) | 0/24 (100%) | 0/24 (**100%**) | $7.14 | $7.34 |

\* An artifact — see "Two pipeline defects" below. Not a judge
reasoning error.

### Per-case movement (fp-corpus, 32 issues)

The 8 round-4 misses were **identical across both judges** (7 shared
with round 3): S3011×3, S6213, S1481, S1854 (WeakRegistryScanner),
S2142, S2386.

| Case | Rule | r4 | r5 opus | r5 sonnet | Note |
|---|---|---|---|---|---|
| LatencyTracker | S6213 | miss | **caught** | **caught** | full file shows the record pattern + "Public API" Javadoc |
| OrderPayload@20 | S3011 | miss | **caught** | miss | reflective-serialization intent clear in full file |
| ChecksumJob | S1854 | caught | caught (0.97, **cites "documented S1854 exception"**) | **miss (new)** | opus directly cites the injected Exceptions doc |
| ProgressListeners@19 | S1186 | caught | **miss (new)** | caught | run-to-run variance |
| EventHandler | S1172 | caught | caught | **miss (new)** | run-to-run variance |
| SettingsIntrospector & CommandDispatcher S3011, WeakRegistryScanner S1481+S1854, PollingWorker S2142, SourceFileTypes S2386 | — | miss | miss | miss | **invariant core** |

## Interpretation

1. **Marginal utility of more context is near zero.** ±5→±30 (r4)
   changed nothing (75%→75%, same 8 misses). Full file + docs (r5)
   moved ±1–2 cases — hard to distinguish from run noise. Of the three
   S3011 cases round 3 classified as "clue not delivered (outside the
   window)", two stayed misses even with the whole file delivered —
   the bottleneck is not input but the **judge's standard of evidence**
   (rule-level prior conviction outweighs intent evidence in code).
2. **Rule doc injection is precise but narrow.** Of the missed rules,
   only S1854 has an Exceptions subsection at all, and its text
   ("ignores initializations to -1/0/1/null/true/false") does not
   strictly cover the case (a re-assignment releasing memory to GC).
   Opus still cited it as supporting evidence with higher confidence
   (0.97–0.99). Seeing a real effect would require corpus cases on
   rules that genuinely have Exceptions (S1068, S1192, S1172…).
3. **The invariant core of 6 shares one shape**: setAccessible
   (S3011), keep-alive variable (S1481/S1854), interrupt protocol
   (S2142), mutable public array (S2386) — in all of them the flagged
   behavior is real and harmlessness exists only in design intent.
   Hardest class for a single-shot judge; partly overlaps with cases
   whose ground-truth label is itself debatable.
4. **The judge-model gap reopened** — the perfect convergence of
   rounds 3–4 broke in round 5 (opus 25 vs sonnet 23, different miss
   sets). Richer input re-exposes differences in the ability to use
   it — consistent with round 2 (answer-key era).
5. **Cost is neutral** (r4 total $20.76 → r5 $19.82). Injecting the
   full file cut the judge's extra Read tool-call turns, offsetting
   the larger prompts.

## Two pipeline defects the benchmark surfaced

Both were exposed when a discarded first attempt of round 5 dropped
tp-corpus precision to 6/24:

1. **Triage context contaminated by local mutations (fixed)** — with
   several issues in one file, an earlier issue's fix mutates the
   local file before the next issue is triaged. The initial full-file
   implementation read the local file, so the judge saw already-fixed
   code and called the finding FP (e.g. "password is read from
   System.getenv, not hardcoded"). Issue line numbers refer to the
   scan snapshot, so the fix reads the **scan-time server snapshot**
   (`/api/sources/raw`) first and falls back to the local checkout
   only for files new in a PR (`SonarQubeClient.get_raw_source`).
2. **Harness judge bypass via Read (remains, documented)** — even
   with snapshot prompts, a claude-code judge can Read the local
   (mutated) file. Round 5's single opus-tp mis-skip (S2095@24) is
   this path: the fix for S2095@23 in the same file had wrapped the
   code in try-with-resources, so the judge concluded "already
   closed". **Operationally harmless** (the defect really is fixed
   and the re-scan confirms it) but it costs benchmark precision.
   Structural fixes — triage-all-then-fix ordering, or fully
   snapshot-pinned judge input — are round-6 candidates.

## Operational implications

- Input expansion does not move the auto-skip ceiling beyond ~75±3%.
  The next lever is the **judgment procedure**, not the input: an
  explicit standard for accepting intent comments as evidence,
  multi-turn investigation, or per-rule specialized prompts.
- The bias stays conservative (0–1 real-defect mis-skips, and that
  one was an already-fixed defect). "Auto-skip + human review of the
  remainder" remains a safe operating mode.

### Reproduction

```bash
# config: assessment.context_lines=30, full_file_max_lines=150,
#         include_rule_docs=true; judge_model: opus|sonnet
cd orchestrator && python3 -m src.main --config <cfg> pr-premerge \
  --repo dummy/bench --pr-number <N> --project-dir <corpus copy> --cleanup
```
