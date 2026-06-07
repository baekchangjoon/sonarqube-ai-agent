**[한국어](tp-corpus-manifest.md)** | English

# TP Corpus Manifest — Real Defect Triage Benchmark Answer Sheet

The ground truth answer sheet for [`benchmark/tp-corpus`](../tp-corpus).
18 cases / **24 issues, all with ground truth = TRUE_POSITIVE** —
an issue skipped here is a count of "a real defect misjudged as a false positive and thus missed".

> The answer sheet is kept only outside the corpus (in this document) to isolate it from the analyzed files —
> see the isolation principle in the [fp-corpus manifest](fp-corpus-manifest.en.md).

Design principles:

- **Rule mirroring**: Use the same rules whose firings were verified in fp-corpus, so the judge
  cannot get the answer from the rule type alone (e.g., S2068 — fp is a public dev default,
  tp is a production DB password).
- **No answer leakage**: Comments describe only the *intent* of the code and never write a
  hint like "this is a defect". They are written so that the intent description itself becomes the evidence of the defect
  (e.g., a Javadoc saying "retries up to MAX_ATTEMPTS" + a loop that never increments the counter).
- **Natural naming**: Use real-code-like class names. The case numbers exist
  only in this manifest.

## Usage (build + scan)

```bash
cd benchmark/tp-corpus
docker run --rm -v "$(pwd)":/project -w /project \
  maven:3.9-eclipse-temurin-17 mvn -q clean compile test-compile
docker run --rm -e SONAR_HOST_URL=$SONAR_URL -e SONAR_TOKEN=$SONAR_TOKEN \
  -v "$(pwd)":/usr/src sonarsource/sonar-scanner-cli \
  -Dsonar.projectKey=tp-corpus -Dsonar.sources=src/main/java \
  -Dsonar.java.binaries=target/classes -Dsonar.java.libraries=
```

The correct triage answer is "real defect (proceed with fix)" for every issue.
`issues_skipped_as_fp` is precisely the count of misjudgments (missed real defects), and combined with the fp-corpus results:

- recall = skipped in fp-corpus / 32
- precision = skipped in fp-corpus / (fp-corpus skipped + tp-corpus skipped)

## Ground Truth Manifest (2026-06-07, measured on SonarQube CE 26.5)

| # | File | Fired rule (line) | Defect summary (why it is a real defect) | Mirror |
|---|------|---------------|--------------------------|------|
| 01 | SessionMetrics | S1068@9 | `failedLogins` is never recorded or read by anyone — a missing dashboard metric | Fp01/02 |
| 02 | InvoiceFormatter | S1144@18 | `formatLegacyDate` is dead code called from nowhere | Fp13 |
| 03 | PaymentService | S106@20,22 | A Logger exists, yet 2 leftover debug `println` remain | Fp04~07/19 |
| 04 | OrderRepository | S2068@15, S6437@18 | Production DB password hardcoded | Fp17 |
| 05 | DiscountCalculator | S1854@18 | The applied discount value is overwritten by a recomputation and lost — an amount bug | Fp09 |
| 06 | ReportGenerator | S1481@14, S1854@14 | `formatted` unused — outputs a raw double instead of the currency format | Fp08 |
| 07 | FeatureFlags | S2447@21 | Returns `Boolean null`, the caller unboxes in a branch → NPE | Fp11 |
| 08 | InventoryQueries | S1192@10 | Same-meaning table-name literal 3 times — a constant-extraction target | Fp12 |
| 09 | BatchCursor | S2272@24 | Returns null instead of `NoSuchElementException` on exhaustion | Fp14 |
| 10 | QueueWorker | S2142@27 | Swallows the interrupt — its own loop condition (`isInterrupted`) is never caught | Fp15 |
| 11 | MediaTypes | S2386@9 | A public mutable array with an `override` that actually mutates it | Fp16 |
| 12 | ExportMonitor | S2189@24 | A `while(true)` with no exit, contrary to the "returns when complete" doc — the worker hangs | Fp20 |
| 13 | ReportConfig | S107@17 | A public 8-parameter constructor (no Builder, called directly) | Fp21 |
| 14 | UploadListener | S1186@27 | An empty `onError` — upload errors silently vanish | Fp22 |
| 15 | PriceFormatter | S1172@15 | The `locale` parameter is ignored — the visitor's locale is not applied | Fp10 |
| 16 | CacheWarmer | S3011@18,19 | Directly manipulates the cache's internal counter via reflection — size/entries mismatch | Fp01/13 |
| 17 | TlsClientFactory | S2068@14, S6437@26 | mTLS keystore password hardcoded | Fp18 |
| 18 | AuditLogReader | S2095@23,24 | Connection/PreparedStatement not returned — connection pool exhaustion | — |

Auxiliary files: `CatalogCache` (the target class of #16, with no intended issue),
`Placeholder` (to cope with the scanner's src/test/java hardcoding).

## Findings during authoring (patterns the analyzer failed to catch)

- S2189: Both the "retry loop that never increments the counter" (`attempts` unchanged in
  `while (attempts < 3)`) and the "loop with an unupdated flag" (`empty` unupdated in
  `while (!empty)`) **do not fire** — CE's S2189 only catches a literal `while (true)`
  with no exit. This means a large share of accidentally created infinite loops go unseen by the rule.
- S2629 (JUL logging string concatenation) was recorded as not firing while authoring fp-corpus, but
  it does fire on the `LOGGER.warning("..." + x)` pattern — it unintentionally fired 6 times in the corpus draft,
  so it was removed by switching to the parameter style (`{0}`).
- S1075 (hardcoded path) is also active — it fired on a keystore-path constant, so it was changed to constructor
  injection and removed.
