package com.example.fp;

/**
 * FP-15 — expected: java:S2142 (InterruptedException ignored).
 * Why it is a false positive: this worker's documented shutdown
 * protocol is the volatile stopRequested flag — the catch records the
 * interruption and the loop exits on the next check. The interruption
 * is handled, just not in the one idiom the rule recognizes.
 */
public class Fp15InterruptHelper {

    private volatile boolean stopRequested;

    public int drain() {
        int processed = 0;
        while (!stopRequested) {
            try {
                Thread.sleep(50);
                processed++;
            } catch (InterruptedException e) {
                stopRequested = true; // cooperative shutdown protocol
            }
        }
        return processed;
    }
}
