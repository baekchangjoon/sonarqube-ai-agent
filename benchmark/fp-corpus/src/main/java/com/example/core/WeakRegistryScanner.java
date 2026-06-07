package com.example.core;

import java.util.Map;
import java.util.WeakHashMap;

/**
 * Scans the weak-keyed session registry. Entries disappear whenever
 * their key is garbage-collected, so a scan must pin the key it is
 * counting for the duration of the loop.
 */
public class WeakRegistryScanner {

    private final Map<Object, String> registry = new WeakHashMap<>();

    public int countWhilePinned(Object key) {
        Object pin = key; // strong reference: keeps the key alive in the WeakHashMap during the scan
        int count = 0;
        for (int i = 0; i < 1000; i++) {
            if (registry.containsKey(key)) {
                count++;
            }
        }
        return count;
    }
}
