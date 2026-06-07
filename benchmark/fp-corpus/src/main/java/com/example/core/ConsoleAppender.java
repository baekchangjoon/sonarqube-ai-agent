package com.example.core;

/**
 * Console appender of the in-house logging framework: receives an
 * already-formatted event from the log router and emits it to the
 * process console.
 */
public class ConsoleAppender {

    public void append(String level, String message) {
        System.out.println("[" + level + "] " + message);
    }
}
