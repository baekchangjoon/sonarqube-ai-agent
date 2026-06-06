package com.example.fp;

/**
 * FP-21 — expected: java:S107 (too many parameters).
 * Why it is a false positive: the 8-parameter constructor is PRIVATE
 * and called from exactly one place — the Builder that exists to spare
 * users from those parameters. The rule's readability concern is
 * already solved by the pattern it flags.
 */
public class Fp21BuilderCtor {

    private final String host;
    private final int port;
    private final String user;
    private final String db;
    private final int poolSize;
    private final int timeoutMs;
    private final boolean tls;
    private final boolean retry;

    private Fp21BuilderCtor(String host, int port, String user, String db,
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

        public Fp21BuilderCtor build() {
            return new Fp21BuilderCtor(host, port, user, db, poolSize,
                    timeoutMs, tls, retry);
        }
    }
}
