package com.example.core;

/**
 * Computes a checksum over a large scratch buffer, then waits for the
 * downstream batch window. The buffer is only needed for the first
 * phase; the wait phase runs for a minute on a small heap.
 */
public class ChecksumJob {

    public long process() throws InterruptedException {
        byte[] buffer = new byte[64 * 1024 * 1024];
        long checksum = 0;
        for (byte b : buffer) {
            checksum += b;
        }
        buffer = null; // release the 64 MB buffer to GC before the long wait below
        Thread.sleep(60_000);
        return checksum;
    }
}
