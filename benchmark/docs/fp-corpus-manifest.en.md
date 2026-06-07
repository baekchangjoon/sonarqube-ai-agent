**[한국어](fp-corpus-manifest.md)** | English

# FP Corpus Manifest — False Positive Triage Benchmark Answer Sheet

The ground truth answer sheet for [`benchmark/fp-corpus`](../fp-corpus).
22 Java files, with all firings verified on SonarQube CE (Sonar Way) —
**32 issues total, all with ground truth = FALSE_POSITIVE**.

> **Why this document lives outside the corpus** — isolation of the analyzed files from the answer sheet.
> Early versions (the 1st and 2nd benchmarks around 2026-06-07) wrote the answer directly into each file's Javadoc as
> `expected: java:S1068`, "Why it is a false positive: ..." and so on,
> so the judge could "read off" the verdict from the ±5-line source context
> rather than "infer" it. The current corpus:
>
> - **Comments describe intent only** — only real-code-style class/method Javadoc remains,
>   with all rule IDs, verdicts, and "false positive"-type meta statements removed (symmetric with tp-corpus).
> - **Neutral naming** — leaky paths like `com.example.fp.Fp08KeepAliveRef` are replaced
>   with `com.example.core.WeakRegistryScanner` (since the judge prompt includes
>   the file path, the package and class names were hints too).
> - Case IDs (Fp01...) and the explanations exist **only in this document**.

## Usage (build + scan)

```bash
cd benchmark/fp-corpus
docker run --rm -v "$(pwd)":/project -w /project \
  maven:3.9-eclipse-temurin-17 mvn -q clean compile test-compile
docker run --rm -e SONAR_HOST_URL=$SONAR_URL -e SONAR_TOKEN=$SONAR_TOKEN \
  -v "$(pwd)":/usr/src sonarsource/sonar-scanner-cli \
  -Dsonar.projectKey=fp-corpus -Dsonar.sources=src/main/java \
  -Dsonar.java.binaries=target/classes -Dsonar.java.libraries=
```

The correct triage answer is "false positive (skip)" for every issue.
`issues_skipped_as_fp / 32` = recall, and running it together with
[tp-corpus](tp-corpus-manifest.en.md) (24 real defects, mirroring the same rules)
also measures precision.

## Ground Truth Manifest (2026-06-07 neutralization revision, measured on SonarQube CE 26.5)

| # | File (old name) | Fired rule (line) | False-positive rationale summary |
|---|------|---------------|----------------|
| 01 | SettingsIntrospector (Fp01ReflectionField) | S1068@11, S3011@15 | Field is read via reflection (string name); setAccessible is an essential part of that design |
| 02 | OrderPayload (Fp02SerializedDto) | S1068@13,14,15, S3011@20 | Fields are consumed wholesale by a reflection-based serializer (Gson/Jackson pattern) |
| 03 | LatencyTracker (Fp03RecordMethodName) | S6213@12 | `record` is restricted only in type position — legal as a method name, and renaming breaks the public API |
| 04 | WordCountTool (Fp04CliOutput) | S106@13,15 | CLI tool — stdout is the product itself (pipe-consumption contract) |
| 05 | FrameWriter (Fp05StdoutProtocol) | S106@11,12,13 | IPC protocol over stdout (LSP-style) — the spec designates the stream |
| 06 | ConsoleAppender (Fp06ConsoleSink) | S106@11 | This class is the console logging sink implementation itself — "use a logger" is circular |
| 07 | InteractivePrompt (Fp07ConsolePrompt) | S106@13 | Interactive prompt — the question must be printed to the terminal (paired with stdin) |
| 08 | WeakRegistryScanner (Fp08KeepAliveRef) | S1481@16, S1854@16 | The "unused" local variable is a strong reference preventing GC of a WeakHashMap key |
| 09 | ChecksumJob (Fp09GcRelease) | S1854@16 | The null assignment is the intended act of returning a large buffer to GC (Effective Java) |
| 10 | EventHandler (Fp10ReflectiveCallback) | S1172@11 | The parameter is part of a fixed signature required by the reflective dispatch contract |
| 11 | RoleVoter (Fp11TriState) | S2447@17 | Boolean null = "abstain" is a documented tri-state API contract (voter pattern) |
| 12 | StatusFields (Fp12DistinctLiterals) | S1192@13 | Same-spelling, different-meaning literals (JSON keys/DB columns/UI labels/metric tags) — constant extraction is mis-coupling |
| 13 | CommandDispatcher (Fp13ReflectiveMethod) | S1144@12, S3011@20 | The private method is dispatched via naming-convention-based reflection |
| 14 | RoundRobinIterator (Fp14CyclicIterator) | S2272@28 | A contractually infinite iterator (round-robin) — no exhausted state exists |
| 15 | PollingWorker (Fp15InterruptHelper) | S2142@18 | The volatile flag is this worker's documented cooperative-shutdown protocol |
| 16 | SourceFileTypes (Fp16InternalTable) | S2386@11 | A conventionally read-only lookup table — copying on every access is a hot-path waste |
| 17 | LocalDevDatabase (Fp17DevDefaults) | S2068@13 | Public default credentials of a local docker postgres — not a secret |
| 18 | SystemTruststore (Fp18TruststoreDefault) | S2068@10 | "changeit" = the publicly documented default of the JDK cacerts |
| 19 | LogBootstrapGuard (Fp19BootstrapErr) | S106@10 | The logging-framework initialization-failure handler — by definition cannot use the logger |
| 20 | TaskPump (Fp20DaemonLoop) | S2189@13 | An intended daemon loop that runs for the JVM's lifetime — the absence of a termination condition is by design |
| 21 | ConnectionSettings (Fp21BuilderCtor) | S107@18 | The 8-parameter constructor is private and called only by the Builder — the pattern already solves the problem |
| 22 | ProgressListeners (Fp22NullObject) | S1186@19,23 | Null Object pattern — doing nothing is the documented behavior |

## Findings during authoring (patterns the analyzer already got right)

Some corpus candidates did not fire because SonarQube **already handles them as exceptions**,
so they were excluded/replaced in the corpus — we record this to avoid overstating
the analyzer's limitations:

- S1068: Fields of a class with native methods are exempt (accounting for JNI access)
- S2095: Standard stream wrappers such as `Scanner(System.in)` are exempt
- S2068: Exempt if the value contains the word "password" (preventing label/field-name false positives)
- S1166, S1244: Inactive in the Sonar Way default profile, or the relevant pattern does not fire
- S2187: Naming a test placeholder `*Test` makes it fire — avoided during the neutralization revision
  by naming it `Placeholder`
