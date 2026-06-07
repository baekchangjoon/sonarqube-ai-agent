**[한국어](README.md)** | English

# False Positive Triage Demo — Rule vs LLM

Whether a static-analysis warning is genuine ("real defect or false positive")
is a question of **intent and context**, so a rule-based filter gets it wrong
in both directions, while an LLM reads the context like a human reviewer and
makes the call — this is a presentation demo showing that with 3 cases.

## Running

```bash
# Default: uses recorded LLM verdicts — 0 dependencies, no network needed (Java 11+)
java FalsePositiveTriageDemo.java

# Live: real-time verdicts via the claude CLI (claude login required, ~15s per case)
java FalsePositiveTriageDemo.java --live
```

Expected output: **Rule 0/3 · LLM 3/3**

## 3 cases (real code: [`cases/`](cases/))

| Case | Rule | Answer | Why the rule is wrong |
|---|---|---|---|
| A. AWS example key, main path | S6418 | **False positive** | Structure/entropy identical to a real key → keyword+entropy rule cries wolf |
| B. `sk_live_` production key, test path | S6418 | **Real defect** | The "exclude test paths" rule lets a genuine leak through |
| C. NPE warning + custom validator | S2259 | **False positive** | The analyzer doesn't know the `Guards.ensureNotNull` contract |

If you twist the rule to block A, then B breaks; if you try to catch B, then A blows up —
**the same rule is wrong in both directions**, and it's not a problem you can solve by refining the rule.

## Rule baseline (implemented in the demo)

1. Exclude test paths (treat as false positive if path contains `/test/`)
2. Secret keyword matching (`secret|key|token|credential|passw`)
3. String Shannon entropy threshold (≥ 3.0)

## On honesty

- The "LLM verdict" in default mode is not a made-up value; it is the response
  recorded from actually calling Claude (`claude -p`, sonnet) with the same
  prompt as the demo. You can reproduce it anytime with `--live`.
- An undecidable response conservatively falls back to "real defect"
  (a false alarm is safer than a miss) — the same principle as the
  `assessment` strategy of the parent-directory orchestrator.
- The key value in case B is a demo dummy and not a real key.
