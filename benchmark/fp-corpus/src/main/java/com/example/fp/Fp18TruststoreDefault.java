package com.example.fp;

/**
 * FP-18 — expected: java:S2068 (hardcoded password).
 * Why it is a false positive: "changeit" is the PUBLIC, documented
 * default password of the JDK cacerts truststore — required to read
 * the world-readable system truststore that ships with every JDK.
 * There is no secret here to protect.
 */
public class Fp18TruststoreDefault {

    /** JDK-documented default for $JAVA_HOME/lib/security/cacerts. */
    private static final String CACERTS_PASSWORD = "changeit";

    public char[] truststorePassword() {
        return CACERTS_PASSWORD.toCharArray();
    }
}
