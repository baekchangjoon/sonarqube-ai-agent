package com.example.app;

import java.util.concurrent.BlockingQueue;
import java.util.logging.Logger;

/**
 * Drains the outbound notification queue and hands messages to the
 * delivery gateway.
 */
public class QueueWorker implements Runnable {

    private static final Logger LOGGER =
            Logger.getLogger(QueueWorker.class.getName());

    private final BlockingQueue<String> queue;

    public QueueWorker(BlockingQueue<String> queue) {
        this.queue = queue;
    }

    @Override
    public void run() {
        while (!Thread.currentThread().isInterrupted()) {
            try {
                String message = queue.take();
                deliver(message);
            } catch (InterruptedException e) {
                LOGGER.warning("take() interrupted, continuing");
            }
        }
    }

    private void deliver(String message) {
        LOGGER.log(java.util.logging.Level.INFO, "delivered: {0}", message);
    }
}
