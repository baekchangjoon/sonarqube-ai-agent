**[한국어](README.md)** | English

# TP Corpus — Labeled corpus for real-defect triage benchmarking

A ground-truth set for measuring the **precision** of LLM triage (judge).
It pairs with [fp-corpus](../fp-corpus/README.en.md) (all false positives); this side is **all ground
truth = TRUE_POSITIVE** — any issue skipped here is a case of "missing a real defect by
misjudging it as a false positive".

Design principles:

- **Rule mirroring**: use the same rules that were verified to fire in fp-corpus, so that the judge
  cannot get the answer right from the rule type alone (e.g. S2068 — fp is a public dev default,
  tp is a production DB password).
- **No answer leakage**: comments describe only the *intent* of the code (symmetric to fp-corpus
  writing "why it is a false positive" in comments, this side never writes a cue saying "this is a
  defect"). They are written so that the description of intent itself becomes the evidence of the
  defect (e.g. a Javadoc saying "retries up to MAX_ATTEMPTS" + a loop that never increments the
  counter).
- **Natural naming**: instead of a case prefix like `Fp01...`, use class names that look like real
  code (so the file name does not leak the answer). Case numbers exist only in this README's manifest.

## Usage

```bash
docker run --rm -v "$(pwd)":/project -w /project \
  maven:3.9-eclipse-temurin-17 mvn -q clean compile test-compile
docker run --rm -e SONAR_HOST_URL=$SONAR_URL -e SONAR_TOKEN=$SONAR_TOKEN \
  -v "$(pwd)":/usr/src sonarsource/sonar-scanner-cli \
  -Dsonar.projectKey=tp-corpus -Dsonar.sources=src/main/java \
  -Dsonar.java.binaries=target/classes -Dsonar.java.libraries=
```

The correct triage answer for every issue is "real defect (proceed to fix)".
`issues_skipped_as_fp` is the number of misjudgments (missed real defects), and combined with the
fp-corpus results:

- recall = skipped in fp-corpus / 32
- precision = skipped in fp-corpus / (fp-corpus skips + tp-corpus skips)

## Ground Truth Manifest (2026-06-07, measured on SonarQube CE 26.5)

18 cases / **24 issues, all ground truth = TRUE_POSITIVE**.

| # | File | Fired rule (line) | Defect summary (why it is a real defect) | Mirror |
|---|------|---------------|--------------------------|------|
| 01 | SessionMetrics | S1068@9 | Nobody records or reads `failedLogins` — a missing dashboard metric | Fp01/02 |
| 02 | InvoiceFormatter | S1144@18 | `formatLegacyDate` is dead code, never called anywhere | Fp13 |
| 03 | PaymentService | S106@20,22 | A Logger exists, yet 2 leftover debug `println` remain | Fp04~07/19 |
| 04 | OrderRepository | S2068@15, S6437@18 | Hardcoded production DB password | Fp17 |
| 05 | DiscountCalculator | S1854@18 | The applied discount value is overwritten by a recomputation and lost — an amount bug | Fp09 |
| 06 | ReportGenerator | S1481@14, S1854@14 | `formatted` unused — outputs a raw double instead of a currency format | Fp08 |
| 07 | FeatureFlags | S2447@21 | Returns `Boolean null`, the caller branches on unboxing → NPE | Fp11 |
| 08 | InventoryQueries | S1192@10 | The same-meaning table-name literal appears 3 times — a target for constant extraction | Fp12 |
| 09 | BatchCursor | S2272@24 | Returns null on exhaustion instead of `NoSuchElementException` | Fp14 |
| 10 | QueueWorker | S2142@27 | Swallows the interrupt — its own loop condition (`isInterrupted`) is never caught | Fp15 |
| 11 | MediaTypes | S2386@9 | An `override` exists that actually mutates the public mutable array | Fp16 |
| 12 | ExportMonitor | S2189@24 | Contrary to its "returns when complete" doc, a `while(true)` with no exit — the worker stalls | Fp20 |
| 13 | ReportConfig | S107@17 | Public 8-parameter constructor (no Builder, called directly) | Fp21 |
| 14 | UploadListener | S1186@27 | Empty `onError` — upload errors silently vanish | Fp22 |
| 15 | PriceFormatter | S1172@15 | Ignores the `locale` parameter — the visitor's locale is not applied | Fp10 |
| 16 | CacheWarmer | S3011@18,19 | Directly manipulates the cache's internal counter via reflection — size/entries mismatch | Fp01/13 |
| 17 | TlsClientFactory | S2068@14, S6437@26 | Hardcoded mTLS keystore password | Fp18 |
| 18 | AuditLogReader | S2095@23,24 | Connection/PreparedStatement not returned — connection pool exhaustion | — |

Auxiliary files: `CatalogCache` (the target class of #16, no intended issue),
`CorpusPlaceholder` (to handle the scanner's src/test/java hardcoding).

## Findings during authoring (patterns the analyzer did not catch)

- S2189: both "a retry loop that never increments the counter" (`while (attempts < 3)` with
  attempts unchanged) and "a flag-not-updated loop" (`while (!empty)` with empty not updated)
  **do not fire** — CE's S2189 catches only a literal `while (true)` + absence of an exit. This
  means a substantial portion of accidental infinite loops go unseen by the rule.
- S2629 (JUL logging string concatenation) was recorded as not firing while writing fp-corpus, but
  it does fire on the `LOGGER.warning("..." + x)` pattern — it unintentionally fired 6 times in the
  corpus draft, so we switched to the parameter style (`{0}`) to remove them.
- S1075 (hardcoded path) is also active — it fired on a keystore path constant, so we changed it to
  constructor injection and removed it.
