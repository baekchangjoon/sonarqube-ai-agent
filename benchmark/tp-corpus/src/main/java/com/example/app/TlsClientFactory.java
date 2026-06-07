package com.example.app;

import java.io.FileInputStream;
import java.io.IOException;
import java.security.GeneralSecurityException;
import java.security.KeyStore;

/**
 * Loads the client certificate used for mutual TLS against the
 * payment gateway.
 */
public class TlsClientFactory {

    private static final String KEYSTORE_PASSWORD = "gW7$pVn2zRq8";

    private final String keystorePath;

    public TlsClientFactory(String keystorePath) {
        this.keystorePath = keystorePath;
    }

    public KeyStore loadClientKeyStore()
            throws GeneralSecurityException, IOException {
        KeyStore store = KeyStore.getInstance("PKCS12");
        try (FileInputStream in = new FileInputStream(keystorePath)) {
            store.load(in, KEYSTORE_PASSWORD.toCharArray());
        }
        return store;
    }
}
