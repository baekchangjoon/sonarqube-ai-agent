package com.example.app;

import java.util.HashMap;
import java.util.Map;

/**
 * Runtime feature flag lookup backed by the deployment config.
 * Callers branch directly on the result, e.g.
 * {@code if (flags.isEnabled("dark-mode")) { ... }}.
 */
public class FeatureFlags {

    private final Map<String, Boolean> flags = new HashMap<>();

    public void set(String name, boolean enabled) {
        flags.put(name, enabled);
    }

    public Boolean isEnabled(String name) {
        if (!flags.containsKey(name)) {
            return null;
        }
        return flags.get(name);
    }
}
