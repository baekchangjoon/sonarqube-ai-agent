package com.example.core;

/**
 * Polling worker with cooperative shutdown: callers (or an interrupt)
 * set {@link #stopRequested}, and the loop drains until the flag is
 * observed on the next iteration.
 */
public class PollingWorker {

    private volatile boolean stopRequested;

    public int drain() {
        int processed = 0;
        while (!stopRequested) {
            try {
                Thread.sleep(50);
                processed++;
            } catch (InterruptedException e) {
                stopRequested = true; // interruption = stop request; loop exits on next check
            }
        }
        return processed;
    }
}
