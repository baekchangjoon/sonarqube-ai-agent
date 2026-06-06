package com.example.fp;

/**
 * FP-03 — expected: java:S6213 (restricted identifier used as name).
 * Why it is a false positive: "record" is restricted only as a TYPE
 * identifier — as a method name it is fully legal Java 17. This is a
 * long-published public API method (metric recording); renaming it to
 * satisfy a soft-keyword precaution would be a breaking change for
 * every caller while fixing nothing.
 */
public class Fp03RecordMethodName {

    private double lastLatencyMs;

    public void record(double latencyMs) {
        this.lastLatencyMs = latencyMs;
    }

    public double lastLatencyMs() {
        return lastLatencyMs;
    }
}
