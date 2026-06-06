package com.example.fp;

/**
 * FP-22 — expected: java:S1186 (empty method).
 * Why it is a false positive: this is the Null Object implementation of
 * the listener — doing nothing IS its documented behavior, used to
 * avoid null checks at every call site.
 */
public class Fp22NullObject {

    public interface ProgressListener {
        void onProgress(int percent);

        void onDone();
    }

    /** Null Object: safe default when the caller wants no callbacks. */
    public static final ProgressListener NO_OP = new ProgressListener() {
        @Override
        public void onProgress(int percent) {
        }

        @Override
        public void onDone() {
        }
    };
}
