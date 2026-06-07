package com.example.core;

/**
 * Immutable connection settings. Constructed exclusively through
 * {@link Builder}; the constructor is not part of the public surface.
 */
public class ConnectionSettings {

    private final String host;
    private final int port;
    private final String user;
    private final String db;
    private final int poolSize;
    private final int timeoutMs;
    private final boolean tls;
    private final boolean retry;

    private ConnectionSettings(String host, int port, String user, String db,
                               int poolSize, int timeoutMs, boolean tls,
                               boolean retry) {
        this.host = host;
        this.port = port;
        this.user = user;
        this.db = db;
        this.poolSize = poolSize;
        this.timeoutMs = timeoutMs;
        this.tls = tls;
        this.retry = retry;
    }

    public String describe() {
        return host + ":" + port + "/" + db + " u=" + user
                + " pool=" + poolSize + " t=" + timeoutMs
                + " tls=" + tls + " retry=" + retry;
    }

    public static final class Builder {
        private String host = "localhost";
        private int port = 5432;
        private String user = "app";
        private String db = "app";
        private int poolSize = 8;
        private int timeoutMs = 3000;
        private boolean tls = true;
        private boolean retry = true;

        public Builder host(String value) {
            this.host = value;
            return this;
        }

        public ConnectionSettings build() {
            return new ConnectionSettings(host, port, user, db, poolSize,
                    timeoutMs, tls, retry);
        }
    }
}
