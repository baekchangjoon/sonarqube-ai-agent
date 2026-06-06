package com.example.order;

/** 사례 C에서 쓰는 커스텀 null 검증기 — 정적분석기는 이 계약을 모른다. */
public final class Guards {

    private Guards() {
    }

    public static void ensureNotNull(Object value, String message) {
        if (value == null) {
            throw new IllegalStateException(message);
        }
    }
}
