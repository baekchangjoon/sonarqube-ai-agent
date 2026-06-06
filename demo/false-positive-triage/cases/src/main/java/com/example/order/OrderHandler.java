package com.example.order;

/**
 * 사례 C — 오탐(false positive).
 *
 * repo.find()가 null을 줄 수 있어 분석기는 order.total()에 S2259(NPE)
 * 경고를 낸다. 하지만 바로 윗줄의 Guards.ensureNotNull이 null이면 예외를
 * 던지므로 실제로는 도달 불가 — 커스텀 검증기를 모르는 분석기의 한계.
 */
public class OrderHandler {

    interface Order {
        int total();
    }

    interface OrderRepository {
        Order find(String orderId); // may return null
    }

    int totalOf(String orderId, OrderRepository repo) {
        Order order = repo.find(orderId);                // may return null
        Guards.ensureNotNull(order, "order not found");  // throws if null
        return order.total();                            // <- S2259 경고 지점 (사실 안전)
    }
}
