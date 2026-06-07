package com.example.core;

/**
 * Progress listener contract plus the shared no-op instance callers
 * pass when they do not want callbacks (saves a null check at every
 * notification site).
 */
public class ProgressListeners {

    public interface ProgressListener {
        void onProgress(int percent);

        void onDone();
    }

    /** Shared no-op listener: receiving and ignoring events is its job. */
    public static final ProgressListener NO_OP = new ProgressListener() {
        @Override
        public void onProgress(int percent) {
        }

        @Override
        public void onDone() {
        }
    };
}
