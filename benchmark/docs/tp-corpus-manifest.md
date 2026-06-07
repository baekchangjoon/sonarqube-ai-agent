한국어 | **[English](tp-corpus-manifest.en.md)**

# TP Corpus Manifest — 실결함 판정 벤치마크 답안지

[`benchmark/tp-corpus`](../tp-corpus)의 ground truth 해설지입니다.
18케이스 / **24이슈, 전부 ground truth = TRUE_POSITIVE** —
여기서 스킵되는 이슈는 "실결함을 오탐으로 오판해 놓친" 건수입니다.

> 답안지는 분석 대상 파일과 격리하기 위해 코퍼스 밖(이 문서)에만
> 둡니다 — [fp-corpus manifest](fp-corpus-manifest.md)의 격리 원칙 참조.

설계 원칙:

- **룰 미러링**: fp-corpus에서 발화 검증된 룰과 같은 룰을 사용해, judge가
  룰 종류만으로 답을 맞힐 수 없게 한다 (예: S2068 — fp는 공개 dev 기본값,
  tp는 운영 DB 비밀번호).
- **정답 미유출**: 주석은 코드의 *의도*만 서술하고, "이건 결함"이라는
  단서를 절대 적지 않는다. 의도 서술이 곧 결함의 증거가 되도록 작성
  (예: "리트라이는 MAX_ATTEMPTS까지" 라는 Javadoc + 카운터 미증가 루프).
- **자연스러운 명명**: 실코드 같은 클래스명을 사용한다. 케이스 번호는
  이 manifest에만 존재한다.

## 사용법 (빌드 + 스캔)

```bash
cd benchmark/tp-corpus
docker run --rm -v "$(pwd)":/project -w /project \
  maven:3.9-eclipse-temurin-17 mvn -q clean compile test-compile
docker run --rm -e SONAR_HOST_URL=$SONAR_URL -e SONAR_TOKEN=$SONAR_TOKEN \
  -v "$(pwd)":/usr/src sonarsource/sonar-scanner-cli \
  -Dsonar.projectKey=tp-corpus -Dsonar.sources=src/main/java \
  -Dsonar.java.binaries=target/classes -Dsonar.java.libraries=
```

트리아지의 정답은 모든 이슈에 대해 "실결함(수정 진행)"입니다.
`issues_skipped_as_fp`가 곧 오판(놓친 실결함) 수이며, fp-corpus 결과와
합치면:

- 재현율(recall) = fp-corpus에서 스킵 / 32
- 정밀도(precision) = fp-corpus에서 스킵 / (fp-corpus 스킵 + tp-corpus 스킵)

## Ground Truth Manifest (2026-06-07, SonarQube CE 26.5 실측)

| # | 파일 | 발화 룰 (라인) | 결함 요약 (왜 실결함인가) | 미러 |
|---|------|---------------|--------------------------|------|
| 01 | SessionMetrics | S1068@9 | `failedLogins`를 아무도 기록·조회하지 않음 — 대시보드 지표 누락 | Fp01/02 |
| 02 | InvoiceFormatter | S1144@18 | `formatLegacyDate`는 어디서도 호출되지 않는 데드 코드 | Fp13 |
| 03 | PaymentService | S106@20,22 | Logger가 있는데 디버그 `println` 잔재 2건 | Fp04~07/19 |
| 04 | OrderRepository | S2068@15, S6437@18 | 운영 DB 비밀번호 하드코딩 | Fp17 |
| 05 | DiscountCalculator | S1854@18 | 할인 적용값이 재계산으로 덮여 사라짐 — 금액 버그 | Fp09 |
| 06 | ReportGenerator | S1481@14, S1854@14 | `formatted` 미사용 — 통화 포맷 대신 raw double 출력 | Fp08 |
| 07 | FeatureFlags | S2447@21 | `Boolean null` 반환, 호출부는 unboxing 분기 → NPE | Fp11 |
| 08 | InventoryQueries | S1192@10 | 동일 의미 테이블명 리터럴 3회 — 상수 추출 대상 | Fp12 |
| 09 | BatchCursor | S2272@24 | 소진 시 `NoSuchElementException` 대신 null 반환 | Fp14 |
| 10 | QueueWorker | S2142@27 | 인터럽트 삼킴 — 자기 루프 조건(`isInterrupted`)이 영영 안 잡힘 | Fp15 |
| 11 | MediaTypes | S2386@9 | public 가변 배열을 실제로 변이시키는 `override` 존재 | Fp16 |
| 12 | ExportMonitor | S2189@24 | "완료되면 반환" 문서와 달리 exit 없는 `while(true)` — 워커 멈춤 | Fp20 |
| 13 | ReportConfig | S107@17 | public 8-파라미터 생성자 (Builder 없음, 직접 호출) | Fp21 |
| 14 | UploadListener | S1186@27 | 빈 `onError` — 업로드 오류가 조용히 증발 | Fp22 |
| 15 | PriceFormatter | S1172@15 | `locale` 파라미터 무시 — 방문자 로케일 미적용 | Fp10 |
| 16 | CacheWarmer | S3011@18,19 | 리플렉션으로 캐시 내부 카운터 직접 조작 — size/entries 불일치 | Fp01/13 |
| 17 | TlsClientFactory | S2068@14, S6437@26 | mTLS 키스토어 비밀번호 하드코딩 | Fp18 |
| 18 | AuditLogReader | S2095@23,24 | Connection/PreparedStatement 미반납 — 커넥션 풀 고갈 | — |

보조 파일: `CatalogCache`(#16의 대상 클래스, 의도된 이슈 없음),
`Placeholder`(스캐너의 src/test/java 하드코딩 대응).

## 작성 과정에서의 발견 (분석기가 잡지 못한 패턴)

- S2189: "카운터 미증가 retry 루프"(`while (attempts < 3)`에서 attempts
  미변경)와 "플래그 미갱신 루프"(`while (!empty)`에서 empty 미갱신) 모두
  **미발화** — CE의 S2189는 문자 그대로의 `while (true)` + exit 부재만
  잡는다. 실수로 생기는 무한 루프의 상당수는 룰이 못 본다는 의미.
- S2629(JUL 로깅 문자열 연결)는 fp-corpus 작성 시 미발화로 기록됐지만
  `LOGGER.warning("..." + x)` 패턴에서는 발화한다 — 코퍼스 초안에서
  의도치 않게 6건 발화해, 파라미터 스타일(`{0}`)로 바꿔 제거했다.
- S1075(하드코딩 경로)도 활성 — 키스토어 경로 상수에서 발화해 생성자
  주입으로 변경, 제거했다.
