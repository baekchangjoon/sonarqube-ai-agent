# FP Corpus — 오탐 판정 벤치마크용 라벨링 코퍼스

LLM 트리아지(judge)의 **오탐 검출 성능**을 측정하기 위한 정답 세트입니다.
22개 Java 파일, **SonarQube CE(Sonar Way 프로파일)에서 전수 발화 검증 완료**
— 총 **32개 이슈, 전부 ground truth = FALSE_POSITIVE**.

각 파일의 Javadoc에 "왜 오탐인가"의 근거가 적혀 있습니다 — 실코드에서
주석·맥락이 판정 단서가 되는 것과 동일한 조건을 의도한 것입니다.

## 사용법

```bash
# 빌드 + 스캔 (예: 원격 서버, 프로젝트 키 fp-corpus)
docker run --rm -v "$(pwd)":/project -w /project \
  maven:3.9-eclipse-temurin-17 mvn -q clean compile
docker run --rm -e SONAR_HOST_URL=$SONAR_URL -e SONAR_TOKEN=$SONAR_TOKEN \
  -v "$(pwd)":/usr/src sonarsource/sonar-scanner-cli \
  -Dsonar.projectKey=fp-corpus -Dsonar.sources=src/main/java \
  -Dsonar.java.binaries=target/classes -Dsonar.java.libraries=
```

스캔 후 트리아지를 돌리면, 이 프로젝트의 모든 이슈에 대한 정답은
"오탐(skip)"입니다. `issues_skipped_as_fp / 32` 가 곧 재현율(recall)이고,
[tp-corpus](../tp-corpus)(실결함 24개, 동일 룰 미러링)와 함께 돌리면
정밀도까지 측정할 수 있습니다.

## Ground Truth Manifest (2026-06-07, SonarQube CE 26.5 실측)

| # | 파일 | 발화 룰 (라인) | 오탐 근거 요약 |
|---|------|---------------|----------------|
| 01 | Fp01ReflectionField | S1068@12, S3011@16 | 필드를 리플렉션(문자열 이름)으로 읽음; setAccessible은 그 설계의 필수 요소 |
| 02 | Fp02SerializedDto | S1068@14,15,16, S3011@21 | 필드들이 리플렉션 기반 직렬화기에 의해 일괄 소비됨 (Gson/Jackson 패턴) |
| 03 | Fp03RecordMethodName | S6213@15 | `record`는 타입 위치에서만 제한 — 메서드명으로 합법, 개명은 공개 API 파괴 |
| 04 | Fp04CliOutput | S106@16,18 | CLI 도구 — stdout이 곧 제품 (파이프 소비 계약) |
| 05 | Fp05StdoutProtocol | S106@13,14,15 | stdout 위 IPC 프로토콜(LSP류) — 명세가 스트림을 지정 |
| 06 | Fp06ConsoleSink | S106@12 | 이 클래스가 콘솔 로깅 싱크 구현체 자체 — "로거를 써라"가 순환 |
| 07 | Fp07ConsolePrompt | S106@16 | 대화형 프롬프트 — 질문은 터미널에 출력되어야 함 (stdin과 짝) |
| 08 | Fp08KeepAliveRef | S1481@18, S1854@18 | "미사용" 지역변수가 WeakHashMap 키의 GC 방지용 강한 참조 |
| 09 | Fp09GcRelease | S1854@17 | null 대입이 대형 버퍼를 GC에 반환하는 의도된 동작 (Effective Java) |
| 10 | Fp10ReflectiveCallback | S1172@13 | 파라미터가 리플렉션 디스패치 계약상 고정 시그니처의 일부 |
| 11 | Fp11TriState | S2447@20 | Boolean null = "기권"이 문서화된 3-상태 API 계약 (voter 패턴) |
| 12 | Fp12DistinctLiterals | S1192@15 | 동철자·이의미 리터럴(JSON 키/DB 컬럼/UI 라벨/메트릭 태그) — 상수 추출이 오결합 |
| 13 | Fp13ReflectiveMethod | S1144@13, S3011@21 | private 메서드가 이름 규약 기반 리플렉션으로 디스패치됨 |
| 14 | Fp14CyclicIterator | S2272@31 | 계약상 무한 이터레이터(라운드로빈) — 소진 상태가 존재하지 않음 |
| 15 | Fp15InterruptHelper | S2142@20 | volatile 플래그가 이 워커의 문서화된 협조적 종료 프로토콜 |
| 16 | Fp16InternalTable | S2386@13 | 관례상 읽기 전용 룩업 테이블 — 접근마다 복사는 hot path 낭비 |
| 17 | Fp17DevDefaults | S2068@14 | 로컬 docker postgres의 공개 기본 자격증명 — 비밀이 아님 |
| 18 | Fp18TruststoreDefault | S2068@13 | "changeit" = JDK cacerts의 공개 문서화된 기본값 |
| 19 | Fp19BootstrapErr | S106@13 | 로깅 프레임워크 초기화 실패 핸들러 — 정의상 로거 사용 불가 |
| 20 | Fp20DaemonLoop | S2189@15 | JVM 수명과 함께 도는 의도된 데몬 루프 — 종료 조건 부재가 설계 |
| 21 | Fp21BuilderCtor | S107@21 | 8-파라미터 생성자는 private이며 Builder만 호출 — 패턴이 이미 문제를 해결 |
| 22 | Fp22NullObject | S1186@20,24 | Null Object 패턴 — 아무것도 안 하는 것이 문서화된 동작 |

## 작성 과정에서의 발견 (분석기가 이미 옳았던 패턴)

코퍼스 후보 중 일부는 SonarQube가 **이미 예외 처리**하고 있어 발화하지
않았고, 코퍼스에서 제외/교체했습니다 — 분석기의 한계를 과장하지 않기 위해
기록을 남깁니다:

- S1068: native 메서드를 가진 클래스의 필드는 면제 (JNI 접근 고려)
- S2095: `Scanner(System.in)` 등 표준 스트림 래퍼는 면제
- S2068: 값에 "password" 단어가 포함되면 면제 (라벨/필드명 오탐 방지)
- S1166, S1075, S1244, S2629(JUL 가드): Sonar Way 기본 프로파일에서
  미활성이거나 해당 패턴 미발화
