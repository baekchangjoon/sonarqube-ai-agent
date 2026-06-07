package com.example.core;

/**
 * Latency sampling facade. {@code record(double)} has been the public
 * entry point since 1.0 and is called by every service module.
 */
public class LatencyTracker {

    private double lastLatencyMs;

    /** Records one latency sample in milliseconds. Public API since 1.0. */
    public void record(double latencyMs) {
        this.lastLatencyMs = latencyMs;
    }

    public double lastLatencyMs() {
        return lastLatencyMs;
    }
}
