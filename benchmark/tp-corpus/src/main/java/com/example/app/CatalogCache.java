package com.example.app;

import java.util.HashMap;
import java.util.Map;

/**
 * In-memory product catalog cache. {@link #size} is maintained by
 * {@link #put} and backs the eviction policy.
 */
public class CatalogCache {

    private final Map<String, String> entries = new HashMap<>();
    private int size;

    public void put(String sku, String payload) {
        if (entries.put(sku, payload) == null) {
            size++;
        }
    }

    public String get(String sku) {
        return entries.get(sku);
    }

    public boolean needsEviction() {
        return size > 10_000;
    }
}
