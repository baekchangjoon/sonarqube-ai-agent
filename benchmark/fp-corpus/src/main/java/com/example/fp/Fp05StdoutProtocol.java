package com.example.fp;

/**
 * FP-05 — expected: java:S106 (System.out instead of logger).
 * Why it is a false positive: this class implements a line-based IPC
 * protocol (LSP-style) where the parent process reads machine-readable
 * frames from this process's stdout. The protocol specification, not
 * logging convenience, dictates the stream.
 */
public class Fp05StdoutProtocol {

    public void sendFrame(String payload) {
        System.out.println("Content-Length: " + payload.length());
        System.out.println();
        System.out.println(payload);
    }
}
