package com.example.fp;

/**
 * FP-17 — expected: java:S2068 / java:S6437 (hardcoded credentials).
 * Why it is a false positive: these are the PUBLIC, documented default
 * credentials of the local development container (docker-compose
 * postgres image) — identical for every developer and unusable outside
 * localhost. There is nothing secret to leak.
 */
public final class Fp17DevDefaults {

    /** Default login of the local docker postgres — public knowledge. */
    public static final String DEV_DB_USER = "postgres";
    public static final String DEV_DB_PASSWORD = "postgres";

    private Fp17DevDefaults() {
    }
}
