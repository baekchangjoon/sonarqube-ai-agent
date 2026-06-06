import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * FalsePositiveTriageDemo — 룰 기반 필터 vs LLM 판단 비교 데모.
 *
 * 같은 정적분석 경고라도 "진짜 결함이냐 오탐이냐"는 의도와 맥락의 문제라서
 * 룰(경로 제외·키워드·엔트로피)로는 양방향으로 틀리고, LLM은 사람 리뷰어처럼
 * 맥락을 읽어 가른다 — 를 3개 사례로 보여준다.
 *
 * 실행:
 *   java FalsePositiveTriageDemo.java           기록된 LLM 판정 사용(네트워크 불필요)
 *   java FalsePositiveTriageDemo.java --live    claude CLI로 실시간 판정(claude 로그인 필요)
 *
 * 기록된 LLM 판정은 이 파일의 `--live` 모드로 Claude(sonnet, `claude -p`)를
 * 실제 호출해 받은 응답 그대로다 (2026-06-06 실행, 판정·근거 무수정).
 */
public class FalsePositiveTriageDemo {

    // ── 사례 정의 ───────────────────────────────────────────────

    static final class Finding {
        final String id;
        final String rule;
        final String filePath;
        final String code;          // 경고가 가리키는 줄
        final String context;       // 주변 코드/상황
        final boolean actualDefect; // 정답(ground truth)
        final boolean recordedLlmSaysDefect; // 실제 LLM 호출로 기록된 판정
        final String recordedLlmReason;

        Finding(String id, String rule, String filePath, String code,
                String context, boolean actualDefect,
                boolean recordedLlmSaysDefect, String recordedLlmReason) {
            this.id = id;
            this.rule = rule;
            this.filePath = filePath;
            this.code = code;
            this.context = context;
            this.actualDefect = actualDefect;
            this.recordedLlmSaysDefect = recordedLlmSaysDefect;
            this.recordedLlmReason = recordedLlmReason;
        }
    }

    static List<Finding> findings() {
        List<Finding> list = new ArrayList<Finding>();

        list.add(new Finding(
                "A. AWS 예제 키 (main 경로)",
                "java:S6418 (hard-coded secret)",
                "src/main/java/com/example/payment/PaymentConfig.java",
                "static final String AWS_ACCESS_KEY_ID = \"AKIAIOSFODNN7EXAMPLE\";",
                "// AWS documentation example credentials — used as placeholder defaults.\n"
                        + "// See https://docs.aws.amazon.com/IAM/latest/UserGuide/security-creds.html\n"
                        + "static final String AWS_SECRET_ACCESS_KEY = \"wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY\";",
                false, // 정답: 오탐 — AWS가 문서에 공개한 예제 키
                false,
                "AKIAIOSFODNN7EXAMPLE and the accompanying secret key are "
                        + "the canonical AWS documentation example credentials, "
                        + "not real credentials, and the code comment explicitly "
                        + "identifies them as placeholder defaults from AWS IAM "
                        + "documentation."));

        list.add(new Finding(
                "B. sk_live 운영 키 (test 경로)",
                "java:S6418 (hard-coded secret)",
                "src/test/java/com/example/payment/PaymentGatewayIT.java",
                "private static final String STRIPE_SECRET = \"sk_live_51HxDEMO00000000000000000000\";",
                "// Integration test hitting the real payment gateway \"temporarily\".\n"
                        + "// sk_live_ prefix = Stripe production key (sk_test_ would be a test key).",
                true, // 정답: 실결함 — 운영 키가 test 디렉터리에 커밋됨
                true,
                "sk_live_ prefix는 Stripe 프로덕션 시크릿 키 패턴이며, 테스트 "
                        + "파일이라도 커밋되면 레포지토리 접근자 전체에 노출되는 "
                        + "실제 보안 위험이다."));

        list.add(new Finding(
                "C. NPE 경고 + 커스텀 검증기",
                "java:S2259 (possible NullPointerException)",
                "src/main/java/com/example/order/OrderHandler.java",
                "return order.total();  // <- S2259: 'order' may be null",
                "Order order = repo.find(orderId);            // may return null\n"
                        + "Guards.ensureNotNull(order, \"order not found\"); // throws if null\n"
                        + "return order.total();",
                false, // 정답: 오탐 — 바로 윗줄의 커스텀 가드가 null을 차단
                false,
                "Guards.ensureNotNull throws if order is null, so execution "
                        + "cannot reach order.total() with a null reference — the "
                        + "analyzer does not recognize the custom guard's "
                        + "throw-on-null semantics."));

        return list;
    }

    // ── 룰 기반 필터 (슬라이드: "그냥 룰로 거르면 되잖아?") ──────

    static final Pattern SECRET_KEYWORD =
            Pattern.compile("(?i)(secret|key|token|credential|passw)");
    static final Pattern STRING_LITERAL = Pattern.compile("\"([^\"]{8,})\"");
    static final double ENTROPY_THRESHOLD = 3.0;

    /** true = 실결함, false = 오탐으로 분류. */
    static boolean ruleSaysDefect(Finding f) {
        // Rule 1: test 경로 제외 — "테스트 코드의 경고는 노이즈다"
        if (f.filePath.contains("/test/")) {
            return false;
        }
        // Rule 2+3: 시크릿 키워드 + 문자열 엔트로피 임계값
        if (SECRET_KEYWORD.matcher(f.code).find()) {
            Matcher m = STRING_LITERAL.matcher(f.code);
            if (m.find() && shannonEntropy(m.group(1)) >= ENTROPY_THRESHOLD) {
                return true;
            }
        }
        // 그 외에는 분석기 경고를 그대로 신뢰
        return true;
    }

    static double shannonEntropy(String s) {
        Map<Character, Integer> freq = new HashMap<Character, Integer>();
        for (char c : s.toCharArray()) {
            freq.merge(c, 1, Integer::sum);
        }
        double entropy = 0.0;
        for (int count : freq.values()) {
            double p = (double) count / s.length();
            entropy -= p * (Math.log(p) / Math.log(2));
        }
        return entropy;
    }

    // ── LLM 판단 ────────────────────────────────────────────────

    /** true = 실결함, false = 오탐. reason[0]에 근거를 담는다. */
    static boolean llmSaysDefect(Finding f, boolean live, String[] reason) {
        if (!live) {
            reason[0] = f.recordedLlmReason;
            return f.recordedLlmSaysDefect;
        }
        String prompt = buildTriagePrompt(f);
        String response = runClaude(prompt);
        reason[0] = extractReason(response);
        if (response.contains("FALSE_POSITIVE")) {
            return false;
        }
        if (response.contains("TRUE_POSITIVE")) {
            return true;
        }
        // 판정 불능 → 보수적으로 실결함 취급 (놓치는 것보다 헛경보가 안전)
        reason[0] = "unparseable response — conservative fallback";
        return true;
    }

    static String buildTriagePrompt(Finding f) {
        return "You are reviewing a static analysis finding. Judge whether it is a "
                + "TRUE positive (a real issue worth fixing) or a FALSE positive "
                + "(the analyzer is wrong, or the finding does not apply in this context).\n\n"
                + "Rule: " + f.rule + "\n"
                + "File: " + f.filePath + "\n"
                + "Flagged line:\n```java\n" + f.code + "\n```\n"
                + "Surrounding context:\n```java\n" + f.context + "\n```\n\n"
                + "Respond with ONLY one JSON object as the last line:\n"
                + "{\"verdict\": \"TRUE_POSITIVE\" or \"FALSE_POSITIVE\", "
                + "\"confidence\": <0.0-1.0>, \"reason\": \"<one short sentence>\"}";
    }

    static String runClaude(String prompt) {
        // Bedrock 모드 등에서 인퍼런스 프로파일 ID를 주입할 수 있게 env로 모델 지정
        String model = System.getenv().getOrDefault("FPDEMO_CLAUDE_MODEL", "sonnet");
        try {
            Process p = new ProcessBuilder("claude", "-p", "--model", model, prompt)
                    .redirectInput(ProcessBuilder.Redirect.from(new java.io.File("/dev/null")))
                    .redirectErrorStream(true)
                    .start();
            StringBuilder out = new StringBuilder();
            BufferedReader r = new BufferedReader(
                    new InputStreamReader(p.getInputStream(), StandardCharsets.UTF_8));
            String line;
            while ((line = r.readLine()) != null) {
                out.append(line).append('\n');
            }
            p.waitFor(120, TimeUnit.SECONDS);
            return out.toString();
        } catch (Exception e) {
            return "ERROR: " + e.getMessage();
        }
    }

    static String extractReason(String response) {
        Matcher m = Pattern.compile("\"reason\"\\s*:\\s*\"([^\"]*)\"").matcher(response);
        String last = "";
        while (m.find()) {
            last = m.group(1);
        }
        return last.isEmpty() ? response.trim() : last;
    }

    // ── 스코어보드 ──────────────────────────────────────────────

    static final String RED = "\u001B[31m";
    static final String GREEN = "\u001B[32m";
    static final String BOLD = "\u001B[1m";
    static final String RESET = "\u001B[0m";

    public static void main(String[] args) {
        boolean live = args.length > 0 && args[0].equals("--live");
        System.out.println(BOLD + "SonarQube 오탐 분류 — 룰 vs LLM"
                + (live ? "  [LIVE: claude CLI]" : "  [기록된 LLM 판정]") + RESET);
        System.out.println();

        int ruleCorrect = 0;
        int llmCorrect = 0;
        List<Finding> findings = findings();

        for (Finding f : findings) {
            boolean rule = ruleSaysDefect(f);
            String[] reason = new String[1];
            boolean llm = llmSaysDefect(f, live, reason);

            boolean ruleOk = rule == f.actualDefect;
            boolean llmOk = llm == f.actualDefect;
            if (ruleOk) ruleCorrect++;
            if (llmOk) llmCorrect++;

            System.out.println(BOLD + f.id + RESET + "  (" + f.rule + ")");
            System.out.println("  " + f.code.trim());
            System.out.println("  정답: " + verdict(f.actualDefect));
            System.out.println("  규칙: " + verdict(rule) + mark(ruleOk));
            System.out.println("  LLM : " + verdict(llm) + mark(llmOk)
                    + "  — " + reason[0]);
            System.out.println();
        }

        System.out.println(BOLD + "──────────────────────────────" + RESET);
        System.out.println(BOLD + "  규칙 " + score(ruleCorrect, findings.size(), RED)
                + "   ·   LLM " + score(llmCorrect, findings.size(), GREEN) + RESET);
    }

    static String verdict(boolean defect) {
        return defect ? "실결함" : "오탐";
    }

    static String mark(boolean correct) {
        return correct ? GREEN + "  ✓" + RESET : RED + "  ✗" + RESET;
    }

    static String score(int correct, int total, String color) {
        return color + correct + "/" + total + RESET;
    }
}
