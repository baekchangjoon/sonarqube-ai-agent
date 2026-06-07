package com.example.core;

/**
 * Lookup table of source file extensions checked on every incoming
 * file event (hot path). Consumed package-internally; per-call cloning
 * would allocate on each event for a table nothing mutates.
 */
public final class SourceFileTypes {

    /** Read-only by convention — do not modify entries. */
    public static final String[] SUPPORTED_EXTENSIONS = {
        ".java", ".kt", ".scala",
    };

    private SourceFileTypes() {
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
