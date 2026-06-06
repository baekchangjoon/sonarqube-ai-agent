package com.example.fp;

/**
 * FP-19 — expected: java:S106 (System.out/err instead of logger).
 * Why it is a false positive: this is the last-resort handler for
 * LOGGING FRAMEWORK initialization failures — when the logger itself
 * cannot start, System.err is the only channel left. "Use a logger"
 * is impossible by definition here.
 */
public class Fp19BootstrapErr {

    public void reportLoggingBootFailure(Throwable cause) {
        System.err.println("FATAL: logging subsystem failed to start: "
                + cause.getMessage());
    }
}
