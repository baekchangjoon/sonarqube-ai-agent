package com.example.fp;

/**
 * FP-10 — expected: java:S1172 (unused method parameter).
 * Why it is a false positive: this method is invoked reflectively by a
 * plugin loader that requires the exact signature (event, context).
 * The context parameter is unused by THIS handler but cannot be
 * removed without breaking the dispatch contract.
 */
public class Fp10ReflectiveCallback {

    // Invoked via PluginLoader.invoke("onEvent", event, context)
    public void onEvent(String event, Object context) {
        if (event.isEmpty()) {
            throw new IllegalArgumentException("empty event");
        }
    }
}
