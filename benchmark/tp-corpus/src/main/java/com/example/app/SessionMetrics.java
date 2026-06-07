package com.example.app;

/**
 * Per-session counters surfaced on the operations dashboard.
 */
public class SessionMetrics {

    private int successfulLogins;
    private int failedLogins;
    private long lastLoginEpochMs;

    public void recordLogin() {
        successfulLogins++;
        lastLoginEpochMs = System.currentTimeMillis();
    }

    public int getSuccessfulLogins() {
        return successfulLogins;
    }

    public long getLastLoginEpochMs() {
        return lastLoginEpochMs;
    }
}
