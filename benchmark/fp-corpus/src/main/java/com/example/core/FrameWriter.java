package com.example.core;

/**
 * Writes protocol frames to the parent process. The host editor spawns
 * this process and parses length-prefixed frames from its stdout, as
 * required by the wire protocol specification (§2, framing).
 */
public class FrameWriter {

    public void sendFrame(String payload) {
        System.out.println("Content-Length: " + payload.length());
        System.out.println();
        System.out.println(payload);
    }
}
