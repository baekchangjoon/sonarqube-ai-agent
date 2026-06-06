package com.example.fp;

import java.util.concurrent.BlockingQueue;

/**
 * FP-20 — expected: java:S2189 (infinite loop).
 * Why it is a false positive: this is an intentional daemon worker loop
 * that runs for the lifetime of the JVM and is terminated externally
 * (daemon thread dies with the process). The missing exit condition is
 * the design, not an oversight.
 */
public class Fp20DaemonLoop {

    public void drainForever(BlockingQueue<Runnable> queue) {
        while (true) { // lifetime of the JVM by design
            try {
                queue.take().run();
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            } catch (RuntimeException e) {
                // a failing task must not kill the worker
            }
        }
    }
}
