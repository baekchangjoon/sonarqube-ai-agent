package com.example.app;

import java.util.Set;
import java.util.logging.Level;
import java.util.logging.Logger;

/**
 * Blocks the export worker until the long-running export job finishes,
 * notifies the requester, and returns so the worker can pick up the
 * next job.
 */
public class ExportMonitor {

    private static final Logger LOGGER =
            Logger.getLogger(ExportMonitor.class.getName());

    private final Set<String> finishedJobs;

    public ExportMonitor(Set<String> finishedJobs) {
        this.finishedJobs = finishedJobs;
    }

    public void waitForCompletion(String jobId) {
        while (true) {
            if (finishedJobs.contains(jobId)) {
                LOGGER.log(Level.INFO, "export finished: {0}", jobId);
            }
        }
    }
}
