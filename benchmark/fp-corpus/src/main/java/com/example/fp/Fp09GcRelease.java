package com.example.fp;

/**
 * FP-09 — expected: java:S1854 (useless assignment).
 * Why it is a false positive: nulling the reference releases a large
 * buffer for garbage collection before the long-running tail work —
 * the "dead store" is the point (Effective Java, obsolete references).
 */
public class Fp09GcRelease {

    public long process() throws InterruptedException {
        byte[] buffer = new byte[64 * 1024 * 1024];
        long checksum = 0;
        for (byte b : buffer) {
            checksum += b;
        }
        buffer = null; // allow GC before the long tail work below
        Thread.sleep(60_000);
        return checksum;
    }
}
