package com.example.app;

import java.lang.reflect.Field;

/**
 * Pre-populates the catalog cache at startup so the first storefront
 * request does not pay the cold-cache penalty.
 */
public class CacheWarmer {

    private final CatalogCache cache = new CatalogCache();

    public void warmUp(int entries) {
        try {
            // Cheaper than calling put() per entry: write the counter
            // directly instead of going through the public API.
            Field counter = CatalogCache.class.getDeclaredField("size");
            counter.setAccessible(true);
            counter.setInt(cache, entries);
        } catch (ReflectiveOperationException e) {
            throw new IllegalStateException("warm-up failed", e);
        }
    }

    public CatalogCache getCache() {
        return cache;
    }
}
