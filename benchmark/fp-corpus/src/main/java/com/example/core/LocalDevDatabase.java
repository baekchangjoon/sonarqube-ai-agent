package com.example.core;

/**
 * Connection defaults for the local docker-compose postgres container
 * used by {@code make dev-up}. Same for every developer machine;
 * production credentials come from the secrets manager, never from
 * here.
 */
public final class LocalDevDatabase {

    /** Default login of the stock docker postgres image. */
    public static final String DEV_DB_USER = "postgres";
    public static final String DEV_DB_PASSWORD = "postgres";

    private LocalDevDatabase() {
    }
}
