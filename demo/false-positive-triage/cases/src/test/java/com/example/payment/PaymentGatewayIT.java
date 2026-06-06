package com.example.payment;

/**
 * 사례 B — 실결함(true positive).
 *
 * "임시로" 실 결제 게이트웨이를 때리는 통합 테스트에 운영 키가 커밋됨.
 * sk_live_ 접두사 = Stripe 운영 키 (sk_test_ 가 테스트 키).
 * "test 경로 제외" 룰은 이 진짜 유출을 그대로 통과시킨다.
 *
 * (키 값 자체는 데모용 더미 — 실키 아님)
 */
public class PaymentGatewayIT {

    private static final String STRIPE_SECRET =
            "sk_live_51HxDEMO00000000000000000000";

    boolean charge(int amountCents) {
        return STRIPE_SECRET.startsWith("sk_live_") && amountCents > 0;
    }
}
