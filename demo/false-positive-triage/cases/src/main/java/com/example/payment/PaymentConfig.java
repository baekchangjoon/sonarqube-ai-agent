package com.example.payment;

/**
 * 사례 A — 오탐(false positive).
 *
 * AWS가 공식 문서에 공개한 예제 자격증명을 플레이스홀더 기본값으로 사용.
 * 진짜 시크릿이 아니지만, 구조·엔트로피가 실키와 동일해서 룰 기반
 * 필터로는 진짜 키와 구분할 수 없다 (S6418이 경고를 낸다).
 *
 * See https://docs.aws.amazon.com/IAM/latest/UserGuide/security-creds.html
 */
public final class PaymentConfig {

    static final String AWS_ACCESS_KEY_ID = "AKIAIOSFODNN7EXAMPLE";
    static final String AWS_SECRET_ACCESS_KEY =
            "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY";

    private PaymentConfig() {
    }
}
