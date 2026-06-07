**[한국어](README.md)** | English

# FP Corpus — Labeled corpus for false-positive triage benchmarking

A ground-truth set for measuring the **false-positive detection performance** of LLM triage (judge).
22 Java files, **fully verified to fire on SonarQube CE (Sonar Way profile)**
— a total of **32 issues, all with ground truth = FALSE_POSITIVE**.

Each file's Javadoc states the rationale for "why it is a false positive" — this intentionally
reproduces the same condition as in real code, where comments and context serve as triage cues.

## Usage

```bash
# Build + scan (e.g. remote server, project key fp-corpus)
docker run --rm -v "$(pwd)":/project -w /project \
  maven:3.9-eclipse-temurin-17 mvn -q clean compile
docker run --rm -e SONAR_HOST_URL=$SONAR_URL -e SONAR_TOKEN=$SONAR_TOKEN \
  -v "$(pwd)":/usr/src sonarsource/sonar-scanner-cli \
  -Dsonar.projectKey=fp-corpus -Dsonar.sources=src/main/java \
  -Dsonar.java.binaries=target/classes -Dsonar.java.libraries=
```

After scanning, when you run triage, the correct answer for every issue in this project is
"false positive (skip)". `issues_skipped_as_fp / 32` is the recall, and running it together with
[tp-corpus](../tp-corpus/README.en.md) (24 real defects, mirroring the same rules) lets you also
measure precision.

## Ground Truth Manifest (2026-06-07, measured on SonarQube CE 26.5)

| # | File | Fired rule (line) | Why it is a false positive (summary) |
|---|------|---------------|----------------|
| 01 | Fp01ReflectionField | S1068@12, S3011@16 | Field is read via reflection (string name); setAccessible is an essential part of that design |
| 02 | Fp02SerializedDto | S1068@14,15,16, S3011@21 | Fields are consumed en masse by a reflection-based serializer (Gson/Jackson pattern) |
| 03 | Fp03RecordMethodName | S6213@15 | `record` is restricted only in type position — legal as a method name; renaming breaks the public API |
| 04 | Fp04CliOutput | S106@16,18 | CLI tool — stdout is the product itself (pipe consumption contract) |
| 05 | Fp05StdoutProtocol | S106@13,14,15 | IPC protocol over stdout (LSP-like) — the spec designates the stream |
| 06 | Fp06ConsoleSink | S106@12 | This class is the console logging sink implementation itself — "use a logger" is circular |
| 07 | Fp07ConsolePrompt | S106@16 | Interactive prompt — the question must be printed to the terminal (paired with stdin) |
| 08 | Fp08KeepAliveRef | S1481@18, S1854@18 | The "unused" local variable is a strong reference preventing GC of a WeakHashMap key |
| 09 | Fp09GcRelease | S1854@17 | The null assignment is the intended behavior of returning a large buffer to GC (Effective Java) |
| 10 | Fp10ReflectiveCallback | S1172@13 | The parameter is part of a fixed signature required by the reflection dispatch contract |
| 11 | Fp11TriState | S2447@20 | Boolean null = "abstain" is a documented 3-state API contract (voter pattern) |
| 12 | Fp12DistinctLiterals | S1192@15 | Same-spelling, different-meaning literals (JSON key/DB column/UI label/metric tag) — constant extraction would wrongly couple them |
| 13 | Fp13ReflectiveMethod | S1144@13, S3011@21 | The private method is dispatched via naming-convention-based reflection |
| 14 | Fp14CyclicIterator | S2272@31 | A contractually infinite iterator (round-robin) — there is no exhausted state |
| 15 | Fp15InterruptHelper | S2142@20 | The volatile flag is this worker's documented cooperative shutdown protocol |
| 16 | Fp16InternalTable | S2386@13 | A conventionally read-only lookup table — copying on every access is hot-path waste |
| 17 | Fp17DevDefaults | S2068@14 | Public default credentials for a local docker postgres — not a secret |
| 18 | Fp18TruststoreDefault | S2068@13 | "changeit" = the publicly documented default of the JDK cacerts |
| 19 | Fp19BootstrapErr | S106@13 | Logging-framework initialization failure handler — by definition the logger is unusable |
| 20 | Fp20DaemonLoop | S2189@15 | An intended daemon loop running for the JVM's lifetime — the absence of a termination condition is by design |
| 21 | Fp21BuilderCtor | S107@21 | The 8-parameter constructor is private and only the Builder calls it — the pattern already solves the problem |
| 22 | Fp22NullObject | S1186@20,24 | Null Object pattern — doing nothing is the documented behavior |

## Findings during authoring (patterns where the analyzer was already right)

Some corpus candidates did not fire because SonarQube **already handles them as exceptions**, and
were excluded/replaced in the corpus — we record this so as not to overstate the analyzer's
limitations:

- S1068: fields of a class that has native methods are exempt (considering JNI access)
- S2095: standard stream wrappers such as `Scanner(System.in)` are exempt
- S2068: exempt when the value contains the word "password" (to avoid false positives on labels/field names)
- S1166, S1075, S1244, S2629 (JUL guard): inactive in the Sonar Way default profile,
  or the relevant pattern does not fire
