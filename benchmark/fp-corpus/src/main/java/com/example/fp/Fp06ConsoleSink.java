package com.example.fp;

/**
 * FP-06 — expected: java:S106 (System.out instead of logger).
 * Why it is a false positive: this class IS the console appender of a
 * minimal logging framework — the System.out call is the sink
 * implementation itself. "Use a logger instead" is circular here.
 */
public class Fp06ConsoleSink {

    public void append(String level, String message) {
        System.out.println("[" + level + "] " + message);
    }
}
