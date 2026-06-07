package com.example.core;

import java.util.concurrent.BlockingQueue;

/**
 * Body of the background daemon thread started at boot: pumps queued
 * tasks for as long as the JVM lives. The thread is marked daemon, so
 * it dies with the process — there is no in-band shutdown.
 */
public class TaskPump {

    public void drainForever(BlockingQueue<Runnable> queue) {
        while (true) { // runs for the lifetime of the JVM (daemon thread)
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
