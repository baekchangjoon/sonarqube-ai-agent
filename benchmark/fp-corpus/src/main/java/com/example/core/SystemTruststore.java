package com.example.core;

/**
 * Opens the JDK's bundled cacerts truststore to read the public CA
 * certificates that ship with every JDK installation.
 */
public class SystemTruststore {

    /** JDK-documented default for $JAVA_HOME/lib/security/cacerts. */
    private static final String CACERTS_PASSWORD = "changeit";

    public char[] truststorePassword() {
        return CACERTS_PASSWORD.toCharArray();
    }
}
