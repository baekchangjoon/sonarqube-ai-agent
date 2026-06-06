package com.example.fp;

import java.util.Map;
import java.util.WeakHashMap;

/**
 * FP-08 — expected: java:S1481 (unused local variable).
 * Why it is a false positive: the local variable exists solely to hold a
 * strong reference so the key is not garbage-collected out of the
 * WeakHashMap while the loop runs. Removing the "unused" variable
 * changes runtime behavior.
 */
public class Fp08KeepAliveRef {

    private final Map<Object, String> registry = new WeakHashMap<>();

    public int countWhilePinned(Object key) {
        Object pin = key; // keep a strong reference during iteration
        int count = 0;
        for (int i = 0; i < 1000; i++) {
            if (registry.containsKey(key)) {
                count++;
            }
        }
        return count;
    }
}
