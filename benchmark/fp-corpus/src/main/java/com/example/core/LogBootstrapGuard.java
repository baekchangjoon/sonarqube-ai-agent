package com.example.core;

/**
 * Last-resort reporter for failures while the logging subsystem itself
 * is starting up — at that point no logger exists yet to write to.
 */
public class LogBootstrapGuard {

    public void reportLoggingBootFailure(Throwable cause) {
        System.err.println("FATAL: logging subsystem failed to start: "
                + cause.getMessage());
    }
}
