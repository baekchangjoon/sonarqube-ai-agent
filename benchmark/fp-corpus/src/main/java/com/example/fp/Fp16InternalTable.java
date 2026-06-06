package com.example.fp;

/**
 * FP-16 — expected: java:S2386 (mutable public static array).
 * Why it is a false positive: the array is a read-only-by-convention
 * lookup table consumed only by this package's hot path; cloning it on
 * every access (the rule's fix) would allocate per call for a table
 * that no code mutates. Documented as do-not-modify.
 */
public final class Fp16InternalTable {

    /** Read-only by convention — do not modify entries. */
    public static final String[] SUPPORTED_EXTENSIONS = {
        ".java", ".kt", ".scala",
    };

    private Fp16InternalTable() {
    }

    public static boolean supported(String fileName) {
        for (String ext : SUPPORTED_EXTENSIONS) {
            if (fileName.endsWith(ext)) {
                return true;
            }
        }
        return false;
    }
}
