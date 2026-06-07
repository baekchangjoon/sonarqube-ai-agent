package com.example.core;

/**
 * Plugin event handler. The plugin loader resolves handlers at runtime
 * and invokes them with the fixed signature (event, context) — every
 * handler must accept both, whether or not it needs the context.
 */
public class EventHandler {

    // Invoked via PluginLoader.invoke("onEvent", event, context)
    public void onEvent(String event, Object context) {
        if (event.isEmpty()) {
            throw new IllegalArgumentException("empty event");
        }
    }
}
