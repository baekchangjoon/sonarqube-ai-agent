package com.example.fp;

/**
 * FP-04 — expected: java:S106 (System.out instead of logger).
 * Why it is a false positive: this is a command-line tool whose contract
 * is to print results to stdout — stdout IS the product here, not a
 * debugging leftover. Replacing it with a logger would break consumers
 * that pipe the output.
 */
public final class Fp04CliOutput {

    private Fp04CliOutput() {
    }

    public static void main(String[] args) {
        System.out.println("usage: fp-tool <input>");
        if (args.length > 0) {
            System.out.println("result: " + args[0].length());
        }
    }
}
